"""Helpers shared by every tool module."""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import markdown as md
from fastmcp.exceptions import ToolError
from pydantic import Field

from plane_fork_mcp.client import PlaneAPI, PlaneAPIError

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
IDENTIFIER_RE = re.compile(r"^([A-Za-z0-9]+)-(\d+)$")

# Fields the API returns that only bloat an agent's context.
NOISY_FIELDS = ("description_binary",)

# Default field set for work item / epic lists: enough to triage without
# pulling every description.
WORK_ITEM_LIST_FIELDS = (
    "id,name,sequence_id,project,state,priority,type_id,parent,assignees,labels,"
    "start_date,target_date,completed_at,created_at,updated_at"
)

PRIORITIES = ("urgent", "high", "medium", "low", "none")

WorkspaceRef = Annotated[
    str | None,
    Field(description="Workspace slug or name; omit to use your default workspace (see `me`)."),
]


def plane_errors(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Turn API failures into ToolErrors an agent can read and act on.

    Also wraps bare lists as {"results": [...]}: FastMCP turns a list into one
    content block per item, so an empty list would come back as no content.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            result = await fn(*args, **kwargs)
            return {"results": result, "count": len(result)} if isinstance(result, list) else result
        except PlaneAPIError as exc:
            detail = exc.body if isinstance(exc.body, str) else json.dumps(exc.body, ensure_ascii=False)
            hint = {
                401: " The API token is missing, invalid or expired.",
                403: " Your Plane role does not allow this (type/property definitions need project admin).",
                404: " Not found: check the ids (an epic is only reachable through the `epic` tool).",
                429: " Rate limited by Plane (API_KEY_RATE_LIMIT, per token): retry in "
                f"{int(exc.retry_after or 60)} s.",
            }.get(exc.status, "")
            raise ToolError(
                f"Plane returned HTTP {exc.status} for {exc.method} /{exc.path}: {detail[:2000]}.{hint}"
            ) from exc

    return wrapper


def need(action: str, **values: Any) -> None:
    missing = [name for name, value in values.items() if value in (None, "", [])]
    if missing:
        raise ToolError(f"Action '{action}' requires: {', '.join(missing)}.")


def unknown(action: str, allowed: tuple[str, ...]) -> ToolError:
    return ToolError(f"Unknown action '{action}'. Allowed: {', '.join(allowed)}.")


def compact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: compact(v) for k, v in obj.items() if k not in NOISY_FIELDS}
    if isinstance(obj, list):
        return [compact(v) for v in obj]
    return obj


def page(response: Any) -> dict[str, Any]:
    """Reduce Plane's paginated envelope to what an agent needs."""
    if not isinstance(response, dict) or "results" not in response:
        return {"results": compact(response)}
    out: dict[str, Any] = {
        "results": compact(response["results"]),
        "total": response.get("total_results", response.get("total_count")),
    }
    if response.get("next_page_results"):
        out["next_cursor"] = response.get("next_cursor")
    return out


def body(**fields: Any) -> dict[str, Any]:
    """Request body with unset (None) fields dropped."""
    return {k: v for k, v in fields.items() if v is not None}


def to_html(markdown_text: str | None) -> str | None:
    if markdown_text is None:
        return None
    return md.markdown(markdown_text, extensions=["fenced_code", "tables", "sane_lists"])


async def all_pages(api: PlaneAPI, path: str, max_items: int = 5000, **params: Any) -> list[dict[str, Any]]:
    """Follow cursors and return every result (bounded by max_items)."""
    results: list[dict[str, Any]] = []
    cursor = None
    while True:
        response = await api.get(path, per_page=1000, cursor=cursor, **params)
        if not isinstance(response, dict):
            return list(response or [])
        results.extend(response.get("results", []))
        if not response.get("next_page_results") or len(results) >= max_items:
            return results[:max_items]
        cursor = response.get("next_cursor")


