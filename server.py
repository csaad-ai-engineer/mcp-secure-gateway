"""Serveur MCP d'exemple : passerelle sécurisée exposant tickets + documentation.

Démontre : transport Streamable HTTP stateless, OAuth 2.0 (resource server),
autorisation par scope et par outil, validation d'entrées, limitation de débit,
journal d'audit, secrets via variables d'environnement.
"""
import functools
import logging
import os
import re
import time
from collections import defaultdict

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from auth import AuthMiddleware, assert_config, audit, current_claims, require_scope

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")

mcp = MCPServer("secure-gateway")

# --- Données factices (en prod : appels API aval avec identité de service ou OBO) ---
TICKETS = {
    "INC-1001": {"title": "VPN instable", "severity": "high", "status": "open"},
    "INC-1002": {"title": "Accès SharePoint refusé", "severity": "low", "status": "closed"},
}
DOCS = [
    {"id": "DOC-1", "title": "Procédure de rotation des secrets", "body": "Rotation tous les 90 jours via Key Vault."},
    {"id": "DOC-2", "title": "Guide d'astreinte", "body": "Escalade N1 puis N2 puis responsable d'astreinte."},
]
TICKET_ID = re.compile(r"^INC-\d{4,8}$")

# --- Limitation de débit (en mémoire ; en prod multi-réplicas : Redis / API Gateway) ---
_calls: dict[str, list[float]] = defaultdict(list)


def _rate_limit(sub: str) -> None:
    limit = int(os.environ.get("RATE_LIMIT_PER_MIN", "60"))
    now = time.monotonic()
    window = [t for t in _calls[sub] if now - t < 60]
    if len(window) >= limit:
        raise RuntimeError("rate_limited")
    window.append(now)
    _calls[sub] = window


def guarded(scope: str):
    """Décorateur : scope requis + rate limit + audit (sans journaliser les valeurs d'arguments)."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            started = time.monotonic()
            sub, outcome = "anonymous", "ok"
            try:
                sub = current_claims()["sub"]  # identité connue même si le scope est refusé
                claims = require_scope(scope)
                _rate_limit(sub)
                return fn(*args, **kwargs)
            except PermissionError:
                outcome = "denied"
                raise
            except Exception:
                outcome = "error"
                raise
            finally:
                audit(
                    "tool_call",
                    tool=fn.__name__,
                    sub=sub,
                    scope=scope,
                    outcome=outcome,
                    arg_names=sorted(kwargs),
                    ms=round((time.monotonic() - started) * 1000, 1),
                )

        return wrapper

    return decorator


@mcp.tool()
@guarded("docs:read")
def search_docs(query: str) -> list[dict]:
    """Recherche dans la documentation interne (titre et contenu)."""
    q = query.strip().lower()[:200]
    return [d for d in DOCS if q in d["title"].lower() or q in d["body"].lower()]


@mcp.tool()
@guarded("tickets:read")
def get_ticket(ticket_id: str) -> dict:
    """Retourne un ticket d'incident à partir de son identifiant (ex. INC-1001)."""
    if not TICKET_ID.match(ticket_id):
        raise ValueError("invalid_ticket_id")
    ticket = TICKETS.get(ticket_id)
    if ticket is None:
        raise LookupError("ticket_not_found")
    return {"id": ticket_id, **ticket}


@mcp.tool()
@guarded("tickets:write")
def create_ticket(title: str, severity: str = "low") -> dict:
    """Crée un ticket d'incident. Action d'écriture : scope tickets:write obligatoire."""
    if severity not in {"low", "medium", "high"}:
        raise ValueError("invalid_severity")
    title = title.strip()
    if not 3 <= len(title) <= 120:
        raise ValueError("invalid_title")
    ticket_id = f"INC-{1001 + len(TICKETS) + 1:04d}"
    TICKETS[ticket_id] = {"title": title, "severity": severity, "status": "open"}
    return {"id": ticket_id, **TICKETS[ticket_id]}


def build_app():
    assert_config()
    # stateless : chaque requête est indépendante -> scalable horizontalement derrière un load balancer
    # Protection DNS-rebinding : seuls les Host/Origin déclarés sont acceptés (ALLOWED_HOSTS, séparés par des virgules)
    hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost:*,127.0.0.1:*,localhost").split(",") if h.strip()]
    origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins)
    return AuthMiddleware(mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=security))


app = None  # construit à la demande (tests : variables d'env définies avant)


def get_app():
    global app
    if app is None:
        app = build_app()
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(), host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
