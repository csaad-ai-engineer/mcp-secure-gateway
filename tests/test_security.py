"""Tests de sécurité : authentification, expiration, audience, signature, scopes."""
import jwt

from conftest import call_tool, make_token, rpc


def test_health_is_public(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_protected_resource_metadata(client):
    meta = client.get("/.well-known/oauth-protected-resource").json()
    assert meta["authorization_servers"] == ["https://idp.test"]
    assert "tickets:write" in meta["scopes_supported"]


def test_missing_token_returns_401_with_discovery_header(client):
    r = rpc(client, None, "tools/list")
    assert r.status_code == 401
    assert "resource_metadata" in r.headers["www-authenticate"]


def test_expired_token_rejected(client):
    r = rpc(client, make_token(exp=1), "tools/list")
    assert r.status_code == 401


def test_wrong_audience_rejected(client):
    r = rpc(client, make_token(aud="another-api"), "tools/list")
    assert r.status_code == 401


def test_wrong_issuer_rejected(client):
    r = rpc(client, make_token(iss="https://evil.example"), "tools/list")
    assert r.status_code == 401


def test_bad_signature_rejected(client):
    forged = jwt.encode({"sub": "mallory", "scope": "tickets:write", "iss": "https://idp.test",
                         "aud": "mcp-gateway", "exp": 9999999999},
                        "x" * 40, algorithm="HS256")
    assert rpc(client, forged, "tools/list").status_code == 401


def test_alg_none_rejected(client):
    unsigned = jwt.encode({"sub": "m", "scope": "tickets:write", "iss": "https://idp.test",
                           "aud": "mcp-gateway", "exp": 9999999999}, key=None, algorithm="none")
    assert rpc(client, unsigned, "tools/list").status_code == 401


def test_error_does_not_leak_reason(client):
    r = rpc(client, make_token(exp=1), "tools/list")
    assert "expired" not in r.text.lower()


def test_read_scope_cannot_write(client):
    r = call_tool(client, make_token("tickets:read"), "create_ticket", {"title": "Panne réseau"})
    assert r.status_code == 200
    assert r.json()["result"]["isError"] is True


def test_write_scope_can_write(client):
    r = call_tool(client, make_token("tickets:write"), "create_ticket", {"title": "Panne réseau", "severity": "high"})
    assert r.json()["result"]["isError"] is False
