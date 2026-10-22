"""A small in-memory Plane: just enough of `/api/v1/` to drive the tools."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import pytest
from fastmcp import Client

from plane_fork_mcp import context
from plane_fork_mcp.client import clear_cache
from plane_fork_mcp.server import build_server

WS = "acme"
WS2 = "beta"
PROJECT = "11111111-1111-1111-1111-111111111111"
PROJECT2 = "11111111-1111-1111-1111-222222222222"
ME = "22222222-2222-2222-2222-222222222222"
ALICE = "22222222-2222-2222-2222-333333333333"
STATE_TODO = "33333333-3333-3333-3333-333333333333"
STATE_DONE = "33333333-3333-3333-3333-444444444444"
LABEL_BUG = "44444444-4444-4444-4444-444444444444"
TYPE_BUG = "55555555-5555-5555-5555-555555555555"
TYPE_EPIC = "55555555-5555-5555-5555-666666666666"
PROP_SEVERITY = "66666666-6666-6666-6666-666666666666"
OPT_HIGH = "77777777-7777-7777-7777-777777777777"
ISSUE = "88888888-8888-8888-8888-888888888888"
EPIC = "99999999-9999-9999-9999-999999999999"
NEW = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def paginated(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"results": rows, "total_results": len(rows), "next_page_results": False, "next_cursor": "1000:1:0"}


class FakePlane:
    def __init__(self) -> None:
        self.retry_after = "60"
        self.calls: list[tuple[str, str, dict[str, str], Any]] = []
        self.values: dict[str, dict[str, list[Any]]] = {ISSUE: {PROP_SEVERITY: [OPT_HIGH]}, EPIC: {}}
        self.items = {
            ISSUE: {
                "id": ISSUE,
                "name": "Login broken",
                "sequence_id": 1,
                "project": PROJECT,
                "state": {"id": STATE_TODO, "name": "Todo", "group": "unstarted"},
                "priority": "high",
                "type_id": TYPE_BUG,
                "parent": EPIC,
                "assignees": [ME],
                "labels": [LABEL_BUG],
                "description_binary": "AAAA",
            },
            "done": {
                "id": "done",
                "name": "Old",
                "sequence_id": 2,
                "project": PROJECT,
                "state": {"id": STATE_DONE, "name": "Done", "group": "completed"},
                "priority": "none",
                "type_id": None,
                "parent": None,
                "assignees": [],
                "labels": [],
            },
        }
        self.epics = {
            EPIC: {"id": EPIC, "name": "Auth revamp", "sequence_id": 7, "project": PROJECT, "type_id": TYPE_EPIC}
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1/")
        payload = json.loads(request.content) if request.content else None
        params = dict(request.url.params)
        self.calls.append((request.method, path, params, payload))
        assert request.headers["X-Api-Key"] == "tok"
        status, data = self.route(request.method, path, payload)
        headers = {"Retry-After": self.retry_after} if status == 429 else {}
        if data is None:
            return httpx.Response(status, headers=headers)
        return httpx.Response(status, json=data, headers=headers)

    def route(self, method: str, path: str, payload: Any) -> tuple[int, Any]:
        p = f"workspaces/{WS}/projects/{PROJECT}/"
        if path == "users/me/":
            return 200, {"id": ME, "display_name": "me", "email": "me@acme.io"}
        if path == "users/me/workspaces/":
            return 200, [
                {"id": "w1", "slug": WS, "name": "Acme", "role": 20},
                {"id": "w2", "slug": WS2, "name": "Beta Corp", "role": 15},
            ]
        if path == f"workspaces/{WS2}/projects/":
            return 200, paginated([{"id": PROJECT2, "identifier": "OPS", "name": "Operations"}])
        if path == f"workspaces/{WS2}/projects/{PROJECT2}/states/":
            return 200, paginated([{"id": STATE_TODO, "name": "Backlog", "group": "backlog"}])
        if path == f"workspaces/{WS}/projects/":
            return 200, paginated([{"id": PROJECT, "identifier": "WEB", "name": "Website"}])
        if path == f"workspaces/{WS}/work-items/WEB-1/":
            return 200, {"id": ISSUE, "project": PROJECT}
        if path.startswith(f"workspaces/{WS}/work-items/WEB-"):
            return 404, {"error": "not found"}
        if not path.startswith(p):
            return 404, {"error": f"unexpected {path}"}
        rest = path.removeprefix(p)
        if rest == "states/":
            return 200, paginated(
                [{"id": STATE_TODO, "name": "Todo", "group": "unstarted"}, {"id": STATE_DONE, "name": "Done"}]
            )
        if rest == "labels/":
            return 200, paginated([{"id": LABEL_BUG, "name": "bug"}])
        if rest == "members/":
            return 200, [{"id": ME, "email": "me@acme.io"}, {"id": ALICE, "email": "alice@acme.io"}]
        if rest == "issue-types/":
            return 200, paginated([{"id": TYPE_BUG, "name": "Bug"}])
        if rest == "epic-type/":
            return 200, {"id": TYPE_EPIC, "name": "Epic", "is_epic": True}
        if rest == f"issue-types/{TYPE_BUG}/properties/":
            return 200, paginated(
                [
                    {
                        "id": PROP_SEVERITY,
                        "name": "severity",
                        "display_name": "Severity",
                        "property_type": "OPTION",
                        "is_multi": False,
                    }
                ]
            )
        if rest == f"issue-types/{TYPE_EPIC}/properties/":
            return 200, paginated([])
        if rest == f"issue-properties/{PROP_SEVERITY}/options/":
            return 200, paginated([{"id": OPT_HIGH, "name": "High"}])
        if rest == "work-items/" and method == "GET":
            return 200, paginated(list(self.items.values()))
        if rest == "work-items/" and method == "POST":
            item = {"id": NEW, "sequence_id": 3, "project": PROJECT, **payload}
            self.items[NEW] = item
            return 201, item
        if rest == "epics/" and method == "GET":
            return 200, paginated(list(self.epics.values()))
        m = re.fullmatch(r"(work-items|epics)/([^/]+)/(property-values/|comments/([^/]+)/)?", rest)
        if m:
            kind, item_id, sub = m.group(1), m.group(2), m.group(3)
            store = self.items if kind == "work-items" else self.epics
            if sub == "property-values/":
                if method == "POST":
                    self.values.setdefault(item_id, {}).update(payload)
                return 200, self.values.get(item_id, {})
            if sub and sub.startswith("comments/") and method == "DELETE":
                return 204, None
            if item_id not in store:
                return 404, {"error": "Issue does not exist"}
            if method == "PATCH":
                store[item_id].update(payload)
            if method == "DELETE":
                return 204, None
            return 200, store[item_id]
        return 404, {"error": f"unexpected {method} {rest}"}


@pytest.fixture
def plane(monkeypatch: pytest.MonkeyPatch) -> FakePlane:
    clear_cache()
    fake = FakePlane()
    monkeypatch.setenv("PLANE_API_KEY", "tok")
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", WS)
    monkeypatch.setenv("PLANE_BASE_URL", "http://plane.test")
    monkeypatch.setattr(context, "TRANSPORT", httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture
async def mcp_client(plane: FakePlane):
    async with Client(build_server()) as client:
        yield client


async def call(client: Client, tool: str, **args: Any) -> Any:
    result = await client.call_tool(tool, args)
    if result.data is not None:
        return result.data
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)
