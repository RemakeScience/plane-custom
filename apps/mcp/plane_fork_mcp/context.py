"""Who is calling, and which workspace: resolved once per tool call.

HTTP mode: every collaborator sends their own Plane API token, either as
`Authorization: Bearer <token>` or `X-Api-Key: <token>`. The server stores no
secret; Plane enforces permissions.

A token reaches every workspace its owner belongs to, so the workspace is
chosen per call: the tool's `workspace` argument (slug or name), else the
`X-Workspace-Slug` header, else `PLANE_WORKSPACE_SLUG`, else the caller's only
workspace.

stdio mode: `PLANE_API_KEY` (and optionally `PLANE_WORKSPACE_SLUG`) from the environment.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers

from plane_fork_mcp.client import PlaneAPI

# Tests swap this for an httpx.MockTransport.
TRANSPORT: httpx.AsyncBaseTransport | None = None


def base_url() -> str:
    return os.getenv("PLANE_BASE_URL", "http://api:8000")


def token_from_headers(headers: dict[str, str]) -> str | None:
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return headers.get("x-api-key") or None


def _token_and_default() -> tuple[str, str | None]:
    headers = get_http_headers(include={"authorization"})
    token = token_from_headers(headers) or os.getenv("PLANE_API_KEY")
    if not token:
        raise ToolError("Missing Plane API token: send 'Authorization: Bearer <token>' or 'X-Api-Key'.")
    return token, headers.get("x-workspace-slug") or os.getenv("PLANE_WORKSPACE_SLUG") or None


def _api(token: str, slug: str) -> PlaneAPI:
    return PlaneAPI(base_url=base_url(), api_key=token, workspace_slug=slug, transport=TRANSPORT)


async def my_workspaces() -> tuple[PlaneAPI, list[dict[str, Any]], str | None]:
    """(workspace-less client, workspaces the caller belongs to, default slug or None)."""
    token, default = _token_and_default()
    root = _api(token, "")
    return root, await root.get("users/me/workspaces/"), default


async def get_api(workspace: str | None = None) -> PlaneAPI:
    token, default = _token_and_default()
    if not workspace and default:
        return _api(token, default)
    workspaces = await _api(token, "").get("users/me/workspaces/")
    if workspace:
        wanted = workspace.strip().lower()
        for ws in workspaces:
            if wanted in (ws["slug"].lower(), str(ws["name"]).lower()):
                return _api(token, ws["slug"])
        raise ToolError(f"No workspace '{workspace}' for you. Your workspaces: {_names(workspaces)}.")
    if len(workspaces) == 1:
        return _api(token, workspaces[0]["slug"])
    raise ToolError(f"Several workspaces: pass `workspace` (slug or name). Your workspaces: {_names(workspaces)}.")


def _names(workspaces: list[dict[str, Any]]) -> str:
    return ", ".join(f"{ws['slug']} ({ws['name']})" for ws in workspaces) or "none"
