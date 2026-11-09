"""Tests fonctionnels et d'intégration des outils MCP."""
from conftest import call_tool, make_token, rpc


def test_tools_list_exposes_three_tools(client):
    r = rpc(client, make_token(), "tools/list")
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert names == {"search_docs", "get_ticket", "create_ticket"}


def test_get_ticket_ok(client):
    r = call_tool(client, make_token("tickets:read"), "get_ticket", {"ticket_id": "INC-1001"})
    result = r.json()["result"]
    assert result["isError"] is False
    assert "VPN" in result["content"][0]["text"]


def test_get_ticket_invalid_id_rejected(client):
    r = call_tool(client, make_token("tickets:read"), "get_ticket", {"ticket_id": "1; DROP TABLE"})
    assert r.json()["result"]["isError"] is True


def test_get_ticket_not_found(client):
    r = call_tool(client, make_token("tickets:read"), "get_ticket", {"ticket_id": "INC-9999"})
    assert r.json()["result"]["isError"] is True


def test_search_docs_requires_docs_scope(client):
    denied = call_tool(client, make_token("tickets:read"), "search_docs", {"query": "secrets"})
    assert denied.json()["result"]["isError"] is True
    ok = call_tool(client, make_token("docs:read"), "search_docs", {"query": "secrets"})
    assert ok.json()["result"]["isError"] is False
    assert "Key Vault" in ok.json()["result"]["content"][0]["text"]


def test_create_ticket_validates_severity(client):
    r = call_tool(client, make_token("tickets:write"), "create_ticket", {"title": "Titre valide", "severity": "critical!"})
    assert r.json()["result"]["isError"] is True


def test_rate_limit(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "3")
    token = make_token("tickets:read", sub="burst-user")
    results = [call_tool(client, token, "get_ticket", {"ticket_id": "INC-1001"}).json()["result"]["isError"]
               for _ in range(5)]
    assert results[:3] == [False, False, False]
    assert results[3:] == [True, True]
