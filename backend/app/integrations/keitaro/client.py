"""Async client for the Keitaro Admin API v1.

Reference: https://admin-api.docs.keitaro.io/
All requests go to ``{tracker_url}/admin_api/v1`` and are authenticated with the ``Api-Key`` header.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.integrations.keitaro.exceptions import (
    KeitaroAPIError,
    KeitaroAuthError,
    KeitaroConnectionError,
    KeitaroNotFoundError,
    KeitaroTimeoutError,
)

logger = logging.getLogger(__name__)

API_PREFIX = "/admin_api/v1"

JSON = dict[str, Any]


def build_base_url(api_url: str) -> str:
    """Normalise user input: ``https://tracker.com`` and ``https://tracker.com/admin_api/v1/`` are both accepted."""
    url = api_url.strip().rstrip("/")
    if url.endswith(API_PREFIX):
        return url
    return url + API_PREFIX


class KeitaroClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = build_base_url(api_url)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Api-Key": api_key, "Accept": "application/json"},
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            transport=transport,
            follow_redirects=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> KeitaroClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ core
    async def _request(self, method: str, path: str, *, params: JSON | None = None, json: Any = None) -> Any:
        started = time.perf_counter()
        try:
            response = await self._client.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:
            raise KeitaroTimeoutError(f"Keitaro не ответил вовремя ({method} {path})") from exc
        except httpx.RequestError as exc:
            raise KeitaroConnectionError(f"Не удалось подключиться к Keitaro: {exc.__class__.__name__}") from exc

        elapsed = (time.perf_counter() - started) * 1000
        logger.info("Keitaro %s %s -> %s (%.0f ms)", method, path, response.status_code, elapsed)

        if response.status_code in (401, 403):
            raise KeitaroAuthError("Keitaro отклонил запрос: неверный API-ключ или недостаточно прав", response.status_code)
        if response.status_code == 404:
            raise KeitaroNotFoundError(f"Объект не найден в Keitaro ({path})", 404)
        if response.status_code >= 400:
            payload = self._safe_json(response)
            raise KeitaroAPIError(self._error_message(response, payload), response.status_code, payload)

        if response.status_code == 204 or not response.content:
            return None
        payload = self._safe_json(response)
        if payload is None:
            raise KeitaroAPIError(
                "Keitaro вернул некорректный ответ (ожидался JSON). Проверьте API URL.", response.status_code
            )
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
        return await self._get_list("/groups", params={"type": group_type})

    async def list_traffic_sources(self) -> list[JSON]:
        return await self._get_list("/traffic_sources")

    async def list_offers(self) -> list[JSON]:
        return await self._get_list("/offers")

    async def get_offer(self, offer_id: int) -> JSON:
        return await self._get_object("GET", f"/offers/{offer_id}")
