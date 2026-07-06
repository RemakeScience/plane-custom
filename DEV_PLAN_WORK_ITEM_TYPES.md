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

- [ ] **Champ projet** — migration : ajouter `Project.is_epic_enabled = BooleanField(default=False)`
      (`apps/api/plane/db/models/project.py`) + exposer dans le serializer projet de `plane/app`.
- [ ] **Type Epic par défaut** — à l'activation des épics sur un projet, garantir l'existence d'un
      `IssueType(is_epic=True, is_default=True)` associé (endpoint d'activation ou signal).
- [ ] **Endpoints Epics** — nouveau viewset (ou paramètre) qui liste/détaille les issues avec
      `type__is_epic=True`. Réutiliser au maximum les viewsets d'issue existants
      (`apps/api/plane/app/views/issue/base.py`) + un filtre.
- [ ] **Exclusion des épics des listes normales** — auditer **toutes** les vues de liste d'issues
      (`issue/base.py`, cycle-issues, module-issues, vues, recherche, sub-issues) et appliquer le filtre
      `Q(type__isnull=True) | Q(type__is_epic=False)` là où c'est pertinent (aujourd'hui présent seulement
      dans `archive.py`). ⚠️ Point sensible : c'est la principale source de régressions potentielles.
- [ ] **Relations épic → work items** — vérifier que le parentage (epic parent d'issues) passe par les
      relations d'issue existantes ; ajuster si besoin (une épic peut parenter au-delà d'un cycle/module).
- [ ] **Tests** — listes filtrées, activation, parentage, non-régression des listes d'issues classiques.

### Phase B3 — API Custom Properties

- [ ] **Modèles** — créer `apps/api/plane/db/models/issue_property.py` :
  - `IssueProperty` : `issue_type (FK)`, `name`, `display_name`, `property_type` (enum : `TEXT, DECIMAL,
OPTION, BOOLEAN, DATETIME, RELATION, URL, EMAIL, FILE`), `relation_type` (member/issue si RELATION),
    `is_required`, `is_multi`, `is_active`, `default_value` (JSON), `settings` (JSON), `sort_order`,
    `logo_props`, `external_source/external_id`.
  - `IssuePropertyOption` : `property (FK)`, `name`, `description`, `logo_props`, `is_active`,
    `is_default`, `sort_order`, `parent` (pour options hiérarchiques éventuelles).
  - `IssuePropertyValue` : `issue (FK)`, `property (FK)`, colonnes de valeur typées
    (`value_text`, `value_decimal`, `value_boolean`, `value_datetime`, `value_uuid`, `value_option (FK)`),
    ou une seule colonne `value` JSON + `value_option`. **Décision de schéma à prendre.**
  - Exporter dans `apps/api/plane/db/models/__init__.py` (ne pas oublier `ProjectIssueType` non plus,
    actuellement non exporté).
- [ ] **Migration** — création des 3 tables (`issue_properties`, `issue_property_options`,
      `issue_property_values`) + contraintes d'unicité (`issue+property`, `property+name` sur options).
- [ ] **Serializers** — `IssuePropertySerializer`, `IssuePropertyOptionSerializer`,
      `IssuePropertyValueSerializer` (+ endpoint « properties AND options » agrégé, cf. fetch-keys front).
- [ ] **ViewSets + URLs** :
  - CRUD définitions de propriétés (scoping type) : `.../issue-types/<id>/properties/`.
  - CRUD options : `.../properties/<id>/options/`.
  - Lecture/écriture des **valeurs** par issue : `.../issues/<id>/property-values/` (bulk upsert).
  - Endpoint agrégé `.../issue-types/properties-and-options/` (aligne `WORK_ITEM_TYPES_PROPERTIES_AND_OPTIONS`).
- [ ] **Validation** — champs `is_required` obligatoires à la création d'issue, cohérence type/valeur.
- [ ] **Intégration create/update issue** — accepter un payload de valeurs de propriété à la création/màj
      d'issue (transactionnel avec l'issue).
- [ ] **Tests** — CRUD définitions/options/valeurs, validation requis, filtrage par type, multi-valeurs.

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
- [ ] `packages/types/src/issues/issue-property.ts` (nouveau) : `EIssuePropertyType` (enum),
      `TIssueProperty`, `TIssuePropertyOption`, `TIssuePropertySettings`.
