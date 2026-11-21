"""Campaign Editor: offers of a stream and the 100% traffic invariant."""
import pytest

CREATE = {"name": "Editor", "country": "DE", "offer_id": 10, "domain_id": 3, "group_id": 1, "traffic_source_id": 2}


@pytest.fixture
async def campaign(configured):
    data = (await configured.post("/api/campaigns", json=CREATE)).json()
    return {"id": data["campaign"]["id"], "stream_id": data["streams"][1]["id"], "geo_id": data["streams"][0]["id"]}


def shares(data, stream_id=None):
    return {i["offer_id"]: (i["share"], i["state"]) for i in data["items"] if stream_id in (None, i["stream_id"])}


def stream_offers(fake, stream_id):
    return {o["offer_id"]: o["share"] for o in fake.streams[stream_id]["offers"]}


async def put_offers(client, campaign, offers, **extra):
    return await client.put(
        f"/api/campaigns/{campaign['id']}/offers", json={"stream_id": campaign["stream_id"], "offers": offers, **extra}
    )


async def test_get_campaign_offers(configured, campaign):
    response = await configured.get(f"/api/campaigns/{campaign['id']}/offers")
    assert response.status_code == 200
    data = response.json()
    assert shares(data) == {10: (100, "active")}
    assert data["items"][0]["offer_name"] == "Offer A"
    # only streams with the "landings" schema are offer streams
    assert [s["stream_id"] for s in data["streams"]] == [campaign["stream_id"]]
    assert data["streams"][0]["total_share"] == 100


async def test_offers_of_unknown_campaign(configured):
    assert (await configured.get("/api/campaigns/9999/offers")).status_code == 404


async def test_add_offer_equal_split(configured, fake, campaign):
    data = (await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 11})).json()
    assert shares(data) == {10: (50, "active"), 11: (50, "active")}
    data = (await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 12})).json()
    assert sorted(s for s, _ in shares(data).values()) == [33, 33, 34]
    assert sum(stream_offers(fake, campaign["stream_id"]).values()) == 100


async def test_add_offer_with_fixed_share(configured, campaign):
    await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 11})
    data = (await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 12, "share": 20})).json()
    assert shares(data) == {10: (40, "active"), 11: (40, "active"), 12: (20, "active")}


async def test_add_duplicate_offer(configured, fake, campaign):
    response = await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 10})
    assert response.status_code == 409
    assert response.json()["code"] == "duplicate_offer"
    assert fake.calls("PUT", r"/streams/\d+") == []


async def test_add_unknown_offer(configured, fake, campaign):
    response = await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 777})
    assert response.status_code == 422
    assert fake.calls("PUT", r"/streams/\d+") == []


async def test_add_to_stream_without_offer_schema(configured, campaign):
    response = await configured.post(
        f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 11, "stream_id": campaign["geo_id"]}
    )
    assert response.status_code == 422


async def test_remove_offer_rebalances(configured, fake, campaign):
    await put_offers(configured, campaign, [{"offer_id": 10, "share": 50}, {"offer_id": 11, "share": 30}, {"offer_id": 12, "share": 20}])
    data = (await configured.delete(f"/api/campaigns/{campaign['id']}/offers/10")).json()
    assert shares(data) == {11: (60, "active"), 12: (40, "active")}
    assert stream_offers(fake, campaign["stream_id"]) == {11: 60, 12: 40}


async def test_remove_last_offer_forbidden(configured, fake, campaign):
    response = await configured.delete(f"/api/campaigns/{campaign['id']}/offers/10")
    assert response.status_code == 422
    assert fake.calls("PUT", r"/streams/\d+") == []


async def test_remove_last_active_offer_forbidden(configured, campaign):
    await put_offers(configured, campaign, [{"offer_id": 10, "share": 100}, {"offer_id": 11, "share": 0, "state": "disabled"}])
    response = await configured.delete(f"/api/campaigns/{campaign['id']}/offers/10")
    assert response.status_code == 422
    assert "активных" in response.json()["detail"]


async def test_remove_missing_offer(configured, campaign):
    assert (await configured.delete(f"/api/campaigns/{campaign['id']}/offers/12")).status_code == 404


async def test_manual_distribution(configured, fake, campaign):
    response = await put_offers(configured, campaign, [{"offer_id": 10, "share": 70}, {"offer_id": 11, "share": 30}])
    assert response.status_code == 200, response.text
    assert stream_offers(fake, campaign["stream_id"]) == {10: 70, 11: 30}


@pytest.mark.parametrize(
    "offers",
    [
        [{"offer_id": 10, "share": 70}, {"offer_id": 11, "share": 20}],  # 90%
        [{"offer_id": 10, "share": 70}, {"offer_id": 11, "share": 40}],  # 110%
        [{"offer_id": 10, "share": 101}],  # out of range
        [{"offer_id": 10, "share": -1}],
        [{"offer_id": 10, "share": 50}, {"offer_id": 10, "share": 50}],  # duplicate
        [{"offer_id": 10, "share": 100, "state": "disabled"}],  # nobody gets traffic
        [],
    ],
)
async def test_invalid_distribution_rejected(configured, fake, campaign, offers):
    response = await put_offers(configured, campaign, offers)
    assert response.status_code == 422
    assert fake.calls("PUT", r"/streams/\d+") == []


