"""`state` and `label` tools (per project)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from plane_fork_mcp.context import get_api
from plane_fork_mcp.tools._common import all_pages, body, compact, need, plane_errors, resolve_project, unknown

ProjectRef = Annotated[str, Field(description="Project UUID, identifier (e.g. 'WEB') or name.")]
StateGroup = Literal["backlog", "unstarted", "started", "completed", "cancelled"]

ACTIONS = ("list", "retrieve", "create", "update")


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="state",
        description=(
            "Workflow states of a project. Actions: list; retrieve(state_id); "
            "create(name, color, group, [description]); update(state_id, [name, color, group, description, default]). "
            "group is one of backlog, unstarted, started, completed, cancelled. Delete with the `delete` tool."
        ),
        annotations=ToolAnnotations(title="Workflow states", destructiveHint=False),
    )
    @plane_errors
    async def state(
        action: Literal["list", "retrieve", "create", "update"],
        project: ProjectRef,
        state_id: str | None = None,
        name: str | None = None,
        color: Annotated[str | None, Field(description="Hex color, e.g. #EF4444")] = None,
        group: StateGroup | None = None,
        description: str | None = None,
        default: bool | None = None,
    ) -> Any:
        api = get_api()
        project_id = await resolve_project(api, project)
        if action == "list":
            states = await all_pages(api, api.project(project_id, "states/"))
            return [{k: s.get(k) for k in ("id", "name", "group", "color", "default", "sequence")} for s in states]
        if action == "create":
            need(action, name=name, color=color)
            payload = body(name=name, color=color, group=group, description=description)
            return compact(await api.post(api.project(project_id, "states/"), payload))
        need(action, state_id=state_id)
        if action == "retrieve":
            return compact(await api.get(api.project(project_id, f"states/{state_id}/")))
        if action == "update":
            payload = body(name=name, color=color, group=group, description=description, default=default)
            need(action, fields=payload)
            return compact(await api.patch(api.project(project_id, f"states/{state_id}/"), payload))
        raise unknown(action, ACTIONS)

    @mcp.tool(
        name="label",
        description=(
            "Labels of a project. Actions: list; retrieve(label_id); create(name, [color, description, parent]); "
            "update(label_id, [name, color, description, parent]). Delete with the `delete` tool."
        ),
        annotations=ToolAnnotations(title="Labels", destructiveHint=False),
    )
    @plane_errors
    async def label(
        action: Literal["list", "retrieve", "create", "update"],
        project: ProjectRef,
        label_id: str | None = None,
        name: str | None = None,
        color: str | None = None,
        description: str | None = None,
        parent: Annotated[str | None, Field(description="Parent label UUID (label groups)")] = None,
    ) -> Any:
        api = get_api()
        project_id = await resolve_project(api, project)
        if action == "list":
            labels = await all_pages(api, api.project(project_id, "labels/"))
            return [{k: lb.get(k) for k in ("id", "name", "color", "parent", "description")} for lb in labels]
        if action == "create":
            need(action, name=name)
            payload = body(name=name, color=color, description=description, parent=parent)
            return compact(await api.post(api.project(project_id, "labels/"), payload))
        need(action, label_id=label_id)
        if action == "retrieve":
            return compact(await api.get(api.project(project_id, f"labels/{label_id}/")))
        if action == "update":
            payload = body(name=name, color=color, description=description, parent=parent)
            need(action, fields=payload)
            return compact(await api.patch(api.project(project_id, f"labels/{label_id}/"), payload))
        raise unknown(action, ACTIONS)
