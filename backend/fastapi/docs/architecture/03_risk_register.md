# ZASKA — Registre des risques
> Generated: 2026-05-31 | Étape 2 — Audit d'architecture

---

## Méthodologie

**Risque = Probabilité × Impact**
- Probabilité : 1 (Rare) → 5 (Quasi-certain)
- Impact : 1 (Négligeable) → 5 (Catastrophique)
- Score : 1-8 FAIBLE | 9-14 MOYEN | 15-19 ÉLEVÉ | 20-25 CRITIQUE

---

## Risques CRITIQUES (score 20-25)

| ID | Risque | P | I | Score | Catégorie | Mitigation actuelle | Action requise |
|----|--------|---|---|-------|-----------|-------------------|----------------|
| R-01 | Webhook replay : faux paiement crédite wallet | 4 | 5 | 20 | Financier | Idempotency table (post-processing) | Vérification idempotency AVANT processing |
| R-02 | JWT algorithm confusion (python-jose CVE) | 3 | 5 | 15→20 | Sécurité | HS256 hardcodé | Migrer vers PyJWT immédiatement |
| R-03 | Photo verification bypassable à 95% | 5 | 4 | 20 | Trust | Warning field dans réponse | Implémenter vraie liveness (FaceLiveness) |
| R-04 | Migration 0039 jamais exécutée en prod | 5 | 4 | 20 | Opérationnel | Script deploy créé | Exécuter avant mise en production |

## Risques ÉLEVÉS (score 15-19)

| ID | Risque | P | I | Score | Catégorie | Mitigation actuelle | Action requise |
|----|--------|---|---|-------|-----------|-------------------|----------------|
| R-05 | OTP rate limiting par IP seulement (multi-IP bypass) | 4 | 4 | 16 | Sécurité | 10 tentatives/IP/10min | Rate limit par email aussi |
| R-06 | Admin suspendu/banni peut continuer à accéder | 2 | 5 | 10→15 | Sécurité/Auth | Aucune | Vérifier suspension dans require_admin() |
| R-07 | Redis non HA sans Sentinel opérationnel | 3 | 5 | 15 | Infrastructure | Script failover créé | Tester et déployer Sentinel |
| R-08 | PostgreSQL SPOF — pas de réplication configurée | 3 | 5 | 15 | Infrastructure | Backup quotidien | Configurer réplication streaming |
| R-09 | Secrets exposés en clair dans .env (pas chiffrés) | 3 | 4 | 12→15 | Sécurité | .gitignore | Vault (HashiCorp/AWS Secrets Manager) |
| R-10 | OTP secret = JWT secret (réutilisation de clé) | 3 | 4 | 12 | Cryptographie | HMAC-SHA256 | Secret séparé pour OTP |
| R-11 | IDOR : n'importe quel user peut voir trust score d'un autre | 4 | 3 | 12 | Vie privée | Auth requise | Limiter données publiques |

## Risques MOYENS (score 9-14)

| ID | Risque | P | I | Score | Catégorie | Mitigation actuelle | Action requise |
|----|--------|---|---|-------|-----------|-------------------|----------------|
| R-12 | Attaque multi-comptes (même personne, N comptes) | 4 | 3 | 12 | Fraude | Phone + email UNIQUE | Device fingerprinting |
| R-13 | Manipulation du Trust Score (achievements farming) | 3 | 3 | 9 | Fraude | Règles basiques | Score decay + audit |
| R-14 | Fuite PII dans logs (email, téléphone) | 3 | 3 | 9 | Conformité | Loguru | Masquage PII dans logs |
| R-15 | Admins peuvent bannir d'autres admins | 2 | 4 | 8 | Gouvernance | Aucune | Hiérarchie admin (super_admin) |
| R-16 | Webhook timestamp absent → replay différé | 2 | 4 | 8 | Sécurité | Aucune | Valider timestamp ≤ 10min |
| R-17 | CORS localhost autorisé en production par défaut | 2 | 4 | 8 | Sécurité | Configurable | Valider en config prod |
| R-18 | Haute latence AWS Rekognition bloque event loop | 2 | 3 | 6→9 | Performance | asyncio.to_thread() | OK — corrigé C-07 |
| R-19 | python-multipart DoS via multipart malformé | 2 | 4 | 8 | DoS | Aucune | Upgrade >= 0.0.18 |
| R-20 | Taux de commission configurable sans audit trail | 2 | 4 | 8 | Financier | Config hardcodée | Audit log sur changements |

## Risques FAIBLES (score 1-8)

| ID | Risque | P | I | Score | Action |
|----|--------|---|---|-------|--------|
| R-21 | Mot de passe faible accepté | 3 | 2 | 6 | Politique min 12 chars + complexité |
| R-22 | CSP trop permissive pour pages d'erreur | 2 | 2 | 4 | Ajuster CSP |
| R-23 | Pas de détection de vivacité pour les selfies KYC | 3 | 2 | 6 | Déjà documenté (C-04) |
| R-24 | Réponses d'erreur exposent détails provider | 2 | 2 | 4 | Messages génériques |
| R-25 | OTP en clair dans logs dev | 2 | 2 | 4 | Masquer dans logs |

---

## Tableau de bord risques

```
CRITIQUE ████████ R-01, R-02, R-03, R-04
ÉLEVÉ    ██████   R-05, R-06, R-07, R-08, R-09, R-10, R-11
MOYEN    ████     R-12..R-20
FAIBLE   ██       R-21..R-25
```

---

## Plan de traitement prioritaire

### Sprint immédiat (avant production)
1. R-02 : Migrer python-jose → PyJWT
2. R-01 : Idempotency webhook check avant processing
3. R-04 : Exécuter migration 0039
4. R-05 : Rate limit OTP par email
5. R-10 : Secret OTP séparé

### Sprint court terme (< 2 semaines)
6. R-03 : AWS FaceLiveness ou iProov
7. R-06 : require_admin() check suspension
8. R-07 : Tester Sentinel failover
9. R-11 : Limiter IDOR trust score
10. R-19 : Upgrade python-multipart

### Planifié (1-3 mois)
11. R-08 : Réplication PostgreSQL
12. R-09 : Vault pour secrets
13. R-12 : Device fingerprinting (Étape 9)
14. R-13 : Trust Score anti-gaming
15. R-16 : Webhook timestamp validation
