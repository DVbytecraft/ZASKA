# ZASKA Cahier des Charges Master

Cahier des charges consolidé de référence.

But :
- regrouper la vision produit
- préciser les règles métier
- fixer les exigences techniques
- intégrer la qualité d’expérience utilisateur

Date : `2026-06-06`

Documents liés :
- `ZASKA_EXPANSION_ARCHITECTURE.md`
- `ZASKA_MASTER_ACTION_PLAN.md`

---

## 1. Vision produit

ZASKA est une plateforme unique multi-profils permettant :
- la création et l’exécution de tâches
- la livraison alimentaire
- la vente et la livraison d’articles
- les abonnements de services récurrents
- les opérations transfrontalières diaspora
- la protection sociale des taskers
- l’administration centralisée par modules, pays et continents

Le système doit être :
- sécurisé
- scalable
- maintenable
- auditable
- activable progressivement

---

## 2. Profils à supporter

### Profils principaux
- client particulier
- tasker
- restaurant
- entreprise B2B
- admin principal
- comptable
- support / call center
- agent KYC
- modérateur
- manager opérations

### Profils futurs préparés
- conducteur VTC
- marchand / vendeur articles
- staff restaurant multi-utilisateurs

### Règle
Un même utilisateur peut à terme porter plusieurs profils métier, mais les accès doivent rester cloisonnés.

---

## 3. Règles d’activation produit

### Principe
Toutes les fonctionnalités peuvent exister dans le backend, mais elles doivent être activables/désactivables par l’admin principal.

### Niveaux d’activation
- global
- continent
- pays
- ville / zone plus tard

### Modules à piloter
- tâches
- food
- boutique / articles
- abonnements
- B2B
- diaspora
- social protection
- comptabilité
- transport / VTC
- KYC avancé
- AML

### Règle absolue
Un module inactif ne doit pas être utilisable même s’il existe en backend.

---

## 4. Exigences UX globales

### Objectif
L’expérience utilisateur doit être excellente, simple, cohérente et rassurante.

### Principes UX
- les actions principales doivent être accessibles en moins de 3 clics
- les prix doivent toujours être visibles avant confirmation
- les taxes doivent être transparentes
- les états doivent être explicites
- les messages d’erreur doivent être compréhensibles
- les parcours `pour moi` et `pour un tiers` doivent être simples
- l’expérience doit être mobile-first
- le design doit rester cohérent entre modules

### Navigation cible
- `Tâches`
- `Food`
- `Abonnements`
- `Boutique`
- plus tard `Transport`

### Règle d’activation UX
Si un module est désactivé dans un pays :
- le système peut l’afficher comme futur module
- mais l’utilisateur doit voir un message clair : zone non encore couverte

---

## 5. Tâches / services à la demande

### Le système doit supporter
- création de tâche
- candidature tasker
- sélection tasker
- négociation
- completion
- validation OTP
- contestation
- notation
- split social automatique

### Sécurité tasker obligatoire
Un tasker ne peut répondre à une tâche que si :
- compte vérifié
- KYC valide
- KYC non expiré
- biométrie requise si applicable
- casier validé
- clearance tasker validée

---

## 6. Protection sociale tasker

### Split obligatoire
Sur tâche validée :
- 77.5% tasker
- 8% Zaska
- 7% pension
- 5% santé
- 2.5% lissage

### Déclenchement
- validation OTP
- ou auto-validation après délai

### Le système doit supporter
- historique des splits
- capital social tasker
- badge social
- lissage automatique
- alertes pension/santé
- comptabilité fonds sociaux

---

## 7. Food

### Activation
Le food n’est pas disponible par défaut partout.
Seul l’admin principal peut l’activer.

### Acteurs
- client
- restaurant
- livreur/tasker
- admin
- support

