"""Async client for the Keitaro Admin API v1.

Reference: https://admin-api.docs.keitaro.io/
All requests go to ``{tracker_url}/admin_api/v1`` and are authenticated with the ``Api-Key`` header.

Error mapping: 401/403 -> KeitaroAuthError, 404 -> KeitaroNotFoundError, 400/422 -> KeitaroValidationError,
429 -> KeitaroRateLimitError, 5xx -> KeitaroServerError, network -> KeitaroConnectionError/KeitaroTimeoutError.
Only idempotent ``GET`` requests are retried (timeouts, connection errors, 429, 502, 503, 504) — retrying a ``POST``
could create a duplicate campaign or stream.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

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

logger = logging.getLogger(__name__)

API_PREFIX = "/admin_api/v1"
RETRYABLE_STATUSES = {429, 502, 503, 504}
MAX_BACKOFF = 10.0

JSON = dict[str, Any]
Sleep = Callable[[float], Awaitable[None]]


def build_base_url(api_url: str) -> str:
    """Normalise user input: ``https://tracker.com`` and ``https://tracker.com/admin_api/v1/`` are both accepted."""
    url = api_url.strip().rstrip("/")
    if url.endswith(API_PREFIX):
        return url
    return url + API_PREFIX


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class KeitaroClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        retries: int = 2,
        backoff: float = 0.5,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.base_url = build_base_url(api_url)
        self.retries = retries
        self.backoff = backoff
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Api-Key": api_key, "Accept": "application/json", "User-Agent": "keitaro-manager"},
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            transport=transport,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> KeitaroClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ core
    async def _request(self, method: str, path: str, *, params: JSON | None = None, json: Any = None) -> Any:
        attempts = 1 + (self.retries if method == "GET" else 0)
        for attempt in range(1, attempts + 1):
            try:
                return await self._send(method, path, params=params, json=json)
            except (KeitaroConnectionError, KeitaroRateLimitError, KeitaroServerError) as exc:
                retryable = isinstance(exc, KeitaroConnectionError) or (
                    isinstance(exc, KeitaroAPIError) and exc.status_code in RETRYABLE_STATUSES
                )
                if not retryable or attempt >= attempts:
                    raise
                delay = min(self.backoff * 2 ** (attempt - 1), MAX_BACKOFF)
                if isinstance(exc, KeitaroRateLimitError) and exc.retry_after is not None:
                    delay = min(exc.retry_after, MAX_BACKOFF)
                logger.warning(
                    "Keitaro %s %s failed (%s), retry %d/%d in %.1fs",
                    method,
                    path,
                    exc.__class__.__name__,
                    attempt,
                    attempts - 1,
                    delay,
                )
                await self._sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    async def _send(self, method: str, path: str, *, params: JSON | None, json: Any) -> Any:
        started = time.perf_counter()
        try:
            response = await self._client.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:
            raise KeitaroTimeoutError(f"Keitaro не ответил вовремя ({method} {path})") from exc
        except httpx.RequestError as exc:
            raise KeitaroConnectionError(f"Не удалось подключиться к Keitaro: {exc.__class__.__name__}") from exc

        elapsed = (time.perf_counter() - started) * 1000
        logger.info(
            "Keitaro %s %s -> %s (%.0f ms)",
            method,
            path,
            response.status_code,
            elapsed,
            extra={"keitaro_path": path, "status": response.status_code, "ms": round(elapsed)},
        )

        status = response.status_code
        if status in (401, 403):
            raise KeitaroAuthError("Keitaro отклонил запрос: неверный API-ключ или недостаточно прав", status)
        if status == 404:
            raise KeitaroNotFoundError(f"Объект не найден в Keitaro ({path})", 404)
        if status >= 300:
            payload = self._safe_json(response)
            message = self._error_message(response, payload)
            if status == 429:
                raise KeitaroRateLimitError(message, _retry_after(response), payload)
            if status in (400, 422):
                raise KeitaroValidationError(message, status, payload)
            if status >= 500:
                raise KeitaroServerError(message, status, payload)
            raise KeitaroAPIError(message, status, payload)

        if status == 204 or not response.content:
            return None
        payload = self._safe_json(response)
        if payload is None:
            raise KeitaroAPIError("Keitaro вернул некорректный ответ (ожидался JSON). Проверьте API URL.", status)
        return payload

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _error_message(response: httpx.Response, payload: Any) -> str:
        detail = None
        if isinstance(payload, dict):
            detail = payload.get("error") or payload.get("message") or payload.get("errors")
        if isinstance(detail, (list, dict)):
            detail = str(detail)
        if isinstance(detail, str) and len(detail) > 500:
            detail = detail[:500] + "…"
        return f"Ошибка Keitaro API ({response.status_code}): {detail or response.reason_phrase}"

    async def _get_list(self, path: str, params: JSON | None = None) -> list[JSON]:
        data = await self._request("GET", path, params=params)
        if not isinstance(data, list):
            raise KeitaroAPIError(f"Неожиданный формат ответа Keitaro для {path}: ожидался список")
        return data

    async def _get_object(self, method: str, path: str, *, params: JSON | None = None, json: Any = None) -> JSON:
        data = await self._request(method, path, params=params, json=json)
        if not isinstance(data, dict):
            raise KeitaroAPIError(f"Неожиданный формат ответа Keitaro для {path}: ожидался объект")
        return data

    # ------------------------------------------------------------- campaigns
    async def list_campaigns(self) -> list[JSON]:
        return await self._get_list("/campaigns")

    async def get_campaign(self, campaign_id: int) -> JSON:
        return await self._get_object("GET", f"/campaigns/{campaign_id}")

    async def create_campaign(self, payload: JSON) -> JSON:
        return await self._get_object("POST", "/campaigns", json=payload)

    async def update_campaign(self, campaign_id: int, payload: JSON) -> JSON:
        return await self._get_object("PUT", f"/campaigns/{campaign_id}", json=payload)

    async def delete_campaign(self, campaign_id: int) -> None:
        await self._request("DELETE", f"/campaigns/{campaign_id}")

    async def enable_campaign(self, campaign_id: int) -> None:
        await self._request("POST", f"/campaigns/{campaign_id}/enable")

    async def disable_campaign(self, campaign_id: int) -> None:
        await self._request("POST", f"/campaigns/{campaign_id}/disable")

    # --------------------------------------------------------------- streams
    async def list_streams(self, campaign_id: int) -> list[JSON]:
        return await self._get_list(f"/campaigns/{campaign_id}/streams")

    async def get_stream(self, stream_id: int) -> JSON:
        return await self._get_object("GET", f"/streams/{stream_id}")

    async def create_stream(self, payload: JSON) -> JSON:
        return await self._get_object("POST", "/streams", json=payload)

    async def update_stream(self, stream_id: int, payload: JSON) -> JSON:
        return await self._get_object("PUT", f"/streams/{stream_id}", json=payload)

    async def delete_stream(self, stream_id: int) -> None:
        await self._request("DELETE", f"/streams/{stream_id}")

    async def enable_stream(self, stream_id: int) -> None:
        await self._request("POST", f"/streams/{stream_id}/enable")

    async def disable_stream(self, stream_id: int) -> None:
        await self._request("POST", f"/streams/{stream_id}/disable")

    # ------------------------------------------------------------- resources
    async def list_domains(self) -> list[JSON]:
        return await self._get_list("/domains")

    async def list_groups(self, group_type: str = "campaign") -> list[JSON]:
        """``GET /groups?type=...``.

        The exact enum value is not consistent across Keitaro versions/docs (``campaign`` vs ``campaigns``), so the
        plural form is tried when the singular one is rejected or returns nothing.
        """
        variants = [group_type, group_type + "s"] if not group_type.endswith("s") else [group_type, group_type[:-1]]
        result: list[JSON] = []
        for index, variant in enumerate(variants):
            try:
                result = await self._get_list("/groups", params={"type": variant})
            except KeitaroValidationError:
                if index == len(variants) - 1:
                    raise
                continue
            if result:
                return result
        return result

    async def list_traffic_sources(self) -> list[JSON]:
        return await self._get_list("/traffic_sources")

    async def list_offers(self) -> list[JSON]:
        return await self._get_list("/offers")

    async def get_offer(self, offer_id: int) -> JSON:
        return await self._get_object("GET", f"/offers/{offer_id}")
