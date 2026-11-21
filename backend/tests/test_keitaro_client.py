"""KeitaroClient: error mapping, retry policy and headers (httpx.MockTransport)."""
import httpx
import pytest

from app.integrations.keitaro.client import KeitaroClient, build_base_url
from app.integrations.keitaro.exceptions import (
    KeitaroAPIError,
    KeitaroAuthError,
    KeitaroConnectionError,
    KeitaroNotFoundError,
    KeitaroRateLimitError,
    KeitaroServerError,
    KeitaroTimeoutError,
    KeitaroValidationError,
)


def make(responses, **kwargs):
    """Client whose transport returns the given responses (or raises given exceptions) in order."""
    seen: list[httpx.Request] = []
    sleeps: list[float] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    client = KeitaroClient(
        "https://t.example.com", "secret-key-1", transport=httpx.MockTransport(handler), sleep=fake_sleep, **kwargs
    )
    return client, seen, sleeps


def test_base_url():
    assert build_base_url("https://t.com/") == "https://t.com/admin_api/v1"
    assert build_base_url(" https://t.com/admin_api/v1/ ") == "https://t.com/admin_api/v1"


async def test_headers_and_path():
    client, seen, _ = make([httpx.Response(200, json=[])])
    await client.list_campaigns()
    assert seen[0].url == "https://t.example.com/admin_api/v1/campaigns"
    assert seen[0].headers["Api-Key"] == "secret-key-1"
    assert seen[0].headers["Accept"] == "application/json"


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (400, KeitaroValidationError),
        (401, KeitaroAuthError),
        (403, KeitaroAuthError),
        (404, KeitaroNotFoundError),
        (422, KeitaroValidationError),
        (429, KeitaroRateLimitError),
        (500, KeitaroServerError),
        (503, KeitaroServerError),
        (302, KeitaroAPIError),
    ],
)
async def test_status_mapping(status, exc):
    client, _, _ = make([httpx.Response(status, json={"error": "boom"})], retries=0)
    with pytest.raises(exc) as info:
        await client.create_campaign({"name": "x"})
    assert info.value.status_code == status


async def test_error_message_uses_keitaro_payload():
    client, _, _ = make([httpx.Response(422, json={"error": "Name is required"})])
    with pytest.raises(KeitaroValidationError, match="Name is required"):
        await client.create_stream({})


async def test_non_json_success_is_an_error():
    client, _, _ = make([httpx.Response(200, text="<html>login</html>")])
    with pytest.raises(KeitaroAPIError, match="JSON"):
        await client.list_offers()


async def test_unexpected_shape():
    client, _, _ = make([httpx.Response(200, json={"not": "a list"})])
    with pytest.raises(KeitaroAPIError, match="список"):
        await client.list_offers()


async def test_get_is_retried_on_transient_errors():
    client, seen, sleeps = make(
        [httpx.Response(503), httpx.ConnectError("refused"), httpx.Response(200, json=[{"id": 1}])], retries=2
    )
    assert await client.list_offers() == [{"id": 1}]
    assert len(seen) == 3
    assert sleeps == [0.5, 1.0]  # exponential backoff


async def test_retry_gives_up():
    client, seen, _ = make([httpx.Response(502)], retries=2)
    with pytest.raises(KeitaroServerError):
        await client.list_domains()
    assert len(seen) == 3


async def test_retry_after_is_respected():
    client, _, sleeps = make([httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(200, json=[])])
    await client.list_domains()
    assert sleeps == [3.0]


async def test_retry_after_is_capped():
    client, _, sleeps = make([httpx.Response(429, headers={"Retry-After": "3600"}), httpx.Response(200, json=[])])
    await client.list_domains()
    assert sleeps == [10.0]


@pytest.mark.parametrize("method", ["create_campaign", "create_stream"])
async def test_writes_are_never_retried(method):
    client, seen, _ = make([httpx.Response(503), httpx.Response(200, json={"id": 1})], retries=3)
    with pytest.raises(KeitaroServerError):
        await getattr(client, method)({"name": "x"})
    assert len(seen) == 1


async def test_put_and_delete_not_retried():
    client, seen, _ = make([httpx.ReadTimeout("slow")], retries=3)
    with pytest.raises(KeitaroTimeoutError):
        await client.update_stream(1, {})
    with pytest.raises(KeitaroTimeoutError):
        await client.delete_campaign(1)
    assert len(seen) == 2


async def test_404_and_400_are_not_retried():
    client, seen, _ = make([httpx.Response(404)], retries=3)
    with pytest.raises(KeitaroNotFoundError):
        await client.get_offer(1)
    assert len(seen) == 1


async def test_connection_error_message_has_no_secret():
    client, _, _ = make([httpx.ConnectError("refused secret-key-1")], retries=0)
    with pytest.raises(KeitaroConnectionError) as info:
        await client.list_offers()
    assert "secret-key-1" not in str(info.value)


async def test_groups_fallback_on_validation_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["type"] == "campaign":
            return httpx.Response(400, json={"error": "invalid type"})
        return httpx.Response(200, json=[{"id": 1, "name": "G"}])

    client = KeitaroClient("https://t.example.com", "k", transport=httpx.MockTransport(handler))
    assert await client.list_groups("campaign") == [{"id": 1, "name": "G"}]


async def test_204_returns_none():
    client, _, _ = make([httpx.Response(204)])
    assert await client.delete_stream(1) is None
