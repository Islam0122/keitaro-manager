from app.integrations.keitaro.client import build_base_url

CREATE = {"name": "Test US", "country": "us", "offer_id": 10, "domain_id": 3, "group_id": 1, "traffic_source_id": 2}


def test_base_url_normalisation():
    assert build_base_url("https://t.com/") == "https://t.com/admin_api/v1"
    assert build_base_url("https://t.com/admin_api/v1/") == "https://t.com/admin_api/v1"


async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.json()["keitaro_configured"] is False


async def test_not_configured(client):
    response = await client.get("/api/campaigns")
    assert response.status_code == 400
    assert response.json()["code"] == "keitaro_not_configured"


async def test_settings_mask_and_encrypt(configured):
    data = (await configured.get("/api/settings")).json()
    assert data["api_key_set"] is True
    assert "valid-key" not in str(data)
    assert data["source"] == "database"
    # empty key keeps the stored one
    response = await configured.put("/api/settings", json={"api_url": "https://tracker.example.com/", "api_key": ""})
    assert response.json()["api_key_set"] is True
    test = (await configured.post("/api/settings/test")).json()
    assert test["ok"] is True


async def test_connection_wrong_key(configured):
    response = await configured.post("/api/settings/test", json={"api_key": "wrong"})
    assert response.json()["ok"] is False


async def test_auth_error_and_timeout(configured, fake):
    await configured.put("/api/settings", json={"api_url": "https://tracker.example.com", "api_key": "wrong"})
    assert (await configured.get("/api/campaigns")).status_code == 502
    await configured.put("/api/settings", json={"api_url": "https://tracker.example.com", "api_key": "valid-key"})
    fake.timeout = True
    assert (await configured.get("/api/campaigns")).status_code == 504


async def test_create_campaign_with_two_streams(configured, fake):
    response = await configured.post("/api/campaigns", json=CREATE)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["campaign"]["name"] == "Test US"
    assert data["campaign"]["group_name"] == "Main"
    assert data["local"]["country"] == "US"
    geo, offer = data["streams"]
    assert geo["schema"] == "redirect"
    assert geo["action_payload"] == "https://www.google.com"
    assert geo["filters"][0] == {"id": None, "name": "country", "mode": "accept", "payload": ["US"]}
    assert offer["schema"] == "landings"
    assert offer["offers"][0]["offer_id"] == 10 and offer["offers"][0]["share"] == 100
    posted = [b for m, p, b in fake.requests if m == "POST" and p == "/campaigns"][0]
    assert posted["type"] == "position" and posted["domain_id"] == 3 and posted["alias"]

    listing = (await configured.get("/api/campaigns")).json()
    assert listing["total"] == 1 and listing["offers_total"] == 1
    assert listing["items"][0]["offers_count"] == 1
    assert (await configured.get("/api/campaigns", params={"search": "nothing"})).json()["total"] == 0

    logs = (await configured.get("/api/logs")).json()
    assert logs[0]["action"] == "campaign.create" and logs[0]["status"] == "success"


async def test_create_validation(configured):
    response = await configured.post("/api/campaigns", json={**CREATE, "country": "USA", "name": " "})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    response = await configured.post("/api/campaigns", json={**CREATE, "offer_id": 999})
    assert response.status_code == 422


async def test_create_rollback_when_stream_fails(configured, fake):
    fake.fail_stream_create = True
    response = await configured.post("/api/campaigns", json=CREATE)
    assert response.status_code == 422
    assert all(c["state"] == "deleted" for c in fake.campaigns.values())
    logs = (await configured.get("/api/logs")).json()
    assert logs[0]["status"] == "error"


async def test_offers_flow(configured):
    cid = (await configured.post("/api/campaigns", json=CREATE)).json()["campaign"]["id"]

    data = (await configured.post(f"/api/campaigns/{cid}/offers", json={"offer_id": 11})).json()
    assert sorted(i["share"] for i in data["items"]) == [50, 50]

    data = (await configured.post(f"/api/campaigns/{cid}/offers", json={"offer_id": 12, "share": 20})).json()
    shares = {i["offer_id"]: i["share"] for i in data["items"]}
    assert shares == {10: 40, 11: 40, 12: 20}
    assert data["streams"][0]["total_share"] == 100

    duplicate = await configured.post(f"/api/campaigns/{cid}/offers", json={"offer_id": 12})
    assert duplicate.status_code == 422

    stream_id = data["streams"][0]["stream_id"]
    bad = await configured.put(
        f"/api/campaigns/{cid}/offers",
        json={"stream_id": stream_id, "offers": [{"offer_id": 10, "share": 70}, {"offer_id": 11, "share": 20}]},
    )
    assert bad.status_code == 422
    good = await configured.put(
        f"/api/campaigns/{cid}/offers",
        json={"stream_id": stream_id, "offers": [{"offer_id": 10, "share": 70}, {"offer_id": 11, "share": 30}]},
    )
    assert {i["offer_id"]: i["share"] for i in good.json()["items"]} == {10: 70, 11: 30}

    data = (await configured.delete(f"/api/campaigns/{cid}/offers/11")).json()
    assert [(i["offer_id"], i["share"]) for i in data["items"]] == [(10, 100)]
    last = await configured.delete(f"/api/campaigns/{cid}/offers/10")
    assert last.status_code == 422


async def test_streams_flow(configured, fake):
    cid = (await configured.post("/api/campaigns", json=CREATE)).json()["campaign"]["id"]
    payload = {
        "name": "DE bots",
        "type": "forced",
        "schema": "redirect",
        "action_type": "http",
        "action_payload": "https://example.org",
        "filters": [{"name": "country", "mode": "reject", "payload": ["de"]}],
    }
    created = await configured.post(f"/api/campaigns/{cid}/streams", json=payload)
    assert created.status_code == 201, created.text
    stream = created.json()
    assert stream["position"] == 3 and stream["filters"][0]["payload"] == ["DE"]

    invalid = await configured.post(f"/api/campaigns/{cid}/streams", json={**payload, "action_payload": "ftp://x"})
    assert invalid.status_code == 422

    disabled = (await configured.post(f"/api/streams/{stream['id']}/disable")).json()
    assert disabled["state"] == "disabled"

    updated = await configured.put(
        f"/api/streams/{stream['id']}",
        json={**payload, "schema": "landings", "offers": [{"offer_id": 10, "share": 100}]},
    )
    assert updated.json()["schema"] == "landings"

    assert (await configured.delete(f"/api/streams/{stream['id']}")).status_code == 204
    assert len((await configured.get(f"/api/campaigns/{cid}/streams")).json()) == 2


async def test_campaign_update_delete_and_resources(configured):
    cid = (await configured.post("/api/campaigns", json=CREATE)).json()["campaign"]["id"]
    updated = (await configured.put(f"/api/campaigns/{cid}", json={"name": "Renamed", "state": "disabled"})).json()
    assert updated["campaign"]["name"] == "Renamed" and updated["campaign"]["state"] == "disabled"
    assert (await configured.get("/api/campaigns", params={"state": "disabled"})).json()["total"] == 1
    assert (await configured.delete(f"/api/campaigns/{cid}")).status_code == 204
    assert (await configured.get("/api/campaigns")).json()["total"] == 0
    assert (await configured.get("/api/campaigns/99999")).status_code == 404

    for name in ("domains", "groups", "sources", "offers"):
        response = await configured.get(f"/api/resources/{name}")
        assert response.status_code == 200 and len(response.json()) >= 1
    offers = (await configured.get("/api/resources/offers")).json()
    assert offers[0]["payout_value"] == 1.5 and offers[2]["country"] == []
