"""SSRF protection, API key protection, encryption and log redaction."""
import base64
import hashlib
import logging

import pytest
from cryptography.fernet import Fernet

from app.core.logging import RedactingFilter, redact, register_secret
from app.core.security import decrypt_secret, encrypt_secret, hash_password, verify_password
from app.core.url_guard import UnsafeURLError, URLGuard
from tests.conftest import TRACKER_URL, fake_resolver
from tests.fake_keitaro import API_KEY

UNSAFE = [
    "http://tracker.example.com",  # plain http not allowed by default
    "ftp://tracker.example.com",
    "https://localhost",
    "https://LOCALHOST.",
    "https://app.localhost",
    "https://127.0.0.1",
    "https://127.1",
    "https://0.0.0.0",
    "https://10.1.2.3",
    "https://172.16.0.1",
    "https://192.168.1.10:8443",
    "https://100.64.0.1",
    "https://169.254.169.254/latest/meta-data",
    "https://[::1]",
    "https://[fd00::1]",
    "https://[::ffff:127.0.0.1]",
    "https://metadata.google.internal",
    "https://keitaro.internal",
    "https://user:pass@tracker.example.com",
    "https://tracker.example.com/?x=1",
    "https://evil-internal.example.com",  # resolves to 10.0.0.5
    "https://metadata-alias.example.com",  # resolves to 169.254.169.254
    "https://rebind.example.com",  # one public + one loopback address
    "https://does-not-exist.example.com",
    "https://",
    "not a url",
]


@pytest.mark.parametrize("url", UNSAFE)
async def test_guard_rejects(url):
    with pytest.raises(UnsafeURLError):
        await URLGuard(resolver=fake_resolver).validate(url)


@pytest.mark.parametrize("url", ["https://tracker.example.com", "https://tracker.example.com:8443/admin_api/v1/", "https://93.184.216.34"])
async def test_guard_accepts(url):
    assert await URLGuard(resolver=fake_resolver).validate(url) == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    ["https://169.254.169.254", "https://metadata.google.internal", "https://metadata-alias.example.com", "https://[fd00:ec2::254]", "https://[::ffff:169.254.169.254]"],
)
async def test_metadata_blocked_even_when_private_hosts_allowed(url):
    with pytest.raises(UnsafeURLError):
        await URLGuard(allow_private=True, resolver=fake_resolver).validate(url)


@pytest.mark.parametrize("url", ["https://127.0.0.1:8443", "https://10.0.0.5", "https://evil-internal.example.com"])
async def test_private_hosts_opt_in(url):
    assert await URLGuard(allow_private=True, resolver=fake_resolver).validate(url)


async def test_guard_http_opt_in():
    assert await URLGuard(allow_http=True, resolver=fake_resolver).validate("http://tracker.example.com")


@pytest.mark.parametrize("url", ["https://127.0.0.1", "https://169.254.169.254", "https://evil-internal.example.com"])
async def test_ssrf_via_settings_api(client, fake, url):
    response = await client.put("/api/settings", json={"api_url": url, "api_key": API_KEY})
    assert response.status_code == 422
    assert response.json()["code"] == "unsafe_url"
    test = (await client.post("/api/settings/test", json={"api_url": url, "api_key": API_KEY})).json()
    assert test["ok"] is False
    assert fake.requests == []  # nothing was sent anywhere


async def test_stored_key_is_never_sent_to_another_host(configured, fake):
    fake.requests.clear()
    result = (await configured.post("/api/settings/test", json={"api_url": "https://other.example.com"})).json()
    assert result["ok"] is False and "API Key" in result["message"]
    assert fake.requests == []
    response = await configured.put("/api/settings", json={"api_url": "https://other.example.com"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "api_key"


async def test_same_host_keeps_stored_key(configured):
    response = await configured.put("/api/settings", json={"api_url": TRACKER_URL + "/admin_api/v1/"})
    assert response.status_code == 200 and response.json()["api_key_set"] is True


async def test_api_key_never_returned(configured):
    for path in ("/api/settings", "/api/logs", "/api/health"):
        assert API_KEY not in (await configured.get(path)).text
    assert (await configured.get("/api/settings")).json()["api_key_masked"] == "va••••••89"


async def test_api_key_encrypted_at_rest(configured, sessions):
    from sqlalchemy import text

    async with sessions() as session:
        stored = (await session.execute(text("SELECT api_key_encrypted FROM keitaro_config"))).scalar_one()
    assert API_KEY not in stored
    assert decrypt_secret(stored) == API_KEY


async def test_dns_rebinding_checked_on_every_use(configured, monkeypatch):
    from tests import conftest

    monkeypatch.setitem(conftest.DNS, "tracker.example.com", ["10.0.0.7"])
    response = await configured.get("/api/campaigns")
    assert response.status_code == 422 and response.json()["code"] == "unsafe_url"


def test_encryption_roundtrip_and_legacy_ciphertexts():
    token = encrypt_secret("secret-value")
    assert token != encrypt_secret("secret-value")  # random IV
    assert decrypt_secret(token) == "secret-value"
    # ciphertexts produced by v1.0 (key = sha256(SECRET_KEY)) remain readable
    from app.core.config import get_settings

    legacy = Fernet(base64.urlsafe_b64encode(hashlib.sha256(get_settings().secret_key.encode()).digest()))
    assert decrypt_secret(legacy.encrypt(b"old").decode()) == "old"


def test_password_hashing():
    encoded = hash_password("Correct-horse-42")
    assert encoded.startswith("scrypt$") and "Correct-horse-42" not in encoded
    assert verify_password("Correct-horse-42", encoded)
    assert not verify_password("correct-horse-42", encoded)
    assert not verify_password("x", "garbage")


def test_log_redaction():
    register_secret("super-secret-api-key")
    assert "super-secret" not in redact("request failed with key super-secret-api-key")
    assert redact("Api-Key: abc123") == "Api-Key: ***"
    assert redact('{"password": "hunter22"}') == '{"password": "***"}'
    assert redact("Authorization: Bearer eyJabc.def") == "Authorization: Bearer ***"

    record = logging.LogRecord("t", logging.INFO, __file__, 1, "key=%s", ("super-secret-api-key",), None)
    RedactingFilter().filter(record)
    assert record.getMessage() == "key=***"


async def test_api_key_not_in_logs(configured, caplog):
    caplog.set_level(logging.DEBUG)
    await configured.get("/api/campaigns")
    await configured.post("/api/settings/test", json={"api_key": "wrong-key-value-123"})
    text = "\n".join(redact(r.getMessage()) for r in caplog.records)
    assert API_KEY not in text
    assert all(API_KEY not in r.getMessage() for r in caplog.records)
