"""Local Keitaro Admin API emulator for demos WITHOUT access to a real tracker.

It serves the same in-memory fake that the test-suite uses (tests/fake_keitaro.py): 3 offers, 1 group,
1 traffic source, 1 domain — all obviously fake (Offer A/B/C, track.example.com). State is lost on restart.

    cd backend && python scripts/mock_keitaro.py            # http://0.0.0.0:9100
    API URL in Settings:  http://127.0.0.1:9100             (local backend)
                          http://host.docker.internal:9100  (backend in Docker on macOS/Windows)
    API key:              valid-key-0123456789

The backend must run with KEITARO_ALLOW_HTTP=true and KEITARO_ALLOW_PRIVATE_HOSTS=true for this to be accepted.
Never use these flags or this emulator in production, and always label a recording made with it as a mock.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import uvicorn

from tests.fake_keitaro import API_KEY, FakeKeitaro

fake = FakeKeitaro()


async def app(scope, receive, send):  # minimal ASGI wrapper around FakeKeitaro.handle
    if scope["type"] != "http":
        return
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body"):
            break
    headers = {k.decode(): v.decode() for k, v in scope["headers"]}
    query = scope["query_string"].decode()
    url = "http://mock" + scope["path"] + (f"?{query}" if query else "")
    response = fake.handle(httpx.Request(scope["method"], url, headers=headers, content=body))
    headers_out = [(b"content-type", b"application/json")]
    await send({"type": "http.response.start", "status": response.status_code, "headers": headers_out})
    await send({"type": "http.response.body", "body": response.content})


if __name__ == "__main__":
    print(f"Mock Keitaro on http://0.0.0.0:9100  (API key: {API_KEY})")
    uvicorn.run(app, host="0.0.0.0", port=9100, log_level="warning")  # noqa: S104
