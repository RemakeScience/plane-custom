"""Thin async client for the fork's external API (`/api/v1/`).

Every path the server calls goes through `PlaneAPI.request`, which checks it
against `routes.ROUTES` so a typo or an endpoint the fork does not expose fails
loudly in tests instead of returning a 404 to an agent.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from plane_fork_mcp.routes import match_route

DEFAULT_TIMEOUT = float(os.getenv("PLANE_TIMEOUT", "30"))

# Name lookups (project 'WEB', state 'Done', label 'bug'...) list the same small
# collections on almost every call, and Plane rate-limits each API token
# (API_KEY_RATE_LIMIT, 60/minute by default). Those GETs are cached briefly per
# token; any write by the same token drops that token's entries.
CACHE_TTL = float(os.getenv("PLANE_CACHE_TTL", "30"))
_CACHEABLE = re.compile(
    r"(^users/me/$|/projects/$|/(states|labels|members|issue-types|epic-type|properties|options)/$)"
)
_cache: dict[tuple[str, str, tuple[tuple[str, Any], ...]], tuple[float, Any]] = {}


MAX_RETRY_WAIT = float(os.getenv("PLANE_MAX_RETRY_WAIT", "15"))


def clear_cache(api_key: str | None = None) -> None:
    for key in [k for k in _cache if api_key is None or k[0] == api_key]:
        del _cache[key]


def _retry_after(response: httpx.Response) -> float | None:
    if response.status_code != 429:
        return None
    try:
        return float(response.headers.get("Retry-After", ""))
    except ValueError:
        return None


class PlaneAPIError(Exception):
    """A non-2xx answer from Plane, with the body kept for the agent."""

    def __init__(self, status: int, method: str, path: str, body: Any):
        self.status = status
        self.method = method
        self.path = path
        self.body = body
        self.retry_after: float | None = None
        super().__init__(f"Plane API {method} {path} -> HTTP {status}: {body}")


@dataclass
class PlaneAPI:
    base_url: str
    api_key: str
    workspace_slug: str
    transport: httpx.AsyncBaseTransport | None = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url.rstrip("/") + "/api/v1/",
            headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
            timeout=DEFAULT_TIMEOUT,
            transport=self.transport,
        )

    def ws(self, suffix: str = "") -> str:
        """Path under the current workspace, e.g. ws('projects/')."""
        return f"workspaces/{self.workspace_slug}/{suffix}"

    def project(self, project_id: str, suffix: str = "") -> str:
        return self.ws(f"projects/{project_id}/{suffix}")

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        match_route(method, path)
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        cacheable = method == "GET" and CACHE_TTL > 0 and _CACHEABLE.search(path) is not None
        cache_key = (self.api_key, path, tuple(sorted(clean_params.items())))
        if cacheable:
            hit = _cache.get(cache_key)
            if hit and time.monotonic() - hit[0] < CACHE_TTL:
                return hit[1]
        elif method != "GET":
            clear_cache(self.api_key)
        result = await self._send(method, path, clean_params, json)
        if cacheable:
            _cache[cache_key] = (time.monotonic(), result)
        return result

    async def _send(self, method: str, path: str, params: dict[str, Any], json: Any) -> Any:
        async with self._client() as client:
            response = await client.request(method, path, params=params, json=json)
            # Rate limited: wait once when Plane says the window frees up soon.
            wait = _retry_after(response)
            if wait is not None and wait <= MAX_RETRY_WAIT:
                await asyncio.sleep(wait)
                response = await client.request(method, path, params=params, json=json)
        if response.status_code == 204 or not response.content:
            if response.is_success:
                return None
        try:
            body = response.json()
        except ValueError:
            body = response.text
        if not response.is_success:
            error = PlaneAPIError(response.status_code, method, path, body)
            error.retry_after = _retry_after(response)
            raise error
        return body

    async def get(self, path: str, **params: Any) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, json: Any = None) -> Any:
        return await self.request("POST", path, json=json)

    async def patch(self, path: str, json: Any = None) -> Any:
        return await self.request("PATCH", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self.request("DELETE", path)
