# ZASKA — Audit Sécurité Approfondi (Étape 3)
> Generated: 2026-05-31 | Methodology: STRIDE + OWASP Top 10 + Code Review

---

## Score global sécurité : 58/100

**Décomposition :**
| Domaine | Score | Commentaire |
|---------|-------|-------------|
| Authentification / JWT | 62/100 | python-jose CVE, type header manquant |
| Autorisation RBAC | 65/100 | Admin check incomplet |
| Paiements / Webhooks | 55/100 | Replay non bloqué avant processing |
| Uploads / Fichiers | 75/100 | Types vérifiés, taille limitée |
| API Security | 70/100 | Rate limiting partiel |
| Trust & Safety | 45/100 | Photo verification inefficace |
| Conformité données | 50/100 | PII dans logs, audit trail incomplet |
| Dépendances | 60/100 | CVE python-jose |

---

## Threat Model STRIDE

### Spoofing (Usurpation d'identité)

**S-01 — JWT Algorithm Confusion [CRITIQUE]**
- `python-jose 3.3.0` : CVE-2024-33664/33663 — confusion algorithme
- Impact : Forgeage de tokens admin sans connaître le secret
- Fix : Migrer vers `PyJWT >= 2.8.0`
- Fichier : `app/core/security.py`

**S-02 — OTP Brute-force via multi-IPs [ÉLEVÉ]**
- Rate limit OTP uniquement par IP → bypass avec VPN/proxies
- Aucune limite par email/phone cible
- Impact : Reset de mot de passe par brute-force
- Fix : `rl:otp:{email}` en plus de `rl:otp:{ip}`
- Fichier : `app/api/v1/routers/auth.py`

**S-03 — WebSocket Ticket : usage multiple possible [MOYEN]**
- Ticket 60s TTL mais non marqué "consommé" immédiatement
- Impact : Un ticket peut établir plusieurs connexions WS
- Fix : Atomic SET+GET+DEL lors de la validation
- Fichier : `app/core/ws_ticket.py`

**S-04 — OTP Secret = JWT Secret [ÉLEVÉ]**
- `_hash_otp()` utilise `settings.jwt_secret` comme clé HMAC
- Violation principe de séparation des clés
- Impact : Compromission JWT → compromission OTP (et vice-versa)
- Fix : Variable `OTP_SECRET` séparée dans config

### Tampering (Altération)

**T-01 — Webhook Replay Attack [CRITIQUE]**
- Idempotency check se fait APRÈS processing
- Un webhook `payment_intent.succeeded` peut être rejoué pour créditer N fois
- Fix : Vérifier `WebhookQueue.is_processed(idem_key)` AVANT verify_webhook
- Fichier : `app/api/v1/routers/payments.py:313-325`

**T-02 — Webhook Timestamp absent [ÉLEVÉ]**
- Aucun check sur l'âge des webhooks
- Replay de webhooks vieillis possible (jours après émission)
- Fix : Rejeter webhooks > 10 minutes (timestamp dans payload)

**T-03 — FX Rate sans validation [MOYEN]**
- `fx_usd_to_xof = 0` → division par zéro en calcul
- `fx_usd_to_xof = 1000000` → overflow financier
- Fix : Validator `0 < rate < 100000` dans Settings

**T-04 — Status Filter sans allowlist [MOYEN]**
- Filtrage par status via ORM mais sans validation enum
- Impact : Injection de valeurs invalides, erreurs DB
- Fix : Validation contre `{"OPEN", "ASSIGNED", "COMPLETED", ...}`

### Repudiation (Répudiation)

**RP-01 — Actions admin non auditées [ÉLEVÉ]**
- Ban/suspend/lock utilisateur sans trace immuable
- Un admin compromis peut agir sans laisser de preuve
- Fix : Étendre `FinancialAuditLogger` aux actions admin

**RP-02 — Audit financier incomplet [MOYEN]**
- Logs de transactions sans IP, user-agent, device fingerprint
- Fix : Enrichir `AuditLog` avec métadonnées de requête

### Information Disclosure (Divulgation d'information)

**ID-01 — IDOR : Trust Score public [ÉLEVÉ]**
- `GET /trust/score/{user_id}` accessible par tout utilisateur authentifié
- Expose le score détaillé d'un autre utilisateur
- Fix : Retourner uniquement le niveau (BRONZE/SILVER/GOLD) pour les autres

**ID-02 — IDOR : Admin user lookup [ÉLEVÉ]**
- `GET /admin/users/lookup?phone=...` expose PII complet
- En cas de compromission admin, enumération massive possible
- Fix : Rate limit par admin + masquage partiel téléphone/email

**ID-03 — OTP en clair dans logs [MOYEN]**
- `logger.info("[OTP MOCK] ... code={}", otp_code)` en mode dev
- Fix : `code=***` dans les logs

**ID-04 — Détails provider dans erreurs [MOYEN]**
- Certains messages d'erreur mentionnent le provider ("Stripe error")
- Fix : Messages génériques côté client

### Denial of Service

**DOS-01 — python-multipart DoS [ÉLEVÉ]**
- `python-multipart 0.0.9` : parsing multipart malformé → boucle infinie
- Fix : Upgrade `>= 0.0.18`

**DOS-02 — WebSocket connections sans auth restent ouvertes [MOYEN]**
- Un client peut ouvrir WS puis ne pas envoyer le ticket → connexion fantôme 15s
- Fix : Timeout strict + fermeture immédiate si auth échoue

