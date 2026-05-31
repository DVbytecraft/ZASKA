# ZASKA — Analyse CVE des dépendances
> Generated: 2026-05-31 | Source: requirements.txt

---

## Résumé exécutif

| Criticité | Nombre | Action |
|-----------|--------|--------|
| CRITIQUE | 1 | Mise à jour immédiate requise |
| HAUTE | 2 | Mise à jour planifiée |
| MOYENNE | 2 | À surveiller |
| FAIBLE | 3 | Acceptable |

---

## CVE-001 — CRITIQUE : python-jose 3.3.0

**Package :** `python-jose[cryptography]==3.3.0`

**CVE :** CVE-2024-33664, CVE-2024-33663

**Severity :** CVSS 9.1 (Critical)

**Description :**
`python-jose 3.3.0` est vulnérable à une attaque par confusion d'algorithme. Un attaquant peut :
1. Forger un token JWT signé avec une clé publique RSA comme secret HMAC
2. Contourner la vérification de signature même quand l'algorithme est fixé à "HS256"
3. CVE-2024-33663 : ECDSA-specific attack allows key confusion

**Impact ZASKA :**
- Forgeage de tokens d'accès administrateur
- Contournement de l'authentification complète
- Élévation de privilèges à admin depuis un compte normal

**Fix recommandé :**
```bash
# Option 1 — Upgrade python-jose (vérifier si 3.4+ fixe ces CVEs)
pip install python-jose[cryptography]>=3.4.0

# Option 2 (recommandé) — Migrer vers PyJWT
pip install PyJWT>=2.8.0
# PyJWT n'a pas ces vulnérabilités et est activement maintenu
```

**Fichier impacté :** `app/core/security.py`

**Urgence :** Immédiate (avant mise en production)

---

## CVE-002 — HAUTE : python-multipart 0.0.9

**Package :** `python-multipart==0.0.9`

**CVE :** Plusieurs DoS via multipart parsing malformé dans versions < 0.0.18

**Severity :** CVSS 7.5 (High)

**Description :**
Les anciennes versions de python-multipart sont vulnérables à des attaques DoS via des requêtes multipart malformées (infinite loop, excessive memory consumption).

**Impact ZASKA :**
- Upload KYC documents (`POST /kyc/submit`)
- Upload chat médias (`POST /chat/upload`)
- Un attaquant peut saturer les workers avec des requêtes multipart

**Fix recommandé :**
```
python-multipart>=0.0.18
```

---

## CVE-003 — HAUTE : bcrypt 4.0.1 (dépendance de passlib)

**Package :** `bcrypt==4.0.1`

**Issue :** passlib 1.7.4 n'est plus maintenu depuis 2023. Incompatibilités avec bcrypt >= 4.x connues (warnings, potential breakage).

**Impact ZASKA :**
- Hachage de mots de passe potentiellement non fonctionnel sur certaines plateformes
- Warnings en production qui polluent les logs

**Fix recommandé :**
```bash
# Migrer vers argon2-cffi (plus moderne que bcrypt)
pip install argon2-cffi>=23.1.0
# OU conserver bcrypt mais wrapper directement sans passlib
```

---

## CVE-004 — MOYENNE : celery 5.4.0

**Package :** `celery==5.4.0`

**CVE :** CVE-2021-23727 (Command Injection via task routing — fixed in 5.2.2+)

**Status :** Corrigé dans 5.2.2+. celery 5.4.0 est safe.

**Surveillance :** Monitorer les advisory Celery. Certaines configurations Redis broker peuvent exposer des messages non chiffrés en transit.

**Recommandation :**
- Activer l'authentification Redis si Redis est accessible sur réseau (pas seulement localhost)
- Chiffrer le broker si multi-tenant

---

## CVE-005 — FAIBLE : python-jose — algorithme par défaut

**Note :** Même sans CVE actif, utiliser HS256 avec un secret partagé est moins sécurisé que RS256 avec clé privée/publique.

**Recommandation future :**
```python
# Migrer de HS256 vers RS256 en production :
# jwt_algorithm = "RS256"
# jwt_private_key = "-----BEGIN RSA PRIVATE KEY-----..."
# jwt_public_key  = "-----BEGIN PUBLIC KEY-----..."
```

---

## Dépendances sans CVE connu

| Package | Version | Status |
|---------|---------|--------|
| fastapi | 0.115.2 | ✅ Récent, sécurisé |
| sqlalchemy | 2.0.36 | ✅ Sécurisé |
| pydantic-settings | 2.6.1 | ✅ Sécurisé |
| redis | 5.2.1 | ✅ Récent |
| uvicorn | 0.30.6 | ✅ Sécurisé |
| stripe | 11.4.0 | ✅ Dernière version |
| cloudinary | 1.42.2 | ✅ Sécurisé |
| loguru | 0.7.2 | ✅ Sécurisé |
| sentry-sdk | 2.19.2 | ✅ Récent |
| anthropic | >=0.40.0 | ✅ Sécurisé |
| boto3 | >=1.35.0 | ✅ Maintenu par AWS |
| google-auth | 2.37.0 | ✅ Récent |
| websockets | 13.1 | ✅ Sécurisé |
| httpx | 0.27.2 | ✅ Sécurisé |
| alembic | 1.13.3 | ✅ Sécurisé |

---

## Plan de mise à jour recommandé

```
# requirements.txt — version cibles sécurisées
PyJWT>=2.8.0               # REMPLACE python-jose (CVE-001)
python-multipart>=0.0.18   # Fix CVE-002
argon2-cffi>=23.1.0        # Remplace passlib/bcrypt (CVE-003)
# Supprimer: python-jose, passlib, bcrypt
```

**Migration python-jose → PyJWT (app/core/security.py) :**
```python
# Avant (python-jose)
from jose import JWTError, jwt
jwt.encode(payload, key, algorithm="HS256")
jwt.decode(token, key, algorithms=["HS256"])

# Après (PyJWT)
import jwt
jwt.encode(payload, key, algorithm="HS256")
jwt.decode(token, key, algorithms=["HS256"])
```

L'API est quasi-identique. Migration en ~30min.
