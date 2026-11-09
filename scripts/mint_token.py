"""Génère un JWT de test (HS256) pour la démo locale. N'existe qu'en dev : en prod, l'IdP émet les tokens.

Usage : JWT_SECRET=... python scripts/mint_token.py --scope "tickets:read docs:read" [--sub alice] [--ttl 3600]
"""
import argparse
import os
import time

import jwt

parser = argparse.ArgumentParser()
parser.add_argument("--scope", default="docs:read tickets:read")
parser.add_argument("--sub", default="alice")
parser.add_argument("--ttl", type=int, default=3600)
args = parser.parse_args()

now = int(time.time())
print(
    jwt.encode(
        {
            "sub": args.sub,
            "scope": args.scope,
            "iss": os.environ.get("JWT_ISSUER", "https://idp.example.com"),
            "aud": os.environ.get("JWT_AUDIENCE", "mcp-gateway"),
            "iat": now,
            "exp": now + args.ttl,
        },
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )
)
