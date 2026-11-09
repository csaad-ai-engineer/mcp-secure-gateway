# Gouvernance et industrialisation des connecteurs MCP

## 1. Cycle de vie d'un nouveau connecteur

1. **Demande** : cas d'usage, propriétaire métier, données touchées, lecture seule ou écriture.
2. **Revue sécurité** : classification des données, scopes minimaux, appels aval, risque d'injection de prompt.
3. **Développement** : gabarit commun (auth, audit, validation, rate limit déjà branchés).
4. **Tests obligatoires** : fonctionnels, droits (cas refusés), entrées invalides, charge légère.
5. **Mise en production** : pipeline CI/CD, déploiement progressif, tableau de bord et alertes prêts.
6. **Revue périodique** : droits, usage réel, secrets, dépendances (trimestrielle).
7. **Retrait** : désactivation, révocation des accès, archivage de la doc.

## 2. Règles non négociables

- Aucun token retransmis tel quel à une API aval.
- Audience du token = le serveur concerné.
- Outils d'écriture/destructifs : scope dédié, journalisés, confirmation humaine côté client si sensible.
- Aucun secret dans le code, l'image ou les logs ; rotation planifiée.
- Pas de données sensibles dans les journaux (noms d'arguments seulement, pas les valeurs).
- Versions des dépendances et du SDK épinglées ; mise à jour via PR + tests.

## 3. Rôles (RACI simplifié)

| Activité | Équipe plateforme IA | Propriétaire métier | Sécurité |
|---|---|---|---|
| Gabarit et standards | R | C | A |
| Nouveau connecteur | R | A | C |
| Revue des droits | C | R | A |
| Incident | R | C | A |

## 4. Indicateurs

Nombre de connecteurs actifs, % couverts par tests de droits, temps moyen de mise en production d'un connecteur, taux de 401/403, incidents de sécurité, dépendances en retard de version.

## 5. Recommandations d'industrialisation

1. Gabarit (« cookiecutter ») de connecteur avec auth/audit/tests intégrés.
2. Registre interne des serveurs MCP autorisés (propriétaire, scopes, version, données).
3. Gateway commune : TLS, quotas, journalisation centralisée.
4. Allowlist des serveurs MCP externes, jamais d'installation libre par les utilisateurs.
5. Jeu de tests de sécurité réutilisable (ce dépôt : `tests/test_security.py`).
6. Suivi de la spécification MCP et du SDK : elle évolue vite (le SDK Python est passé en v2 avec des changements incompatibles).
