"""Builds the FastMCP server and its HTTP app."""

from __future__ import annotations

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from plane_fork_mcp import __version__
from plane_fork_mcp.context import token_from_headers
from plane_fork_mcp.tools import MODULES

INSTRUCTIONS = """\
Plane project management (RemakeScience fork): projects, work items, epics, work item types,
custom properties, cycles, modules, comments, links.

- Start with `me` to learn your workspace and project identifiers.
- Projects accept an identifier ('WEB'), a name or a UUID. Work items and epics accept an
  identifier such as 'WEB-42' or a UUID (then also pass project).
- States, labels, assignees, types, custom properties and their options accept names.
- Epics are separate: use the `epic` tool; a work item joins an epic via parent=<epic>.
- Descriptions and comments are Markdown.
- Deleting goes through the `delete` tool only: confirm with the user before calling it.
"""


def build_server() -> FastMCP:
    mcp = FastMCP("Plane (RemakeScience fork)", instructions=INSTRUCTIONS, version=__version__)
    for module in MODULES:
        module.register(mcp)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    return mcp


class RequireToken:
    """Reject MCP calls without a Plane token before they reach a tool."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] != "/health":
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            if scope["method"] != "OPTIONS" and not token_from_headers(headers):
                response = JSONResponse(
                    {
                        "error": "missing_token",
                        "detail": "Send your Plane API token as 'Authorization: Bearer <token>' "
                        "(or 'X-Api-Key') and your workspace as 'X-Workspace-Slug'.",
                    },
                    status_code=401,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def build_http_app():
    return build_server().http_app(path="/mcp", stateless_http=True, middleware=[Middleware(RequireToken)])
