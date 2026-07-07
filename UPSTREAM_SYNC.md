# Synchronisation avec l'upstream (makeplane/plane) — runbook

Ce dépôt est un **fork** de Plane (`makeplane/plane`) qui réintègre des features gardées dans l'édition
Enterprise (Work Item Types, Epics, Custom Properties, upload FILE) + ajoute une liaison **GitHub → Plane**
(les Pull Requests remontent sur les work items).

Ce fichier explique **quoi faire le jour où une nouvelle version de Plane sort**, pour récupérer ses mises à jour
sans casser le fork. Suivre les étapes dans l'ordre.

---

## Règles de base (à connaître une fois)

- **Branche d'intégration = `main`.** Tout le fork vit dessus. On déploie depuis `main`. Les features se font sur des
  branches `feat/*` puis reviennent dans `main` par PR.
- **On synchronise depuis des TAGS stables (`vX.Y.Z`), jamais depuis `preview`.** `preview` est la branche de dev
  mouvante de Plane ; s'en servir comme source = conflits permanents.
- **Remotes** : `upstream` = `makeplane/plane` (la source), `origin` = ton fork `RemakeScience/plane-custom`.
- **Marqueurs `[FORK]`** : chaque modification d'un fichier upstream porte un commentaire `// [FORK] <slug>` (TS) ou
  `# [FORK] <slug>` (Python). Ils servent à **savoir quel côté garder** pendant un conflit et à **vérifier qu'aucun bloc
  fork n'a été écrasé** après un merge. Slugs : `work-item-types` (features EE réintégrées) et `github-pr-integration`
  (liaison GitHub).

### ⚠️ Situation de départ (2026-07-07) — à lire une fois

La base actuelle du fork est un commit de `preview` du **2026-07-01**, qui est **plus récent** que le dernier tag
stable disponible à ce moment (`v1.3.1`, du 2026-05-15) **et a divergé** de la ligne de release.
**Conséquence : ne PAS merger `v1.3.1` (ni un tag antérieur)** — ce serait un retour en arrière. Le **premier** sync
par tag se fera avec le **prochain** tag qui sort **après** le 2026-07-01 (probablement `v1.4.0`). En attendant, on
reste sur la base actuelle (saine) ; si un fix upstream précis est nécessaire avant, on le **cherry-pick** (voir plus
bas), on ne re-merge pas `preview`.

---

## Procédure : un nouveau tag stable est sorti

Exemple avec `v1.4.0` — remplacer par le tag réel.

### 1. Récupérer les tags et vérifier qu'il est bien EN AVANT de ta base

```bash
git fetch upstream --tags
# Doit répondre "OUI" : le tag doit contenir ta base (sinon c'est un retour arrière, ne pas merger)
git merge-base --is-ancestor $(git rev-parse main) v1.4.0 && echo "OUI, en avant" || echo "NON, ne pas merger"
```

> Astuce : `git tag | sort -V | tail -5` pour lister les derniers tags.

### 2. Partir d'un `main` propre et créer une branche de sync

```bash
git checkout main
git pull origin main            # main local a jour
git status                      # doit etre clean
git checkout -b sync/v1.4.0     # on merge dans une branche jetable, pas directement dans main
```

### 3. Merger le tag (PAS `preview`, PAS un tag plus vieux)

```bash
git merge v1.4.0
```

Git va lister les conflits. Les résoudre fichier par fichier (étape 4).

### 4. Résoudre les conflits en s'appuyant sur les marqueurs `[FORK]`

Dans un fichier en conflit (`<<<<<<<` / `=======` / `>>>>>>>`) :

- Les blocs marqués `// [FORK] ...` (ou `# [FORK] ...`) = **ton code fork**, à **conserver**.
- Le reste = **prendre la version upstream** (les améliorations de Plane).
- En pratique : garder tes blocs `[FORK]` ET intégrer les changements upstream autour. Ne jamais supprimer un marqueur
  sans raison.
- Fichiers les plus susceptibles de conflit (les « chauds ») : `apps/api/plane/db/models/issue.py`,
  `app/views/issue/base.py`, `apps/web/core/store/**/root.store.ts`, `packages/types/src/issues/issue.ts`,
  `core/components/issues/issue-modal/*`, les layouts `spreadsheet/*`, les filtres `work-item-filters/*`.

Après résolution d'un fichier : `git add <fichier>`. Quand tout est résolu : `git commit` (message du merge).

