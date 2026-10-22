# Serveur MCP — Plane (fork RemakeScience)

Serveur [MCP](https://modelcontextprotocol.io) qui permet à un agent IA (Claude Code, Cursor, VS Code…) de piloter
**notre** Plane : projets, work items, **epics**, **types de work items**, **propriétés personnalisées**, cycles,
modules, commentaires, liens, intake.

Il parle uniquement à l'**API externe v1** du fork (`/api/v1/`, authentifiée par token API). Il est versionné dans
le monorepo et publié avec le même tag que les autres images (`ghcr.io/remakescience/plane-mcp:<sha>`), donc il est
toujours aligné sur l'API déployée.

> Pourquoi pas le MCP officiel `makeplane/plane-mcp-server` ? Il cible Plane commercial (endpoints `-lite`, PQL,
> API v2, `work-item-types`…) : la plupart de ses outils renvoient des 404 sur notre instance, et il ignore nos
> endpoints `epics/`, `issue-types/`, `property-values/`.

## Utiliser le MCP (collaborateurs)

Adresse : **`https://mcp.plane.glyphe.io/mcp`** (transport « streamable HTTP »).

Chacun utilise **son propre token API** : les actions sont faites en son nom, avec ses droits Plane.
**Un seul connecteur suffit pour tous ses workspaces** : le token donne accès à chaque workspace dont on est
membre, l'outil `me` les liste, et chaque outil prend un paramètre `workspace` (slug ou nom) que l'agent
renseigne selon la demande (« dans le workspace Glyphe, … »).

1. Dans Plane : **Paramètres du profil → Tokens API** (`<plane>/settings/profile/api-tokens`) → ajouter un token,
   puis le copier (`plane_api_…`).
2. Déclarer le serveur dans son client. L'en-tête `X-Workspace-Slug` est **facultatif** : il fixe le workspace
   utilisé quand l'agent n'en précise pas. Sans lui, et si l'on a plusieurs workspaces, l'agent doit en choisir
   un à chaque appel. Le slug est la partie de l'URL après le domaine (`https://plane…/<slug>/projects`).

**Claude Code**

```bash
claude mcp add --transport http plane https://mcp.plane.glyphe.io/mcp \
  --header "Authorization: Bearer plane_api_xxx" \
  --header "X-Workspace-Slug: mon-workspace"   # facultatif
```

**Cursor** (`~/.cursor/mcp.json`) / **VS Code** (`.vscode/mcp.json`, clé `servers` au lieu de `mcpServers`)

```json
{
  "mcpServers": {
    "plane": {
      "url": "https://mcp.plane.glyphe.io/mcp",
      "headers": {
        "Authorization": "Bearer plane_api_xxx",
        "X-Workspace-Slug": "mon-workspace"
      }
    }
  }
}
```

**Claude (web, Desktop, iOS, Android)** : connecteur personnalisé, sans `mcp-remote`.

1. Sur **claude.ai (web)** → Paramètres → Connecteurs → **Ajouter un connecteur personnalisé**.
   On ne peut pas l'ajouter depuis le mobile, mais il y apparaît ensuite automatiquement, de même que dans
   Claude Desktop.
2. URL : `https://mcp.plane.glyphe.io/mcp`. C'est bien `/mcp` : les chemins `/http/mcp` et `/http/api-key/mcp`
   sont ceux du MCP officiel de Plane, pas du nôtre.
3. Pas d'OAuth : notre serveur n'en propose pas. Dans la section **en-têtes de requête**, ajouter :
   - `Authorization` = `Bearer plane_api_xxx` (son propre token) ;
   - facultatif : `X-Workspace-Slug` = `mon-workspace` (workspace par défaut ; sans lui, l'agent choisit).
4. Tester dans une conversation avec le connecteur activé : « liste mes projets Plane ».

Les appels partent de l'infrastructure d'Anthropic, pas de l'appareil : le serveur doit être joignable depuis
Internet, ce qui est le cas derrière Dokploy.

Le token est un secret : ne pas le commiter (dans VS Code, préférer une variable `${input:…}`). Il donne accès à
Plane avec les droits de son propriétaire : en cas de fuite, le révoquer dans Plane. Sur une organisation Claude
Team/Enterprise où c'est un admin qui ajoute le connecteur pour tout le monde, les en-têtes seraient communs à
tous : chacun agirait alors avec le même token. Dans ce cas, que chacun ajoute plutôt son propre connecteur.

### Les outils

| Outil               | Actions                                                                                                                                                                                                                                                        |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `me`                | utilisateur courant, tous ses workspaces avec leurs projets, workspace par défaut — **à appeler en premier**                                                                                                                                                   |
| `project`           | list, retrieve, create, update, archive, unarchive, list_members                                                                                                                                                                                               |
| `workitem`          | list (filtres état/groupe/assigné/label/type/priorité/parent), retrieve, create, update, search, list_children, list_activity, list_attachments, list_relations, add_relation                                                                                  |
| `epic`              | list, retrieve, create, update, list_children                                                                                                                                                                                                                  |
| `state`, `label`    | list, retrieve, create, update                                                                                                                                                                                                                                 |
| `workitem_type`     | list, retrieve, create, update, epic_type                                                                                                                                                                                                                      |
| `workitem_property` | définitions (list, retrieve, create, update), options (list_options, create_option, update_option), valeurs (get_values, set_values)                                                                                                                           |
| `comment`, `link`   | list, create, update                                                                                                                                                                                                                                           |
| `cycle`             | list, retrieve, create, update, list/add/remove/transfer work items, archive, unarchive                                                                                                                                                                        |
| `module`            | list, retrieve, create, update, list/add/remove work items, archive, unarchive                                                                                                                                                                                 |
| `intake`            | list, retrieve, create, update (accepter, rejeter, doublon…)                                                                                                                                                                                                   |
| `delete`            | **toutes** les suppressions (work item, epic, commentaire, lien, pièce jointe, état, label, cycle, module, intake, type, propriété, option). Seul outil marqué destructif : les clients demandent confirmation. La suppression d'un projet n'est pas proposée. |

Côté agent :

- chaque outil (sauf `me`) accepte `workspace` (slug ou nom), sinon le workspace par défaut ;
- les projets acceptent un identifiant (`WEB`), un nom ou un UUID ; les work items et epics un identifiant
  (`WEB-42`) ou un UUID ;
- états, labels, assignés (`me`, email, nom), types, propriétés et options acceptent **des noms** ;
- descriptions et commentaires en **Markdown** ;
- propriétés personnalisées à la création ou à la mise à jour :
  `properties={"Sévérité": "Haute", "Story points": 3}`.

Droits : lecture = membre du projet ; **définir des types, propriétés ou options = admin du projet** ; renseigner
des valeurs, créer des epics ou des work items = membre.

## Déployer sur Dokploy

L'image est construite par `.github/workflows/build.yml` à chaque push sur `main`, comme les autres :
`ghcr.io/remakescience/plane-mcp:<sha complet>` et `:latest`.

1. Ajouter ce service au compose du stack Plane (même `APP_RELEASE` que le reste) :

   ```yaml
   mcp:
     image: ghcr.io/remakescience/plane-mcp:${APP_RELEASE:-latest}
     deploy:
       replicas: 1
       restart_policy:
         condition: any
     environment:
       PLANE_BASE_URL: http://api:8000
       # PLANE_WORKSPACE_SLUG: mon-workspace  # facultatif : défaut si ni `workspace` ni X-Workspace-Slug
     networks:
       - default
       - dokploy-network
     depends_on:
       - api
   ```

2. Dokploy → **Domains** → ajouter `mcp.plane.glyphe.io`, service **`mcp`**, port **`8000`**, HTTPS activé.
   Un enregistrement DNS `mcp.plane` vers le serveur est nécessaire.
3. **Monter la limite de requêtes de l'API** dans `plane.env` : `API_KEY_RATE_LIMIT=300/minute` (60 par défaut).
   La limite s'applique **par token**, et un appel d'outil coûte en moyenne près de 3 requêtes (recherche par nom
   comprise, malgré le cache) : avec 60/minute, un agent est bloqué au bout de quelques dizaines d'appels.
4. Vérifier : `curl https://mcp.plane.glyphe.io/health` → `ok`, puis un appel sans token → `401`.

Le serveur ne stocke aucun secret : il transmet le token de chaque appelant à l'API (en `X-Api-Key`) et ne garde
qu'un cache mémoire de 30 s des listes de référence (projets, états, labels, membres, types, propriétés, options).

Variables d'environnement :

| Variable               | Défaut            | Rôle                                                                           |
| ---------------------- | ----------------- | ------------------------------------------------------------------------------ |
| `PLANE_BASE_URL`       | `http://api:8000` | API Plane (réseau interne du stack)                                            |
| `PLANE_WORKSPACE_SLUG` | —                 | défaut quand ni l'outil (`workspace`) ni l'en-tête ne précisent de workspace   |
| `PORT`                 | `8000`            | port HTTP                                                                      |
| `PLANE_CACHE_TTL`      | `30`              | durée du cache des listes de référence (s), `0` pour désactiver                |
| `PLANE_MAX_RETRY_WAIT` | `15`              | sur un 429, réessaie une fois si Plane demande d'attendre au plus ce délai (s) |
| `PLANE_TIMEOUT`        | `30`              | timeout des appels à l'API (s)                                                 |

## Développer

```bash
cd apps/mcp
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest -q                 # contrat des routes + comportement des outils
ruff check . && ruff format --check .

# serveur local contre la stack docker-compose-local.yml
PLANE_BASE_URL=http://localhost:8000 PORT=8765 python -m plane_fork_mcp http
# ou en stdio (PLANE_API_KEY + PLANE_WORKSPACE_SLUG)
python -m plane_fork_mcp stdio
```

### Garder le MCP à jour avec l'API

- `plane_fork_mcp/routes.py` liste **chaque** `(méthode, route)` appelée. Le client refuse toute route absente
  de cette liste.
- `tests/test_routes.py` vérifie chaque entrée contre `apps/api/plane/api/urls/*.py` et les méthodes des vues
  (héritage compris). Ce job (`mcp-tests`) **conditionne la publication de toutes les images** : une modification
  de l'API v1 qui casse un outil bloque la CI.
- Nouvel endpoint v1 utile aux agents → ajouter la route dans `routes.py`, l'action dans l'outil concerné et un
  test dans `tests/test_tools.py`.
- `apps/mcp/` n'existe pas en amont : aucun conflit lors des syncs upstream (voir `UPSTREAM_SYNC.md`).
