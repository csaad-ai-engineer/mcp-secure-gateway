"""Authentification / autorisation du serveur MCP.

Le serveur MCP agit comme un *resource server* OAuth 2.0 :
- il ne délivre jamais de tokens, il les valide (signature, exp, iss, aud) ;
- l'audience (aud) doit être CE serveur : pas de "token passthrough" ;
- les scopes du token pilotent l'accès outil par outil (moindre privilège).

Mode dev/test : HS256 avec JWT_SECRET.
Mode prod     : RS256/ES256 avec JWKS_URL (clés publiques de l'IdP, ex. Entra ID).
"""
import contextvars
import json
import logging
import os
from functools import lru_cache

import jwt
from starlette.responses import JSONResponse

audit_log = logging.getLogger("audit")
claims_var: contextvars.ContextVar = contextvars.ContextVar("claims", default=None)

SCOPES_SUPPORTED = ["docs:read", "tickets:read", "tickets:write"]


def audit(event: str, **fields) -> None:
    """Une ligne JSON par évènement : facile à ingérer dans Log Analytics / ELK."""
    audit_log.info(json.dumps({"event": event, **fields}, default=str))


def _cfg(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Variable d'environnement manquante : {name}")
    return value


def assert_config() -> None:
    """Fail fast au démarrage : mieux vaut ne pas démarrer que démarrer non sécurisé."""
    if not os.environ.get("JWKS_URL") and len(os.environ.get("JWT_SECRET", "")) < 32:
        raise RuntimeError("Définir JWKS_URL (prod) ou JWT_SECRET >= 32 caractères (dev).")


@lru_cache(maxsize=1)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True)


def verify_token(token: str) -> dict:
    """Valide le JWT et renvoie les claims, sinon lève jwt.PyJWTError."""
    audience = _cfg("JWT_AUDIENCE", "mcp-gateway")
    issuer = _cfg("JWT_ISSUER", "https://idp.example.com")
    jwks_url = os.environ.get("JWKS_URL")
    if jwks_url:
        key = _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
        algorithms = ["RS256", "ES256"]
    else:
        key = _cfg("JWT_SECRET")
        algorithms = ["HS256"]
    return jwt.decode(
        token,
        key,
        algorithms=algorithms,  # liste blanche : jamais "none"
        audience=audience,
        issuer=issuer,
        options={"require": ["exp", "iss", "aud", "sub"]},
        leeway=5,
    )


def current_claims() -> dict:
    claims = claims_var.get()
    if claims is None:
        raise PermissionError("not_authenticated")
    return claims


def require_scope(scope: str) -> dict:
    claims = current_claims()
    granted = set(str(claims.get("scope", "")).split())
    if scope not in granted:
        raise PermissionError(f"missing_scope:{scope}")
    return claims


def _metadata_url() -> str:
    return _cfg("RESOURCE_URL", "http://localhost:8000").rstrip("/") + "/.well-known/oauth-protected-resource"


def protected_resource_metadata() -> dict:
    """RFC 9728 : permet à un client MCP de découvrir quel serveur d'autorisation utiliser."""
    return {
        "resource": _cfg("RESOURCE_URL", "http://localhost:8000"),
        "authorization_servers": [_cfg("JWT_ISSUER", "https://idp.example.com")],
        "scopes_supported": SCOPES_SUPPORTED,
        "bearer_methods_supported": ["header"],
    }


def _unauthorized(reason: str) -> JSONResponse:
    return JSONResponse(
        {"error": "invalid_token", "error_description": reason},
        status_code=401,
        headers={"WWW-Authenticate": f'Bearer resource_metadata="{_metadata_url()}"'},
    )


class AuthMiddleware:
    """Middleware ASGI pur (compatible streaming) : valide le Bearer avant tout traitement MCP."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope["path"]
        if path == "/health":
            return await JSONResponse({"status": "ok"})(scope, receive, send)
        if path == "/.well-known/oauth-protected-resource":
            return await JSONResponse(protected_resource_metadata())(scope, receive, send)

        headers = dict(scope["headers"])
        header = headers.get(b"authorization", b"").decode()
        if not header.lower().startswith("bearer "):
            audit("auth_denied", reason="missing_token", path=path)
            return await _unauthorized("missing_token")(scope, receive, send)

        try:
            claims = verify_token(header[7:].strip())
        except jwt.PyJWTError as exc:
            # On journalise la cause, on ne la renvoie PAS au client.
            audit("auth_denied", reason=type(exc).__name__, path=path)
            return await _unauthorized("invalid_token")(scope, receive, send)

        reset = claims_var.set(claims)
        try:
            await self.app(scope, receive, send)
        finally:
            claims_var.reset(reset)