- [ ] Remplacer `TIssuePropertyValues = Record<string, unknown>` par un type structuré
      (`packages/types/src/issues/issue-property-values.ts`), garder la rétrocompat des imports.

### Services (`apps/web/core/services`)

- [x] `apps/web/core/services/issue-type.service.ts` : CRUD types + `markAsDefault` + `enable`
      (Session 2, mirror `module.service.ts`).
- [ ] `apps/web/core/services/issue-property.service.ts` : CRUD propriétés + options + `propertiesAndOptions`.
- [ ] `apps/web/core/services/issue-property-value.service.ts` : lecture/upsert des valeurs par issue.
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
- [ ] `issue-property.store.ts` + `issue-property-value.store.ts` (Session 7).
- [ ] **Activer le store épic** — remplacer les stubs `apps/web/ce/store/issue/epic/{issue,filter}.store.ts`
      (retirer `// will never be used`) par une vraie implémentation reliée au filtre `is_epic=True` (Session 5).

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

- [ ] `issue-modal/provider.tsx` — remplacer les no-ops par la vraie logique :
      `getIssueTypeIdOnProjectChange`, `getActiveAdditionalPropertiesLength`, `handlePropertyValuesValidation`,
      `handleCreateUpdatePropertyValues`, `handleProjectEntitiesFetch`.
- [ ] `issue-modal/modal-additional-properties.tsx` — rendu **dynamique** des champs custom selon
      `property_type` (text, number, boolean, date, select simple/multi, member, relation…).
- [ ] `issue-details/additional-properties.tsx` — affichage/édition des valeurs dans la sidebar du détail
      (et peek). Mirror des consommateurs `apps/web/core/components/issues/issue-detail/sidebar.tsx:269`.
- [ ] `issue-layouts/additional-properties.tsx` — valeurs custom en colonnes (spreadsheet) / badges.
- [ ] Composants de saisie réutilisables par type de propriété (dans `@plane/ui` ou local) :
      `PropertyInput` (text/number/url/email), `PropertyOptionSelect`, `PropertyDatePicker`,
      `PropertyBooleanToggle`, `PropertyMemberSelect`.

### Epics

- [ ] `epics/epic-modal/modal.tsx` — vraie `CreateUpdateEpicModal` (aujourd'hui `<></>`).
- [ ] Page Epics — créer la route `/epics` (assets d'empty-state déjà présents dans
      `apps/web/app/assets/empty-state/epics`). Réutiliser les layouts d'issue avec le store épic.
- [ ] Nav — activer l'entrée « epics » (`project-navigation.tsx` + `tab-navigation-utils.ts:76`) sous
      condition `is_epic_enabled`.

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
- [~] **Session 3 — UI Types.** ✅ **Partie 1 (page settings)** : onglet + route + page « Work Item Types »
  (activation + liste + créer/éditer/supprimer + set default), vérifiée en live via Chrome DevTools
  (activation crée le type par défaut + backfill, création OK, protection du défaut). Détail §14.
  ⏳ **Partie 2 restante** : `issue-type-select` (modale de création), badge `issue-type-identifier`,
  `getIssueTypeIdOnProjectChange` (provider), filtres.
- [ ] **Session 4 — Backend Epics (B2).** Champ `is_epic_enabled`, endpoints filtrés, audit du filtrage
      des listes. Livrable : API épics + non-régression.
- [ ] **Session 5 — Store + UI Epics.** Store épic réel, page `/epics`, nav, modale. Livrable : épics
      utilisables.
- [ ] **Session 6 — Backend Propriétés (B3).** Modèles + migrations + serializers + endpoints + valeurs.
      Livrable : API propriétés.
- [ ] **Session 7 — Data layer + stores Propriétés.** Types, services, stores propriétés/valeurs.
- [ ] **Session 8 — UI Propriétés.** Provider réel, rendu dynamique (modale/sidebar/layout), settings des
      propriétés par type. Livrable : propriétés custom de bout en bout.
- [ ] **Session 9 — Polish & tests.** i18n complète, non-régressions, revue, doc.

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