### Le domaine food doit supporter
- inscription restaurant
- validation restaurant
- staff restaurant
- menu
- photos
- options
- promos
- panier
- commande
- préparation
- dispatch livreur
- remise restaurant
- livraison
- OTP bénéficiaire ou client
- paiement restaurant
- paiement livreur

### Split food
- prix repas -> restaurant
- frais livraison -> split social livreur
- commission restaurant configurable

### Food transfrontalier
Le client peut commander depuis un pays A pour un bénéficiaire dans un pays B.
Le restaurant et le livreur opèrent localement dans la zone du bénéficiaire.

---

## 8. Boutique / Articles

### Objectif
Permettre l’achat d’articles livrables à distance.

### Cas d’usage
- fleurs
- cadeaux
- artisanat
- vêtements
- produits non alimentaires

### Acteurs
- client
- marchand
- livreur/tasker
- admin

### Le système doit supporter
- onboarding marchand
- catalogue
- disponibilité
- commande
- livraison locale
- gifting pour un tiers
- split livraison
- commission vente

---

## 9. Abonnements

### Types
- abonnement Zaska Pro
- abonnement par service
- abonnement B2B

### Fonctionnalités
- plan
- fréquence
- calendrier
- wallet dédié
- prélèvement automatique
- pause
- reprise
- suspension
- réassignation tasker
- visibilité support

---

## 10. Diaspora / Commandes pour tiers

### Le système doit supporter
- commande pour soi
- commande pour un tiers
- bénéficiaire différent
- collecte différente
- exécution différente
- livraison différente

### Le livreur / tasker doit recevoir
- adresse de collecte
- adresse d’exécution si besoin
- adresse de livraison
- contact bénéficiaire
- instructions spéciales

---

## 11. Carnet d’adresses universel

### Le système doit permettre
- adresses enregistrées
- adresses par défaut
- adresses pour proches
- ajout d’adresse à la volée
- réutilisation des adresses partout :
  - tâches
  - food
  - boutique
  - abonnements

---

## 12. Fiscalité

### Le système doit gérer
- TVA par pays
- B2C
- B2B
- exonération si document valide
- traçabilité par transaction
- reporting/export fiscal

### Règle
La TVA n’est jamais mélangée aux revenus Zaska.

---

## 13. AML / conformité

### Le système doit gérer
- plafond par transaction
- plafond mensuel
- patterns suspects
- gel / revue
- reporting autorité
- audit trail

---

## 14. Litiges

### Le système doit gérer
- contestation avant validation
- gel `FROZEN_AUDIT`
- preuves
- historique
- assignation agent
- décisions
- notifications
- SLA 24h

---

## 15. Administration

### Admin principal
Peut :
- activer/désactiver modules
- créer les comptes staff
- attribuer les périmètres pays / continent / module
- voir les rapports globaux

### Comptable
Ne voit que :
- ses chiffres
- son périmètre
- ses pays / continents / modules

### Support
Ne voit que :
- tickets
- abonnements
- cas opérationnels selon scope

### Agent KYC
Ne voit que :
- dossiers KYC

### Modérateur
Ne voit que :
- modération / signalements

### Règle absolue
Chaque rôle ne voit que son périmètre.

---

## 16. Géographie et couverture

### Tous les pays
Tous les pays doivent être préconfigurés.

### Mais
Tous les pays ne sont pas actifs.

### Le système doit gérer
- pays configuré mais inactif
- pays actif
- pays suspendu
- modules actifs par pays
- plus tard modules actifs par continent et ville

---

## 17. Exigences backend

### Architecture
- modular monolith propre
- services métier séparés
- pas de logique métier lourde dans les routes
- dépendances claires

### Base de données
- migrations additives
- rollback
- pas de modification directe prod
- decimal uniquement pour finance
- auditabilité

### Sécurité
- contrôle d’accès strict
- journal d’audit
- idempotence
- antifraude
- RLS progressive sur tables sensibles

### Scalabilité
- jobs asynchrones
- cache si nécessaire
- séparation lecture / calcul / reporting
- design compatible très forte montée en charge

