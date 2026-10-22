"""`me` and `project` tools."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from plane_fork_mcp.client import PlaneAPIError
from plane_fork_mcp.context import get_api, my_workspaces
from plane_fork_mcp.tools._common import (
    WorkspaceRef,
    all_pages,
    body,
    compact,
    need,
    plane_errors,
    resolve_project,
    unknown,
)

ProjectRef = Annotated[str | None, Field(description="Project UUID, identifier (e.g. 'WEB') or name.")]

PROJECT_ACTIONS = ("list", "retrieve", "create", "update", "archive", "unarchive", "list_members")


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="me",
        description=(
            "Who you are in Plane: the authenticated user, every workspace you belong to with its projects "
            "(id, identifier, name), and the default workspace. Call this first. Every other tool takes an "
            "optional `workspace` (slug or name); without it, the default workspace is used."
        ),
        annotations=ToolAnnotations(title="Current user & workspaces", readOnlyHint=True),
    )
    @plane_errors
    async def me() -> dict[str, Any]:
        root, workspaces, default = await my_workspaces()
        if default is None and len(workspaces) == 1:
            default = workspaces[0]["slug"]
        user = await root.get("users/me/")
        out = []
        for ws in workspaces:
            api = await get_api(ws["slug"])
            try:
                projects = await all_pages(api, api.ws("projects/"), fields="id,identifier,name,archived_at")
            except PlaneAPIError as exc:
                projects = f"unavailable (HTTP {exc.status})"
            out.append({"slug": ws["slug"], "name": ws["name"], "role": ws["role"], "projects": projects})
        return {
            "user": {k: user.get(k) for k in ("id", "display_name", "email", "first_name", "last_name")},
            "default_workspace": default,
            "workspaces": out,
        }

    @mcp.tool(
        name="project",
        description=(
            "Projects. Actions: list; retrieve(project); create(name, identifier, [description, network]); "
            "update(project, [name, identifier, description, network]); archive(project); unarchive(project); "
            "list_members(project) -> users you can assign. network: 0 = secret, 2 = public."
        ),
        annotations=ToolAnnotations(title="Projects", destructiveHint=False),
    )
    @plane_errors
    async def project(
        action: Literal["list", "retrieve", "create", "update", "archive", "unarchive", "list_members"],
        project: ProjectRef = None,
        name: str | None = None,
        identifier: Annotated[str | None, Field(description="Short uppercase key used in ids, e.g. 'WEB'.")] = None,
        description: str | None = None,
        network: Annotated[int | None, Field(description="0 = secret, 2 = public")] = None,
        workspace: WorkspaceRef = None,
    ) -> Any:
        api = await get_api(workspace)
        if action == "list":
            return compact(await all_pages(api, api.ws("projects/")))
        if action == "create":
            need(action, name=name, identifier=identifier)
            payload = body(name=name, identifier=identifier, description=description, network=network)
            return compact(await api.post(api.ws("projects/"), payload))
        project_id = await resolve_project(api, project)
        if action == "retrieve":
            return compact(await api.get(api.ws(f"projects/{project_id}/")))
        if action == "update":
            payload = body(name=name, identifier=identifier, description=description, network=network)
            need(action, fields=payload)
            return compact(await api.patch(api.ws(f"projects/{project_id}/"), payload))
        if action == "archive":
            await api.post(api.project(project_id, "archive/"))
            return {"archived": project_id}
        if action == "unarchive":
            await api.delete(api.project(project_id, "archive/"))
            return {"unarchived": project_id}
        if action == "list_members":
            members = await all_pages(api, api.project(project_id, "members/"))
            return [{k: m.get(k) for k in ("id", "display_name", "email", "first_name", "last_name")} for m in members]
        raise unknown(action, PROJECT_ACTIONS)
