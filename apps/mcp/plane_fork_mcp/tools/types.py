"""[FORK] `workitem_type` and `workitem_property` tools, plus the value helpers
the work item / epic tools use to set custom properties by name."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from plane_fork_mcp.client import PlaneAPI, PlaneAPIError
from plane_fork_mcp.context import get_api
from plane_fork_mcp.tools._common import (
    UUID_RE,
    WorkspaceRef,
    all_pages,
    body,
    compact,
    match_row,
    need,
    plane_errors,
    resolve_project,
    resolve_work_item,
    unknown,
)

ProjectRef = Annotated[str, Field(description="Project UUID, identifier (e.g. 'WEB') or name.")]
PropertyType = Literal["TEXT", "DECIMAL", "OPTION", "BOOLEAN", "DATETIME", "RELATION", "URL", "EMAIL"]

TYPE_ACTIONS = ("list", "retrieve", "create", "update", "epic_type")
PROPERTY_ACTIONS = (
    "list",
    "retrieve",
    "create",
    "update",
    "list_options",
    "create_option",
    "update_option",
    "get_values",
    "set_values",
)

PropertyValues = Annotated[
    dict[str, Any] | None,
    Field(
        description=(
            "Custom property values keyed by property id or name, e.g. "
            '{"Severity": "High", "Story points": 3}. A list sets several values on a multi property; '
            "OPTION values may be option names or ids; an empty list clears the property."
        )
    ),
]


async def resolve_type(api: PlaneAPI, project_id: str, ref: str | None) -> str | None:
    """Work item type UUID or name -> UUID. 'Epic' is not a work item type here: use the epic tool."""
    if ref is None:
        return None
    if UUID_RE.match(ref):
        return ref
    types = await all_pages(api, api.project(project_id, "issue-types/"))
    row = match_row(types, ref, ("name",))
    if row is None:
        names = ", ".join(t["name"] for t in types) or "none"
        raise ToolError(f"No work item type '{ref}'. Types: {names}. (Epics: use the `epic` tool.)")
    return row["id"]


async def type_properties(api: PlaneAPI, project_id: str, type_id: str) -> list[dict[str, Any]]:
    return await all_pages(api, api.project(project_id, f"issue-types/{type_id}/properties/"))


async def build_values(
    api: PlaneAPI, project_id: str, type_id: str | None, values: dict[str, Any]
) -> dict[str, list[Any]]:
    """Map {name-or-id: value(s)} to the API payload {property_id: [values]}."""
    if not type_id:
        raise ToolError("This work item has no type, so it has no custom properties. Set type first.")
    props = await type_properties(api, project_id, type_id)
    payload: dict[str, list[Any]] = {}
    for key, raw in values.items():
        prop = match_row(props, key, ("name", "display_name"))
        if prop is None:
            names = ", ".join(p.get("display_name") or p["name"] for p in props) or "none"
            raise ToolError(f"No custom property '{key}' on this type. Properties: {names}.")
        items = raw if isinstance(raw, list) else [raw]
        if prop["property_type"] == "OPTION" and items:
            options = await all_pages(api, api.project(project_id, f"issue-properties/{prop['id']}/options/"))
            resolved = []
            for item in items:
                option = match_row(options, str(item), ("name",))
                if option is None:
                    names = ", ".join(o["name"] for o in options) or "none"
                    raise ToolError(f"'{item}' is not an option of '{key}'. Options: {names}.")
                resolved.append(option["id"])
            items = resolved
        payload[prop["id"]] = items
    return payload


async def named_values(api: PlaneAPI, project_id: str, type_id: str | None, raw: dict[str, Any]) -> dict[str, Any]:
    """Make GET property-values readable: {display name: values}, option ids -> names."""
    if not type_id or not raw:
        return raw or {}
    props = {p["id"]: p for p in await type_properties(api, project_id, type_id)}
    out: dict[str, Any] = {}
    for prop_id, values in raw.items():
        prop = props.get(prop_id)
        if prop is None:
            out[prop_id] = values
            continue
        if prop["property_type"] == "OPTION":
            options = await all_pages(api, api.project(project_id, f"issue-properties/{prop_id}/options/"))
            by_id = {o["id"]: o["name"] for o in options}
            values = [by_id.get(v, v) for v in values]
        label = prop.get("display_name") or prop["name"]
        out[label] = values if prop.get("is_multi") else (values[0] if values else None)
    return out


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="workitem_type",
        description=(
            "Work item types of a project (e.g. Bug, Story). Actions: list; retrieve(type_id); "
            "create(name, [description]); update(type_id, [name, description, is_active, is_default]); "
            "epic_type -> the project's epic type. Creating/updating types needs project admin. "
            "Epics are not listed here: use the `epic` tool. Delete with the `delete` tool."
        ),
        annotations=ToolAnnotations(title="Work item types", destructiveHint=False),
    )
    @plane_errors
    async def workitem_type(
        action: Literal["list", "retrieve", "create", "update", "epic_type"],
        project: ProjectRef,
        type_id: Annotated[str | None, Field(description="Type UUID or name")] = None,
        name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        is_default: bool | None = None,
        workspace: WorkspaceRef = None,
    ) -> Any:
        api = await get_api(workspace)
        project_id = await resolve_project(api, project)
        if action == "list":
            return compact(await all_pages(api, api.project(project_id, "issue-types/")))
        if action == "epic_type":
            return compact(await api.get(api.project(project_id, "epic-type/")))
        if action == "create":
            need(action, name=name)
            payload = body(name=name, description=description, is_active=is_active, is_default=is_default)
            return compact(await api.post(api.project(project_id, "issue-types/"), payload))
        need(action, type_id=type_id)
        resolved = await resolve_type(api, project_id, type_id)
        if action == "retrieve":
            return compact(await api.get(api.project(project_id, f"issue-types/{resolved}/")))
        if action == "update":
            payload = body(name=name, description=description, is_active=is_active, is_default=is_default)
            need(action, fields=payload)
            return compact(await api.patch(api.project(project_id, f"issue-types/{resolved}/"), payload))
        raise unknown(action, TYPE_ACTIONS)

    @mcp.tool(
        name="workitem_property",
        description=(
            "Custom properties. Definitions belong to a work item type (or the epic type): "
            "list(type_id); retrieve(type_id, property_id); "
            "create(type_id, display_name, property_type, [description, is_required, is_multi, relation_type, "
            "default_value, settings]); update(type_id, property_id, [...]). "
            "Options of an OPTION property: list_options(property_id); create_option(property_id, name, "
            "[is_default]); update_option(property_id, option_id, [name, is_default, is_active]). "
            "Values on a work item or epic: get_values(work_item); set_values(work_item, values). "
            "Definitions and options need project admin; values only need membership. "
            "type_id accepts a type name, or 'epic' for the epic type."
        ),
        annotations=ToolAnnotations(title="Custom properties", destructiveHint=False),
    )
    @plane_errors
    async def workitem_property(
        action: Literal[
            "list",
            "retrieve",
            "create",
            "update",
            "list_options",
            "create_option",
            "update_option",
            "get_values",
            "set_values",
        ],
        project: Annotated[str | None, Field(description="Project UUID, identifier or name")] = None,
        type_id: Annotated[str | None, Field(description="Type UUID or name, or 'epic'")] = None,
        property_id: str | None = None,
        option_id: str | None = None,
        work_item: Annotated[str | None, Field(description="Work item / epic UUID or identifier like 'WEB-42'")] = None,
        values: PropertyValues = None,
        display_name: str | None = None,
        name: str | None = None,
        property_type: PropertyType | None = None,
        relation_type: Annotated[Literal["ISSUE", "MEMBER"] | None, Field(description="For RELATION")] = None,
        description: str | None = None,
        is_required: bool | None = None,
        is_multi: bool | None = None,
        is_active: bool | None = None,
        is_default: bool | None = None,
        default_value: list[Any] | None = None,
        settings: dict[str, Any] | None = None,
        workspace: WorkspaceRef = None,
    ) -> Any:
        api = await get_api(workspace)

        if action in ("get_values", "set_values"):
            project_id, issue_id = await resolve_work_item(api, work_item, project)
            item_type = await _work_item_type(api, project_id, issue_id)
            path = api.project(project_id, f"work-items/{issue_id}/property-values/")
            if action == "get_values":
                return await named_values(api, project_id, item_type, await api.get(path))
            need(action, values=values)
            payload = await build_values(api, project_id, item_type, values or {})
            return await named_values(api, project_id, item_type, await api.post(path, payload))

        project_id = await resolve_project(api, project)

        if action in ("list_options", "create_option", "update_option"):
            need(action, property_id=property_id)
            base = f"issue-properties/{property_id}/options/"
            if action == "list_options":
                return compact(await all_pages(api, api.project(project_id, base)))
            if action == "create_option":
                need(action, name=name)
                payload = body(name=name, description=description, is_default=is_default, is_active=is_active)
                return compact(await api.post(api.project(project_id, base), payload))
            need(action, option_id=option_id)
            payload = body(name=name, description=description, is_default=is_default, is_active=is_active)
            need(action, fields=payload)
            return compact(await api.patch(api.project(project_id, f"{base}{option_id}/"), payload))

        need(action, type_id=type_id)
        if str(type_id).lower() == "epic":
            resolved_type = (await api.get(api.project(project_id, "epic-type/")))["id"]
        else:
            resolved_type = await resolve_type(api, project_id, type_id)
        base = f"issue-types/{resolved_type}/properties/"
        definition = body(
            display_name=display_name,
            name=name,
            property_type=property_type,
            relation_type=relation_type,
            description=description,
            is_required=is_required,
            is_multi=is_multi,
            is_active=is_active,
            default_value=default_value,
            settings=settings,
        )
        if action == "list":
            return compact(await all_pages(api, api.project(project_id, base)))
        if action == "create":
            need(action, display_name=display_name, property_type=property_type)
            definition.setdefault("name", display_name)
            return compact(await api.post(api.project(project_id, base), definition))
        need(action, property_id=property_id)
        if action == "retrieve":
            return compact(await api.get(api.project(project_id, f"{base}{property_id}/")))
        if action == "update":
            need(action, fields=definition)
            return compact(await api.patch(api.project(project_id, f"{base}{property_id}/"), definition))
        raise unknown(action, PROPERTY_ACTIONS)


async def _work_item_type(api: PlaneAPI, project_id: str, issue_id: str) -> str | None:
    """type_id of a work item, falling back to the epics endpoint for epics."""
    try:
        item = await api.get(api.project(project_id, f"work-items/{issue_id}/"), fields="id,type_id")
    except PlaneAPIError as exc:
        if exc.status != 404:
            raise
        item = await api.get(api.project(project_id, f"epics/{issue_id}/"), fields="id,type_id")
    return item.get("type_id")
