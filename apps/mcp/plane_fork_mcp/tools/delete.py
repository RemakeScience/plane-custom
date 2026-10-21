"""`delete`: every destructive operation lives in this one tool.

Keeping deletes out of the other tools lets clients auto-approve everything
else and still ask before anything is removed (destructiveHint). Deleting a
whole project is deliberately not offered.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from plane_fork_mcp.context import get_api
from plane_fork_mcp.tools._common import need, plane_errors, resolve_project, resolve_work_item
from plane_fork_mcp.tools.types import resolve_type

Resource = Literal[
    "workitem",
    "epic",
    "comment",
    "link",
    "attachment",
    "state",
    "label",
    "cycle",
    "module",
    "intake",
    "workitem_type",
    "property",
    "property_option",
]

# Resources that live under a work item: resource -> sub-collection.
ON_WORK_ITEM = {"comment": "comments", "link": "links", "attachment": "attachments"}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="delete",
        description=(
            "Permanently delete something. Irreversible: confirm with the user first.\n"
            "- workitem / epic: work_item.\n"
            "- comment / link / attachment: work_item + id.\n"
            "- state / label / cycle / module / workitem_type: project + id "
            "(workitem_type id may be a name).\n"
            "- intake: project + id (the intake work item's issue id).\n"
            "- property: project + type_id (name, or 'epic') + id.\n"
            "- property_option: project + property_id + id.\n"
            "Projects cannot be deleted through this server."
        ),
        annotations=ToolAnnotations(title="Delete", destructiveHint=True, idempotentHint=True),
    )
    @plane_errors
    async def delete(
        resource: Resource,
        project: Annotated[str | None, Field(description="Project UUID, identifier or name")] = None,
        id: Annotated[str | None, Field(description="Id of the thing to delete")] = None,
        work_item: Annotated[str | None, Field(description="Work item / epic UUID or identifier")] = None,
        type_id: str | None = None,
        property_id: str | None = None,
    ) -> Any:
        api = get_api()

        if resource in ("workitem", "epic"):
            project_id, issue_id = await resolve_work_item(api, work_item or id, project)
            kind = "work-items" if resource == "workitem" else "epics"
            await api.delete(api.project(project_id, f"{kind}/{issue_id}/"))
            return {"deleted": resource, "id": issue_id}

        if resource in ON_WORK_ITEM:
            need(resource, work_item=work_item, id=id)
            project_id, issue_id = await resolve_work_item(api, work_item, project)
            await api.delete(api.project(project_id, f"work-items/{issue_id}/{ON_WORK_ITEM[resource]}/{id}/"))
            return {"deleted": resource, "id": id, "work_item": issue_id}

        need(resource, project=project, id=id)
        project_id = await resolve_project(api, project)
        if resource == "workitem_type":
            path = f"issue-types/{await resolve_type(api, project_id, id)}/"
        elif resource == "property":
            need(resource, type_id=type_id)
            if str(type_id).lower() == "epic":
                resolved_type = (await api.get(api.project(project_id, "epic-type/")))["id"]
            else:
                resolved_type = await resolve_type(api, project_id, type_id)
            path = f"issue-types/{resolved_type}/properties/{id}/"
        elif resource == "property_option":
            need(resource, property_id=property_id)
            path = f"issue-properties/{property_id}/options/{id}/"
        else:
            collection = {
                "state": "states",
                "label": "labels",
                "cycle": "cycles",
                "module": "modules",
                "intake": "intake-issues",
            }[resource]
            path = f"{collection}/{id}/"
        await api.delete(api.project(project_id, path))
        return {"deleted": resource, "id": id}
