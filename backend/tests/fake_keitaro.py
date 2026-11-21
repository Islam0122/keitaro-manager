"""In-memory emulation of the Keitaro Admin API v1 used by the tests (httpx.MockTransport)."""
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

API_KEY = "valid-key-0123456789"


@dataclass
class Failure:
    method: str
    pattern: str
    status: int
    skip: int = 0  # let this many matching requests pass first
    times: int = 1  # then fail this many times (-1 = forever)
    body: Any = None
    headers: dict[str, str] | None = None


class FakeKeitaro:
    def __init__(self) -> None:
        self.campaigns: dict[int, dict[str, Any]] = {}
        self.streams: dict[int, dict[str, Any]] = {}
        self.offers = {
            10: {"id": 10, "name": "Offer A", "country": ["US"], "state": "active", "payout_value": "1.5"},
            11: {"id": 11, "name": "Offer B", "country": [], "state": "active"},
            12: {"id": 12, "name": "Offer C", "country": None, "state": "active"},
        }
        self.groups = [{"id": 1, "name": "Main", "type": "campaign"}]
        self.sources = [{"id": 2, "name": "Facebook", "state": "active"}]
        self.domains = [{"id": 3, "name": "track.example.com", "network_status": "active"}]
        self.requests: list[tuple[str, str, Any]] = []
        self._seq = 100
        self.fail_stream_create = False
        self.timeout = False
        self.failures: list[Failure] = []
        self.groups_type = "campaign"  # value of ?type= this fake Keitaro version understands

    def fail(self, method: str, pattern: str, status: int = 500, **kwargs: Any) -> Failure:
        failure = Failure(method, pattern, status, **kwargs)
        self.failures.append(failure)
        return failure

    def _injected(self, method: str, path: str) -> httpx.Response | None:
        for failure in self.failures:
            if failure.method != method or not re.fullmatch(failure.pattern, path):
                continue
            if failure.skip > 0:
                failure.skip -= 1
                return None
            if failure.times == 0:
                continue
            failure.times -= 1
            return httpx.Response(
                failure.status, json=failure.body or {"error": f"injected {failure.status}"}, headers=failure.headers
            )
        return None

    def calls(self, method: str, pattern: str) -> list[Any]:
        return [b for m, p, b in self.requests if m == method and re.fullmatch(pattern, p)]

    def _id(self) -> int:
        self._seq += 1
        return self._seq

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.timeout:
            raise httpx.ReadTimeout("timeout", request=request)
        if request.headers.get("Api-Key") != API_KEY:
            return httpx.Response(401, json={"error": "Unauthorized"})
        path = request.url.path.removeprefix("/admin_api/v1")
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, path, body))
        method = request.method
        if (injected := self._injected(method, path)) is not None:
            return injected

        def ok(data: Any, status: int = 200) -> httpx.Response:
            return httpx.Response(status, json=data)

        if path == "/campaigns" and method == "GET":
            return ok(list(self.campaigns.values()))
        if path == "/campaigns" and method == "POST":
            cid = self._id()
            self.campaigns[cid] = {"id": cid, "state": "active", **body}
            return ok(self.campaigns[cid])
        if m := re.fullmatch(r"/campaigns/(\d+)(/\w+)?", path):
            cid, sub = int(m.group(1)), m.group(2)
            if cid not in self.campaigns:
                return httpx.Response(404, json={"error": "Not found"})
            if sub is None and method == "GET":
                return ok(self.campaigns[cid])
            if sub is None and method == "PUT":
                self.campaigns[cid].update(body)
                return ok(self.campaigns[cid])
            if sub is None and method == "DELETE":
                self.campaigns[cid]["state"] = "deleted"
                for stream in self.streams.values():
                    if stream["campaign_id"] == cid:
                        stream["state"] = "deleted"
                return httpx.Response(204)
            if sub == "/streams":
                return ok([s for s in self.streams.values() if s["campaign_id"] == cid])
            if sub in ("/enable", "/disable"):
                self.campaigns[cid]["state"] = "active" if sub == "/enable" else "disabled"
                return ok(self.campaigns[cid])
        if path == "/streams" and method == "POST":
            if self.fail_stream_create:
                return httpx.Response(400, json={"error": "Invalid stream"})
            sid = self._id()
            self.streams[sid] = {"id": sid, "offers": [], "filters": [], **body}
            return ok(self.streams[sid])
        if m := re.fullmatch(r"/streams/(\d+)(/\w+)?", path):
            sid, sub = int(m.group(1)), m.group(2)
            if sid not in self.streams:
                return httpx.Response(404, json={"error": "Not found"})
            stream = self.streams[sid]
            if sub in ("/enable", "/disable"):
                stream["state"] = "active" if sub == "/enable" else "disabled"
                return ok(stream)
            if method == "GET":
                return ok(stream)
            if method == "PUT":
                stream.update(body)
                if "offers" in body:
                    stream["offers"] = [{"id": self._id(), "stream_id": sid, **o} for o in body["offers"]]
                return ok(stream)
            if method == "DELETE":
                del self.streams[sid]
                return httpx.Response(204)
        if path == "/offers":
            return ok(list(self.offers.values()))
        if m := re.fullmatch(r"/offers/(\d+)", path):
            oid = int(m.group(1))
            return ok(self.offers[oid]) if oid in self.offers else httpx.Response(404, json={"error": "Not found"})
        if path == "/groups":
            return ok(self.groups if request.url.params.get("type") == self.groups_type else [])
        if path == "/traffic_sources":
            return ok(self.sources)
        if path == "/domains":
            return ok(self.domains)
        return httpx.Response(404, json={"error": f"Unknown route {method} {path}"})
