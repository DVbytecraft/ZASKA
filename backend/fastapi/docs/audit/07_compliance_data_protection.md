# ZASKA — Conformité & Protection des données (Étape 7)
> Generated: 2026-05-31

---

## Cadre réglementaire applicable

| Réglementation | Territoire | Applicable ? | Score conformité |
|---------------|-----------|-------------|----------------|
| RGPD (EU) | Europe | OUI (users EU possible) | 45/100 |
| PDPO (Ghana) | Ghana | OUI (GHS support) | Non évalué |
| NDPR (Nigeria) | Nigeria | OUI (NGN support) | Non évalué |
| DSL (Côte d'Ivoire) | Côte d'Ivoire | OUI | Non évalué |
| PCI DSS | Global (cartes) | Via Stripe (OUI) | 75/100 (délégué) |

---

## Données personnelles collectées

### Catégorie 1 : Données d'identification
| Donnée | Table | Chiffrement au repos | Chiffrement transit |
|--------|-------|---------------------|-------------------|
| Prénom/Nom | `users` | Non (PostgreSQL) | TLS |
| Email | `users` | Non | TLS |
| Téléphone | `users` | Non | TLS |
| Avatar URL | `users` | Via Cloudinary | TLS |
| Ville | `users` | Non | TLS |

### Catégorie 2 : Données biométriques [HAUTE SENSIBILITÉ]
| Donnée | Stockage | Durée retention | Consentement explicite |
|--------|----------|-----------------|----------------------|
| Selfie photo | Cloudinary | Indéterminé | Non documenté |
| Photo KYC | Cloudinary | Indéterminé | Non documenté |
| Score liveness | `photo_verifications` | Permanent | Non documenté |

**⚠️ ALERTE RGPD :** Les selfies et photos KYC sont des données biométriques (Art. 9 RGPD — catégories spéciales). Nécessitent :
- Consentement explicite et informé (Case à cocher spécifique)
- Base légale documentée (contrat ou intérêt légitime insuffisant)
- Politique de rétention définie
- Possibilité de suppression sur demande

### Catégorie 3 : Données financières
| Donnée | Stockage | PCI DSS |
|--------|----------|---------|
| Numéros de carte | Via Stripe uniquement | Délégué Stripe |
| Soldes wallet | PostgreSQL | Non applicable |
| Historique transactions | PostgreSQL | Audit trail requis |

### Catégorie 4 : Données de localisation
| Donnée | Table | Précision | Consentement |
|--------|-------|-----------|-------------|
| Latitude/Longitude tâche | `tasks` | GPS | Implicite (création tâche) |
| Ville utilisateur | `users` | Ville | Implicite |
| IP (rate limiting) | Redis | IP | Non informé |

---

## Analyse RGPD

### Droits des personnes (Art. 12-22)

| Droit | Implémenté | Endpoint | Note |
|-------|-----------|----------|------|
| Accès (Art. 15) | Partiel | `GET /users/me` | Ne couvre pas les logs, KYC, transactions |
| Rectification (Art. 16) | Partiel | `PATCH /users/me` | Email/phone non modifiable |
| Suppression (Art. 17) | ❌ Non | Aucun | Aucun endpoint de suppression de compte |
| Portabilité (Art. 20) | ❌ Non | `GET /statement` (partiel) | Pas d'export JSON complet |
| Opposition (Art. 21) | ❌ Non | Aucun | Pas de désabonnement notifications |
| Limitation (Art. 18) | ❌ Non | Aucun | |

**Priorité :** Implémenter `DELETE /users/me` avec anonymisation RGPD (pas suppression physique — conserver transactions pour obligations légales).

### Durées de conservation

| Données | Durée légale minimale | Durée actuelle ZASKA |
|---------|-----------------------|---------------------|
| Transactions financières | 5-10 ans (EU) | Indéfinie (append-only) |
| Données KYC | 5 ans (AML) | Indéfinie |
| Logs audit | 3 ans min | Indéfinie |
| Selfies/photos | Durée traitement uniquement | Indéfinie sur Cloudinary |
| Messages chat | Pas d'obligation légale | Indéfinie |
| Données marketing | 3 ans sans activité | N/A |

### Chiffrement

| Élément | État actuel | Recommandation |
|---------|-------------|----------------|
| Transit (HTTPS) | ✅ TLS | OK |
| Repos PostgreSQL | ❌ Non chiffré | pg_crypto ou disk encryption |
| Repos Redis | ❌ Non chiffré | Redis TLS + AUTH |
| Selfies Cloudinary | ✅ Authenticated delivery | OK |
| Secrets .env | ❌ Texte clair | HashiCorp Vault / AWS Secrets |
| Backups PostgreSQL | ❌ Gzip (pas GPG) | Chiffrement GPG |

---

## Registre des traitements (RGPD Art. 30)

| Traitement | Base légale | Données | Retention | Destinataires |
|-----------|-------------|---------|-----------|---------------|
| Authentification | Contrat | email, phone, hash pw | Durée compte | Brevo (OTP) |
| KYC | Obligation légale (AML) | docs identité, selfie | 5 ans | Admin ZASKA, Cloudinary |
| Paiements | Contrat | transactions, wallet | 10 ans | Stripe/FedaPay/etc. |
| Push notifications | Consentement | FCM token | Durée compte | Firebase |
| Trust Score | Intérêt légitime | comportement, notes | Durée compte | Interne |
| Modération | Intérêt légitime | raisons signalement | 1 an | Claude AI (anonymisé) |
| Analytics | Intérêt légitime | logs, métriques | 1 an | Sentry, Prometheus |

---

## Actions correctives prioritaires

### Immédiat (avant RGPD exposure)
1. **Endpoint suppression compte** : anonymisation RGPD (pas delete physique)
2. **Politique de rétention** : définir et documenter les durées
3. **Consentement biométrique** : case à cocher explicite pour selfie KYC
4. **Mentions légales** : page politique de confidentialité

### Court terme (< 3 mois)
5. **Export données** : `GET /users/me/data` — export JSON complet
6. **Purge automatique** : job scheduler nettoyant données expirées
7. **Chiffrement backups** : GPG sur pg_dump
8. **Audit trail RGPD** : log toutes les demandes de droits (accès, suppression)

### Long terme
9. **Chiffrement au repos** : PostgreSQL disk encryption
10. **DPO** : Nommer un délégué protection des données
11. **PIA** : Privacy Impact Assessment pour biométrie