---

## 18. Exigences UX spécifiques par profil

### Client
- prix clair
- taxes claires
- adresses simples
- historique simple
- modules visibles selon couverture

### Tasker
- portefeuille clair
- capital social clair
- sécurité claire
- badges visibles
- paiements transparents

### Restaurant
- dashboard distinct
- commandes visibles en temps réel
- menu simple à gérer
- disponibilité rapide à modifier

### Comptable
- interface filtrée
- réconciliation claire
- exports simples

### Admin principal
- pilotage modules simple
- création staff simple
- zéro passage par le code

---

## 19. Ce qu’on traite d’abord

Avant toute grosse interface, il faut terminer :

1. RBAC / scopes
2. activation modulaire
3. géographie hiérarchique
4. socle comptable
5. domaines backend prioritaires

---

## 20. Définition du résultat attendu

Le résultat final attendu est :
- une seule plateforme
- plusieurs expériences produit
- chaque module pilotable par admin
- chaque rôle isolé
- chaque flux financier traçable
- chaque pays préconfiguré
- chaque lancement activable sans modifier le code
- une UX fluide et cohérente


---

## 21. Implementation Note - 2026-06-06

### Backend progress confirmed

The backend now includes a first RBAC foundation for staff and principal admin governance:
- staff account creation by principal admin
- role catalog and permission catalog
- role assignment per staff user
- scope assignment per staff user
- backward compatibility with the historical admin account model

### UX implication for later interfaces

When interfaces are built on top of this foundation:
- the principal admin must see only actions allowed by the role catalog
- scoped staff must only see their countries, continents and modules
- restaurant, accountant and support interfaces must be separated cleanly
- hidden or inactive modules must remain non-actionable in the UI

### Backend module-control progress confirmed

The backend now supports a first unified activation layer for product modules:
- tasks
- food
- shop
- subscriptions
- B2B
- diaspora
- transport
- social protection
- accounting
- advanced KYC

This means future interfaces can rely on a single backend source of truth for module availability by scope.

### Backend geography progress confirmed

The backend now exposes a first geographic hierarchy source of truth:
- continent
- country
- primary city
- service zones by module

This means future interfaces can guide users by real launch geography instead of only a flat country boolean.

### Backend accounting ledger progress confirmed

The backend now exposes a first accounting foundation that future interfaces will rely on:
- chart of accounts
- immutable ledger entries
- reconciliation snapshots
- country revenue snapshots

This means future accounting and admin interfaces can be designed around:
- real account balances by currency
- reconciliation status of social funds
- country-by-country revenue visibility
- progressive accountant scoping by perimeter

### UX implication for later interfaces

When interfaces are built on top of this foundation:
- the principal admin must see a consolidated accounting cockpit
- the accountant must only see the countries and continents assigned to them
- reconciliation drift must be visible clearly and without ambiguity
- finance screens must explain operational balance vs accounting balance in simple language

### Backend food foundation confirmed

The backend now exposes a first restaurant and food-order foundation:
- restaurants
- restaurant staff
- menus
- menu items
- food orders
- food order items

This means future interfaces can now be designed with clearly separated experiences for:
- client ordering food
- restaurant accepting and preparing orders
- admin activating or disabling food by perimeter

### UX implication for later interfaces

When interfaces are built on top of this foundation:
- the client must browse restaurants and menus without confusion
- the restaurant interface must be operationally distinct from the client interface
- inactive food countries must show a clear unavailable-state message
- meal amount and delivery amount must remain visibly separated in order summaries

### Backend food payment and dispatch foundation confirmed

The backend now supports the first full financial and operational backbone for food delivery:
- food order funding
- meal hold for restaurant payout
- delivery escrow
- automatic creation of a linked delivery task
- automatic restaurant payout release after confirmed delivery

### UX implication for later interfaces

