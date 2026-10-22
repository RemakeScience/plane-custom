"""Tool behaviour against the in-memory Plane in conftest."""

from __future__ import annotations

import pytest
from conftest import (
    EPIC,
    ISSUE,
    LABEL_BUG,
    ME,
    NEW,
    OPT_HIGH,
    PROJECT,
    PROP_SEVERITY,
    STATE_TODO,
    TYPE_BUG,
    WS,
    call,
)
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

from plane_fork_mcp.server import build_http_app

P = f"workspaces/{WS}/projects/{PROJECT}/"


async def test_lists_the_expected_tools(mcp_client):
    names = {t.name for t in await mcp_client.list_tools()}
    assert names == {
        "me",
        "project",
        "workitem",
        "epic",
        "state",
        "label",
        "workitem_type",
        "workitem_property",
        "comment",
        "link",
        "cycle",
        "module",
        "intake",
        "delete",
    }


async def test_only_delete_is_destructive(mcp_client):
    destructive = {t.name for t in await mcp_client.list_tools() if t.annotations and t.annotations.destructiveHint}
    assert destructive == {"delete"}


async def test_me_lists_every_workspace_with_projects(mcp_client):
    data = await call(mcp_client, "me")
    assert data["default_workspace"] == WS
    assert {w["slug"]: [p["identifier"] for p in w["projects"]] for w in data["workspaces"]} == {
        WS: ["WEB"],
        "beta": ["OPS"],
    }


async def test_workspace_argument_targets_another_workspace(mcp_client, plane):
    data = await call(mcp_client, "state", action="list", project="OPS", workspace="Beta Corp")
    assert [s["name"] for s in data["results"]] == ["Backlog"]
    assert all(c[1].startswith(("users/", "workspaces/beta/")) for c in plane.calls)


async def test_unknown_workspace_lists_yours(mcp_client):
    with pytest.raises(ToolError, match=r"Your workspaces: acme \(Acme\), beta \(Beta Corp\)"):
        await mcp_client.call_tool("project", {"action": "list", "workspace": "nope"})


async def test_without_default_several_workspaces_must_be_chosen(mcp_client, monkeypatch):
    monkeypatch.delenv("PLANE_WORKSPACE_SLUG")
    with pytest.raises(ToolError, match="Several workspaces: pass `workspace`"):
        await mcp_client.call_tool("project", {"action": "list"})
    data = await call(mcp_client, "me")
    assert data["default_workspace"] is None


async def test_create_resolves_names_and_sets_properties(mcp_client, plane):
    item = await call(
        mcp_client,
        "workitem",
        action="create",
        project="web",
        name="New bug",
        description="**Steps**\n\n1. open",
        state="todo",
        labels=["Bug"],
        assignees=["me"],
        type_id="bug",
        properties={"Severity": "High"},
    )
    post = next(c for c in plane.calls if c[0] == "POST" and c[1] == P + "work-items/")
    assert post[3]["state"] == STATE_TODO
    assert post[3]["labels"] == [LABEL_BUG]
    assert post[3]["assignees"] == [ME]
    assert post[3]["type_id"] == TYPE_BUG
    assert "<strong>Steps</strong>" in post[3]["description_html"]
    values = next(c for c in plane.calls if c[0] == "POST" and c[1].endswith("property-values/"))
    assert values[1] == P + f"work-items/{NEW}/property-values/"
    assert values[3] == {PROP_SEVERITY: [OPT_HIGH]}
    assert item["custom_properties"] == {"Severity": "High"}


async def test_retrieve_by_identifier_strips_noise_and_names_values(mcp_client):
    item = await call(mcp_client, "workitem", action="retrieve", work_item="WEB-1")
    assert item["id"] == ISSUE
    assert "description_binary" not in item
    assert item["custom_properties"] == {"Severity": "High"}


async def test_epic_identifier_resolves_through_epics(mcp_client, plane):
    item = await call(mcp_client, "workitem", action="retrieve", work_item="WEB-7")
    assert item["id"] == EPIC
    assert item["is_epic"] is True
    assert ("GET", P + f"epics/{EPIC}/", {}, None) in plane.calls


