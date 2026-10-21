"""Who is calling, and which workspace: resolved once per tool call.

HTTP mode: every collaborator sends their own Plane API token, either as
`Authorization: Bearer <token>` or `X-Api-Key: <token>`, plus the workspace in
`X-Workspace-Slug`. The server stores no secret; Plane enforces permissions.

stdio mode: `PLANE_API_KEY` and `PLANE_WORKSPACE_SLUG` from the environment.
"""

from __future__ import annotations

import os

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


def get_api() -> PlaneAPI:
    headers = get_http_headers(include={"authorization"})
    token = token_from_headers(headers) or os.getenv("PLANE_API_KEY")
    slug = headers.get("x-workspace-slug") or os.getenv("PLANE_WORKSPACE_SLUG")
    if not token:
        raise ToolError("Missing Plane API token: send 'Authorization: Bearer <token>' or 'X-Api-Key'.")
    if not slug:
        raise ToolError("Missing workspace: send the 'X-Workspace-Slug' header.")
    return PlaneAPI(base_url=base_url(), api_key=token, workspace_slug=slug, transport=TRANSPORT)