When interfaces are built on top of this foundation:
- the client must see clearly when an order is created versus funded
- the restaurant must see whether payment is secured before preparing
- the delivery task lifecycle must stay understandable across food and task screens
- the final confirmation screen must make it clear that restaurant payout and delivery payout are distinct

### Backend food operations foundation confirmed

The backend now supports a first operational control layer for restaurants:
- pause/reopen restaurant intake
- temporary closure
- stock tracking per menu item
- sold-out state
- service-zone linkage
- payout reporting snapshots

### UX implication for later interfaces

When interfaces are built on top of this foundation:
- a restaurant must be able to close intake instantly without confusing users
- sold-out items must disappear or be clearly disabled
- dispatch teams must see prioritized delivery candidates
- payout screens must help restaurants understand pending, released and refunded amounts

### Backend food catalog and accounting sync foundation confirmed

The backend now supports:
- modifier groups and options on menu items
- time-based availability for restaurants and items
- first service-zone delivery blocking
- restaurant payout synchronization toward accounting

### UX implication for later interfaces

When interfaces are built on top of this foundation:
- customers must see modifiers clearly and transparently priced
- unavailable items must explain whether they are sold out or outside hours
- restaurant payout dashboards must reconcile with admin accounting views
- out-of-zone delivery attempts must return a clear and user-friendly explanation

### Backend food combos and closures foundation confirmed

The backend now supports:
- combo offers
- exceptional restaurant closures
- first polygon-style delivery blocking
- payout sync from restaurant reporting toward accounting

### UX implication for later interfaces

When interfaces are built on top of this foundation:
- combo offers must be easy to understand and priced transparently
- closure windows must surface clear unavailability reasons
- zone blocking must feel precise rather than arbitrary
- restaurant payout views and admin finance views must tell the same story

### Backend reputation system foundation confirmed

- Le cahier backend inclut maintenant une notation bidirectionnelle compl�te et compatible prod.
- Chaque t�che termin�e peut porter:
  - un avis client sur tasker,
  - un avis tasker sur client.
- La note globale est calcul�e automatiquement � partir des crit�res m�tier.
- Les profils publics exposent les deux r�putations sans casser l'ancien affichage tasker.
- Les garde-fous automatiques sont en place:
  - suspension tasker en dessous du seuil d�fini,
  - restriction client vis-�-vis des taskers premium en dessous du seuil d�fini.
- Cette fondation backend pr�pare directement:
  - premium matching,
  - badges avanc�s,
  - scoring relationnel,
  - mod�ration et anti-abus.

### Backend subscriptions foundation confirmed

- Le cahier backend inclut maintenant un moteur de souscriptions persistant.
- Deux familles sont support�es:
  - abonnement g�n�ral `Zaska Pro`,
  - abonnements par cat�gorie de service.
- Chaque abonnement g�re son cycle, son statut et son quota mensuel.
- Le backend peut d�j� d�terminer si un quota s�applique � une t�che donn�e.
- L�admin peut cr�er, ajuster et attribuer les plans via API s�curis�e.
- Cette fondation pr�pare:
  - le premium access r�el,
  - les �conomies mensuelles calcul�es,
  - la facturation et les renouvellements automatiques.

### Backend referral foundation confirmed

- Le cahier backend inclut maintenant un moteur de parrainage persistant.
- Un code de parrainage utilisateur unique est g�n�r� et conserv�.
- Deux parcours sont couverts:
  - parrainage client avec cr�dit sur la premi�re commande,
  - parrainage tasker avec prime apr�s 10 t�ches compl�t�es.
- Les programmes de r�compense sont pilotables par pays et par type de parrainage.
- Le backend g�re d�j� les �v�nements, la qualification et la r�compense.
- Cette fondation pr�pare:
  - affichage profil �parrain� par ��,
  - dashboard parrainage,
  - cr�dits appliqu�s automatiquement c�t� checkout et souscription.