async def test_list_filters_client_side(mcp_client, plane):
    data = await call(mcp_client, "workitem", action="list", project="WEB", state_group="unstarted", assignee="me")
    assert [r["id"] for r in data["results"]] == [ISSUE]
    assert data["total"] == 1
    listing = next(c for c in plane.calls if c[1] == P + "work-items/")
    assert listing[2]["expand"] == "state"


async def test_unfiltered_list_uses_server_pagination(mcp_client, plane):
    data = await call(mcp_client, "workitem", action="list", project="WEB", limit=10)
    assert data["total"] == 2
    listing = next(c for c in plane.calls if c[1] == P + "work-items/")
    assert listing[2]["per_page"] == "10"


async def test_epic_children(mcp_client):
    children = await call(mcp_client, "epic", action="list_children", epic="WEB-7")
    assert [c["id"] for c in children["results"]] == [ISSUE]


async def test_set_values_on_epic_uses_epic_type(mcp_client, plane):
    with pytest.raises(ToolError, match="No custom property 'Severity'"):
        await mcp_client.call_tool(
            "workitem_property", {"action": "set_values", "work_item": "WEB-7", "values": {"Severity": "High"}}
        )


async def test_unknown_state_lists_valid_ones(mcp_client):
    with pytest.raises(ToolError, match="States: Todo, Done"):
        await mcp_client.call_tool("workitem", {"action": "update", "work_item": "WEB-1", "state": "Blocked"})


async def test_delete_comment_path(mcp_client, plane):
    cid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    await call(mcp_client, "delete", resource="comment", work_item="WEB-1", id=cid)
    assert plane.calls[-1][:2] == ("DELETE", P + f"work-items/{ISSUE}/comments/{cid}/")


async def test_api_errors_become_readable_tool_errors(mcp_client):
    with pytest.raises(ToolError, match="HTTP 404"):
        await mcp_client.call_tool("workitem", {"action": "retrieve", "work_item": NEW, "project": PROJECT})


async def test_name_lookups_are_cached_until_a_write(mcp_client, plane):
    def state_lists() -> int:
        return sum(1 for c in plane.calls if c[1] == P + "states/")

    await call(mcp_client, "workitem", action="list", project="WEB", state="Todo")
    await call(mcp_client, "workitem", action="list", project="WEB", state="Todo")
    assert state_lists() == 1
    await call(mcp_client, "workitem", action="update", work_item="WEB-1", state="Done")
    await call(mcp_client, "workitem", action="list", project="WEB", state="Todo")
    assert state_lists() == 2


async def test_failure_after_create_warns_instead_of_raising(mcp_client, plane):
    original = plane.route

    def values_fail(method, path, payload):
        if method == "POST" and path.endswith("property-values/"):
            return 429, {"error_code": 5900}
        return original(method, path, payload)

    plane.route = values_fail
    item = await call(
        mcp_client, "workitem", action="create", project="WEB", name="X", type_id="Bug", properties={"Severity": "High"}
    )
    assert item["id"] == NEW
    assert "do not create it again" in item["warning"]
    assert sum(1 for c in plane.calls if c[0] == "POST" and c[1] == P + "work-items/") == 1


async def test_unknown_property_fails_before_anything_is_created(mcp_client, plane):
    with pytest.raises(ToolError, match="No custom property 'Nope'"):
        await mcp_client.call_tool(
            "workitem",
            {"action": "create", "project": "WEB", "name": "X", "type_id": "Bug", "properties": {"Nope": 1}},
        )
    assert not any(c[0] == "POST" for c in plane.calls)


async def test_short_rate_limit_is_retried_once(mcp_client, plane, monkeypatch):
    import plane_fork_mcp.client as client_module

    monkeypatch.setattr(client_module.asyncio, "sleep", _no_sleep)
    original = plane.route
    hits = {"n": 0}

    def throttled(method, path, payload):
        if path == "users/me/" and hits["n"] == 0:
            hits["n"] += 1
            return 429, {"error_code": 5900}
        return original(method, path, payload)

    plane.route = throttled
    plane.retry_after = "2"
    data = await call(mcp_client, "me")
    assert data["user"]["id"] == ME
    assert sum(1 for c in plane.calls if c[1] == "users/me/") == 2


async def _no_sleep(_: float) -> None:
    return None


def test_http_requires_a_token():
    with TestClient(build_http_app()) as client:
        assert client.get("/health").text == "ok"
        response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert response.status_code == 401
        assert response.json()["error"] == "missing_token"
