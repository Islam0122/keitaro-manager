"""Campaign Creator: payloads sent to Keitaro, validation and compensation (rollback)."""
import pytest

from app.repositories.campaign_repository import CampaignRepository

CREATE = {"name": "Test US", "country": "us", "offer_id": 10, "domain_id": 3, "group_id": 1, "traffic_source_id": 2}


def live_objects(fake):
    campaigns = [c for c in fake.campaigns.values() if c["state"] != "deleted"]
    streams = [s for s in fake.streams.values() if s.get("state") != "deleted"]
    return campaigns, streams


async def test_success_payloads(configured, fake):
    response = await configured.post("/api/campaigns", json=CREATE)
    assert response.status_code == 201, response.text
    data = response.json()
    cid = data["campaign"]["id"]

    campaign = fake.calls("POST", "/campaigns")[0]
    assert campaign == {
        "name": "Test US",
        "alias": campaign["alias"],
        "type": "position",
        "state": "active",
        "group_id": 1,
        "traffic_source_id": 2,
        "domain_id": 3,
    }
    assert len(campaign["alias"]) == 8

    geo, offers = fake.calls("POST", "/streams")
    assert geo["campaign_id"] == cid and offers["campaign_id"] == cid
    assert (geo["name"], geo["type"], geo["state"], geo["schema"]) == ("GEO Redirect", "regular", "active", "redirect")
    assert geo["action_type"] == "http" and geo["action_payload"] == "https://www.google.com"
    assert geo["filters"] == [{"name": "country", "mode": "accept", "payload": ["US"]}]
    assert geo["collect_clicks"] is True
    assert (offers["name"], offers["type"], offers["state"], offers["schema"]) == ("Offers", "regular", "active", "landings")
    assert offers["filters"] == []
    assert offers["offers"] == [{"offer_id": 10, "share": 100, "state": "active"}]
    # GEO stream must be evaluated first, the offer stream catches everybody else
    assert geo["position"] < offers["position"]

    assert data["local"]["country"] == "US"
    assert data["local"]["geo_stream_id"] == data["streams"][0]["id"]
    assert data["local"]["offer_stream_id"] == data["streams"][1]["id"]
    assert [s["name"] for s in data["streams"]] == ["GEO Redirect", "Offers"]


async def test_groups_type_fallback(configured, fake):
    fake.groups_type = "campaigns"
    response = await configured.post("/api/campaigns", json=CREATE)
    assert response.status_code == 201, response.text
    types = [p for m, p, _ in fake.requests if p == "/groups"]
    assert len(types) >= 2


@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"country": "USA"}, "country"),
        ({"country": "1A"}, "country"),
        ({"country": ""}, "country"),
        ({"name": "   "}, "name"),
        ({"name": "x" * 256}, "name"),
        ({"offer_id": 0}, "offer_id"),
        ({"domain_id": -1}, "domain_id"),
    ],
)
async def test_input_validation(configured, fake, patch, field):
    response = await configured.post("/api/campaigns", json={**CREATE, **patch})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert any(e["field"] == field for e in body["errors"])
    assert fake.calls("POST", "/campaigns") == []


@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"offer_id": 999}, "offer_id"),
        ({"domain_id": 999}, "domain_id"),
        ({"group_id": 999}, "group_id"),
        ({"traffic_source_id": 999}, "traffic_source_id"),
    ],
)
async def test_unknown_references_rejected_before_writing(configured, fake, patch, field):
    response = await configured.post("/api/campaigns", json={**CREATE, **patch})
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == [field]
    assert fake.calls("POST", "/campaigns") == []  # nothing was written to Keitaro


async def test_several_unknown_references_reported_together(configured):
    response = await configured.post("/api/campaigns", json={**CREATE, "group_id": 9, "traffic_source_id": 9})
    assert {e["field"] for e in response.json()["errors"]} == {"group_id", "traffic_source_id"}


async def test_failure_creating_campaign(configured, fake):
    fake.fail("POST", "/campaigns", 500)
    response = await configured.post("/api/campaigns", json=CREATE)
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "keitaro_server_error"
    assert body["rollback"]["performed"] is False
    assert fake.calls("POST", "/streams") == []
    assert live_objects(fake) == ([], [])


async def test_failure_on_first_stream(configured, fake):
    fake.fail("POST", "/streams", 422, body={"error": "Invalid filter"})
    response = await configured.post("/api/campaigns", json=CREATE)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "keitaro_rejected"
    assert "Invalid filter" in body["detail"] and "откат выполнен" in body["detail"]
    assert [s["object"] for s in body["rollback"]["steps"]] == ["campaign"]
    assert live_objects(fake) == ([], [])


async def test_failure_on_second_stream_deletes_first_stream_and_campaign(configured, fake):
    fake.fail("POST", "/streams", 400, skip=1)
    response = await configured.post("/api/campaigns", json=CREATE)
    assert response.status_code == 422
    rollback = response.json()["rollback"]
    assert rollback["ok"] is True
    assert [s["object"] for s in rollback["steps"]] == ["stream", "campaign"]
    assert len(fake.calls("DELETE", r"/streams/\d+")) == 1
    assert live_objects(fake) == ([], [])
    logs = (await configured.get("/api/logs")).json()
    assert logs[0]["action"] == "campaign.create" and logs[0]["status"] == "error"
    assert logs[0]["details"]["rollback"]["ok"] is True
    assert logs[0]["username"] == "admin"


async def test_stream_created_in_wrong_campaign_is_rolled_back(configured, fake, monkeypatch):
    original = fake.handle

    def handle(request):
        response = original(request)
        if request.method == "POST" and request.url.path.endswith("/streams"):
            sid = response.json()["id"]
            fake.streams[sid]["campaign_id"] = 424242
            import httpx

            return httpx.Response(200, json=fake.streams[sid])
        return response

    monkeypatch.setattr(fake, "handle", handle)
    response = await configured.post("/api/campaigns", json=CREATE)
    assert response.status_code == 502
    assert "вместо" in response.json()["detail"]
    steps = response.json()["rollback"]["steps"]
    assert [s["object"] for s in steps] == ["stream", "campaign"]


async def test_database_failure_compensates_keitaro(configured, fake, monkeypatch):
    async def broken(self, **fields):
        raise RuntimeError("database is down")

    monkeypatch.setattr(CampaignRepository, "create", broken)
    response = await configured.post("/api/campaigns", json=CREATE)
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "persistence_failed"
    assert "database is down" not in body["detail"]  # internal details are not exposed
    assert [s["object"] for s in body["rollback"]["steps"]] == ["stream", "stream", "campaign"]
    assert live_objects(fake) == ([], [])


async def test_incomplete_rollback_is_reported(configured, fake):
    fake.fail("POST", "/streams", 400, skip=1)
    fake.fail("DELETE", r"/campaigns/\d+", 500)
    response = await configured.post("/api/campaigns", json=CREATE)
    body = response.json()
    assert body["rollback"]["ok"] is False
    assert "удалите вручную" in body["detail"] and "campaign #" in body["detail"]


async def test_custom_safe_url_is_used(configured, fake):
    await configured.put(
        "/api/settings",
        json={"api_url": "https://tracker.example.com", "default_safe_url": "https://example.org/safe"},
    )
    await configured.post("/api/campaigns", json=CREATE)
    assert fake.calls("POST", "/streams")[0]["action_payload"] == "https://example.org/safe"