async def test_inactive_offers_do_not_count(configured, fake, campaign):
    response = await put_offers(
        configured,
        campaign,
        [{"offer_id": 10, "share": 100}, {"offer_id": 11, "share": 40, "state": "disabled"}],
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert shares(data) == {10: (100, "active"), 11: (40, "disabled")}
    assert data["streams"][0]["total_share"] == 100


async def test_toggle_offer_state(configured, campaign):
    await put_offers(configured, campaign, [{"offer_id": 10, "share": 50}, {"offer_id": 11, "share": 50}])
    response = await put_offers(
        configured, campaign, [{"offer_id": 10, "share": 100}, {"offer_id": 11, "share": 50, "state": "disabled"}]
    )
    assert shares(response.json())[11] == (50, "disabled")


async def test_update_with_unknown_offer(configured, fake, campaign):
    response = await put_offers(configured, campaign, [{"offer_id": 10, "share": 50}, {"offer_id": 555, "share": 50}])
    assert response.status_code == 422
    assert "#555" in response.json()["detail"]
    assert fake.calls("PUT", r"/streams/\d+") == []


async def test_update_conflict_when_stream_changed(configured, fake, campaign):
    await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 11})  # someone else
    response = await put_offers(configured, campaign, [{"offer_id": 10, "share": 100}], expected_offer_ids=[10])
    assert response.status_code == 409
    assert response.json()["code"] == "stale_stream"
    ok = await put_offers(
        configured, campaign, [{"offer_id": 10, "share": 60}, {"offer_id": 11, "share": 40}], expected_offer_ids=[11, 10]
    )
    assert ok.status_code == 200


async def test_update_foreign_stream(configured, campaign):
    other = (await configured.post("/api/campaigns", json={**CREATE, "name": "Other"})).json()
    response = await configured.put(
        f"/api/campaigns/{campaign['id']}/offers",
        json={"stream_id": other["streams"][1]["id"], "offers": [{"offer_id": 10, "share": 100}]},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(("mode", "expected"), [("equal", [33, 33, 34]), ("normalize", [17, 33, 50])])
async def test_distribute_endpoint(configured, fake, campaign, mode, expected):
    # 10/20/30 (sum 60)
    fake.streams[campaign["stream_id"]]["offers"] = [
        {"offer_id": 10, "share": 10, "state": "active"},
        {"offer_id": 11, "share": 20, "state": "active"},
        {"offer_id": 12, "share": 30, "state": "active"},
    ]
    response = await configured.post(
        f"/api/campaigns/{campaign['id']}/offers/distribute", json={"stream_id": campaign["stream_id"], "mode": mode}
    )
    assert response.status_code == 200, response.text
    assert sorted(stream_offers(fake, campaign["stream_id"]).values()) == expected


async def test_distribute_keeps_disabled_offer(configured, fake, campaign):
    fake.streams[campaign["stream_id"]]["offers"] = [
        {"offer_id": 10, "share": 30, "state": "active"},
        {"offer_id": 11, "share": 30, "state": "active"},
        {"offer_id": 12, "share": 25, "state": "disabled"},
    ]
    data = (
        await configured.post(
            f"/api/campaigns/{campaign['id']}/offers/distribute", json={"stream_id": campaign["stream_id"], "mode": "normalize"}
        )
    ).json()
    assert shares(data) == {10: (50, "active"), 11: (50, "active"), 12: (25, "disabled")}


async def _second_offer_stream(client, campaign):
    response = await client.post(
        f"/api/campaigns/{campaign['id']}/streams",
        json={
            "name": "Backup",
            "schema": "landings",
            "offers": [{"offer_id": 10, "share": 50}, {"offer_id": 12, "share": 50}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_multiple_streams(configured, fake, campaign):
    second = await _second_offer_stream(configured, campaign)
    await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 11})  # first offer stream
    data = (await configured.get(f"/api/campaigns/{campaign['id']}/offers")).json()
    assert {s["stream_id"] for s in data["streams"]} == {campaign["stream_id"], second}
    assert all(s["total_share"] == 100 for s in data["streams"])

    # removal limited to one stream
    data = (await configured.delete(f"/api/campaigns/{campaign['id']}/offers/10", params={"stream_id": second})).json()
    assert stream_offers(fake, second) == {12: 100}
    assert stream_offers(fake, campaign["stream_id"]) == {10: 50, 11: 50}

    # removal from every stream that has the offer
    await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 10, "stream_id": second})
    data = (await configured.delete(f"/api/campaigns/{campaign['id']}/offers/10")).json()
    assert all(i["offer_id"] != 10 for i in data["items"])
    assert stream_offers(fake, campaign["stream_id"]) == {11: 100}
    assert stream_offers(fake, second) == {12: 100}


async def test_partial_failure_is_compensated(configured, fake, campaign):
    second = await _second_offer_stream(configured, campaign)
    await configured.post(f"/api/campaigns/{campaign['id']}/offers", json={"offer_id": 11})
    before = {campaign["stream_id"]: stream_offers(fake, campaign["stream_id"]), second: stream_offers(fake, second)}

    fake.fail("PUT", rf"/streams/{second}", 500)  # first stream succeeds, second fails
    response = await configured.delete(f"/api/campaigns/{campaign['id']}/offers/10")
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "partial_update_failed"
    assert body["rollback"]["ok"] is True
    after = {campaign["stream_id"]: stream_offers(fake, campaign["stream_id"]), second: stream_offers(fake, second)}
    assert after == before
    log = (await configured.get("/api/logs")).json()[0]
    assert log["action"] == "offer.remove" and log["status"] == "error"


async def test_single_stream_failure_returns_keitaro_error(configured, fake, campaign):
    fake.fail("PUT", r"/streams/\d+", 422, body={"error": "bad share"})
    response = await put_offers(configured, campaign, [{"offer_id": 10, "share": 60}, {"offer_id": 11, "share": 40}])
    assert response.status_code == 422
    assert response.json()["code"] == "keitaro_rejected"