### 5. Vérifier qu'aucun bloc fork n'a disparu

```bash
# Doit rester >= au compte d'avant le merge (128 au 2026-07-07). Une chute = un bloc fork ecrase.
grep -rn "\[FORK\]" apps packages --include="*.ts" --include="*.tsx" --include="*.py" | grep -v node_modules | grep -c ""
```

Si le compte a chuté : retrouver le(s) marqueur(s) manquant(s) (comparer avec `git show main:<fichier>`) et réintégrer
le bloc fork.

### 6. Gate de non-régression (OBLIGATOIRE avant de merger dans `main`)

```bash
# Backend (necessite la stack docker up, cf docker-compose-local.yml)
docker compose -f docker-compose-test.yml run --rm api-tests pytest -m unit
docker exec plane-fork-api-1 python manage.py check
docker exec plane-fork-api-1 python manage.py makemigrations --check   # 0 = pas de derive de schema

# Frontend / packages
pnpm --filter @plane/types build          # IMPORTANT : rebuild types AVANT le typecheck web
pnpm --filter web check:types             # doit finir a 0 erreur
pnpm --filter @plane/i18n run sync:check  # doit etre 100%
```

- Si une **nouvelle migration upstream** entre en collision de numéro : régénérer/renuméroter la migration du fork,
  puis relancer `manage.py migrate`. `makemigrations --check` détecte toute dérive.
- Si `check:types` échoue : c'est souvent qu'upstream a renommé/déplacé un type qu'un bloc fork utilise → adapter le
  bloc fork.

### 7. Vérif fonctionnelle rapide (smokes)

Lancer l'app (`pnpm dev` sur `apps/web`, port 3000 ; backend via docker) et vérifier que les features fork marchent
toujours :

- créer un **work item type** et une **propriété custom** sur un projet ;
- ouvrir un work item qui a une PR liée → le widget **Pull Requests** s'affiche (état + lien + preview) ;
- créer un **Epic**.

### 8. Fusionner dans `main` et pousser

```bash
git checkout main
git merge --no-ff sync/v1.4.0     # garde une trace du sync dans l'historique
git push origin main
git branch -d sync/v1.4.0         # nettoyage
```

À partir de là, **ta base upstream = `v1.4.0`**. Le prochain sync se fera avec le tag suivant (`v1.5.0`, …), toujours
en repartant de l'étape 1.

---

## Cas particuliers

### Besoin d'un fix upstream AVANT le prochain tag

Ne pas re-merger `preview`. Cherry-pick le commit précis :

```bash
git fetch upstream
git checkout main
git cherry-pick <sha-du-commit-upstream>
# resoudre les conflits comme a l'etape 4, puis push
```

### Le merge tourne mal / trop de conflits

Abandonner proprement, rien n'est perdu :

```bash
git merge --abort        # pendant un merge non commite
# ou, si deja commite sur la branche sync : jeter la branche
git checkout main && git branch -D sync/v1.4.0
```

### Réduire la dette au fil du temps

Quand une modif du fork dans `apps/web/core/**` peut être déplacée derrière la couture `@/plane-web/*` →
`apps/web/ce/**` (l'indirection prévue par Plane pour surcharger sans toucher le core), le faire lors d'un sync :
les conflits en `core/` coûtent le plus cher. Idéalement, envisager d'**upstreamer** la liaison GitHub (feature
générique, non-EE) via une PR sur `makeplane/plane` — si acceptée, on cesse de la maintenir.

---

## Référence rapide

| Question                               | Réponse                                                                                                         |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| On merge quoi ?                        | Un **tag stable** `vX.Y.Z` **plus récent** que la base actuelle. Jamais `preview`.                              |
| On merge où ?                          | Dans une branche `sync/vX.Y.Z`, puis `--no-ff` dans `main`.                                                     |
| Comment résoudre un conflit ?          | Garder les blocs `[FORK]`, prendre l'upstream ailleurs.                                                         |
| Comment savoir si j'ai cassé le fork ? | Le compte de marqueurs `[FORK]` ne doit pas chuter + la gate CI (étape 6) verte.                                |
| Voir toute ma divergence ?             | `grep -rn "\[FORK\]" apps packages --include="*.ts" --include="*.tsx" --include="*.py" \| grep -v node_modules` |

Détails et carte de divergence complète : voir `DEV_PLAN_WORK_ITEM_TYPES.md` §25 (mise en prod) et §26 (maintenabilité).
