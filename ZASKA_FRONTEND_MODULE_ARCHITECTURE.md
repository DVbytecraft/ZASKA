# ZASKA Frontend Module Architecture

## Objectif

Ce socle frontend web aligne l’expérience Zaska sur trois principes:

- `local-first`: l’utilisateur voit d’abord ce qui est pertinent dans son pays, sa ville et sa zone
- `remote-ready`: l’utilisateur peut cibler un autre pays, une autre ville ou une autre adresse pour commander pour quelqu’un
- `dual-sided`: chaque module expose une surface client et une surface opérateur/partenaire

## Routes principales

### Hub

- `/marketplace`
  - point d’entrée multi-modules
  - choix local ou à distance
  - sélection pays / ville / adresse cible

### Food

- `/food`
  - interface client
  - découverte restaurants par pays / ville / proximité
  - quote livraison
  - création et financement commande
  - historique client

- `/food/partner`
  - interface restaurant
  - commandes restaurant
  - changement de statut
  - payouts restaurant

### Shop

- `/shop`
  - interface acheteur
  - découverte marchands par pays / ville / proximité
  - quote livraison
  - création et financement commande
  - historique client

- `/shop/partner`
  - interface vendeur / marchand
  - dashboard marchand
  - commandes marchand
  - changement de statut
  - payouts marchand

### VTC

- `/vtc`
  - interface client
  - devis course
  - demande de course locale
  - demande de course à distance pour un proche
  - historique client

- `/vtc/driver`
  - interface chauffeur
  - présence chauffeur
  - offres de courses
  - actions de cycle de course
  - dashboard chauffeur

### Services généralistes

- `/tasks/new`
  - publication de tâche
- `/tasks`
  - liste et suivi
- `/tasks/:taskId`
  - détail, négociation, suivi

## Logique de ciblage géographique

Le composant commun `TargetLocationPicker` porte:

- mode `local`
- mode `remote`
- pays cible
- ville cible
- adresse cible
- coordonnées géographiques si disponibles

Ce composant doit rester la base de:

- FOOD
- SHOP
- VTC
- futures commandes diaspora

## Inscription

`/auth` applique désormais:

- chargement des pays réellement couverts
- sélection du pays d’inscription
- blocage implicite des pays non couverts
- message explicite si le pays n’apparaît pas dans la liste

## Navigation

La navigation principale expose maintenant:

- Dashboard
- Explorer
- Manger
- Articles
- VTC
- Créer
- Tâches
- Wallet
- Notifications
- Profil

Et pour les taskers:

- Mon capital
- Courses

## Pilotage admin

La surface admin dédiée `Pays & Tarifs` doit désormais couvrir:

- activation / suspension d’un pays
- ouverture / fermeture de l’inscription par pays
- activation food par pays
- activation module par module pour le pays ciblé
- édition du pricing pays
- édition du pricing continent

Cette page doit rester la console unique pour:

- rollout pays
- contrôle modules
- réglage des prix de base VTC
- réglage des prix de base livraison nourriture
- réglage des prix de base livraison articles

## Contrat backend exploité

Le frontend consomme principalement:

- `/auth/signup-countries`
- `/geo/countries`
- `/geo/cities`
- `/geo/places/autocomplete`
- `/food/*`
- `/shop/*`
- `/vtc/*`

via `apps/web/src/services/marketplaceApi.ts`.

Le frontend admin consomme désormais aussi:

- `/admin/modules/catalog`
- `/admin/modules/runtime/{country_code}`
- `/admin/modules/{module_code}/settings`
- `/admin/geo/continents`
- `/admin/geo/continents/{continent_code}/pricing`
- `/admin/geo/countries`
- `/admin/geo/countries/{country_code}`
- `/admin/geo/countries/{country_code}/pricing`
- `/admin/pricing/templates/continents/{continent_code}`
- `/admin/pricing/templates/countries/{country_code}`

## Priorités suivantes

1. enrichir `MarketplacePage` comme cockpit narratif principal
2. ajouter états vides premium et feedbacks plus riches
3. ajouter centre de commande à distance unifié
4. brancher l’admin pricing et l’activation modules côté frontend admin
5. aligner le mobile/app shell sur la même logique d’expérience
