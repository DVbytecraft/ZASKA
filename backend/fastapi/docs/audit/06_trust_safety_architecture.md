# ZASKA — Audit Trust & Safety (Étape 6)
> Generated: 2026-05-31

---

## État actuel : Trust & Safety Score 48/100

| Composante | Score | Commentaire |
|-----------|-------|-------------|
| Vérification identité | 35/100 | KYC doc + selfie, pas de liveness |
| Détection multi-comptes | 20/100 | Email/phone unique seulement |
| Anti-fraude paiements | 65/100 | Limits, rapid cycle, fraud flags |
| Modération contenu | 70/100 | IA Claude + règles |
| Trust Score | 55/100 | 6 composantes, pas de decay |
| Réputation | 50/100 | Ratings basiques |
| Device fingerprinting | 0/100 | Non implémenté |
| Analyse comportementale | 0/100 | Non implémenté |
| Détection arnaques | 40/100 | Basique (rapport utilisateur) |

---

## Vecteurs de fraude actuellement possibles

### FV-01 — Faux compte + photo quelconque → PHOTO_VERIFIED [CRITIQUE]
- N'importe qui peut créer un compte avec la photo d'un inconnu
- `detect_faces` accepte n'importe quelle photo contenant un visage
- Badge `PHOTO_VERIFIED` obtenu illégitimement → Trust Score boosté
- **Coût pour l'attaquant :** 0 (une photo Google suffit)

### FV-02 — Multi-comptes (même personne, N accounts) [ÉLEVÉ]
- Phone et email UNIQUE mais rien n'empêche des SIMs jetables
- Pas de device fingerprinting → même téléphone, N comptes
- Contourne les bans et les rate limits par user_id
- **Coût :** SIM jetable (1-2€), nouvelle adresse email (gratuit)

### FV-03 — Farming du Trust Score [ÉLEVÉ]
- Créer 2 comptes → se faire des tâches à soi-même → se noter 5 étoiles
- Trust Score monte sans vraie activité
- Pas de decay temporel (inactif pendant 6 mois = même score)
- **Coût :** Temps + légère complexité

### FV-04 — Sortie de plateforme (off-platform) [MOYEN]
- Tasker et Client s'accordent pour payer directement (éviter commission 15%)
- Difficile à détecter sans analyse des messages
- Perte de revenus ZASKA

### FV-05 — Arnaques après prise de contact [MOYEN]
- Tasker demande paiement anticipé hors plateforme
- Pas de détection de patterns de demande de paiement dans le chat
- Plateforme peut être tenue responsable si modération insuffisante

### FV-06 — Manipulation des avis [MOYEN]
- Sybil attack : créer N comptes pour noter un Tasker 5 étoiles
- Pas de vérification "le noteur a vraiment utilisé ce Tasker"
- `POST /tasks/{task_id}/rate` : vérifier que `rater_id != tasker_id` mais pas anti-Sybil

### FV-07 — Contournement du ban [MOYEN]
- Utilisateur banni peut créer un nouveau compte (SIM jetable)
- Sans device fingerprinting, le ban est contournable en 5 minutes

---

## Architecture Trust & Safety recommandée

### Couche 1 : Vérification d'identité (améliorée)

```
Niveau 0 : Email/phone vérifié (OTP) → score de base
Niveau 1 : KYC docs uploadés + admin review → confiance identité
Niveau 2 : Selfie liveness (FaceLiveness) → face = vraie personne
Niveau 3 : Selfie ↔ KYC doc matching (Rekognition CompareFaces) → cohérence identité
Niveau 4 : Manuelle (admin call pour cas douteux)
```

### Couche 2 : Device fingerprinting

```
Header X-Device-ID (client génère et persiste un UUID par device)
→ Stocké dans Redis : device:{device_id}:{user_id}
→ Alerte si 1 device = N user_ids (multi-compte potentiel)
→ Alerte si 1 user_id = N devices inconnus en peu de temps
→ Score de risque device additionné au Trust Score
```

### Couche 3 : Analyse comportementale

```
Signaux :
- Temps entre création compte et première transaction (< 10min = suspect)
- Fréquence de création de tâches (burst = bot)
- Pattern de notation (toujours 5 étoiles à soi-même = farming)
- Heures d'activité inhabituelles (bots actifs 24h/24)
- Progression Trust Score anormalement rapide
```

### Couche 4 : Trust Score avancé (à implémenter Étape 9)

```
Composantes actuelles (6) :
  - verified_phone     (15 pts)
  - verified_email     (10 pts)
  - kyc_approved       (25 pts)
  - photo_verified     (10 pts)  ← À revaloriser après liveness
  - first_task         (10 pts)
  - account_age        (10 pts — à ajouter)
  
Composantes à ajouter :
  - completion_rate    (0-15 pts) : tâches terminées / tâches acceptées
  - response_time      (0-10 pts) : temps moyen de réponse aux messages
  - rating_consistency (0-10 pts) : variance des notes (stable = fiable)
  - activity_recency   (0-10 pts) : decay si inactif > 30 jours
  - device_trust       (0-5 pts)  : device fingerprint connu depuis X jours
  
Pénalités :
  - report_received    (-10 pts par signalement validé)
  - task_abandoned     (-5 pts par abandon)
  - payment_disputed   (-15 pts si dispute perdue)
  
Niveaux :
  0-20   : UNVERIFIED (rouge)
  21-40  : BASIC      (orange)
  41-60  : SILVER     (gris)
  61-80  : GOLD       (or)
  81-100 : PLATINUM   (platine)
```

---

## Plan anti-fraude détaillé

### Phase 1 : Device fingerprinting (Étape 9b)
- Client envoie `X-Device-ID` header
- Backend stocke `device:{id} → [user_ids]` dans Redis
- Alerte si > 3 user_ids/device → flag fraude
- Score de risque ajouté au Trust Score

### Phase 2 : Liveness réelle (Étape 9a)
- AWS FaceLiveness ou Smile Identity
- Client capture session vidéo de 2s (challenge blink/sourire)
- Backend vérifie avec SDK AWS → true liveness
- KYC doc + face matching en bonus

### Phase 3 : Analyse comportementale (futur)
- Score de vélocité : transactions / période
- Score de cohérence : comportement vs historique
- Score réseau : connexions avec comptes suspects

### Phase 4 : Détection off-platform (futur)
- Analyse NLP des messages chat (pas de PII scan)
- Détection de patterns ("paiement directement", "sans commission", "hors plateforme")
- Alerte modération automatique

---

## Métriques de fraude à monitorer

```
Dashboard Trust & Safety :
- Taux de comptes suspendus / total
- Taux de signalements validés
- Score moyen Trust Score par cohorte
- Devices avec multi-comptes détectés
- Taux de liveness rejected
- Taux de disputes gagnées par ZASKA vs user
- Nouveaux comptes avec Trust Score > 60 en < 24h (anomalie)
```
