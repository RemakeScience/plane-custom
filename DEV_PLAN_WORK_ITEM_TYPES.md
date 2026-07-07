# Plan de développement — Work Item Types, Epics & Propriétés personnalisées

> Fork de [makeplane/plane](https://github.com/makeplane/plane) — objectif : réintégrer dans l'édition
> communautaire les fonctionnalités payantes **Work Item Types** (types d'issues), **Epics** et
> **Custom Properties** (propriétés personnalisées).
>
> Ce document est le plan de référence. Il est découpé en **sessions** pour permettre un développement
> incrémental. Cocher les cases au fur et à mesure.
>
> Base : branche `preview`, version `1.3.1` (clone du 2026-07-06).

---

## 0. État des lieux (ce qui existe déjà dans le repo public)

Plane sépare son code payant (`ee/`) du code communautaire (`ce/`) via un **alias de compilation**
`@/plane-web/*`. Dans ce repo, `apps/web/tsconfig.json:10` mappe `@/plane-web/* → ./ce/*`, et il
**n'existe pas de dossier `apps/web/ee`**. Les composants payants sont donc présents sous forme de
**stubs** (qui retournent `<></>` / `null` / des no-ops). Le gating n'est **pas** un feature-flag runtime :
c'est le remplacement de l'alias qui « allume » la feature dans le build EE.

| Brique                | Fondation existante                                                                                                                                                                      | Ce qu'il manque                                                                         | Effort                                   |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ---------------------------------------- |
| **Work Item Types**   | Modèles `IssueType` + `ProjectIssueType`, FK `Issue.type`, flag projet `is_issue_type_enabled`, `type_id` dans le serializer REST public, types TS `TIssue.type_id`, i18n, stubs UI      | API interne (viewset/serializer/urls), service, store, vraie UI                         | 🟢 Modéré                                |
| **Epics**             | Réutilise les issues + `IssueType.is_epic`, `EIssuesStoreType.EPIC`, `EIssueServiceType.EPICS`, slot `epicDetail` dans le root store, route `/epics`, nav, empty-states                  | Endpoints filtrés `is_epic=True`, page épics, store épic concret, modale                | 🟢 Modéré (≈80 % partagé avec les types) |
| **Custom Properties** | **Rien côté backend.** Front : contrat `TIssueModalContext`, stubs de rendu, fetch-keys `WORK_ITEM_TYPES_PROPERTIES_AND_OPTIONS`, types `TIssuePropertyValues = Record<string, unknown>` | 3 modèles backend + migrations + endpoints + enum de types + rendu dynamique + settings | 🔴 Lourd                                 |

### Fichiers clés déjà présents (les « prises »)

**Backend**

- `apps/api/plane/db/models/issue_type.py` — `IssueType` (workspace-scoped), `ProjectIssueType`.
- `apps/api/plane/db/models/issue.py:164` — FK `Issue.type → IssueType` (`SET_NULL`, nullable).
- `apps/api/plane/db/models/project.py:99` — `is_issue_type_enabled` (bool, défaut `False`).
- `apps/api/plane/api/serializers/issue.py:66` — `type_id` exposé (API REST **publique** uniquement).
- `apps/api/plane/app/views/issue/archive.py:99` — pattern de filtrage des épics : `Q(type__isnull=True) | Q(type__is_epic=False)`.
- ⚠️ Les modèles `*UserProperty` (ex-`IssueProperty`) sont des **préférences d'affichage par user**, sans rapport avec les propriétés custom.

**Frontend**

- Alias : `apps/web/tsconfig.json:10` (`@/plane-web/* → ./ce/*`), résolu par Vite via `vite-tsconfig-paths`.
- Stubs types : `apps/web/ce/components/issues/issue-modal/issue-type-select.tsx`, `.../modal-additional-properties.tsx`, `.../provider.tsx`, `apps/web/ce/components/issues/issue-details/{issue-type-switcher,additional-properties,issue-identifier,issue-type-activity}.tsx`, `.../issue-layouts/additional-properties.tsx`, `.../filters/issue-types.tsx`.
- Stubs epics : `apps/web/ce/components/epics/epic-modal/modal.tsx`, `apps/web/ce/store/issue/epic/{issue,filter}.store.ts` (marqués « will never be used »).
- Contrat modale : `apps/web/core/components/issues/issue-modal/context/issue-modal-context.tsx` (`TIssueModalContext`).
- Store : slot `epicDetail` dans `apps/web/core/store/issue/root.store.ts:239` (`new IssueDetail(this, EIssueServiceType.EPICS)`).
- Enum stores : `packages/constants/src/issue/common.ts` (`EIssuesStoreType.EPIC`), fetch-keys `packages/constants/src/fetch-keys.ts:199-203`.
- Types : `packages/types/src/issues/issue.ts:65,78` (`type_id`, `is_epic`), `packages/types/src/issues/issue-property-values.ts` (`Record<string, unknown>`).
- i18n : `packages/i18n/src/locales/*/work-item-type.json` + `work-item.json` (déjà livrés).
- Réglages projet : `apps/web/core/components/project/settings/features-list.tsx` (`PROJECT_FEATURES_LIST`, aujourd'hui : cycles/modules/views/pages/intake).

### Patterns de référence à copier

- ViewSet DRF : `apps/api/plane/app/views/state/base.py` (`StateViewSet`, `BaseViewSet`, `allow_permission`, `mark_as_default`).
- URLs : `apps/api/plane/app/urls/state.py` (routes list/create + retrieve/update/delete + action custom).
- Service front : `apps/web/core/services/module.service.ts`, `apps/web/core/services/project/project-state.service.ts` (héritent de `APIService`).
- Store + registration : `apps/web/core/store/root.store.ts:121-122` (`this.state = new StateStore(...)`), stores injectés via `@/plane-web/store/*` → `apps/web/ce/store/*`.
- Page de settings projet d'une feature existante : suivre le routage des états/labels dans `apps/web/app/.../settings/`.

---

## 1. Décisions d'architecture (à valider avant de coder)

1. **Où vit le code payant réintégré ?** → On implémente **directement dans `apps/web/ce/**`** en remplaçant
les stubs (puisque `@/plane-web → ce`). Pas besoin de créer un dossier `ee/`. Avantage : les points
d'insertion dans `core/` restent inchangés.
2. **Gating** → On réutilise le booléen projet **`is_issue_type_enabled`** (déjà en base) pour les types,
   et on ajoute **`is_epic_enabled`** (nouveau champ projet) pour les épics. Pas de système de feature-flag
   runtime à reconstruire. Les propriétés custom suivent `is_issue_type_enabled` (elles dépendent d'un type).
3. **Portée des types** → `IssueType` est **workspace-scoped** (déjà le cas), associé aux projets via
   `ProjectIssueType`. On garde ce modèle : un type peut être partagé entre projets d'un même workspace.
4. **Exposer `type_id` côté app interne** → Le serializer d'issue de `plane/app` ne l'expose pas encore ;
   il faudra l'ajouter (lecture + écriture) sans casser les autres conscommateurs.
5. **Compat migrations** → Ne **jamais** modifier les migrations existantes. Toute évolution de schéma =
   nouvelle migration. On reste rebasable sur `upstream/preview`.

> ⚠️ À trancher avec l'équipe : garde-t-on la compat avec le schéma EE d'origine de Plane (mêmes noms de
> tables/champs pour les propriétés) pour faciliter un futur import, ou on conçoit notre propre schéma ?
> Recommandation : coller au schéma EE connu (`issue_properties`, `issue_property_options`,
> `issue_property_values`) pour limiter les surprises.

---

## 2. Backend (Django — `apps/api`)

### Phase B1 — API Work Item Types _(socle, à faire en premier)_

**✅ Phase B1 livrée en Session 1** (voir §12 pour le détail des fichiers et la vérification).

- [x] **Serializers** — `apps/api/plane/app/serializers/issue_type.py` : `IssueTypeSerializer`,
      `IssueTypeLiteSerializer`, `ProjectIssueTypeSerializer` (+ export). `is_epic` et `workspace` en read-only.
- [x] **ViewSet** — `apps/api/plane/app/views/issue_type/base.py` : `IssueTypeViewSet` (CRUD workspace-scoped
      via `ProjectIssueType`, `mark_as_default`, protection du type par défaut) + `DefaultIssueTypeEndpoint`.
- [x] **URLs** — `apps/api/plane/app/urls/issue_type.py` : `issue-types/` (list/create),
      `issue-types/<pk>/` (retrieve/patch/delete), `.../mark-default/`, `default-issue-type/`.
- [x] **Exposer `type_id`** — ajouté en lecture (`IssueSerializer`) et écriture (`IssueCreateSerializer`)
      dans `apps/api/plane/app/serializers/issue.py`.
- [x] **Décision seed** → **création à la volée à l'activation** (`DefaultIssueTypeEndpoint`), pas de
      migration data. Backfill des issues sans type vers le type par défaut. `ProjectIssueType` exporté
      dans `db/models/__init__.py`.
- [x] **Tests** — `plane/tests/contract/app/test_issue_type_app.py` : 14 cas (CRUD, défaut unique,
      permissions ADMIN/GUEST/non-auth, exclusion des épics, backfill, idempotence). **14/14 verts.**
- [ ] **Display property** (reporté) — `issue_type` existe déjà dans `display_properties`
      (`workspace_seed_task.py:157`) ; le rendu list/kanban se câblera côté front (Session 3).
- 🐛 **Bug trouvé & corrigé** : soft-delete Plane ⇒ le `SET_NULL` DB ne se déclenche pas à la suppression
  d'un type ⇒ `destroy` détache désormais explicitement les work items (`Issue.objects...update(type=None)`).

### Phase B2 — API Epics

**✅ Phase B2 livrée en Session 4** (voir §17 pour le détail). Foundation (champ projet + type Epic)
livrée dès la Session 4 initiale ; endpoints + audit d'exclusion + parentage complétés ensuite.

- [x] **Champ projet** — migration 0122 : `Project.is_epic_enabled = BooleanField(default=False)` +
      exposé dans le serializer projet de `plane/app` + type TS.
- [x] **Type Epic par défaut** — `DefaultEpicTypeEndpoint` (`/default-epic-type/`) crée
      l'`IssueType(is_epic=True, is_default=True)` à l'activation (idempotent, pas de backfill).
- [x] **Endpoints Epics** — `EpicViewSet` (`apps/api/plane/app/views/issue/epic.py`) sous-classe
      `IssueViewSet`, scope tout sur `Issue.epic_objects` (`type__is_epic=True`) et force le type épic à
      la création. Routes `epics/` (list/create) + `epics/<pk>/` (retrieve/update/delete).
- [x] **Exclusion des épics des listes normales** — résolu **au niveau du manager** :
      `IssueManager.get_queryset()` applique `Q(type__isnull=True) | Q(type__is_epic=False)`. Comme toutes
      les vraies vues de liste (`issue/base`, cycle, module, view, paginated, search, sub-issues) passent
      par `Issue.issue_objects`, l'exclusion est automatique et sans audit vue-par-vue. ⚠️ Piège Django NULL
      évité en utilisant l'OR explicite (pas `.exclude(type__is_epic=True)`). Nouveau manager symétrique
      `Issue.epic_objects` pour les épics.
- [x] **Relations épic → work items** — le parentage passe par le FK `Issue.parent` existant : une épic
      parente des work items normaux (qui restent dans `issue_objects`), l'épic reste hors des listes.
      Vérifié par test.
- [x] **Tests** — `plane/tests/contract/app/test_epic_app.py` : 11 cas (create force le type + ignore le
      type client + 400 sans type + guest 403, list only-epics, **exclusion des listes de work items**,
      partition des managers, retrieve/update/delete, parentage). **11/11 verts**, 28/28 avec les types.

### Phase B3 — API Custom Properties

**✅ Phase B3 livrée en Session 6** (voir §19). Schéma **EE-compat, colonnes de valeur typées**.

- [x] **Modèles** — `apps/api/plane/db/models/issue_property.py` : `IssueProperty` (issue*type FK,
      name, display_name, property_type, relation_type, is_required, is_multi, is_active, default_value,
      settings, sort_order, logo_props, external*\*), `IssuePropertyOption` (property FK, name, description,
      logo_props, is_active, is_default, sort_order, parent), `IssuePropertyValue` (issue FK, property FK,
      **colonnes typées** value_text/value_boolean/value_decimal/value_datetime/value_uuid + value_option FK).
      Enums `PropertyTypeEnum`/`RelationTypeEnum`. Tous extends `ProjectBaseModel` (project+workspace auto).
      Exportés dans `db/models/__init__.py`.
- [x] **Migration** — `0123_...` : 3 tables (`issue_properties`, `issue_property_options`,
      `issue_property_values`) + contrainte unique `(property, name)` sur options (deleted_at null). Appliquée.
      (Pas d'unicité `issue+property` car le multi-valeur = plusieurs lignes.)
- [x] **Serializers** — `IssuePropertySerializer`, `IssuePropertyOptionSerializer`,
      `IssuePropertyValueSerializer` (`serializers/issue_property.py`).
- [x] **ViewSets + URLs** (`views/issue_property/base.py`, `urls/issue_property.py`) :
  - CRUD définitions (scoping type) : `.../issue-types/<type_id>/properties/[<pk>/]` (ADMIN écrit).
  - CRUD options : `.../issue-properties/<property_id>/options/[<pk>/]` (ADMIN écrit).
  - Valeurs par issue (bulk upsert typé) : `.../issues/<issue_id>/property-values/` (GET/POST).
  - Agrégé : `.../issue-property-types/` (propriétés + options imbriquées ; aligne le fetch-key front).
- [x] **Validation** — `is_required` (rejet si vide), `is_multi` (rejet si >1 valeur pour non-multi),
      cohérence type/valeur (coercition typée DECIMAL/DATETIME/BOOLEAN/OPTION/RELATION avant écriture,
      400 si invalide). Validation **complète avant** la transaction (pas d'écriture partielle).
- [~] **Intégration create/update issue** — **différée** : le front appelle `property-values/` après
  create (comme le stub provider `handleCreateUpdatePropertyValues`). Câblage inline dans `IssueViewSet`
  = follow-up (Session 8/9), évite de toucher le viewset d'issue partagé maintenant.
- [x] **Tests** — `plane/tests/contract/app/test_issue_property_app.py` : 12 cas (CRUD props, options +
      agrégé, valeurs texte/option/multi, requis, non-multi rejette, décimal invalide, upsert remplace,
      guest 403). **12/12 verts.**

### Phase B4 — Activation / gating backend

- [ ] Endpoint d'activation feature par projet (types + épics) qui : bascule le booléen projet, crée le
      type par défaut (et l'Epic type si épics). Mirror du toggle des autres features projet.
- [ ] Exposer `is_issue_type_enabled` **et** `is_epic_enabled` dans le serializer projet de `plane/app`
      (aujourd'hui `is_issue_type_enabled` n'est exposé que dans l'API REST publique).

---

## 3. Data layer (`packages`)

### Types (`packages/types/src`)

- [x] `packages/types/src/issues/issue-type.ts` : `TIssueType`, `TProjectIssueType` (Session 2, exporté).
      Aussi ajouté `is_issue_type_enabled?` sur le type projet (`project/projects.ts`).
- [x] `packages/types/src/issues/issue-property.ts` (Session 7) : `EIssuePropertyType`,
      `EIssuePropertyRelationType`, `TIssueProperty`, `TIssuePropertyOption`, `TIssuePropertySettings`,
      `TIssuePropertyWithOptions`. Exporté dans l'index.
- [x] `TIssuePropertyValues` structuré en `Record<string, TIssuePropertyValue[]>`
      (`TIssuePropertyValue = string | boolean | null`) + `TIssuePropertyValueErrors` (Session 7).

### Services (`apps/web/core/services`)

- [x] `apps/web/core/services/issue-type.service.ts` : CRUD types + `markAsDefault` + `enable`
      (Session 2, mirror `module.service.ts`).
- [x] `apps/web/core/services/issue-property.service.ts` (Session 7) : `fetchPropertiesAndOptions` +
      CRUD propriétés (`issue-types/<type>/properties/`) + CRUD options (`issue-properties/<id>/options/`).
- [x] `apps/web/core/services/issue-property-value.service.ts` (Session 7) : `fetch` + `upsert` (bulk) des
      valeurs par issue (`issues/<id>/property-values/`).
- [ ] `apps/web/core/services/epic.service.ts` (ou réutiliser l'issue service avec le filtre épic).

> Note : certains services sont aussi disponibles dans `packages/services/src` (variantes « sites »/public).
> Pour l'app web interne, on cible `apps/web/core/services`.

---

## 4. Stores MobX

Convention : stores injectés via `@/plane-web/store/*` → `apps/web/ce/store/*`.

- [x] `apps/web/ce/store/issue-types.store.ts` : `IssueTypesStore` (Session 2) — maps `issueTypeMap` + `projectIssueTypeIdsMap` + `fetchedMap`, getters (`getIssueTypeById`, `getProjectIssueTypeIds`,
      `getProjectIssueTypes`, `getProjectDefaultIssueTypeId`, `isIssueTypeEnabledForProject`),
      fetch + CRUD + `enableIssueTypes` (optimiste avec revert).
- [x] **Registration** — `issueTypes` branché dans `apps/web/core/store/root.store.ts` (constructeur +
      `resetOnSignOut`) + typé dans l'interface, via `@/plane-web/store/issue-types.store`.
- [x] Hook `apps/web/core/hooks/store/use-issue-types.ts` (`useIssueTypes()`).
- [x] `apps/web/ce/store/issue-properties.store.ts` (Session 7) : `IssuePropertiesStore` — maps
      `propertyMap`/`optionMap`/`projectPropertyIdsMap`/`propertyOptionIdsMap`/`fetchedMap`, getters
      (`getPropertyById`, `getProjectPropertyIds`, `getTypeProperties`, `getPropertyOptions`),
      `fetchProjectProperties` (agrégé) + CRUD props/options (optimiste avec revert). Registration
      `issueProperties` dans `root.store.ts` + hook `use-issue-properties.ts`. Valeurs par issue = via le
      service directement (transient, consommé en Session 8). Voir §20.
- [x] **Activer le store épic** (Session 5) — stubs `apps/web/ce/store/issue/epic/{issue,filter}.store.ts`
      remplacés : `ProjectEpics` passe `EIssueServiceType.EPICS` (via un param `serviceType` optionnel ajouté
      à `ProjectIssues`) ⇒ requêtes sur `/epics/`. Voir §18.

---

## 5. Frontend UI (remplacer les stubs CE)

### Types d'issues

- [ ] `issue-type-select.tsx` — dropdown de sélection du type dans la modale de création/édition
      (aujourd'hui `return <></>`). Icône + couleur via `logo_props`. Respecter la signature
      `TIssueTypeSelectProps` déjà définie.
- [ ] `issue-type-switcher.tsx` + `issue-identifier.tsx` — afficher le badge/icône du type à côté de
      l'identifiant (`PROJ-123`) dans le détail et le peek. Implémenter `IssueTypeIdentifier`.
- [ ] `issue-type-activity.tsx` — entrées d'activité lors d'un changement de type.
- [ ] `filters/issue-types.tsx` + `filters/applied-filters/issue-types.tsx` — filtre par type dans les
      layouts (aujourd'hui `null`).
- [ ] Layouts : afficher la colonne/badge type quand la display-property `issue_type` est active
      (branché via `WorkItemLayoutAdditionalProperties` ou directement).

### Propriétés personnalisées

- [x] **Settings — gestion des propriétés par type** (Session 8 P1) : `work-item-types/type-properties.tsx`
      (`WorkItemTypeProperties` + `OptionsManager` inline) — chaque type dépliable dans la page settings,
      CRUD propriétés (nom, type, required, multi) + options pour les OPTION. Vérifié live. Voir §21.
- [x] `issue-modal/provider.tsx` (Session 8 P2) — provider réel : `getActiveAdditionalPropertiesLength`,
      `handlePropertyValuesValidation` (requis), `handleCreateUpdatePropertyValues` (upsert via le value
      service, ref pour valeurs fraîches), `handleProjectEntitiesFetch`.
- [x] `issue-modal/modal-additional-properties.tsx` (Session 8 P2) — rendu **dynamique** par `property_type`
      (text/url/email/number/date/boolean/dropdown simple+multi), lié aux valeurs du contexte modale ; fetch
      des définitions + seed des valeurs existantes. **Vérifié live** : Severity=High persisté à la création.
      (Backend : `type_id` ajouté à la réponse `.values()` de create.)
- [x] `issue-details/additional-properties.tsx` (Session 8 P3) — `WorkItemAdditionalSidebarProperties` :
      rend les propriétés actives du type du work item avec leur valeur (éditable si droits), persistée
      immédiatement par propriété via le value endpoint. Fetch défs + valeurs via useSWR. **Vérifié live**
      (Severity=High affiché, édition → Low persistée). Voir §21.
- [ ] `issue-layouts/additional-properties.tsx` — valeurs custom en colonnes (spreadsheet) / badges.
- [ ] Composants de saisie réutilisables (RELATION member/issue, FILE) — actuellement TEXT/DECIMAL/BOOLEAN/
      DATETIME/URL/EMAIL/OPTION couverts ; RELATION/FILE à ajouter.

### Epics

- [x] `epics/epic-modal/modal.tsx` — `CreateUpdateEpicModal` réelle (réutilise `CreateUpdateIssueModal`
      `storeType=EPIC` + `isEpicModal`). Session 5, §18.
- [x] Page Epics — route `/epics` + `EpicLayoutRoot` (`IssuesStoreContext=EPIC`). Session 5, §18.
- [x] Nav — entrée « epics » injectée via `additionalNavigationItems` (CE `project-navigation-root.tsx`),
      gated `is_epic_enabled`. Session 5, §18.

### Réglages (settings projet)

- [ ] Ajouter **« Work Item Types »** (et **« Epics »**) à `PROJECT_FEATURES_LIST`
      (`apps/web/core/components/project/settings/features-list.tsx`) avec toggle d'activation.
- [ ] Écran de gestion des types : liste / créer / éditer / supprimer, définir le type par défaut,
      choisir icône + couleur (`logo_props`).
- [ ] Écran de gestion des propriétés d'un type : liste des propriétés, ajout (choix du `property_type`),
      configuration des options (pour les selects), `is_required`, `is_multi`.
- [ ] Routage : créer les pages sous `apps/web/app/.../settings/` en suivant le pattern des états/étiquettes.

### i18n

- [ ] Réutiliser `packages/i18n/src/locales/*/work-item-type.json` (déjà présent). Compléter les clés
      manquantes via la skill `translate` (ne pas traduire à la main les termes réservés).

---

## 6. Gating & toggles (récapitulatif)

- `Project.is_issue_type_enabled` (existe) → active types + propriétés.
- `Project.is_epic_enabled` (à créer) → active les épics.
- Exposer les deux dans le serializer projet `plane/app` + UI de settings.
- Côté front, garder les points d'insertion `@/plane-web` : on remplit les stubs, on ne touche pas `core/`.

---

## 7. Tests & vérification

- [ ] Backend : pytest via `docker-compose-test.yml` (cf. `AGENTS.md`). Cibler types, épics, propriétés,
      et **non-régression des listes d'issues** (le filtre épic est le risque n°1).
- [ ] Front : `pnpm check` (format/lint/types) + build.
- [ ] E2E manuel via `docker-compose-local.yml` : activer la feature sur un projet, créer un type,
      assigner à une issue, ajouter une propriété custom, créer une épic.
- [ ] Skills utiles : `/validate` (prettier/ts/eslint), `/verify` (bout-en-bout), `/code-review`.

---

## 8. Roadmap session par session

> Chaque session ≈ un lot cohérent et testable. Ordre pensé pour livrer de la valeur tôt et limiter les
> régressions.

- [x] **Session 0 — Fork & environnement.** ✅ `origin`→`upstream`, branche `feat/work-item-types`, `.env`
      générés + `SECRET_KEY`, `pnpm install` OK, typecheck **28/28 vert**, stack backend Docker up (API HTTP 200,
      migrations OK, tables `issue_types`/`project_issue_types` présentes). Voir §11 pour les commandes.
- [x] **Session 1 — Backend Types (B1).** ✅ Serializers + ViewSet + URLs + `type_id` dans le serializer app
  - tests. Livrable : on peut créer/lister des types via l'API interne.
- [x] **Session 2 — Data layer + store Types.** ✅ Types TS + `issue-type.service` + `IssueTypesStore` +
      hook `useIssueTypes` + registration. Typecheck 28/28, app boote sans erreur (RootStore construit). Détail §13.
- [x] **Session 3 — UI Types.** ✅ **P1 (page settings)** : onglet + route + page (activation + CRUD +
      défaut) — §14. ✅ **P2 (types sur les work items)** : `IssueTypeSelect` (dropdown modale de création),
      badge `IssueTypeIdentifier`, `getIssueTypeIdOnProjectChange` (défaut pré-sélectionné) — §15. Vérifiés
      live end-to-end. ✅ **P3 (optionnelles)** : switcher de type interactif dans le détail, toggle
      display-property `issue_type`, filtres par type (backend + composants) — §16.
- [x] **Session 4 — Backend Epics (B2).** ✅ **Foundation** : champ `Project.is_epic_enabled` (+ migration
      0122, exposé via serializer app + type TS), `DefaultEpicTypeEndpoint` (crée le type Epic `is_epic=True`
      à l'activation, idempotent) — route `/default-epic-type/`. ✅ **Endpoints + exclusion** : `EpicViewSet`
      (routes `epics/`), exclusion des épics des listes via `IssueManager` (+ manager `epic_objects`), parentage
      vérifié. 11 tests épics verts (28/28 avec les types ; non-régression contract/app OK — seuls les 8
      échecs rate-limit magic-link pré-existants restent). Détail §17.
- [x] **Session 5 — Store + UI Epics.** ✅ Stores CE réels (`ProjectEpics`/`ProjectEpicsFilter` passent
      `EIssueServiceType.EPICS`), miroir d'URLs backend `epics/` (+ sous-ressources + `v2/epics/`), page
      `/epics` (route + layout root + header + modale), nav gated `is_epic_enabled`, toggle settings. Fixé un
      500 latent (`activity.py`) et câblé la création via `/epics/`. **Vérifié live end-to-end** (toggle →
      nav → page → créer épic → détail/activité → exclusion des listes). Détail §18.
- [x] **Session 6 — Backend Propriétés (B3).** ✅ 3 modèles (schéma EE-compat, colonnes typées) + migration
      0123 + serializers + viewsets/URLs (CRUD props/options, valeurs bulk upsert typé, endpoint agrégé) +
      validation (requis/multi/coercition). **12/12 tests** ; non-régression contract/app OK. Vérifié live
      (props/options/valeurs multi + agrégé + cascade) sur le projet WIT. Détail §19.
- [x] **Session 7 — Data layer + stores Propriétés.** ✅ Types TS (`issue-property.ts` + `TIssuePropertyValues`
      structuré), services (`issue-property.service`, `issue-property-value.service`), store
      `IssuePropertiesStore` + registration + hook `useIssueProperties`. `pnpm check:types` **28/28**, app boote
      (RootStore construit), endpoint agrégé consommable. Détail §20.
- [~] **Session 8 — UI Propriétés.** ✅ **P1** settings (gestion props + options), ✅ **P2** modale (rendu
  dynamique + sauvegarde), ✅ **P3** sidebar détail (voir/éditer). Custom properties **utilisables de bout en
  bout** (définir → saisir à la création → voir/éditer sur l'existant). Tous **vérifiés live**. ⏳ **Reste** :
  colonnes **layouts**, types RELATION/FILE, i18n. Détail §21.
- [x] **Session 9 — Polish & tests.** ✅ Backend polish (`default_value` à la création + valeurs inline dans
      `IssueViewSet.create` + endpoint `epics-detail/`), ✅ colonnes de propriétés custom dans le **spreadsheet**
      (lecture seule, niveau projet), ✅ types **RELATION** (member/issue) **et FILE** (lien) dans modale +
      sidebar + création dans les settings, ✅ **i18n** des libellés (namespace `...properties.ce`, 19 locales
      100% sync). Non-régression : 115 tests contract/app (8 rate-limit pré-existants), check:types 28/28, lint web
      0 erreur. Détail §22.
- [x] **Post-S9 — améliorations & correctifs.** ✅ Filtre par type dans la vue principale (rich-filters) ; ✅ fix bug
      d'hydratation qui cassait la barre de filtres en dev ; ✅ spreadsheet batch-fetch + édition inline (fin du N+1) ;
      ✅ FILE = vrai upload (pipeline d'assets MinIO/Scaleway). 121 tests contract/app. Récap §23, backlog §23.
- [ ] **Session 10 — Liaison GitHub (PR ↔ work items).** Voir §24 (prépa) — à lancer en contexte vierge.

---

## 9. Risques & points d'attention

- **Filtrage des épics** : oublier d'exclure `is_epic=True` d'une liste d'issues = épics qui polluent les
  vues normales. Auditer exhaustivement (Session 4). Risque de régression n°1.
- **Rebase sur upstream** : ne jamais éditer les migrations existantes ; toujours de nouvelles migrations.
  Garder les changements concentrés dans `apps/api/plane/app/...`, `apps/web/ce/...`, `packages/...`.
- **`ProjectIssueType` non exporté** aujourd'hui dans `db/models/__init__.py` — à corriger.
- **Schéma des propriétés** : décision structurante (colonnes typées vs JSON, compat schéma EE). À trancher
  en début de Session 6.
- **Exposition `type_id` app** : vérifier tous les consommateurs (list/detail/draft/search) pour éviter les
  `null` inattendus.
- **Cohérence EE** : on remplit les stubs `ce/`, donc si un jour on rebase sur une version où Plane change
  la signature des stubs, il faudra réaligner nos implémentations.

---

## 10. Décisions ouvertes (à figer avant Session 1)

1. Where to host the fork (remote GitHub perso/org) — sinon rester en local.
2. Schéma des propriétés : colonnes typées vs `value` JSON unique.
3. Compat schéma EE d'origine (noms de tables/champs) : oui/non.
4. Seed du type par défaut : migration data globale vs création à l'activation.
5. Portée des types : workspace-level (actuel) confirmé ?

---

## 11. Environnement local (rappel des commandes)

Setup one-shot (déjà fait en Session 0) : `.env` copiés depuis `.env.example` pour root + web/api/space/admin/live,
`SECRET_KEY` Django ajouté dans `apps/api/.env`, `pnpm install`. (Le `./setup.sh` fait tout ça mais relance
aussi `pnpm install`.)

**Backend** (Postgres, Redis/Valkey, RabbitMQ, MinIO, Django API + workers + migrator) :

```bash
docker compose -f docker-compose-local.yml up -d --build     # démarrer
docker compose -f docker-compose-local.yml logs -f api        # logs API
docker compose -f docker-compose-local.yml down               # arrêter (garde les volumes)
```

- API sur http://localhost:8000 — Postgres exposé sur `:5432` (user/db : `plane`/`plane`).
- Accès DB : `docker compose -f docker-compose-local.yml exec plane-db psql -U plane -d plane`.

**Frontend** (web:3000, admin:3001) :

```bash
pnpm dev
```

**Checks avant commit** :

```bash
pnpm check:types      # TypeScript (référence : 28/28 vert)
pnpm check            # format + lint + types
```

**Tests backend** (stack isolée) : voir `AGENTS.md` / `docker-compose-test.yml`.

> Note env : Node 24 installé, projet ciblé sur Node 22.18 (compatible). Le hook de sécurité local bloque
> les accents dans les commandes shell → messages de commit en ASCII.

---

## 12. Session 1 — Backend Work Item Types (livré)

**Endpoints (API interne `plane/app`)** — tous scoping workspace + projet, permissions type `State` :

| Méthode | Route                                                       | Rôle    | Effet                                                          |
| ------- | ----------------------------------------------------------- | ------- | -------------------------------------------------------------- |
| GET     | `/api/workspaces/<slug>/projects/<project_id>/issue-types/` | member+ | liste les types (exclut les épics)                             |
| POST    | idem                                                        | admin   | crée un type + l'associe au projet                             |
| GET     | `/api/.../issue-types/<pk>/`                                | member+ | détail                                                         |
| PATCH   | `/api/.../issue-types/<pk>/`                                | admin   | modifie                                                        |
| DELETE  | `/api/.../issue-types/<pk>/`                                | admin   | supprime (interdit sur le défaut ; détache les work items)     |
| POST    | `/api/.../issue-types/<pk>/mark-default/`                   | admin   | définit le type par défaut                                     |
| POST    | `/api/.../default-issue-type/`                              | admin   | crée le type par défaut à l'activation + backfill (idempotent) |

**Fichiers créés** : `serializers/issue_type.py`, `views/issue_type/base.py`, `urls/issue_type.py`,
`tests/contract/app/test_issue_type_app.py`.
**Fichiers modifiés** : `serializers/__init__.py`, `serializers/issue.py` (+`type_id`), `views/__init__.py`,
`urls/__init__.py`, `db/models/__init__.py` (+`ProjectIssueType`).

**Vérification** : Django `check` OK · routing 401 comme `states` · smoke-test ORM 13/13 ·
pytest `test_issue_type_app.py` **14/14** · non-régression `contract/app` : 85 passés, les 8 échecs
sont pré-existants (rate-limit 429 sur les magic-links `test_authentication.py`, reproduits sur base clean).

**À noter pour la suite** : `is_issue_type_enabled` (toggle projet) est déjà writable via le
`ProjectSerializer` (`fields="__all__"`) ; le front pourra donc l'activer sans changement backend
supplémentaire. Le type d'épic (`is_epic=True`) reste géré en Session 4 (non créable via cet endpoint).

---

## 13. Session 2 — Data layer + store Types (livré)

**Fichiers créés** :

- `packages/types/src/issues/issue-type.ts` — `TIssueType`, `TProjectIssueType` (exportés dans l'index).
- `apps/web/core/services/issue-type.service.ts` — `IssueTypeService` (fetchAll, retrieve, create, update,
  remove, markAsDefault, enable).
- `apps/web/ce/store/issue-types.store.ts` — `IssueTypesStore` (MobX, injecté via `@/plane-web/store`).
- `apps/web/core/hooks/store/use-issue-types.ts` — hook `useIssueTypes()`.

**Fichiers modifiés** : `packages/types/src/index.ts` (export), `packages/types/src/project/projects.ts`
(+`is_issue_type_enabled?`), `apps/web/core/store/root.store.ts` (déclaration + instanciation dans les
deux constructeurs).

**API du store** (à consommer en Session 3) :
`fetchProjectIssueTypes(slug, projectId)` · `getProjectIssueTypes(projectId, activeOnly?)` ·
`getProjectIssueTypeIds(projectId)` · `getIssueTypeById(id)` · `getProjectDefaultIssueTypeId(projectId)` ·
`isIssueTypeEnabledForProject(projectId)` · `enableIssueTypes` · `createType` · `updateType` ·
`deleteType` · `markAsDefault`. CRUD optimiste avec revert sur erreur.

**Vérification** : `pnpm check:types` **28/28** · app démarrée (`pnpm --filter web dev`, :3001) et rendue
avec succès via Chrome DevTools (écran instance setup) → `new RootStore()` incluant `IssueTypesStore`
construit sans erreur. Restent des warnings d'hydratation pré-existants (`next-themes`/`LogoSpinner` dans
`root.tsx`), hors périmètre. Vérif fonctionnelle live (créer un type dans l'UI) → Session 3.

---

## 14. Session 3 (partie 1) — Page de settings Work Item Types (livré)

**Fichiers créés** :

- Route : `apps/web/app/(all)/[workspaceSlug]/(settings)/settings/projects/[projectId]/work-item-types/{page,header}.tsx`
- UI : `apps/web/core/components/work-item-types/{settings-root,create-update-modal,delete-modal,index}.tsx`

**Fichiers modifiés** : `apps/web/app/routes/core.ts` (route), `packages/types/src/settings.ts`
(+`work_item_types`), `packages/constants/src/settings/project.ts` (`PROJECT_SETTINGS` + groupe
WORK_STRUCTURE), `apps/web/core/components/settings/project/sidebar/item-icon.tsx` (icône `ListTodo`).

**Décisions** : toggle d'activation **dans la page** (pas dans `PROJECT_FEATURES_LIST`) pour éviter une
collision de clé i18n (`work_item_types` est un namespace). i18n : réutilise `work_item_types.label`.

**Vérifié en live (Chrome DevTools, :3001)** — env de test (`admin@plane.local`, workspace `test-ws`,
projet WIT) : onglet visible sous « Work Structure » · activation → crée le type par défaut « Task » +
backfill · création « Bug » (toast succès) · suppression du défaut désactivée. Aucune erreur console
imputable à la feature.

**Reste (Session 3 partie 2)** : `issue-type-select` (dropdown modale de création → `type_id`),
`getIssueTypeIdOnProjectChange` (provider CE), badge `IssueTypeIdentifier` / `IssueTypeSwitcher`, filtres.

**Env de test** : stack backend Docker + `pnpm --filter web dev` (port **3001** ; le 3000 est un autre
process). Compte : `admin@plane.local` / `Testpass123!`.

---

## 15. Session 3 (partie 2) — Types sur les work items (livré)

**Fichiers (stubs CE remplacés / modifiés)** :

- `apps/web/ce/components/issues/issue-modal/issue-type-select.tsx` — `IssueTypeSelect` réel : dropdown
  (`CustomSearchSelect`) des types actifs du projet, câblé sur le champ `type_id` du formulaire ; ne rend
  rien si la feature est off ou aucun type. Fetch paresseux des types.
- `apps/web/ce/components/issues/issue-modal/provider.tsx` — `getIssueTypeIdOnProjectChange` renvoie le
  type par défaut du projet (valeur du contexte mémoïsée pour satisfaire le lint).
- `apps/web/ce/components/issues/issue-details/issue-identifier.tsx` — `IssueTypeIdentifier` réel (icône
  `Logo` du type) + branché dans `IssueIdentifier` (affiché si `displayProperties.issue_type`), avec
  fetch paresseux des types (garde `fetchedMap`).

**Bug corrigé** 🐛 : `IssueTypesStore.getProjectIssueTypes(projectId, activeOnly?)` était en `computedFn` —
mobx-utils `DeepMap` exige un **nombre d'arguments constant** ⇒ crash « expected: 2, got: 1 » quand appelé
avec 1 puis 2 args. Passé en fonction simple (réactivité conservée via `getProjectIssueTypeIds`/`issueTypeMap`).

**Vérifié en live (Chrome DevTools)** : modale de création → dropdown liste **Task/Bug** · sélection « Bug »

- création → **WIT-1** créée, `type_id` = Bug **confirmé en base** · icône 🐛 posée sur le type Bug → badge
  visible sur la **page de détail**. Aucune erreur console imputable à la feature.

**Notes** : le badge sur les layouts liste/spreadsheet dépend de la display-property `issue_type`.

---

## 16. Session 3 (partie 3) — Optionnelles (livré)

- **Switcher de type interactif** — `apps/web/ce/components/issues/issue-details/issue-type-switcher.tsx` :
  dropdown (`CustomSearchSelect`) qui change le type d'une issue existante via `updateIssue`, fallback sur
  l'identifiant simple si feature off / read-only. **Vérifié live** : Bug→Task changé depuis le détail,
  confirmé en base.
- **Display-property `issue_type`** — ajouté à `ISSUE_DISPLAY_PROPERTIES` (`packages/constants/src/issue/common.ts`)
  ⇒ toggle « Work item Types » dans le menu Display pour montrer/cacher le badge sur les layouts. (Au passage,
  suppression d'un warning oxlint pré-existant `no-duplicate-enum-values` sur `project`/`team_project`.)
- **Filtres par type** :
  - Backend : `filter_issue_type` dans `apps/api/plane/utils/issue_filters.py` (+ dispatch `"issue_type"`) →
    `type__in` / `type__isnull`. **Vérifié** (le filtre renvoie bien les issues du type).
  - Frontend : `FilterIssueTypes` (sélection) + `AppliedIssueTypeFilters` (chip) implémentés depuis le store ;
    **wirés dans le widget sub-issues** (déjà consommateur + `issue_type` dans ses filtres dispo).

**⏳ Reste (follow-up dédié)** : brancher le filtre par type dans le **filtre principal des work items**, qui
utilise le système typé **rich-filters** (`packages/utils/src/work-item-filters/configs/filters/*`,
`apps/web/core/hooks/work-item-filters/use-work-item-filters-config.tsx`). Il faut : étendre
`TWorkItemFilterProperty`, créer une config `work-item-type.ts` (mirror de `state.ts`), l'enregistrer dans le
hook (gate `allowedFilters`), et mapper la clé rich-filter vers le param API `issue_type`. Chantier typé
multi-fichiers → mérite sa propre session.

---

## 17. Session 4 — Backend Epics (endpoints + exclusion) (livré)

**Décision d'architecture clé** — l'exclusion des épics des listes normales est faite **au niveau du
manager**, pas par un audit vue-par-vue :

- `IssueManager.get_queryset()` (`Issue.issue_objects`) ajoute `.filter(Q(type__isnull=True) | Q(type__is_epic=False))`.
  Toutes les vraies listes de work items passent déjà par `issue_objects` (`issue/base`, cycle, module, view,
  paginated `v2/issues`, search, sub-issues) ⇒ épics exclus **partout, automatiquement**. C'est la parade au
  risque n°1 du plan (oublier une vue).
- ⚠️ **Piège Django NULL** évité : `.exclude(type__is_epic=True)` droppe les issues sans type
  (`NOT (NULL = True)` = NULL = falsy). On utilise l'OR explicite (même pattern que `archive.py`).
- Nouveau manager symétrique `Issue.epic_objects` = mirror d'`IssueManager` mais `.filter(type__is_epic=True)`.
  Aucune migration requise (managers non `use_in_migrations`).

**Endpoints (API interne `plane/app`)** — `EpicViewSet` sous-classe `IssueViewSet`, réutilise toute la
machinerie (grouping, annotations, activités, `partial_update`, `destroy`) :

| Méthode   | Route                           | Effet                                             |
| --------- | ------------------------------- | ------------------------------------------------- |
| GET       | `/api/.../projects/<id>/epics/` | liste les épics (`epic_objects`)                  |
| POST      | idem                            | crée un épic (force le type épic ; 400 si absent) |
| GET       | `/api/.../epics/<pk>/`          | détail                                            |
| PUT/PATCH | `/api/.../epics/<pk>/`          | modifie                                           |
| DELETE    | `/api/.../epics/<pk>/`          | supprime                                          |

- `EpicViewSet.create` force `type_id` = type épic du projet (ignore ce que le client envoie) ; renvoie 400
  si les épics ne sont pas activés (aucun type épic). Appel `super().create(request, slug=..., project_id=...)`
  en **kwargs** (le décorateur `allow_permission` lit `kwargs["slug"]`).
- `get_queryset` scope sur `Issue.epic_objects` ⇒ `list`/`partial_update` restreints aux épics.

**Parentage épic → work items** : via le FK `Issue.parent` existant. Un épic parente des work items normaux
(qui restent dans `issue_objects`) ; l'épic lui-même reste hors des listes. Vérifié par test.

**Fichiers créés** : `apps/api/plane/app/views/issue/epic.py` (`EpicViewSet`),
`apps/api/plane/tests/contract/app/test_epic_app.py` (11 cas).
**Fichiers modifiés** : `apps/api/plane/db/models/issue.py` (`IssueManager` + nouveau `EpicManager` +
`epic_objects`), `apps/api/plane/app/views/__init__.py` (export), `apps/api/plane/app/urls/issue.py` (routes).

**Vérification** : `manage.py check` OK · `makemigrations --check` → _No changes detected_ · routing épics
401 non-auth · smoke ORM (managers partitionnent épics/issues, 0 fuite) · pytest `test_epic_app.py` **11/11** ·
non-régression `contract/app` : 99 passés, seuls les 8 échecs rate-limit magic-link **pré-existants** restent.

**Reste (Session 5)** : store épic réel (remplacer les stubs `ce/store/issue/epic/*`), page `/epics`, nav
(gate `is_epic_enabled`), modale de création.

---

## 18. Session 5 — Store + UI Epics (livré)

**Découverte clé** : l'essentiel de l'infra épic était déjà câblée dans `core/` (slots `projectEpics`/
`projectEpicsFilter`/`epicDetail` dans `root.store`, `useIssues(EPIC)`, `useIssuesActions(EPIC)`,
`HeaderFilters storeType=EPIC`, service `IssueService(EPICS)` → path `/epics/`). Les stubs CE ne
passaient simplement pas le service type.

**Stores (CE, stubs remplacés)** :

- `apps/web/ce/store/issue/epic/issue.store.ts` — `ProjectEpics` passe `EIssueServiceType.EPICS` à
  `ProjectIssues` ⇒ toutes les requêtes vont sur `/epics/`.
- `apps/web/ce/store/issue/epic/filter.store.ts` — `ProjectEpicsFilter` (nettoyage « will never be used »).
- `apps/web/core/store/issue/project/issue.store.ts` — `ProjectIssues` accepte un 3ᵉ param `serviceType`
  optionnel (défaut `ISSUES`, rétrocompatible) transmis à `BaseIssuesStore`.

**Backend — miroir d'URLs `epics/`** (`apps/api/plane/app/urls/issue.py`) : la plupart des sous-ressources
sont clés par pk ⇒ réutilisent les viewsets issue existants (history, comments, reactions, subscribe,
issue-relation, archive, meta, links `epics/<id>/links/`, sub-issues `epics/<id>/issues/`, attachments v2).
Nouveau `EpicPaginatedViewSet` (`v2/epics/`, scopé `epic_objects`) pour le fetch de sync.

- 🐛 **Bug latent corrigé** (`apps/api/plane/app/views/issue/activity.py`) : le fall-through de
  `IssueActivityEndpoint` triait des **instances de modèle** par `instance["created_at"]` ⇒ 500 « not
  subscriptable ». Jamais atteint par les issues (qui passent toujours `activity_type=issue-*`), mais
  atteint par les épics (`getIssueActivities` appelle `/history/` **sans** param). Fix : accepter les
  variantes `epic-property`/`epic-comment` **et** sérialiser avant de trier (corrige aussi le cas issue nu).

**Frontend — page & UI** :

- Route `/epics` enregistrée (`apps/web/app/routes/core.ts`) + fichiers
  `.../[projectId]/epics/(list)/{page,layout,header,mobile-header}.tsx`.
- `apps/web/core/components/epics/layout-root.tsx` — `EpicLayoutRoot` (miroir de `ProjectLayoutRoot` sous
  `IssuesStoreContext.Provider value={EPIC}` ⇒ tous les layouts enfants lisent le store épic).
- `apps/web/ce/components/epics/epic-modal/modal.tsx` — `CreateUpdateEpicModal` réelle : réutilise
  `CreateUpdateIssueModal` avec `storeType=EPIC` + `isEpicModal`. Nouveau flag `isEpicModal` dans
  `IssuesModalProps` : le modal base ne rabat plus EPIC→PROJECT quand il est set ⇒ création via `/epics/`
  (le backend force le type épic). `withDraftIssueWrapper={false}`.
- `apps/web/ce/components/sidebar/project-navigation-root.tsx` — injecte l'onglet « Epics »
  (`additionalNavigationItems`, `sortOrder 1.5`, `LayersIcon`), gated `project.is_epic_enabled`.
- `apps/web/core/components/work-item-types/settings-root.tsx` — toggle « Enable epics » (met
  `is_epic_enabled` + appelle `default-epic-type/` via `enableEpics`). Service `enableEpics` +
  store `enableEpics` ajoutés. `ISSUE_STORE_TO_FILTERS_MAP[EPIC]` = config issues.

**Vérification** : `pnpm check:types` **28/28** · Django `check` OK · `makemigrations --check` clean ·
tests `test_epic_app.py` **11/11**, `test_issue_type_app.py` 17/17, contract/app 99 passés (8 rate-limit
pré-existants) · **live (Chrome DevTools, :3001)** : toggle épics ON (`is_epic_enabled=true` persisté) →
onglet nav « Epics » visible → page `/epics` rendue → « Add Epic » → modale → épic **WIT-3** créé via
`/epics/` (type épic forcé) → visible dans la liste épics, **absent** des work items → détail/peek complet
(propriétés, sous-work-items, relations, liens, commentaires, **Activity**). Aucune erreur console
imputable à la feature (restent les warnings hydration/refs pré-existants).

**⏳ Reste (follow-up)** : endpoint `epics-detail/` (seulement layout GANTT/spreadsheet avec
`expand=issue_relation`, 404 non fatal) ; filtres rich-filter par type (déjà noté §16) ; épic detail comme
**page** dédiée (aujourd'hui via peek/detail générique).

---

## 19. Session 6 — Backend Custom Properties (livré)

**Décision de schéma** (§10 #2/#3) : schéma **EE-compat** avec **colonnes de valeur typées**. Tables
`issue_properties`, `issue_property_options`, `issue_property_values`.

**Modèles** (`db/models/issue_property.py`, tous `ProjectBaseModel` → project+workspace auto) :

- `IssueProperty` : `issue_type` FK, `name`, `display_name`, `description`, `logo_props`, `property_type`
  (`PropertyTypeEnum` : TEXT/DECIMAL/OPTION/BOOLEAN/DATETIME/RELATION/URL/EMAIL/FILE), `relation_type`
  (`RelationTypeEnum` ISSUE/MEMBER), `is_required`, `is_multi`, `is_active`, `default_value`, `settings`,
  `sort_order`, `external_*`.
- `IssuePropertyOption` : `property` FK, `name`, `description`, `logo_props`, `is_active`, `is_default`,
  `sort_order`, `parent` (self FK). Unique `(property, name)` quand `deleted_at` null.
- `IssuePropertyValue` : `issue` FK, `property` FK, colonnes typées `value_text`/`value_boolean`/
  `value_decimal`/`value_datetime`/`value_uuid` + `value_option` FK. **1 ligne = 1 valeur** (multi-valeur =
  plusieurs lignes ⇒ pas d'unicité `issue+property`).

**Endpoints** (`views/issue_property/base.py`, `urls/issue_property.py`) :

- `GET/POST /issue-types/<type_id>/properties/[<pk>/]` — CRUD définitions (member+ lit, ADMIN écrit).
- `GET/POST /issue-properties/<property_id>/options/[<pk>/]` — CRUD options.
- `GET /issue-property-types/` — **agrégé** : toutes les props du projet + options imbriquées (fetch-key front).
- `GET/POST /issues/<issue_id>/property-values/` — lit / **bulk upsert typé** `{ property_id: [values] }`.

Le bulk upsert **valide tout avant** d'écrire (requis, non-multi ≤ 1, coercition typée → 400 si invalide),
puis remplace transactionnellement (hard-delete + `bulk_create`). Piège évité : ne pas appeler la méthode
`get` décorée depuis `post` (le décorateur lit `kwargs["slug"]` → KeyError → 400) ⇒ extrait dans
`_serialize_values`.

**Vérification** : `manage.py check` OK, migration 0123 appliquée (3 tables), routing 401,
pytest `test_issue_property_app.py` **12/12**, non-régression contract/app (111 passés, 8 rate-limit
pré-existants). **Live (WIT)** : prop OPTION multi + 2 options → agrégé OK → POST valeurs multi 200 + relu →
DELETE 204 cascade.

**Reste (follow-ups)** : intégration inline des valeurs dans `IssueViewSet.create/update` (le front appelle
`property-values/` après create) ; filtrage/tri par valeur ; `default_value` appliqué à la création
(Sessions 7/8/9).

---

## 20. Session 7 — Data layer + stores Propriétés (livré)

**Types** (`packages/types/src/issues/`) : `issue-property.ts` — `EIssuePropertyType` (9 types),
`EIssuePropertyRelationType` (ISSUE/MEMBER), `TIssueProperty`, `TIssuePropertyOption`,
`TIssuePropertySettings`, `TIssuePropertyWithOptions`. `issue-property-values.ts` structuré :
`TIssuePropertyValue = string | boolean | null`, `TIssuePropertyValues = Record<string, TIssuePropertyValue[]>`.
Exportés dans l'index.

**Services** (`apps/web/core/services/`) : `issue-property.service.ts` (`fetchPropertiesAndOptions`, CRUD
propriétés scopées type, CRUD options scopées propriété) ; `issue-property-value.service.ts` (`fetch` +
`upsert` bulk). Alignés sur les endpoints backend §19.

**Store** (`apps/web/ce/store/issue-properties.store.ts`) : `IssuePropertiesStore` — observables
`propertyMap`/`optionMap`/`projectPropertyIdsMap`/`propertyOptionIdsMap`/`fetchedMap` ; getters
`getPropertyById`/`getProjectPropertyIds`/`getTypeProperties`/`getPropertyOptions` ; `fetchProjectProperties`
(endpoint agrégé) + CRUD props/options optimiste avec revert. Registration `issueProperties` dans
`root.store.ts` (2 constructeurs + interface) ; hook `use-issue-properties.ts`.

**Choix** : les **valeurs par issue** (transient) ne passent pas par le store — lues/écrites via
`IssuePropertyValueService` directement dans le provider de la modale (Session 8).

**Vérification** : `pnpm check:types` **28/28**, oxlint 0 warning, app rendue (RootStore construit avec
`IssuePropertiesStore`), endpoint agrégé consommé (200) via la session navigateur.

---

## 21. Session 8 — UI Propriétés (P1 settings + P2 modale) (livré)

**P1 — Gestion des propriétés dans les settings** (`work-item-types/type-properties.tsx`) : chaque type de la
page Work Item Types est **dépliable** (chevron) et affiche `WorkItemTypeProperties` — liste des propriétés
custom (badge type + Required/Multi), ajout inline (nom → slug auto, type parmi Text/Number/Boolean/Date/URL/
Email/Dropdown, toggles Required/Multi), suppression, et `OptionsManager` inline pour les propriétés OPTION
(ajout/suppression d'options). Consomme `IssuePropertiesStore` (`fetchProjectProperties` au montage + CRUD).
`settings-root.tsx` : état `expandedTypeId` + fetch des propriétés à l'activation. **Vérifié live** : prop
OPTION « Severity » + options High/Low créées via l'UI, persistées.

**P2 — Rendu + sauvegarde dans la modale** :

- `issue-modal/provider.tsx` (CE) : provider réel. `getActiveAdditionalPropertiesLength` (compte les props
  actives du type courant via `watch("type_id")`), `handlePropertyValuesValidation` (requis → errors),
  `handleCreateUpdatePropertyValues` (bulk upsert via `IssuePropertyValueService`), `handleProjectEntitiesFetch`.
  Les valeurs courantes sont gardées dans un **ref** pour que les handlers impératifs ne lisent jamais un état
  périmé.
- `issue-modal/modal-additional-properties.tsx` (CE) : lit `type_id` via `useFormContext`, rend un champ par
  propriété active selon `property_type` (text/url/email/number/date/boolean/dropdown simple+multi), lié aux
  valeurs du contexte modale. `useSWR` pour charger les définitions du projet et **seed** les valeurs
  existantes (édition).
- Backend : `type_id` ajouté à la réponse `.values()` de `IssueViewSet.create` (le front en a besoin pour
  scoper les valeurs à persister).

**Vérifié live (WIT)** : ouverture de la modale de création → le champ **Severity** (dropdown High/Low)
apparaît sous le type Task → sélection « High » → création → **valeur persistée** (`property-values/` renvoie
l'option) et relue. `check:types` 28/28, oxlint clean, django check OK.

**P3 — Sidebar du détail** (`issue-details/additional-properties.tsx`) : `WorkItemAdditionalSidebarProperties`
reçoit `workItemTypeId` en prop (pas besoin du form context). Rend chaque propriété active du type avec sa
valeur, éditable si `isEditable`, **persistée immédiatement par propriété** via le value endpoint (upsert
`{ [propId]: [value] }`). Fetch défs + valeurs via useSWR. **Vérifié live** : Severity=High affiché sur un
work item, édition → Low persistée et relue.

**⏳ Reste (Session 8 suite / 9)** : colonnes/badges dans les layouts (spreadsheet) ; types RELATION (member/
issue) et FILE ; i18n des libellés ; `default_value` appliqué à la création ; intégration inline des valeurs
dans `IssueViewSet.create` (aujourd'hui appel séparé `property-values/` après create).

---

## 22. Session 9 — Polish & tests (livré)

**A. Backend polish** (`issue_property/base.py` + `issue/base.py`) :

- Helpers réutilisables extraits dans `issue_property/base.py` : `default_values_payload(type_id)` (défauts
  d'un type — options `is_default` pour OPTION, `default_value` sinon), `build_property_values(project,
issue_id, payload, enforce_required)` (validation + construction des lignes), `persist_property_values`
  (hard-replace transactionnel), `write_property_values_for_issue(project, issue, inline_payload,
apply_defaults, enforce_required)`. `IssuePropertyValueEndpoint.post` refactoré pour les réutiliser (comportement
  strict inchangé : `enforce_required=True`).
- `IssueViewSet.create` : après `serializer.save()`, appel best-effort (jamais bloquant, `enforce_required=False`)
  qui **applique les défauts du type** puis **écrase avec les valeurs inline** envoyées sous `property_values`
  dans le payload de création. Import local pour éviter tout cycle.
- **`default_value` visible dans la modale** : `modal-additional-properties.tsx` seed les champs à la sélection du
  type (create only, `useEffect` sur `propertyIdsKey`/`typeId`) via `getPropertyDefaultValue` — les défauts
  s'affichent et transitent par le flux d'upsert existant (donc pas écrasés par l'appel séparé qui envoie `[]`
  pour les props non touchées).
- Endpoint **`epics-detail/`** ajouté (`urls/issue.py`) → `IssueDetailEndpoint` (name `project-epic-detail`),
  miroir de `issues-detail/` ; corrige le 404 non fatal du GANTT épics. Vérifié : `resolve()` → `IssueDetailEndpoint`.
- 4 nouveaux tests (`test_issue_property_app.py::TestIssueCreateWithPropertyValues`) : backfill TEXT, backfill
  option `is_default`, inline override du défaut, pas de valeurs sans type. **16 tests props verts** ; suite
  contract/app **115 passés** (8 rate-limit magic-link pré-existants).

**B. Colonnes spreadsheet** (`issue-layouts/spreadsheet/custom-property-columns.tsx`, nouveau) :

- Composant autonome, **niveau projet** (skip si vue workspace/pas de `projectId` param). `SpreadsheetCustomPropertyHeaders`
  (th par propriété active du projet) + `SpreadsheetCustomPropertyValueCells` (td par propriété).
  Hook `useProjectCustomProperties` : fetch défs + tri stable (`sort_order` puis `id`) pour que header et cellules
  rendent le même jeu de colonnes. **[MàJ post-S9]** valeurs récupérées en **un seul fetch batch** (endpoint
  `property-values/` projet, `fetchBulkValues` → cache `valuesByIssue` dans le store) au lieu du N+1 par ligne ; et
  cellules **éditables inline** (commit via upsert + maj optimiste du store) sauf RELATION (lecture seule, éditée
  dans modale/sidebar). Rendu par type (bool toggle, option→select, date/number/text/url inputs).
- Injecté : `<SpreadsheetCustomPropertyHeaders/>` en fin de `<tr>` du header, `<SpreadsheetCustomPropertyValueCells/>`
  en fin de `IssueRowDetails` (après le map `IssueColumn`). Registry keyé `IIssueDisplayProperties` **contourné**
  (colonnes en fin de ligne, hors `WithDisplayPropertiesHOC`).

**C. Types RELATION & FILE** :

- Composant partagé `ce/components/issues/property-fields/relation-field.tsx` (`PropertyRelationField`) : MEMBER →
  `MemberDropdown` (single/multi selon `is_multi`, résout les noms) ; ISSUE → `ExistingIssuesListModal` + chips
  (label capturé depuis la sélection). Rendu dans la modale (`PropertyField`) et la sidebar (`SidebarPropertyField`),
  qui reçoivent désormais `projectId`/`workspaceSlug`.
- **FILE** = **vrai upload** (post-S9, livré). Réutilise le pipeline d'assets projet de Plane (S3/MinIO en dev,
  Scaleway en prod par config) : composant partagé `property-fields/file-field.tsx` (`FilePropertyField`) → upload via
  `fileService.uploadProjectAsset({entity_type: ISSUE_PROPERTY_VALUE})` → stocke `{id,name}` JSON dans `value_text` →
  lien de download (endpoint GET projet, 302 vers URL présignée). Backend : type `ISSUE_PROPERTY_VALUE` ajouté à
  `EntityTypeContext` (asset.py, pas de migration) + MIME élargis aux `ATTACHMENT_MIME_TYPES` pour ce type dans
  `ProjectAssetEndpoint.post` (asset/v2.py) ; enum TS `EFileAssetType`. Câblé modale + sidebar + spreadsheet. **Vérifié
  live E2E** (presign 200 → upload MinIO 204 → confirm 204 → download 302 ; champ rendu dans le spreadsheet).
- Settings (`type-properties.tsx`) : options **Relation** et **File** ajoutées + sélecteur member/issue (envoie
  `relation_type` au create, `null` sinon).

**D. i18n** : namespace dédié `work_item_types.settings.properties.ce.*` (28 leaves : labels de type, required/multi,
placeholders, relation, valeurs bool, erreurs). `t()` câblé dans les 5 composants (settings, modale, sidebar,
relation-field, spreadsheet) + réutilisation `common.error`/`common.cancel`. Traduit dans **les 18 autres locales**
(règles DNT respectées : `URL` et `https://…` verbatim ; « Work item »/« Boolean »/« Multi » traduits). `sync:check`
**19 locales à 100%**, `generate:types` OK (3865 clés).

**Vérifié** : `check:types` **28/28**, lint web **0 erreur** (978 warnings < budget 11957), format oxfmt clean,
django check OK, contract/app 115 passés, `epics-detail/` résout. **Work Item Types + Epics + Custom Properties =
complets et polis.**

**E. Filtre par type dans la vue principale (rich-filters)** — chantier §16 « reste » repris :

- Backend : filtre `issue_type`/`issue_type__in` ajouté à `IssueFilterSet` (`utils/filters/filterset.py`, mappé sur
  `Issue.type` → `type_id`). `ComplexFilterBackend._validate_fields` n'accepte que les clés déclarées → sans cet
  ajout la condition `issue_type__in` renverrait un 400. `IssueViewSet.list` passe déjà par ce backend. Test unitaire
  `TestIssueTypeFilter` (17 tests props verts).
- Frontend rich-filters : clé `issue_type` ajoutée à `WORK_ITEM_FILTER_PROPERTY_KEYS` (`types/view-props.ts`) ;
  config `getWorkItemTypeFilterConfig` (`utils/.../filters/work-item-type.ts`, miroir de `state.ts`, options =
  `TIssueType`, valeur = id) + export barrel ; enregistrée dans `use-work-item-filters-config.tsx` (memo
  `workItemTypes`, config gatée `is_issue_type_enabled && workItemTypes !== undefined`, ajout à `configs`/`configMap`,
  icône `Layers` + `Logo` par option) ; `issue_type` ajouté à l'allow-list `ISSUE_DISPLAY_FILTERS_BY_PAGE.issues` ;
  `issueTypeIds` injecté par `project-level.tsx` (+ **fetch des types au montage** pour que le filtre soit dispo, à
  l'image du filtre legacy). Pas de mapping API à écrire : le rich-filter sérialise `issue_type__in` dans le blob JSON
  `filters` que le backend lit directement.
- **Vérifié live end-to-end** (Chrome DevTools, `pnpm dev`) : le filtre **« Work item type »** apparaît dans le
  dropdown d'ajout de filtre (aux côtés de State/Priority/…), sous-menu Task/Bug ; sélection **Bug → 0** résultat
  (« No matching results »), **Task → 3** (WIT-6/5/1). Côté API : `?filters={"issue_type__in":[TaskId]}` → 3,
  `[BugId]` → 0, statut 200. `check:types` 28/28, lint 0 erreur.
- ✅ **Bug pré-existant corrigé** (`fix(web)`) : en `dev`, un hard reload cassait toute la barre de filtres. Deux
  causes chaînées : (1) `HydrateFallback` (`app/root.tsx`) rendait un markup **theme-dependent** différent du
  document prérendu (SPA mode `ssr:false`) → mismatch → hydratation avortée → bascule CSR ; (2) combiné au double-
  invoke **StrictMode**, l'enregistrement de l'instance de filtre en **phase de render** (`useMemo` dans
  `filters-hoc/base.tsx` `WorkItemFilterRoot`) se désynchronisait de sa suppression en **cleanup d'effet**, laissant
  le toggle du header (monté séparément) sans instance (« filter instance not available » + setState-in-render). Fix :
  `HydrateFallback` rend le même markup au prerender et au 1er paint client (div vide → spinner après `mount`) ;
  `WorkItemFilterRoot` crée/enregistre l'instance dans un **effet** (symétrique avec la suppression). **Vérifié live
  sur hard reload** : plus aucune des 3 erreurs, le dropdown d'ajout s'ouvre et le filtre par type marche.

**⏳ Reste éventuel (post-S9)** : ~~batch endpoint~~ ✅ ; ~~édition inline spreadsheet~~ ✅ ; ~~upload binaire FILE~~ ✅ ;
colonnes custom en vue workspace (multi-projet) ; nettoyage des assets orphelins quand on remplace un fichier.

**Amélioration spreadsheet (post-S9, livré)** : endpoint batch `IssuePropertyValuesBulkEndpoint`
(POST `.../property-values/` avec `{issue_ids}` → `{issue_id:{prop_id:[vals]}}`, +2 tests) ; `fetchBulkValues` +
cache `valuesByIssue` dans `IssuePropertiesStore` ; `custom-property-columns.tsx` fetch batch unique (via le header,
`issueIds` threadé table→header) + **cellules éditables** (commit upsert + optimiste, RELATION lecture seule). Vérifié
live sur le layout spreadsheet (colonne « Severity », édition High persistée, 0 appel per-issue).

---

## 23. Récapitulatif post-Session 9 (livré & vérifié)

Après la S9, quatre incréments ont été livrés, chacun vérifié live et commité (branche `feat/work-item-types`) :

| #   | Incrément                                                                                                                                                                                                                      | Commits                   | Vérif                                                           |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------- | --------------------------------------------------------------- |
| 1   | **Filtre par type dans la vue principale** (rich-filters) — clé `issue_type` + config miroir de `state`, filtre backend `IssueFilterSet`, gate `is_issue_type_enabled`, fetch des types au montage du HOC                      | `feat(api)` + `feat(web)` | Live : Bug→0, Task→3 ; API 200 ; §22 E                          |
| 2   | **Fix bug d'hydratation/filtres** (pré-existant) — `HydrateFallback` stable + instance de filtre créée en effet (StrictMode-safe)                                                                                              | `fix(web)`                | Live hard reload : plus d'erreurs, dropdown OK ; §22            |
| 3   | **Spreadsheet batch + édition inline** — endpoint batch valeurs, cache store, cellules éditables (fin du N+1)                                                                                                                  | `feat(api)` + `feat(web)` | Live : édition Severity persistée, 0 N+1                        |
| 4   | **FILE = vrai upload** — réutilise le pipeline d'assets projet (MinIO dev / Scaleway prod par config) ; type `ISSUE_PROPERTY_VALUE` + MIME élargis ; composant `file-field.tsx` (modale/sidebar/spreadsheet) ; i18n 19 locales | `feat(api)` + `feat(web)` | Live E2E : presign 200 → MinIO 204 → confirm 204 → download 302 |

**État global** : Work Item Types + Epics + Custom Properties **complets, polis et vérifiés**. `check:types` 28/28,
lint web 0 erreur, oxfmt clean, i18n 19/19, contract/app **121 passés** (8 rate-limit magic-link pré-existants).

### Conversion de type work item ↔ Epic (2026-07-07, livré & vérifié live)

Le **sélecteur de type** (`ce/components/issues/issue-details/issue-type-switcher.tsx`) permet désormais de **convertir
un work item dans les deux sens** : issue régulière → Epic **et** Epic → issue régulière.

- **Cause du bug initial (404)** : un epic est un `Issue` dont le `type` a `is_epic=True`, servi **uniquement** par
  l'endpoint `epics/` (`Issue.epic_objects`) ; l'endpoint `issues/` (`Issue.issue_objects`) **exclut** les epics. Le
  switcher appelait `useIssueDetail()` sans serviceType → `PATCH issues/<id>/` → 404 sur un epic. En plus, le front ne
  pouvait pas **savoir** qu'un item était un epic (le payload `browse`/`IssueDetailSerializer` ne portait pas `is_epic`,
  et le type Epic est exclu de la map des types).
- **Fix (backend + frontend)** :
  - `api` : `IssueDetailSerializer` expose `is_epic` (dérivé de `type.is_epic`) ; nouveau **GET** (member) sur
    `default-epic-type/` (via `DefaultEpicTypeEndpoint.list`) pour lire le type Epic du projet.
  - `web` : le switcher lit le type Epic (SWR sur `fetchDefaultEpicType`), **route l'update par comparaison de type**
    (`issue.type_id === epicType.id` → service `EPICS`, sinon `ISSUES` ; robuste après conversion et re-édition, ne
    dépend pas du flag `is_epic` qui peut être périmé), et **ajoute l'option "Epic"** au menu.
- **Vérif live (Chrome DevTools)** : régulière→Epic = `PATCH issues/ 204` (l'item bascule dans `epic_objects`) ;
  Epic→régulière = `PATCH epics/ 204` (rebascule dans `issue_objects`). Affichage du type "Epic" OK.
- **Note UX / edge** : après conversion, la vue courante (browse/peek) reste sur son service d'origine jusqu'à un
  rechargement ; le routing par type gère correctement la ré-édition immédiate, mais un refetch/redirection auto vers la
  bonne vue après conversion serait un plus (non bloquant).

### Enfants d'un epic = n'importe quel work item (2026-07-07, livré & vérifié live)

Ajouter un **sous-item existant à un epic** échouait (liste vide + impossible d'ajouter). Deux endpoints **upstream**
n'avaient pas été mis à jour quand le fork a introduit les epics (exclus de `Issue.issue_objects`) :

- `app/views/search/issue.py` : les helpers (`filter_root_issues_only`, `search_issues_and_excluding_parent`,
  `filter_issues_excluding_related_issues`) résolvaient le parent via `Issue.issue_objects.filter(pk=issue_id)` → `None`
  pour un parent epic → `filter_root_issues_only` crashait sur `issue.parent` → **500** (`/search-issues/?sub_issue=true`).
- `app/views/issue/sub_issue.py` : le POST faisait `Issue.issue_objects.get(pk=issue_id)` → `DoesNotExist` → **404**.
- **Fix** : résoudre le parent/self via `Issue.objects` (inclut les epics) + garde `.parent` sous `if issue`. Les
  **candidats** restent des work items réguliers (la base `Issue.issue_objects` exclut les epics), donc un epic accepte
  désormais **n'importe quel work item régulier** en enfant.
- **Vérif live** : `/search-issues/?sub_issue=true&issue_id=<epic>` → 200 (candidats réguliers) ;
  `POST epics|issues/<epic>/sub-issues/` → 200 (l'enfant est bien rattaché).
- **Sens inverse (epic comme PARENT d'un work item)** : le picker de parent (`parent=true` dans `/search-issues/`)
  utilisait `Issue.issue_objects` comme base de candidats → les epics n'apparaissaient jamais. Fix : pour `parent=true`,
  utiliser `Issue.objects` (inclut les epics) en ré-appliquant les exclusions du manager (triage/archived/draft). Les
  autres modes (`sub_issue`, relation…) gardent `issue_objects`. Vérifié live : le picker de parent d'un work item
  liste désormais les epics, et `PATCH parent_id=<epic>` → 204.
- **⚠️ Pattern systémique à surveiller** : partout où le code fait `Issue.issue_objects.filter(pk=...)` /
  `.get(pk=...)` sur un id qui **peut être un epic** (parent/self/target), il faut `Issue.objects`. Audit rapide :
  `grep -rn "issue_objects\.\(filter\|get\)(pk=" apps/api` puis vérifier si la cible peut être un epic.

### Backlog / nice-to-have (non bloquant, aucun engagement)

- **Colonnes custom en vue workspace** (multi-projet) : aujourd'hui les colonnes/valeurs custom du spreadsheet sont
  scopées **projet** (`custom-property-columns.tsx` skip si pas de `projectId` param). Une vue workspace mélange des
  projets aux propriétés différentes → nécessiterait de grouper par projet ou d'agréger les définitions.
- **Nettoyage des assets orphelins** : remplacer/supprimer la valeur d'une propriété FILE n'efface pas l'ancien
  `FileAsset` (soft-delete à câbler sur le remplacement).
- **Édition inline RELATION dans le spreadsheet** : les cellules RELATION restent en lecture seule (édition via
  modale/sidebar) — on pourrait y mettre le `PropertyRelationField` comme pour les autres types.
- **Batch endpoint épics-detail / GANTT** : `epics-detail/` existe (S9) ; vérifier d'autres 404 non fatals éventuels.
- **`default_value` côté settings UI** : le backend applique `default_value`/option `is_default` à la création, mais
  l'UI settings ne permet pas encore de _saisir_ un défaut par propriété (à ajouter dans `type-properties.tsx`).

---

## 24. Session 10 — Liaison GitHub ↔ Plane (PR sur les work items) — **LIVRÉ**

> **État : LIVRÉ le 2026-07-07** sur la branche `feat/github-pr-integration` (3 commits, non poussée à ce jour).
> MVP complet, testé de bout en bout (25 tests backend verts, widget validé via Chrome DevTools sur un work item réel).
> Les sous-sections 24.1–24.8 ci-dessous documentent l'**objectif et la conception** (toujours exacts). Le récap de
> **ce qui a réellement été codé** est en **24.9**. Le **guide de mise en production du fork** (handoff pour l'agent
> DevOps) est en **§25**.
>
> Décisions d'archi actées avec l'utilisateur : **GitHub App + webhooks entrants**, sens **GitHub → Plane** seulement
> (bidirectionnel = plus tard), **modèle `GithubPullRequest` dédié** (état live + URL d'env éphémère), **multi-repo**
> (front + API, même org).

### 24.1 Objectif

Relier GitHub et Plane pour **faire remonter les Pull Requests sur les work items**, piloté par des **événements
(webhooks GitHub)**. Cas d'usage : quand une PR GitHub est ouverte / mise à jour / mergée et référence un work item
(ex. `WIT-123` dans le titre ou la branche), elle apparaît sur le work item Plane correspondant avec son état
(open / merged / closed / draft) et un lien cliquable. Direction principale : **GitHub → Plane** (bidirectionnel =
plus tard, hors MVP). Le mécanisme (GitHub App vs OAuth, webhooks vs polling) est **à trancher en début de session**
(voir 24.4).

### 24.2 Ce qui existe déjà dans le repo (les « prises »)

- **Webhooks sortants (Plane → externe), complets — à réutiliser comme patron** :
  - Modèles `apps/api/plane/db/models/webhook.py` (`Webhook` signé HMAC-SHA256 via `secret_key`, `WebhookLog`,
    `ProjectWebhook`).
  - Dispatch `apps/api/plane/bgtasks/webhook_task.py` : `model_activity` → `webhook_activity` → `webhook_send_task`
    (header `X-Plane-Signature`, `pinned_fetch` anti-SSRF, retry/backoff). Événements : project/issue/cycle/module/
    issue_comment/intake.
  - Vues/urls `app/views/webhook/base.py`, `app/urls/webhook.py`.
  - ⇒ copier ce module comme template pour la signature/vérif HMAC et le dispatch.
- **Modèles d'intégration DORMANTS** (présents en DB, aucune vue/serializer/url branchée — scaffolding legacy) :
  `apps/api/plane/db/models/integration/` : `Integration`, `WorkspaceIntegration` (bot `actor`, `api_token`,
  `config`), `github.py` : `GithubRepository`, `GithubRepositorySync`, `GithubIssueSync` (mirroring d'**issues**, pas
  de PR), `GithubCommentSync`. ⇒ à _revive_ ou ignorer. **Aucun modèle PR n'existe.**
- **Surface « lien externe » sur un work item, réutilisable** : `IssueLink` (`db/models/issue.py:392`, `title`+`url`+
  `metadata` JSON) + `IssueLinkViewSet` (`app/views/issue/link.py`) + widget front
  `apps/web/core/components/issues/issue-detail/links/*`. ⇒ chemin le plus rapide pour « afficher une PR » (url = lien
  PR, metadata = état/auteur). Manque un champ d'état → metadata JSON, ou modèle dédié pour un statut live.
- **Config/secrets** : `InstanceConfiguration` (`license/models/instance.py:72`) + helper `get_configuration_value`
  (`plane.license.utils.instance_value`). Registre `utils/instance_config_variables/core.py` (contient déjà
  `GITHUB_CLIENT_ID/SECRET` pour le **login** OAuth). ⇒ y ajouter `GITHUB_APP_ID`/`GITHUB_APP_PRIVATE_KEY`/
  `GITHUB_WEBHOOK_SECRET`.
- **GitHub aujourd'hui = login OAuth seulement** : `authentication/provider/oauth/github.py` (+ vues app/space). Pas
  d'accès repo/PR.
- **Registre des widgets du détail work item** (points d'insertion UI) :
  `apps/web/ce/components/issues/issue-detail-widgets/{collapsibles,action-buttons,modals}.tsx`.

### 24.3 Ce qui manque (à construire)

- **Endpoint entrant** recevant les webhooks GitHub (`pull_request`, `pull_request_review`, `push`) — aucun récepteur
  inbound n'existe.
- **Helper de vérification HMAC entrante** (`X-Hub-Signature-256`) — n'existe pas (seule la signature _sortante_
  existe) ; à écrire en comparaison constant-time.
- **Modèle PR** `GithubPullRequest` (ou `IssueLinkedPR`) : pr_number, repo, url, title, state, author, merged_at, FK
  `Issue` (+ workspace/project) + migration. `GithubIssueSync` ne couvre pas les PR.
- **Trigger de liaison** : parser les refs `#IDENT-seq` (titre PR / branche / body) → résoudre le work item via
  `project.identifier` + `sequence_id` → upsert PR + `issue_activity`. bgtask miroir de `webhook_activity`.
- **UI** : section « Pull Requests » sur le détail work item (nouveau collapsible dans le registre CE) + réglages de
  connexion (installer la GitHub App / mapper repo↔projet). Rien côté front (tree EE absent, pas même stub).
- **Flux d'installation** : GitHub App (recommandé) ou OAuth-app scope repo. L'OAuth actuel est login-only.

### 24.4 Options d'architecture (à trancher en début de session)

- **A. GitHub App + webhooks (recommandé)** : la App (installée sur l'org/les repos) envoie les événements
  `pull_request` à un endpoint Plane ; auth par installation token (JWT App → installation token). Permissions fines,
  webhooks natifs, secret de webhook pour la vérif HMAC. Coût : flux d'install + gestion des tokens.
- **B. OAuth PAT + webhook repo** : plus simple (un token perso + un webhook créé à la main), moins propre/scalable.
  Bon pour un POC.
- **C. Polling API GitHub** (sans webhook) : cron listant les PR référençant des work items. Simple, pas d'endpoint
  entrant, mais latence/quota. Fallback si Plane n'est pas exposé publiquement en dev.
- **Surface PR** : (i) réutiliser `IssueLink` (rapide, état en metadata, pas de live-status) vs (ii) modèle
  `GithubPullRequest` dédié (état live, checks, filtrable).

**Reco MVP** : Option A + modèle PR dédié + widget détail. Pour un premier jet livrable vite : `IssueLink` +
Option B, puis migration vers A.

### 24.5 Plan MVP proposé (phases, à affiner)

1. **Backend socle** : modèle `GithubPullRequest` (+ migration) ; secrets via `InstanceConfiguration` ; helper de
   vérif HMAC entrante (tests unitaires).
2. **Endpoint entrant** : `POST .../github/webhook/` → vérifie signature, parse `pull_request`, extrait `#IDENT-seq`,
   résout le work item, upsert PR + `issue_activity`. Tests contract.
3. **UI détail** : collapsible « Pull Requests » (liste + état + lien) branché dans le registre widgets CE.
4. **Connexion/réglages** : settings pour installer la GitHub App / mapper repos↔projets (ou POC : secret + repo). i18n
   19 locales (skill translate).
5. **Vérif live** : rejouer un payload `pull_request` signé → voir la PR remonter sur un work item (`pnpm dev`,
   Chrome DevTools).

### 24.6 Décisions à figer avant de coder

- GitHub **App** vs OAuth/PAT (24.4 A/B) ? Multi-repo/multi-org attendu ?
- Sens : GitHub→Plane seulement, ou aussi Plane→GitHub (créer/brancher une PR depuis Plane) ?
- Convention de référence work item : `#WIT-123` dans le **titre** / la **branche** / le **body** ? (définir le
  regex ; `IDENT` = `project.identifier`, `seq` = `sequence_id`.)
- Surface : `IssueLink` (rapide) vs modèle `GithubPullRequest` (état live) ?
- Étendue du statut : open/merged/closed seulement, ou aussi checks CI / reviewers ?

### 24.7 Gotchas connus

- **Webhooks entrants en dev** : Plane local n'est pas exposé publiquement → GitHub ne peut pas le POST. Prévoir un
  tunnel (ngrok / cloudflared) OU tester via un **payload signé rejoué localement** (fixture) — plus simple pour les
  tests. La signature HMAC utilise `GITHUB_WEBHOOK_SECRET`.
- Réutiliser `pinned_fetch` (anti-SSRF) pour tout appel **sortant** vers l'API GitHub.
- Le tree d'intégration EE est **absent** en CE (pas de stub) → tout l'UI est à créer ; s'inspirer du widget `links/`
  et du registre `issue-detail-widgets/`.
- Stack : front `pnpm dev` (port 3000, cf. §22 bug hydratation déjà corrigé) ; backend `docker-compose-local.yml` ;
  tests `docker-compose-test.yml`. Hook local : pas d'accents dans les commandes shell, pas de `../`.

### 24.8 Comment lancer la prochaine session

Dire : « **vas-y, on passe à la liaison GitHub** ». Le nouvel agent doit lire ce §24 + la mémoire projet
`plane-fork-work-item-types`, valider l'option d'archi (24.4) avec l'utilisateur, puis dérouler le plan 24.5 sur une
**nouvelle branche** (ex. `feat/github-pr-integration`) — ne pas continuer sur `feat/work-item-types` (dédiée aux
types/propriétés).

### 24.9 Ce qui a réellement été livré (récap technique)

Branche `feat/github-pr-integration`. Comportements livrés, tous vérifiés :

1. Une PR qui référence un work item (`#IDENT-seq` — `IDENT` = `project.identifier`, `seq` = `issue.sequence_id`,
   dans le **titre**, la **branche head** ou le **body**) → **rattachée automatiquement** au work item (upsert d'un
   `GithubPullRequest`).
2. PR **mergée** (`action=closed` + `merged=true`) → l'issue passe dans l'état du groupe **`completed`** du projet
   (plus petit `sequence`), via le pipeline standard `issue_activity` → `track_state` (apparaît dans le feed d'activité).
   **Cascade récursif (2026-07-07)** : la même bascule est appliquée à **toute la descendance** (sous-items, petits-enfants…,
   BFS cycle-safe, état cible calculé par projet de chaque nœud). Garde-fous : on ne touche pas un nœud déjà en groupe
   `completed`/`cancelled` (pas de ré-ouverture ni d'écrasement d'un état volontaire), on ignore les enfants archivés/draft.
   Fonctions `_move_issue_to_completed` (cascade BFS) + `_complete_single_issue` (un nœud). Test :
   `test_merge_cascades_to_all_descendants`.
3. Un **commentaire de PR** contenant une URL avec le mot `preview` → l'URL est stockée dans `ephemeral_env_url` et
   affichée sur le work item (event `issue_comment`).
4. **Widget « Pull Requests »** (collapsible) sur le détail du work item : badge d'état (Open/Merged/Closed), lien PR
   (`repo #num — titre`), auteur + « il y a X », et lien **« Open preview environment »** si `ephemeral_env_url`. Le
   widget fetch au montage et **s'auto-masque** s'il n'y a aucune PR.

**Fichiers backend (`apps/api/plane/`)** :

- `db/models/github.py` — modèles `GithubPullRequest` (FK issue, `pr_number`, `repository_full_name`, `url`, `state`
  OPEN/CLOSED/MERGED, `merged`, `author_login`, `ephemeral_env_url`, `github_pr_id`, `merged_at`) et
  `GithubRepositoryMap` (`repository_id`, `full_name`, `installation_id`). Enregistrés dans `db/models/__init__.py`.
- Migration `db/migrations/0124_githubrepositorymap_githubpullrequest.py` (tables `github_pull_requests`,
  `github_repository_maps`).
- `utils/github_signature.py` — `verify_github_signature()` : HMAC-SHA256 **constant-time** sur le **body brut**,
  header `X-Hub-Signature-256` (format `sha256=<hex>`).
- `app/views/external/github/receiver.py` — `GithubWebhookEndpoint` (`AllowAny`, pas d'auth session) : vérifie la
  signature, gère `ping`, enfile `github_webhook_task.delay(...)`, répond **202** vite.
- `app/views/external/github/settings.py` — `GithubRepositoryMapEndpoint` (CRUD mapping repo↔projet,
  `WorkspaceEntityPermission`) + `GithubPullRequestListEndpoint` (lecture des PR d'une issue, `ProjectEntityPermission`).
- `app/urls/external_github.py` (branché dans `app/urls/__init__.py`).
- `bgtasks/github_webhook_task.py` — regex `WORK_ITEM_REF` + `EPHEMERAL_URL`, handlers `_handle_pull_request` /
  `_handle_issue_comment`, `_move_issue_to_completed`. Celery `@shared_task`.
- `app/serializers/github.py` (+ export dans `serializers/__init__.py`).
- Config : 4 clés ajoutées à `github_config_variables` dans `utils/instance_config_variables/core.py` :
  `GITHUB_APP_ID`, `GITHUB_APP_SLUG` (clairs), `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET` (chiffrés).
- Tests : `tests/unit/utils/test_github_signature.py`, `tests/unit/bgtasks/test_github_webhook.py`,
  `tests/contract/app/test_github_webhook.py` (25 tests).

**Fichiers frontend (`apps/web/`, `packages/`)** :

- Types `packages/types/src/issues/github_pull_request.ts` (+ export dans `issues/base.ts`, + `"pull-requests"` ajouté
  à `TWorkItemWidgets` dans `issues/issue.ts`).
- Store `core/store/issue/issue-details/github-pull-request.store.ts` (read-only) câblé dans `.../root.store.ts`.
- Méthode `fetchGithubPullRequests` dans `core/services/issue/issue.service.ts`.
- Widget `core/components/issues/issue-detail-widgets/pull-requests/*` (root/title/content/pull-request-detail/index).
- Enregistré via la couture de fork CE `ce/components/issues/issue-detail-widgets/collapsibles.tsx` (aucune édition du
  registre core).
- i18n : bloc top-level `pull_requests` dans les **19 locales** (`packages/i18n/.../common.json`), `sync:check` à 100 %.

**Endpoints exposés** (préfixe `/api/`, donc déjà routés par le proxy Plane existant) :

- `POST /api/workspaces/<slug>/github/webhook/` — **public**, HMAC (cible du webhook GitHub App).
- `GET|POST /api/workspaces/<slug>/github/repositories/` et `DELETE .../<uuid>/` — mapping repo↔projet (admin).
- `GET /api/workspaces/<slug>/projects/<pid>/issues/<iid>/github/pull-requests/` — lecture (consommé par le widget).

**Non fait / différé (hors périmètre MVP)** : UI de réglages pour installer la GitHub App et mapper les repos depuis
l'app (aujourd'hui le mapping se fait via l'endpoint `github/repositories/` ; et le rattachement des PR marche **même
sans mapping** grâce au référencement `#IDENT-seq`) ; auth **sortante** GitHub App (JWT App → installation token) pour
le futur « issues GitHub → Plane » (bidirectionnel) ; dédup replay via Redis (`X-GitHub-Delivery`) — les upsert rendent
les rejeux sûrs en correction, mais pas contre les doublons d'activité ; `pull_request_count` annoté sur le payload
issue (abandonné : le widget fetch et s'auto-masque, donc inutile).

---

## 25. Mise en production du fork Plane (handoff DevOps)

> **But de cette section** : donner à l'agent qui a accompagné la mise en ligne de l'environnement Plane tout le
> nécessaire pour **déployer cette version fork en production**. Ce fork réintègre des features payantes upstream +
> ajoute la liaison GitHub. Les points marqués **[À VALIDER]** dépendent de votre infra (compose/k8s/CI) et sont à
> confirmer avec l'agent DevOps ; les points marqués **[VÉRIFIÉ]** ont été testés pendant le dev.

### 25.1 Ce que le fork ajoute par rapport à Plane upstream

Cumul des sessions (voir sections précédentes de ce doc pour le détail) :

- **Work Item Types**, **Epics**, **Custom Properties** (types de propriétés + options + valeurs, dont propriété
  **FILE** avec upload réel) — S0→S9 + post-S9.
- **Liaison GitHub → Plane** (PR sur les work items) — §24, cette session.

Conséquence déploiement : par rapport à un Plane CE standard, il faut surtout **(a)** appliquer les **migrations DB**
du fork, **(b)** **rebuild le frontend** depuis cette branche, **(c)** optionnellement configurer la **GitHub App**.

### 25.2 Base de données — migrations

- Le fork ajoute des migrations dans `apps/api/plane/db/migrations/` ; la dernière est **`0124`**
  (`0124_githubrepositorymap_githubpullrequest`). Les migrations du fork antérieures incluent notamment `0122`
  (`project_is_epic_enabled`), `0123` (`issueproperty_...`), puis `0124`.
- Déploiement : lancer **`python manage.py migrate`** (comme upstream). Aucune migration destructive ; `0124` crée
  seulement 2 tables (`github_pull_requests`, `github_repository_maps`). **[VÉRIFIÉ]** en dev (appliquée sans erreur).
- **[À VALIDER]** l'ordre/mécanisme de migration dans votre pipeline prod (job init, hook de déploiement, etc.).

### 25.3 Services & processus

- **API (web)** : sert les nouveaux endpoints sous `/api/…` → **aucune règle de proxy/ingress supplémentaire** (le
  routage `/api/` existant suffit). **[VÉRIFIÉ]** en dev via le proxy sur `:8000`.
- **Worker Celery** : la nouvelle task `plane.bgtasks.github_webhook_task.github_webhook_task` est **auto-découverte au
  démarrage** du worker. → **redéployer / redémarrer le service worker** pour qu'il l'enregistre (un worker déjà en
  cours ne connaît pas la task tant qu'il n'est pas relancé). Pas de nouvelle **queue** ni de nouveau worker dédié.
  **[VÉRIFIÉ]** : l'import de la task sous contexte Django est OK ; il restait juste à relancer le worker.
- **Beat / autres** : rien de spécifique (pas de tâche périodique ajoutée).

### 25.4 Configuration (GitHub App) — optionnel mais requis pour activer la liaison

4 clés d'instance (catégorie `GITHUB`) lues via `get_configuration_value()` :
`GITHUB_APP_ID`, `GITHUB_APP_SLUG` (non chiffrés), `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET` (chiffrés).

- **`GITHUB_WEBHOOK_SECRET` est requis** pour que le récepteur fonctionne : sans lui, `POST …/github/webhook/` renvoie
  **503** (fail-safe). Avec un secret configuré mais une signature invalide → **401** ; payload accepté → **202**.
- Mécanisme de config Plane : `SKIP_ENV_VAR` (défaut `"1"`) fait lire les valeurs depuis la table
  `InstanceConfiguration` (God-mode / admin d'instance) ; sinon depuis les **variables d'environnement**. **[À VALIDER]**
  avec l'agent DevOps selon votre méthode habituelle de config d'instance (vous utilisez probablement déjà l'une des
  deux pour SMTP, OAuth GitHub login, etc. — même canal ici). Les valeurs `*_SECRET`/`*_PRIVATE_KEY` sont chiffrées au
  repos par la couche config (`plane.license.utils.encryption`).
- **Création de la GitHub App** (côté GitHub, org qui contient les repos front + API) :
  - Webhook URL = `https://<votre-domaine-plane>/api/workspaces/<slug>/github/webhook/` (le `slug` scope le secret par
    workspace). Webhook secret = la valeur mise dans `GITHUB_WEBHOOK_SECRET`.
  - Events à cocher : **Pull requests** et **Issue comments** (les seuls traités au MVP ; `pull_request_review`/`push`
    sont ignorés). Permissions repo minimales correspondantes (Pull requests: Read, Issues/Contents selon besoin).
  - Installer l'App sur l'org / les repos concernés.
- **Mapping repo↔projet** : facultatif au MVP — le rattachement des PR marche via `#IDENT-seq` sans mapping. Le mapping
  (`installation_id`, `repository_id`, `full_name` → projet) se crée via `POST …/github/repositories/` et servira pour
  l'auth sortante future. Pas d'UI de réglages encore.

### 25.5 Build frontend & packages

- **Ordre de build important** : `@plane/types` est consommé par le web via son **build (`dist/`)**, pas la source.
  Rebuild `@plane/types` **avant** le typecheck/build web, sinon les nouveaux types (`TGithubPullRequest`,
  `"pull-requests"`) ne sont pas vus. Commande : `pnpm --filter @plane/types build`. **[VÉRIFIÉ]** (piège rencontré en
  dev ; `dist/` n'est pas commité, il est rebuild au build). Un build monorepo normal (turbo) enchaîne ça tout seul si
  l'ordre de dépendances est respecté.
- **i18n** : `pnpm --filter @plane/i18n run generate:types` puis `sync:check` (doit être **100 %**, sinon le CI
  `check:sync` échoue). **[VÉRIFIÉ]** 100 %.
- **Web** : `pnpm --filter web build` (react-router build). Typecheck `check:types` = **0 erreur** en dev. **[VÉRIFIÉ]**.
- **[À VALIDER]** l'intégration de ces étapes dans votre pipeline de build/déploiement prod (images Docker web, cache
  turbo, etc.).

### 25.6 Sécurité (points de contrôle pour la revue prod)

- Le récepteur webhook est **volontairement non authentifié** (GitHub ne peut pas présenter une session Plane) et
  protégé par **HMAC-SHA256 constant-time** sur le **body brut** (`hmac.compare_digest`). C'est le seul endpoint public
  ajouté. Il ne fait que vérifier + enfiler (pas de traitement lourd synchrone) → surface DoS faible.
- **Pas de surface SSRF** : c'est un récepteur pur, il ne va jamais fetch une URL issue du payload (le MVP ne fait
  aucun appel sortant vers GitHub).
- Secret de webhook stocké chiffré (config d'instance). Rotation = mettre à jour `GITHUB_WEBHOOK_SECRET` des deux côtés
  (Plane + GitHub App).
- **[À VALIDER]** exposition réseau : confirmer que `/api/workspaces/<slug>/github/webhook/` est joignable depuis
  Internet (GitHub) sans passer par une auth mTLS/WAF qui bloquerait GitHub.

### 25.7 Vérification post-déploiement (checklist)

1. `manage.py migrate` OK ; tables `github_pull_requests` / `github_repository_maps` présentes.
2. `GET /api/…/github/pull-requests/` (avec session) répond 200 `[]` sur un work item sans PR.
3. `POST /api/workspaces/<slug>/github/webhook/` sans secret configuré → **503** ; avec secret + signature invalide →
   **401** ; event `ping` signé → **200**.
4. Depuis la GitHub App : ouvrir une PR de test référençant `#IDENT-1`, vérifier que la PR remonte sur le work item ;
   la merger → l'issue passe en état `completed` ; poster un commentaire `Preview: https://…preview…` → le lien
   « Open preview environment » apparaît.
5. Le worker log montre bien l'exécution de `github_webhook_task` (sinon → worker pas relancé, cf. 25.3).

### 25.8 Problématiques rencontrées (utiles au déploiement)

- **Worker à relancer** pour enregistrer la nouvelle task Celery (sinon les webhooks sont reçus/202 mais jamais
  traités).
- **Secret manquant = 503** (fail-safe voulu) : bien configurer `GITHUB_WEBHOOK_SECRET`.
- **`@plane/types` en dist** : rebuild obligatoire avant le web (cf. 25.5).
- **Webhooks entrants injoignables en local** (dev) : tunnel ngrok/cloudflared nécessaire — **non pertinent en prod**
  si Plane est exposé publiquement (le cas ici).
- Rappel : le rattachement `#IDENT-seq` est **case-insensitive** sur l'identifiant ; il matche dans titre/branche/body
  et évite les faux positifs collés à des chiffres (`123WIT-45` ignoré). Un identifiant inconnu → simplement pas de
  rattachement (pas d'erreur).

### 25.9 État git au moment du handoff

Branche `feat/github-pr-integration`, **3 commits, non poussée** :

- `feat(api): surface GitHub pull requests on work items via inbound webhooks`
- `chore(i18n): add pull_requests keys across all locales`
- `feat(web): Pull Requests widget on the work item detail panel`

(Un `no-shadow` préexistant dans `root.store.ts` a été corrigé au passage — param `action` → `widget` — car le hook
pre-commit `oxlint --deny-warnings` le bloquait dès qu'on touchait ce fichier.)

---

## 26. Maintenabilité & synchronisation avec l'upstream (makeplane/plane)

> **But** : garder ce fork fonctionnel tout en récupérant au fil de l'eau les releases de la source open-source. Cette
> section donne la **carte de divergence**, la **convention de marquage** et la **procédure de sync** recommandée.

### 26.1 Carte de divergence (mesurée le 2026-07-07)

Remote `upstream` = `https://github.com/makeplane/plane.git`. Divergence de la branche `feat/github-pr-integration`
par rapport au `merge-base` avec `upstream/preview` :

- **93 fichiers upstream MODIFIÉS** (= surface de conflit potentielle) et **59 fichiers AJOUTÉS** (neufs → zéro
  conflit).
- La **feature GitHub de cette session** ne pèse que ~9 fichiers de code partagés (barrels `__init__.py`, 1 méthode de
  service, `root.store.ts`, 2 fichiers de types) + 19 JSON i18n — tout le reste est en fichiers neufs. **Peu coûteux.**
- L'essentiel de la divergence (donc du coût de sync) vient des **sessions antérieures** (Work Item Types / Epics /
  Custom Properties), qui **réintègrent des features gardées dans le repo EE privé** de Plane → le CE ne convergera
  jamais avec, on porte ce diff en permanence.

**Fichiers upstream « chauds » à surveiller en priorité** (édités par le fork ET souvent par l'upstream) :

- Backend : `apps/api/plane/db/models/issue.py`, `db/models/project.py`, `app/views/issue/base.py`,
  `app/views/issue/activity.py`, `utils/issue_filters.py`.
- Frontend : `apps/web/core/store/issue/issue-details/root.store.ts`, `core/store/root.store.ts`,
  `core/components/issues/issue-modal/{base,modal}.tsx`, les layouts `issue-layouts/spreadsheet/*`, les filtres
  `work-item-filters/*`, `core/services/issue/issue.service.ts`.
- Packages : `packages/types/src/issues/issue.ts`, `types/src/enums.ts`, `types/src/index.ts`,
  `constants/src/issue/*`.

Régénérer la carte à tout moment :

```
git fetch upstream
git merge-base HEAD upstream/preview            # -> <BASE>
git diff --diff-filter=M --name-only <BASE> HEAD   # fichiers modifies (surface de conflit)
git diff --diff-filter=A --name-only <BASE> HEAD   # fichiers ajoutes (sans risque)
```

### 26.2 Convention de marquage `[FORK]`

Toute édition d'un **fichier upstream** doit porter un commentaire grep-able `// [FORK] <slug>` (TS) ou
`# [FORK] <slug>` (Python). Permet de **lister toute la surface de divergence d'un coup** et, après un merge upstream,
de vérifier que chaque marqueur a survécu.

```
grep -rn "\[FORK\]" apps packages --include=*.ts --include=*.tsx --include=*.py | grep -v node_modules
```

État actuel (2026-07-07) : **toute la surface de divergence est marquée** — **128 marqueurs** au total :
`github-pr-integration` (15) pour la liaison GitHub, `work-item-types` (113) pour l'ensemble des sessions antérieures
(Work Item Types / Epics / Custom Properties). Slugs utilisés :

- `github-pr-integration` — liaison GitHub (§24).
- `work-item-types` — umbrella pour tout le reste du fork (types d'items, epics, propriétés custom, upload FILE, fix
  d'hydratation §22).

Convention : un marqueur par **région contiguë** de divergence ; pour un fichier qui est une **réécriture complète**
d'un stub upstream, un seul marqueur bannière en tête. Deux fichiers n'ont pas pu être marqués sur la ligne exacte car
leur seule divergence est un **attribut JSX** (pas de position de commentaire valide) — le marqueur a été posé sur
l'élément JSX parent. Après chaque merge upstream, re-vérifier que le nombre de marqueurs n'a pas chuté (un marqueur
disparu = un bloc fork écrasé par l'upstream).

### 26.3 Procédure de sync upstream recommandée

1. **Suivre des tags stables, pas `preview`.** Le fork est basé sur `upstream/preview` (branche de dev mouvante = pire
   cas). Se re-baseliner sur un **tag** (`v1.3.1`, …) et intégrer **de tag en tag** à cadence (ex. mensuelle).
2. **Merger, pas rebaser.** `git merge upstream/<tag>` dans la branche du fork → conflits résolus **une fois** par sync
   (rebaser 90+ fichiers en boucle est intenable).
3. **Résoudre en s'appuyant sur les marqueurs** `[FORK]` (26.2) : sur chaque fichier chaud (26.1), garder la version
   fork des blocs marqués, prendre la version upstream ailleurs.
4. **Gate de non-régression obligatoire après chaque merge** (c'est ce qui prouve « ça marche encore ») :
   - Backend : `docker compose -f docker-compose-test.yml run --rm api-tests pytest -m unit` + `manage.py check` +
     `manage.py makemigrations --check` (détecte une dérive de schéma).
   - Frontend : `pnpm --filter @plane/types build` **puis** `pnpm --filter web check:types` ; i18n
     `pnpm --filter @plane/i18n run sync:check` (doit rester 100 %).
   - Smokes E2E sur les features réintégrées (le flow widget PR via Chrome DevTools, création d'un work item type,
     d'une propriété custom).
5. **Réduire la surface `core/` au fil des syncs.** Quand une édition dans `apps/web/core/**` peut être déplacée
   derrière la couture `@/plane-web/*` → `apps/web/ce/**` (l'indirection prévue par Plane pour l'EE/les forks), le
   faire — les conflits en `core/` coûtent le plus. Le widget GitHub le fait déjà (rendu via le stub CE).
6. **Éditer additif dans les fichiers chauds** : ajouter des champs/lignes plutôt que reflow le code existant → le
   merge 3-way réussit tout seul bien plus souvent.

### 26.4 Cas particuliers

- **i18n** : la divergence i18n est _additive_ (bloc top-level `pull_requests` + les clés des sessions antérieures).
  Pas de marqueur possible (JSON) → repérable par la **clé** elle-même (`grep -rn '"pull_requests"' packages/i18n`).
  Un conflit n'arrive que si l'upstream insère au même endroit ; `sync:check` garantit la complétude après résolution.
- **Migrations DB** : l'upstream ajoute des migrations avec ses propres numéros. En cas de collision de numéro/branche,
  régénérer/renuméroter la migration du fork après merge et relancer `migrate`. `makemigrations --check` en CI détecte
  toute dérive de modèle non migrée.
- **Feature upstreamable** : la liaison GitHub est générique (non-EE) → envisager une PR vers `makeplane/plane`. Si
  acceptée, on cesse totalement de la maintenir dans le fork.