**DOS-03 — Rekognition sans circuit breaker [FAIBLE]**
- Si AWS tombe, toutes les photo-vérifications bloquent pendant timeout
- Fix : Circuit breaker (5 échecs → fallback mock pendant 60s)

### Elevation of Privilege

**EP-01 — Admin suspendu conserve ses droits [ÉLEVÉ]**
- `require_admin()` vérifie `role == "admin"` mais pas `is_suspended`
- Fix : `if user.is_suspended or user.is_locked: raise 403`

**EP-02 — Admin peut bannir un autre admin [MOYEN]**
- Aucune hiérarchie admin (super_admin vs admin)
- Fix : Vérifier `target.role != "admin"` avant ban/suspend

**EP-03 — Bootstrap secret sans rate limit [MOYEN]**
- `POST /admin/bootstrap` : aucune limite de tentatives
- Fix : Rate limit 3/IP/heure + audit log

---

## Analyse Authentification

### JWT
```
✅ Algorithme fixé à HS256 (pas de "none" possible en théorie)
✅ Secret minimum 32 chars (validé au démarrage)
✅ Token types: access (30min) + refresh (7j) séparés
✅ Blacklist logout (Redis)
✅ Token versioning (password reset invalide tous les tokens)
✅ Claims: sub (user_id), type, ver (version), exp, iat

❌ python-jose 3.3.0 — CVE algorithm confusion
❌ Header "typ" non validé
❌ Algorithme non vérifié dans le payload (header alg)
❌ Refresh token non lié à un device/IP (stolen token = full access)
```

### RBAC
```
Rôles : client | tasker | admin

✅ get_current_user_id() — authentification obligatoire
✅ require_admin() — vérification role == "admin"
✅ require_verified_user() — vérification email/phone
✅ require_kyc_not_rejected() — protection paiements basique
✅ require_kyc_approved() — paiements haute valeur

❌ Pas de ABAC (Attribute-Based Access Control)
❌ Admin suspendu conserve droits (EP-01)
❌ Pas de scopes (admin:read vs admin:write)
❌ Pas de MFA pour admins
```

---

## Analyse Paiements

```
✅ Signature webhook HMAC vérifiée (Stripe/FedaPay/Flutterwave/Paystack)
✅ Idempotency keys sur payment intents
✅ Safety layer avec limites financières
✅ Mock mode protégé (production requis pour real_money_enabled)
✅ Config validator: sk_live_ requis en production

❌ Idempotency check webhook POST-processing (T-01)
❌ Webhook timestamp non validé (T-02)
❌ Rapid cycle window configurable à 0 (désactive détection fraude)
❌ FedaPay signature verification à auditer
```

---

## Analyse Uploads

```
✅ Content-type validé (JPEG/PNG/WebP/PDF seulement)
✅ Taille max configurée (max_upload_bytes = 5 MB défaut)
✅ Upload vers Cloudinary (pas stockage local)
✅ KYC docs sous authenticated delivery

❌ Pas de scan antivirus sur PDF uploads
❌ Pas de validation contenu image (EXIF stripping)
❌ Photo verification peut accepter n'importe quelle photo
```

---

## Matrice de vulnérabilités

| ID | Vulnérabilité | CVSS | P | Exploitation | Fix Disponible |
|----|---------------|------|---|-------------|----------------|
| SEC-001 | python-jose CVE | 9.8 | 3 | Forgeage token admin | ✅ PyJWT migration |
| SEC-002 | Webhook replay | 9.2 | 4 | Wallet crédit multiple | ✅ Pre-check idem |
| SEC-003 | OTP brute-force multi-IP | 8.2 | 3 | Reset password arbitraire | ✅ Rate limit email |
| SEC-004 | Admin bypass suspension | 8.5 | 2 | Accès admin post-ban | ✅ require_admin fix |
| SEC-005 | python-multipart DoS | 7.5 | 2 | Saturation workers | ✅ Upgrade 0.0.18 |
| SEC-006 | OTP key reuse | 7.5 | 3 | Compromission croisée | ✅ OTP_SECRET séparé |
| SEC-007 | IDOR trust score | 7.1 | 4 | Profiling utilisateurs | ✅ Masquage données |
| SEC-008 | Webhook timestamp | 7.5 | 2 | Replay différé | ✅ Validation age |
| SEC-009 | CORS localhost prod | 5.8 | 2 | CSRF en production | ✅ Config validator |
| SEC-010 | OTP code dans logs | 5.4 | 3 | Exfiltration logs | ✅ Masquage |

---

## Plan de remédiation priorisé

### P0 — Avant toute mise en production (bloquant)

1. **SEC-001** : Migrer `python-jose` → `PyJWT` (~2h)
2. **SEC-002** : Webhook pre-check idempotency (~4h)
3. **SEC-003** : Rate limit OTP par email (~1h)

### P1 — Dans les 48h post-production

4. **SEC-004** : `require_admin()` vérification suspension (~30min)
5. **SEC-006** : Variable `OTP_SECRET` séparée (~1h)
6. **SEC-005** : Upgrade `python-multipart >= 0.0.18` (~15min)
7. **SEC-010** : Masquer OTP dans logs (~15min)

### P2 — Sprint sécurité (2 semaines)

8. **SEC-007** : IDOR trust score — masquer scores tiers (~2h)
9. **SEC-008** : Webhook timestamp validation (~3h)
10. **SEC-009** : CORS validator production (~30min)
11. Audit trail admin actions complet
12. Admin suspension bypass fix (EP-02)
