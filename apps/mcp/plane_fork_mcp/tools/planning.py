"""`cycle`, `module` and `intake` tools."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from plane_fork_mcp.client import PlaneAPI
from plane_fork_mcp.context import get_api
from plane_fork_mcp.tools._common import (
    WORK_ITEM_LIST_FIELDS,
    all_pages,
    body,
    compact,
    need,
    page,
    plane_errors,
    resolve_members,
    resolve_project,
    resolve_work_item,
    to_html,
    unknown,
)

ProjectRef = Annotated[str, Field(description="Project UUID, identifier (e.g. 'WEB') or name.")]
WorkItems = Annotated[list[str] | None, Field(description="Work item UUIDs or identifiers such as 'WEB-42'")]

CYCLE_ACTIONS = (
    "list",
    "retrieve",
    "create",
    "update",
    "list_workitems",
    "add_workitems",
    "remove_workitem",
    "transfer_workitems",
    "archive",
    "unarchive",
)
MODULE_ACTIONS = (
    "list",
    "retrieve",
    "create",
    "update",
    "list_workitems",
    "add_workitems",
    "remove_workitem",
    "archive",
    "unarchive",
)
INTAKE_ACTIONS = ("list", "retrieve", "create", "update")
INTAKE_STATUS = {"pending": -2, "rejected": -1, "snoozed": 0, "accepted": 1, "duplicate": 2}

CYCLE_FIELDS = "id,name,description,start_date,end_date,status,owned_by,total_issues,completed_issues,archived_at"
MODULE_FIELDS = "id,name,description,start_date,target_date,status,lead,members,total_issues,completed_issues"


async def _issue_ids(api: PlaneAPI, project_id: str, refs: list[str] | None) -> list[str]:
    return [(await resolve_work_item(api, ref, project_id))[1] for ref in refs or []]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="cycle",
        description=(
            "Cycles (sprints). Actions: list([view]); retrieve(cycle_id); "
            "create(name, [description, start_date, end_date]) — give both dates or neither; "
            "update(cycle_id, [name, description, start_date, end_date]); list_workitems(cycle_id); "
            "add_workitems(cycle_id, work_items); remove_workitem(cycle_id, work_item); "
            "transfer_workitems(cycle_id, new_cycle_id) moves unfinished items; archive / unarchive(cycle_id). "
            "view: all, current, upcoming, completed, draft, incomplete. Delete with the `delete` tool."
        ),
        annotations=ToolAnnotations(title="Cycles", destructiveHint=False),
    )
    @plane_errors
    async def cycle(
        action: Literal[
            "list",
            "retrieve",
            "create",
            "update",
            "list_workitems",
            "add_workitems",
            "remove_workitem",
            "transfer_workitems",
            "archive",
            "unarchive",
        ],
        project: ProjectRef,
        cycle_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        view: Literal["all", "current", "upcoming", "completed", "draft", "incomplete"] | None = None,
        work_items: WorkItems = None,
        work_item: Annotated[str | None, Field(description="UUID or identifier")] = None,
        new_cycle_id: str | None = None,
        cursor: str | None = None,
    ) -> Any:
        api = get_api()
        project_id = await resolve_project(api, project)
        if action == "list":
            return page(await api.get(api.project(project_id, "cycles/"), cycle_view=view, fields=CYCLE_FIELDS))
        if action == "create":
            need(action, name=name)
            payload = body(name=name, description=description, start_date=start_date, end_date=end_date)
            return compact(await api.post(api.project(project_id, "cycles/"), payload))
        need(action, cycle_id=cycle_id)
        base = api.project(project_id, f"cycles/{cycle_id}/")
        if action == "retrieve":
            return compact(await api.get(base))
        if action == "update":
            payload = body(name=name, description=description, start_date=start_date, end_date=end_date)
            need(action, fields=payload)
            return compact(await api.patch(base, payload))
        if action == "list_workitems":
            return page(
                await api.get(base + "cycle-issues/", cursor=cursor, fields=WORK_ITEM_LIST_FIELDS, expand="state")
            )
        if action == "add_workitems":
            need(action, work_items=work_items)
            ids = await _issue_ids(api, project_id, work_items)
            return compact(await api.post(base + "cycle-issues/", {"issues": ids}))
        if action == "remove_workitem":
            need(action, work_item=work_item)
            issue_id = (await resolve_work_item(api, work_item, project_id))[1]
            await api.delete(base + f"cycle-issues/{issue_id}/")
            return {"removed": issue_id, "cycle": cycle_id}
        if action == "transfer_workitems":
            need(action, new_cycle_id=new_cycle_id)
            return await api.post(base + "transfer-issues/", {"new_cycle_id": new_cycle_id})
        if action == "archive":
            await api.post(base + "archive/")
            return {"archived": cycle_id}
        if action == "unarchive":
            await api.delete(api.project(project_id, f"archived-cycles/{cycle_id}/unarchive/"))
            return {"unarchived": cycle_id}
        raise unknown(action, CYCLE_ACTIONS)

    @mcp.tool(
        name="module",
        description=(
            "Modules (feature areas / workstreams). Actions: list; retrieve(module_id); "
            "create(name, [description, start_date, target_date, status, lead, members]); "
            "update(module_id, [same fields]); list_workitems(module_id); add_workitems(module_id, work_items); "
            "remove_workitem(module_id, work_item); archive / unarchive(module_id). "
            "status: backlog, planned, in-progress, paused, completed, cancelled. Delete with the `delete` tool."
        ),
        annotations=ToolAnnotations(title="Modules", destructiveHint=False),
    )
    @plane_errors
    async def module(
        action: Literal[
            "list",
            "retrieve",
            "create",
            "update",
            "list_workitems",
            "add_workitems",
            "remove_workitem",
            "archive",
            "unarchive",
        ],
        project: ProjectRef,
        module_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        start_date: str | None = None,
        target_date: str | None = None,
        status: Literal["backlog", "planned", "in-progress", "paused", "completed", "cancelled"] | None = None,
        lead: Annotated[str | None, Field(description="UUID, email, name or 'me'")] = None,
        members: Annotated[list[str] | None, Field(description="UUIDs, emails, names or 'me'")] = None,
        work_items: WorkItems = None,
        work_item: Annotated[str | None, Field(description="UUID or identifier")] = None,
        cursor: str | None = None,
    ) -> Any:
        api = get_api()
        project_id = await resolve_project(api, project)

        async def payload() -> dict[str, Any]:
            lead_id = (await resolve_members(api, project_id, [lead]))[0] if lead else None
            return body(
                name=name,
                description=description,
                start_date=start_date,
                target_date=target_date,
                status=status,
                lead=lead_id,
                members=await resolve_members(api, project_id, members),
            )

        if action == "list":
            return compact(await all_pages(api, api.project(project_id, "modules/"), fields=MODULE_FIELDS))
        if action == "create":
            need(action, name=name)
            return compact(await api.post(api.project(project_id, "modules/"), await payload()))
        need(action, module_id=module_id)
        base = api.project(project_id, f"modules/{module_id}/")
        if action == "retrieve":
            return compact(await api.get(base))
        if action == "update":
            data = await payload()
            need(action, fields=data)
            return compact(await api.patch(base, data))
        if action == "list_workitems":
            return page(
                await api.get(base + "module-issues/", cursor=cursor, fields=WORK_ITEM_LIST_FIELDS, expand="state")
            )
        if action == "add_workitems":
            need(action, work_items=work_items)
            ids = await _issue_ids(api, project_id, work_items)
            return compact(await api.post(base + "module-issues/", {"issues": ids}))
        if action == "remove_workitem":
            need(action, work_item=work_item)
            issue_id = (await resolve_work_item(api, work_item, project_id))[1]
            await api.delete(base + f"module-issues/{issue_id}/")
            return {"removed": issue_id, "module": module_id}
        if action == "archive":
            await api.post(base + "archive/")
            return {"archived": module_id}
        if action == "unarchive":
            await api.delete(api.project(project_id, f"archived-modules/{module_id}/unarchive/"))
            return {"unarchived": module_id}
        raise unknown(action, MODULE_ACTIONS)

    @mcp.tool(
        name="intake",
        description=(
            "Intake (triage queue) of a project, if enabled. Actions: list; retrieve(issue_id); "
            "create(name, [description, priority]); update(issue_id, [status, name, description, priority, "
            "duplicate_to]). status: pending, accepted, rejected, snoozed, duplicate. Delete with the `delete` tool."
        ),
        annotations=ToolAnnotations(title="Intake", destructiveHint=False),
    )
    @plane_errors
    async def intake(
        action: Literal["list", "retrieve", "create", "update"],
        project: ProjectRef,
        issue_id: Annotated[str | None, Field(description="The intake work item's issue UUID")] = None,
        name: str | None = None,
        description: Annotated[str | None, Field(description="Markdown")] = None,
        priority: Literal["urgent", "high", "medium", "low", "none"] | None = None,
        status: Literal["pending", "accepted", "rejected", "snoozed", "duplicate"] | None = None,
        duplicate_to: Annotated[str | None, Field(description="Work item UUID or identifier")] = None,
        cursor: str | None = None,
    ) -> Any:
        api = get_api()
        project_id = await resolve_project(api, project)
        base = api.project(project_id, "intake-issues/")
        issue = body(name=name, description_html=to_html(description), priority=priority)
        if action == "list":
            return page(await api.get(base, cursor=cursor))
        if action == "create":
            need(action, name=name)
            return compact(await api.post(base, {"issue": issue}))
        need(action, issue_id=issue_id)
        if action == "retrieve":
            return compact(await api.get(f"{base}{issue_id}/"))
        if action == "update":
            data: dict[str, Any] = {}
            if status is not None:
                data["status"] = INTAKE_STATUS[status]
            if duplicate_to:
                data["duplicate_to"] = (await resolve_work_item(api, duplicate_to, project_id))[1]
            if issue:
                data["issue"] = issue
            need(action, fields=data)
            return compact(await api.patch(f"{base}{issue_id}/", data))
        raise unknown(action, INTAKE_ACTIONS)
