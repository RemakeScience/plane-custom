"""`workitem` and [FORK] `epic` tools.

An epic is a work item whose type is the project's epic type. The API only
serves epics through `/epics/` (the `work-items/` endpoints exclude them), so
the two tools share their write logic but never their read paths.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from plane_fork_mcp.client import PlaneAPI, PlaneAPIError
from plane_fork_mcp.context import get_api
from plane_fork_mcp.tools._common import (
    WORK_ITEM_LIST_FIELDS,
    WorkspaceRef,
    all_pages,
    body,
    compact,
    need,
    page,
    plane_errors,
    resolve_labels,
    resolve_members,
    resolve_project,
    resolve_state,
    resolve_work_item,
    to_html,
    unknown,
)
from plane_fork_mcp.tools.types import PropertyValues, build_values, named_values, resolve_type

Priority = Literal["urgent", "high", "medium", "low", "none"]
StateGroup = Literal["backlog", "unstarted", "started", "completed", "cancelled"]
RelationType = Literal[
    "blocking", "blocked_by", "duplicate", "relates_to", "start_before", "start_after", "finish_before", "finish_after"
]

ProjectRef = Annotated[str | None, Field(description="Project UUID, identifier (e.g. 'WEB') or name.")]
WorkItemRef = Annotated[
    str | None, Field(description="Work item UUID (then project is required) or identifier such as 'WEB-42'.")
]

WORKITEM_ACTIONS = (
    "list",
    "retrieve",
    "create",
    "update",
    "search",
    "list_children",
    "list_activity",
    "list_attachments",
    "list_relations",
    "add_relation",
)
EPIC_ACTIONS = ("list", "retrieve", "create", "update", "list_children")

# Shared write parameters (create/update) for work items and epics.
Name = Annotated[str | None, Field(description="Title")]
Description = Annotated[str | None, Field(description="Description in Markdown (converted to HTML)")]
DescriptionHtml = Annotated[str | None, Field(description="Description as raw HTML (overrides description)")]
State = Annotated[str | None, Field(description="State UUID or name, e.g. 'In Progress'")]
Assignees = Annotated[
    list[str] | None, Field(description="User UUIDs, emails or display names; 'me' is you. Replaces the list.")
]
Labels = Annotated[list[str] | None, Field(description="Label UUIDs or names. Replaces the list.")]
Parent = Annotated[str | None, Field(description="Parent work item/epic UUID or identifier; '' to clear")]
TypeRef = Annotated[str | None, Field(description="Work item type UUID or name (e.g. 'Bug')")]
Date = Annotated[str | None, Field(description="YYYY-MM-DD; '' to clear")]


async def _write_payload(
    api: PlaneAPI,
    project_id: str,
    *,
    name: str | None,
    description: str | None,
    description_html: str | None,
    state: str | None,
    priority: str | None,
    assignees: list[str] | None,
    labels: list[str] | None,
    parent: str | None,
    type_id: str | None,
    start_date: str | None,
    target_date: str | None,
) -> dict[str, Any]:
    payload = body(
        name=name,
        description_html=description_html if description_html is not None else to_html(description),
        state=await resolve_state(api, project_id, state),
        priority=priority,
        assignees=await resolve_members(api, project_id, assignees),
        labels=await resolve_labels(api, project_id, labels),
        type_id=await resolve_type(api, project_id, type_id),
        start_date=start_date,
        target_date=target_date,
    )
    if parent is not None:
        payload["parent"] = (await resolve_work_item(api, parent, project_id))[1] if parent else None
    for field in ("start_date", "target_date"):
        if payload.get(field) == "":
            payload[field] = None
    return payload


async def _list_filtered(
    api: PlaneAPI,
    path: str,
    *,
    project_id: str,
    state: str | None,
    state_group: str | None,
    assignee: str | None,
    label: str | None,
    type_id: str | None,
    priority: str | None,
    parent_id: str | None,
    order_by: str | None,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    """The v1 list endpoints take no filters, so filter here when asked to."""
    params = {"fields": WORK_ITEM_LIST_FIELDS, "expand": "state", "order_by": order_by}
    filtered = any(v is not None for v in (state, state_group, assignee, label, type_id, priority, parent_id))
    if not filtered:
        return page(await api.get(path, per_page=min(limit, 1000), cursor=cursor, **params))

    state_id = await resolve_state(api, project_id, state)
    assignee_id = (await resolve_members(api, project_id, [assignee]))[0] if assignee else None
    label_id = (await resolve_labels(api, project_id, [label]))[0] if label else None
    wanted_type = await resolve_type(api, project_id, type_id)

    def keep(item: dict[str, Any]) -> bool:
        st = item.get("state") or {}
        st_id = st.get("id") if isinstance(st, dict) else st
        return (
            (state_id is None or st_id == state_id)
            and (state_group is None or (isinstance(st, dict) and st.get("group") == state_group))
            and (assignee_id is None or assignee_id in (item.get("assignees") or []))
            and (label_id is None or label_id in (item.get("labels") or []))
            and (wanted_type is None or item.get("type_id") == wanted_type)
            and (priority is None or item.get("priority") == priority)
            and (parent_id is None or item.get("parent") == parent_id)
        )

    matches = [item for item in await all_pages(api, path, **params) if keep(item)]
    out: dict[str, Any] = {"results": compact(matches[:limit]), "total": len(matches)}
    if len(matches) > limit:
        out["truncated"] = f"Showing {limit} of {len(matches)}; raise limit or narrow the filters."
    return out


async def _children(api: PlaneAPI, project_id: str, parent_id: str) -> list[dict[str, Any]]:
    params = {"fields": WORK_ITEM_LIST_FIELDS, "expand": "state"}
    items = await all_pages(api, api.project(project_id, "work-items/"), **params)
    epics = await all_pages(api, api.project(project_id, "epics/"), **params)
    return compact([i for i in items + epics if i.get("parent") == parent_id])


async def _with_values(api: PlaneAPI, project_id: str, item: dict[str, Any]) -> dict[str, Any]:
    raw = await api.get(api.project(project_id, f"work-items/{item['id']}/property-values/"))
    item = compact(item)
    item["custom_properties"] = await named_values(api, project_id, item.get("type_id"), raw)
    return item


async def _epic_type(api: PlaneAPI, project_id: str) -> str:
    return (await api.get(api.project(project_id, "epic-type/")))["id"]


async def _default_type(api: PlaneAPI, project_id: str) -> str | None:
    types = await all_pages(api, api.project(project_id, "issue-types/"))
    return next((t["id"] for t in types if t.get("is_default")), None)


async def _save(
    api: PlaneAPI,
    project_id: str,
    send: Callable[[], Awaitable[dict[str, Any]]],
    *,
    values_type: str | None,
    properties: dict[str, Any] | None,
) -> dict[str, Any]:
    """Write a work item or epic, then its custom property values.

    Every lookup happens before the write. Once the write has succeeded this
    never raises: a failure afterwards comes back as a `warning`, so an agent
    does not retry the call and create a duplicate.
    """
    values = await build_values(api, project_id, values_type, properties) if properties else None
    item = await send()
    warning = None
    if values:
        try:
            await api.post(api.project(project_id, f"work-items/{item['id']}/property-values/"), values)
        except PlaneAPIError as exc:
            warning = (
                f"The work item was saved but its custom properties were NOT (HTTP {exc.status}: {exc.body}). "
                "Retry with action=update and only `properties`; do not create it again."
            )
    try:
        item = await _with_values(api, project_id, item)
    except PlaneAPIError as exc:
        item = compact(item)
        item["note"] = (
            f"Saved. Its custom properties could not be read back (HTTP {exc.status}); "
            "use action=retrieve later to see them."
        )
    if warning:
        item["warning"] = warning
    return item


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="workitem",
        description=(
            "Work items (tickets) — not epics, use the `epic` tool for those. Actions:\n"
            "- list(project, [state, state_group, assignee, label, type_id, priority, parent, order_by, limit, "
            "cursor]): compact rows, state expanded.\n"
            "- retrieve(work_item): full item + custom_properties.\n"
            "- create(project, name, [description, state, priority, assignees, labels, parent, type_id, "
            "start_date, target_date, properties]).\n"
            "- update(work_item, [same fields]); only the fields you pass change.\n"
            "- search(query, [project]): by title or number across the workspace.\n"
            "- list_children(work_item): sub-items.\n"
            "- list_activity / list_attachments / list_relations(work_item).\n"
            "- add_relation(work_item, relation_type, related): related is a list of UUIDs or identifiers.\n"
            "Delete with the `delete` tool. Comments and links have their own tools."
        ),
        annotations=ToolAnnotations(title="Work items", destructiveHint=False),
    )
    @plane_errors
    async def workitem(
        action: Literal[
            "list",
            "retrieve",
            "create",
            "update",
            "search",
            "list_children",
            "list_activity",
            "list_attachments",
            "list_relations",
            "add_relation",
        ],
        project: ProjectRef = None,
        work_item: WorkItemRef = None,
        name: Name = None,
        description: Description = None,
        description_html: DescriptionHtml = None,
        state: State = None,
        priority: Priority | None = None,
        assignees: Assignees = None,
        labels: Labels = None,
        parent: Parent = None,
        type_id: TypeRef = None,
        start_date: Date = None,
        target_date: Date = None,
        properties: PropertyValues = None,
        state_group: Annotated[StateGroup | None, Field(description="list filter")] = None,
        assignee: Annotated[str | None, Field(description="list filter: UUID, email, name or 'me'")] = None,
        label: Annotated[str | None, Field(description="list filter: label UUID or name")] = None,
        order_by: Annotated[str | None, Field(description="e.g. -created_at, priority, state__group")] = None,
        limit: Annotated[int, Field(ge=1, le=1000)] = 50,
        cursor: str | None = None,
        query: Annotated[str | None, Field(description="search text")] = None,
        relation_type: RelationType | None = None,
        related: Annotated[list[str] | None, Field(description="add_relation targets")] = None,
        workspace: WorkspaceRef = None,
    ) -> Any:
        api = await get_api(workspace)
        write = dict(
            name=name,
            description=description,
            description_html=description_html,
            state=state,
            priority=priority,
            assignees=assignees,
            labels=labels,
            parent=parent,
            type_id=type_id,
            start_date=start_date,
            target_date=target_date,
        )

        if action == "search":
            need(action, query=query)
            project_id = await resolve_project(api, project) if project else None
            result = await api.get(
                api.ws("work-items/search/"),
                search=query,
                limit=limit,
                project_id=project_id,
                workspace_search="false" if project_id else "true",
            )
            return [
                {
                    "id": r["id"],
                    "identifier": f"{r['project__identifier']}-{r['sequence_id']}",
                    "name": r["name"],
                    "project_id": r["project_id"],
                }
                for r in result.get("issues", [])
            ]

        if action == "list":
            project_id = await resolve_project(api, project)
            parent_id = (await resolve_work_item(api, parent, project_id))[1] if parent else None
            return await _list_filtered(
                api,
                api.project(project_id, "work-items/"),
                project_id=project_id,
                state=state,
                state_group=state_group,
                assignee=assignee,
                label=label,
                type_id=type_id,
                priority=priority,
                parent_id=parent_id,
                order_by=order_by,
                limit=limit,
                cursor=cursor,
            )

        if action == "create":
            need(action, name=name)
            project_id = await resolve_project(api, project)
            payload = await _write_payload(api, project_id, **write)
            values_type = payload.get("type_id")
            if properties and not values_type:
                values_type = await _default_type(api, project_id)
            return await _save(
                api,
                project_id,
                lambda: api.post(api.project(project_id, "work-items/"), payload),
                values_type=values_type,
                properties=properties,
            )

        project_id, issue_id = await resolve_work_item(api, work_item, project)
        wi = api.project(project_id, f"work-items/{issue_id}/")

        if action == "retrieve":
            try:
                item = await api.get(wi)
            except PlaneAPIError as exc:
                if exc.status != 404:
                    raise
                item = await api.get(api.project(project_id, f"epics/{issue_id}/"))
                item["is_epic"] = True
            return await _with_values(api, project_id, item)
        if action == "update":
            payload = await _write_payload(api, project_id, **write)
            if not payload and not properties:
                raise ToolError("Nothing to update: pass at least one field or properties.")
            values_type = payload.get("type_id")
            if properties and not values_type:
                values_type = (await api.get(wi, fields="id,type_id")).get("type_id")
            return await _save(
                api,
                project_id,
                (lambda: api.patch(wi, payload)) if payload else (lambda: api.get(wi)),
                values_type=values_type,
                properties=properties,
            )
        if action == "list_children":
            return await _children(api, project_id, issue_id)
        if action == "list_activity":
            return page(await api.get(wi + "activities/", per_page=min(limit, 1000), cursor=cursor))
        if action == "list_attachments":
            return compact(await api.get(wi + "attachments/"))
        if action == "list_relations":
            return await api.get(wi + "relations/")
        if action == "add_relation":
            need(action, relation_type=relation_type, related=related)
            ids = [(await resolve_work_item(api, ref, project_id))[1] for ref in related or []]
            return compact(await api.post(wi + "relations/", {"relation_type": relation_type, "issues": ids}))
        raise unknown(action, WORKITEM_ACTIONS)

    @mcp.tool(
        name="epic",
        description=(
            "Epics: large work items that group other work items as children. Actions:\n"
            "- list(project, [state, state_group, assignee, label, priority, order_by, limit, cursor]).\n"
            "- retrieve(epic): full epic + custom_properties.\n"
            "- create(project, name, [description, state, priority, assignees, labels, parent, start_date, "
            "target_date, properties]): the epic type is set by the server.\n"
            "- update(epic, [same fields]).\n"
            "- list_children(epic): its work items. To attach a work item to an epic, update the work item "
            "with parent=<epic>.\n"
            "Epic custom properties are defined on the epic type (workitem_property with type_id='epic'). "
            "Delete with the `delete` tool."
        ),
        annotations=ToolAnnotations(title="Epics", destructiveHint=False),
    )
    @plane_errors
    async def epic(
        action: Literal["list", "retrieve", "create", "update", "list_children"],
        project: ProjectRef = None,
        epic: Annotated[str | None, Field(description="Epic UUID (then project is required) or identifier")] = None,
        name: Name = None,
        description: Description = None,
        description_html: DescriptionHtml = None,
        state: State = None,
        priority: Priority | None = None,
        assignees: Assignees = None,
        labels: Labels = None,
        parent: Parent = None,
        start_date: Date = None,
        target_date: Date = None,
        properties: PropertyValues = None,
        state_group: Annotated[StateGroup | None, Field(description="list filter")] = None,
        assignee: Annotated[str | None, Field(description="list filter: UUID, email, name or 'me'")] = None,
        label: Annotated[str | None, Field(description="list filter: label UUID or name")] = None,
        order_by: str | None = None,
        limit: Annotated[int, Field(ge=1, le=1000)] = 50,
        cursor: str | None = None,
        workspace: WorkspaceRef = None,
    ) -> Any:
        api = await get_api(workspace)
        write = dict(
            name=name,
            description=description,
            description_html=description_html,
            state=state,
            priority=priority,
            assignees=assignees,
            labels=labels,
            parent=parent,
            type_id=None,
            start_date=start_date,
            target_date=target_date,
        )
        if action == "list":
            project_id = await resolve_project(api, project)
            return await _list_filtered(
                api,
                api.project(project_id, "epics/"),
                project_id=project_id,
                state=state,
                state_group=state_group,
                assignee=assignee,
                label=label,
                type_id=None,
                priority=priority,
                parent_id=None,
                order_by=order_by,
                limit=limit,
                cursor=cursor,
            )
        if action == "create":
            need(action, name=name)
            project_id = await resolve_project(api, project)
            payload = await _write_payload(api, project_id, **write)
            return await _save(
                api,
                project_id,
                lambda: api.post(api.project(project_id, "epics/"), payload),
                values_type=await _epic_type(api, project_id) if properties else None,
                properties=properties,
            )

        project_id, epic_id = await resolve_work_item(api, epic, project)
        path = api.project(project_id, f"epics/{epic_id}/")
        if action == "retrieve":
            return await _with_values(api, project_id, await api.get(path))
        if action == "update":
            payload = await _write_payload(api, project_id, **write)
            if not payload and not properties:
                raise ToolError("Nothing to update: pass at least one field or properties.")
            return await _save(
                api,
                project_id,
                (lambda: api.patch(path, payload)) if payload else (lambda: api.get(path)),
                values_type=await _epic_type(api, project_id) if properties else None,
                properties=properties,
            )
        if action == "list_children":
            return await _children(api, project_id, epic_id)
        raise unknown(action, EPIC_ACTIONS)
