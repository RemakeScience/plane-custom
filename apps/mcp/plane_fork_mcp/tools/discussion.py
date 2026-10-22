"""`comment` and `link` tools (on work items and epics)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from plane_fork_mcp.context import get_api
from plane_fork_mcp.tools._common import (
    WorkspaceRef,
    body,
    compact,
    need,
    page,
    plane_errors,
    resolve_work_item,
    to_html,
    unknown,
)

WorkItemRef = Annotated[str, Field(description="Work item / epic UUID (then project is required) or 'WEB-42'.")]
ProjectRef = Annotated[str | None, Field(description="Project UUID, identifier or name (needed with a UUID).")]

ACTIONS = ("list", "create", "update")


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="comment",
        description=(
            "Comments on a work item or epic. Actions: list(work_item); create(work_item, text); "
            "update(work_item, comment_id, text). text is Markdown. Delete with the `delete` tool."
        ),
        annotations=ToolAnnotations(title="Comments", destructiveHint=False),
    )
    @plane_errors
    async def comment(
        action: Literal["list", "create", "update"],
        work_item: WorkItemRef,
        project: ProjectRef = None,
        comment_id: str | None = None,
        text: Annotated[str | None, Field(description="Comment in Markdown")] = None,
        text_html: Annotated[str | None, Field(description="Comment as raw HTML (overrides text)")] = None,
        cursor: str | None = None,
        workspace: WorkspaceRef = None,
    ) -> Any:
        api = await get_api(workspace)
        project_id, issue_id = await resolve_work_item(api, work_item, project)
        base = api.project(project_id, f"work-items/{issue_id}/comments/")
        html = text_html if text_html is not None else to_html(text)
        if action == "list":
            response = page(await api.get(base, cursor=cursor))
            response["results"] = [
                {k: c.get(k) for k in ("id", "comment_html", "actor", "created_at", "updated_at", "access")}
                for c in response["results"]
            ]
            return response
        need(action, text=html)
        if action == "create":
            return compact(await api.post(base, {"comment_html": html}))
        if action == "update":
            need(action, comment_id=comment_id)
            return compact(await api.patch(f"{base}{comment_id}/", {"comment_html": html}))
        raise unknown(action, ACTIONS)

    @mcp.tool(
        name="link",
        description=(
            "External links on a work item or epic (URLs to docs, designs, PRs...). Actions: list(work_item); "
            "create(work_item, url, [title]); update(work_item, link_id, [url, title]). "
            "Delete with the `delete` tool."
        ),
        annotations=ToolAnnotations(title="Links", destructiveHint=False),
    )
    @plane_errors
    async def link(
        action: Literal["list", "create", "update"],
        work_item: WorkItemRef,
        project: ProjectRef = None,
        link_id: str | None = None,
        url: str | None = None,
        title: str | None = None,
        workspace: WorkspaceRef = None,
    ) -> Any:
        api = await get_api(workspace)
        project_id, issue_id = await resolve_work_item(api, work_item, project)
        base = api.project(project_id, f"work-items/{issue_id}/links/")
        if action == "list":
            return page(await api.get(base))
        if action == "create":
            need(action, url=url)
            return compact(await api.post(base, body(url=url, title=title)))
        if action == "update":
            need(action, link_id=link_id)
            payload = body(url=url, title=title)
            need(action, fields=payload)
            return compact(await api.patch(f"{base}{link_id}/", payload))
        raise unknown(action, ACTIONS)
