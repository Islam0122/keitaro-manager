"""Authentication, authorization and brute-force protection."""
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token, derive_key
from app.models import LoginAttempt
from tests.conftest import PASSWORD, USERNAME

PROTECTED = [
    ("GET", "/api/campaigns"),
    ("POST", "/api/campaigns"),
    ("GET", "/api/campaigns/1"),
    ("PUT", "/api/campaigns/1"),
    ("DELETE", "/api/campaigns/1"),
    ("GET", "/api/campaigns/1/offers"),
    ("POST", "/api/campaigns/1/offers"),
    ("PUT", "/api/campaigns/1/offers"),
    ("POST", "/api/campaigns/1/offers/distribute"),
    ("DELETE", "/api/campaigns/1/offers/1"),
    ("GET", "/api/campaigns/1/streams"),
    ("POST", "/api/campaigns/1/streams"),
    ("GET", "/api/streams/1"),
    ("PUT", "/api/streams/1"),
    ("POST", "/api/streams/1/enable"),
    ("DELETE", "/api/streams/1"),
    ("GET", "/api/resources/offers"),
    ("GET", "/api/settings"),
    ("PUT", "/api/settings"),
    ("POST", "/api/settings/test"),
    ("GET", "/api/logs"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/password"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
async def test_unauthorized_access(anon, method, path):
    response = await anon.request(method, path, json={})
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_health_and_login_are_public(anon):
    assert (await anon.get("/api/health")).status_code == 200
    assert (await anon.post("/api/auth/login", json={"username": "x", "password": "y"})).status_code == 401


@pytest.mark.parametrize(
    "header",
    [
        "Bearer not-a-jwt",
        "Basic YWRtaW46cGFzcw==",
        "Bearer " + __import__("jwt").encode({"sub": "1", "exp": 9999999999, "iat": 1, "iss": "keitaro-manager"}, "wrong-key-" * 4, algorithm="HS256"),
        "Bearer " + __import__("jwt").encode({"sub": "1", "exp": 9999999999, "iat": 1, "iss": "keitaro-manager"}, "", algorithm="none"),
    ],
)
async def test_invalid_authentication(anon, header):
    response = await anon.get("/api/campaigns", headers={"Authorization": header})
    assert response.status_code == 401


async def test_expired_token(anon):
    import jwt

    token = jwt.encode(
        {"sub": "1", "iat": 1, "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()), "iss": "keitaro-manager"},
        derive_key("jwt-signing"),
        algorithm="HS256",
    )
    response = await anon.get("/api/campaigns", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401 and response.json()["code"] == "invalid_token"


async def test_token_of_deleted_user(anon):
    token, _ = create_access_token(999, "ghost")
    assert (await anon.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401


async def test_login_and_me(anon):
    response = await anon.post("/api/auth/login", json={"username": " ADMIN ", "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["user"]["username"] == USERNAME
    me = await anon.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["username"] == USERNAME and me.json()["last_login_at"]


async def test_wrong_password_and_unknown_user_look_the_same(anon):
    a = await anon.post("/api/auth/login", json={"username": USERNAME, "password": "wrong"})
    b = await anon.post("/api/auth/login", json={"username": "nobody", "password": "wrong"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


async def test_brute_force_lockout(anon):
    for _ in range(5):
        assert (await anon.post("/api/auth/login", json={"username": USERNAME, "password": "bad"})).status_code == 401
    blocked = await anon.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "too_many_attempts"
    assert int(blocked.headers["Retry-After"]) > 0


async def test_lockout_expires(anon, sessions):
    async with sessions() as session:
        old = datetime.now(UTC) - timedelta(minutes=30)
        session.add_all(LoginAttempt(username=USERNAME, ip="127.0.0.1", success=False, created_at=old) for _ in range(10))
        await session.commit()
    assert (await anon.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})).status_code == 200


async def test_success_resets_username_counter(anon):
    for _ in range(4):
        await anon.post("/api/auth/login", json={"username": USERNAME, "password": "bad"})
    assert (await anon.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})).status_code == 200
    for _ in range(4):
        await anon.post("/api/auth/login", json={"username": USERNAME, "password": "bad"})
    assert (await anon.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})).status_code == 200


async def test_ip_lockout_across_usernames(anon):
    for i in range(20):
        await anon.post("/api/auth/login", json={"username": f"user{i}", "password": "bad"})
    response = await anon.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 429


async def test_change_password(client, anon):
    weak = await client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "short"})
    assert weak.status_code == 422
    wrong = await client.post("/api/auth/password", json={"current_password": "nope", "new_password": "N3w-password!"})
    assert wrong.status_code == 422
    ok = await client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "N3w-password!"})
    assert ok.status_code == 204
    login = await anon.post("/api/auth/login", json={"username": USERNAME, "password": "N3w-password!"})
    assert login.status_code == 200


async def test_audit_log_records_user(configured):
    log = (await configured.get("/api/logs")).json()[0]
    assert log["action"] == "settings.update" and log["username"] == USERNAME
