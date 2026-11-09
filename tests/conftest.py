import os
import sys
import time
from pathlib import Path

os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-32chars"
os.environ["JWT_ISSUER"] = "https://idp.test"
os.environ["JWT_AUDIENCE"] = "mcp-gateway"
os.environ["RESOURCE_URL"] = "http://localhost:8000"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt  # noqa: E402
import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from server import get_app  # noqa: E402


def make_token(scope="docs:read tickets:read", **overrides):
    now = int(time.time())
    claims = {
        "sub": "alice",
        "scope": scope,
        "iss": "https://idp.test",
        "aud": "mcp-gateway",
        "iat": now,
        "exp": now + 600,
    }
    claims.update(overrides)
    return jwt.encode(claims, os.environ["JWT_SECRET"], algorithm="HS256")


@pytest.fixture(scope="session")
def client():
    with TestClient(get_app(), base_url="http://localhost") as c:
        yield c


def rpc(client, token, method, params=None, rid=1):
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}},
        headers=headers,
    )


def call_tool(client, token, name, arguments):
    return rpc(client, token, "tools/call", {"name": name, "arguments": arguments})
