# mcp-secure-gateway

Serveur MCP d'exemple, sécurisé, pour pratiquer les livrables de la mission « déploiement MCP & IA générative ».

| Livrable de la fiche | Où dans le projet |
|---|---|
| Architecture cible serveurs/connecteurs | `docs/ARCHITECTURE.md` |
| Connecteur MCP (outils exposés) | `server.py` (3 outils : docs, tickets lecture/écriture) |
| OAuth 2.0, autorisation, secrets | `auth.py`, `.env.example` |
| Environnements, déploiement, supervision | `Dockerfile`, `.github/workflows/ci.yml`, section *Environnements* de l'architecture |
| Tests fonctionnels, intégration, sécurité | `tests/` (18 tests) |
| Gouvernance & industrialisation | `docs/GOUVERNANCE.md` |

## Démarrage (5 min)

```bash
pip install -r requirements.txt
pytest -q                                   # 18 tests

export JWT_SECRET="dev-secret-dev-secret-dev-secret-32chars"
python server.py                            # http://127.0.0.1:8000/mcp
```

Dans un autre terminal :

```bash
TOK=$(python scripts/mint_token.py --scope "tickets:read")
H='-H Accept:application/json,text/event-stream -H Content-Type:application/json'

# 1. sans token -> 401 + WWW-Authenticate (découverte OAuth)
curl -i -X POST localhost:8000/mcp $H -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# 2. lecture autorisée
curl -s -X POST localhost:8000/mcp $H -H "Authorization: Bearer $TOK" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_ticket","arguments":{"ticket_id":"INC-1001"}}}'

# 3. écriture refusée avec un token en lecture seule (isError:true) + trace d'audit côté serveur
curl -s -X POST localhost:8000/mcp $H -H "Authorization: Bearer $TOK" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"create_ticket","arguments":{"title":"Test"}}}'

# 4. métadonnées OAuth (RFC 9728)
curl -s localhost:8000/.well-known/oauth-protected-resource
```

Docker : `docker build -t mcp-secure-gateway . && docker run -p 8000:8000 -e JWT_SECRET=... -e ALLOWED_HOSTS="localhost:*" mcp-secure-gateway`

## Limites assumées (à dire franchement en entretien)

- Données factices en mémoire ; en prod, appels à des API aval (identité de service ou On-Behalf-Of).
- HS256 pour le dev ; en prod RS256/ES256 via `JWKS_URL` (code déjà prévu, non testé contre un vrai IdP ici).
- Rate limit en mémoire : insuffisant avec plusieurs réplicas (Redis ou API Gateway).
- Pas de flux d'autorisation côté serveur : l'IdP (Entra ID, Keycloak...) émet les tokens.
- SDK `mcp` v2 : l'API a changé par rapport à la v1 (`FastMCP` devenu `MCPServer`, options HTTP déplacées vers `streamable_http_app()`). Épingler la version et lire le guide de migration.