async def resolve_project(api: PlaneAPI, project: str | None) -> str:
    """Accept a project UUID, identifier (e.g. 'WEB') or exact name."""
    if not project:
        raise ToolError("project is required (UUID, identifier such as 'WEB', or name).")
    if UUID_RE.match(project):
        return project
    projects = await all_pages(api, api.ws("projects/"), fields="id,identifier,name")
    wanted = project.strip().lower()
    for p in projects:
        if str(p.get("identifier", "")).lower() == wanted or str(p.get("name", "")).lower() == wanted:
            return p["id"]
    known = ", ".join(f"{p.get('identifier')} ({p.get('name')})" for p in projects)
    raise ToolError(f"No project matches '{project}'. Projects you can see: {known or 'none'}.")


def match_row(rows: list[dict[str, Any]], ref: str, keys: tuple[str, ...]) -> dict[str, Any] | None:
    wanted = ref.strip().lower()
    for row in rows:
        if str(row.get("id", "")).lower() == wanted:
            return row
    for row in rows:
        if any(str(row.get(k) or "").lower() == wanted for k in keys):
            return row
    return None


async def resolve_state(api: PlaneAPI, project_id: str, ref: str | None) -> str | None:
    """State UUID or name (case-insensitive) -> state UUID."""
    if ref is None:
        return None
    if UUID_RE.match(ref):
        return ref
    states = await all_pages(api, api.project(project_id, "states/"))
    row = match_row(states, ref, ("name",))
    if row is None:
        raise ToolError(f"No state '{ref}'. States: {', '.join(s['name'] for s in states)}.")
    return row["id"]


async def resolve_labels(api: PlaneAPI, project_id: str, refs: list[str] | None) -> list[str] | None:
    """Label UUIDs or names -> label UUIDs."""
    if refs is None:
        return None
    if all(UUID_RE.match(r) for r in refs):
        return refs
    labels = await all_pages(api, api.project(project_id, "labels/"))
    out = []
    for ref in refs:
        row = match_row(labels, ref, ("name",))
        if row is None:
            raise ToolError(f"No label '{ref}'. Labels: {', '.join(lb['name'] for lb in labels) or 'none'}.")
        out.append(row["id"])
    return out


async def resolve_members(api: PlaneAPI, project_id: str, refs: list[str] | None) -> list[str] | None:
    """Member UUIDs, emails or display names -> user UUIDs. 'me' is the caller."""
    if refs is None:
        return None
    out = []
    members: list[dict[str, Any]] | None = None
    for ref in refs:
        if UUID_RE.match(ref):
            out.append(ref)
            continue
        if ref.lower() == "me":
            out.append((await api.get("users/me/"))["id"])
            continue
        if members is None:
            members = await all_pages(api, api.project(project_id, "members/"))
        row = match_row(members, ref, ("email", "display_name"))
        if row is None:
            raise ToolError(f"No project member '{ref}'. Use the `project` tool, action list_members.")
        out.append(row["id"])
    return out


async def resolve_work_item(api: PlaneAPI, ref: str | None, project: str | None) -> tuple[str, str]:
    """Return (project_id, issue_id) for a UUID (with project) or an identifier like 'WEB-42'.

    Identifiers also resolve epics, which the workspace lookup endpoint does not see.
    """
    if not ref:
        raise ToolError("A work item is required: its UUID (with project) or identifier such as 'WEB-42'.")
    if UUID_RE.match(ref):
        return await resolve_project(api, project), ref
    m = IDENTIFIER_RE.match(ref.strip())
    if not m:
        raise ToolError(f"'{ref}' is neither a UUID nor an identifier such as 'WEB-42'.")
    identifier, sequence = m.group(1).upper(), int(m.group(2))
    try:
        item = await api.get(api.ws(f"work-items/{identifier}-{sequence}/"), fields="id,project")
        return item["project"], item["id"]
    except PlaneAPIError as exc:
        if exc.status != 404:
            raise
    project_id = await resolve_project(api, identifier)
    for epic in await all_pages(api, api.project(project_id, "epics/"), fields="id,sequence_id"):
        if epic.get("sequence_id") == sequence:
            return project_id, epic["id"]
    raise ToolError(f"No work item or epic '{identifier}-{sequence}'.")
