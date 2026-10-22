"""Every (method, path) the MCP server calls on the fork's `/api/v1/`.

This is the contract between the MCP server and the API. `tests/test_routes.py`
checks each entry against the Django URL conf and view methods in
`apps/api/plane/api/`, so an API change that breaks a tool fails CI.

Placeholders use Django's converter names so the comparison is literal.
"""

from __future__ import annotations

import re

W = "workspaces/<str:slug>/"
P = W + "projects/<uuid:project_id>/"
WI = P + "work-items/<uuid:issue_id>/"

ROUTES: tuple[tuple[str, str], ...] = (
    # user
    ("GET", "users/me/"),
    ("GET", "users/me/workspaces/"),  # [FORK] mcp-server
    # workspace
    ("GET", W + "members/"),
    ("GET", W + "work-items/search/"),
    ("GET", W + "work-items/<str:project_identifier>-<str:issue_identifier>/"),
    # projects
    ("GET", W + "projects/"),
    ("POST", W + "projects/"),
    ("GET", W + "projects/<uuid:pk>/"),
    ("PATCH", W + "projects/<uuid:pk>/"),
    ("POST", P + "archive/"),
    ("DELETE", P + "archive/"),
    ("GET", P + "members/"),
    # states
    ("GET", P + "states/"),
    ("POST", P + "states/"),
    ("GET", P + "states/<uuid:state_id>/"),
    ("PATCH", P + "states/<uuid:state_id>/"),
    ("DELETE", P + "states/<uuid:state_id>/"),
    # labels
    ("GET", P + "labels/"),
    ("POST", P + "labels/"),
    ("GET", P + "labels/<uuid:pk>/"),
    ("PATCH", P + "labels/<uuid:pk>/"),
    ("DELETE", P + "labels/<uuid:pk>/"),
    # work items
    ("GET", P + "work-items/"),
    ("POST", P + "work-items/"),
    ("GET", P + "work-items/<uuid:pk>/"),
    ("PATCH", P + "work-items/<uuid:pk>/"),
    ("DELETE", P + "work-items/<uuid:pk>/"),
    ("GET", WI + "activities/"),
    ("GET", WI + "attachments/"),
    ("DELETE", WI + "attachments/<uuid:pk>/"),
    ("GET", WI + "relations/"),
    ("POST", WI + "relations/"),
    ("GET", WI + "comments/"),
    ("POST", WI + "comments/"),
    ("PATCH", WI + "comments/<uuid:pk>/"),
    ("DELETE", WI + "comments/<uuid:pk>/"),
    ("GET", WI + "links/"),
    ("POST", WI + "links/"),
    ("PATCH", WI + "links/<uuid:pk>/"),
    ("DELETE", WI + "links/<uuid:pk>/"),
    # [FORK] epics
    ("GET", P + "epics/"),
    ("POST", P + "epics/"),
    ("GET", P + "epics/<uuid:pk>/"),
    ("PATCH", P + "epics/<uuid:pk>/"),
    ("DELETE", P + "epics/<uuid:pk>/"),
    ("GET", P + "epic-type/"),
    # [FORK] work item types
    ("GET", P + "issue-types/"),
    ("POST", P + "issue-types/"),
    ("GET", P + "issue-types/<uuid:pk>/"),
    ("PATCH", P + "issue-types/<uuid:pk>/"),
    ("DELETE", P + "issue-types/<uuid:pk>/"),
    # [FORK] custom properties
    ("GET", P + "issue-types/<uuid:type_id>/properties/"),
    ("POST", P + "issue-types/<uuid:type_id>/properties/"),
    ("GET", P + "issue-types/<uuid:type_id>/properties/<uuid:pk>/"),
    ("PATCH", P + "issue-types/<uuid:type_id>/properties/<uuid:pk>/"),
    ("DELETE", P + "issue-types/<uuid:type_id>/properties/<uuid:pk>/"),
    ("GET", P + "issue-properties/<uuid:property_id>/options/"),
    ("POST", P + "issue-properties/<uuid:property_id>/options/"),
    ("PATCH", P + "issue-properties/<uuid:property_id>/options/<uuid:pk>/"),
    ("DELETE", P + "issue-properties/<uuid:property_id>/options/<uuid:pk>/"),
    ("GET", WI + "property-values/"),
    ("POST", WI + "property-values/"),
    # cycles
    ("GET", P + "cycles/"),
    ("POST", P + "cycles/"),
    ("GET", P + "cycles/<uuid:pk>/"),
    ("PATCH", P + "cycles/<uuid:pk>/"),
    ("DELETE", P + "cycles/<uuid:pk>/"),
    ("GET", P + "cycles/<uuid:cycle_id>/cycle-issues/"),
    ("POST", P + "cycles/<uuid:cycle_id>/cycle-issues/"),
    ("DELETE", P + "cycles/<uuid:cycle_id>/cycle-issues/<uuid:issue_id>/"),
    ("POST", P + "cycles/<uuid:cycle_id>/transfer-issues/"),
    ("POST", P + "cycles/<uuid:cycle_id>/archive/"),
    ("DELETE", P + "archived-cycles/<uuid:cycle_id>/unarchive/"),
    # modules
    ("GET", P + "modules/"),
    ("POST", P + "modules/"),
    ("GET", P + "modules/<uuid:pk>/"),
    ("PATCH", P + "modules/<uuid:pk>/"),
    ("DELETE", P + "modules/<uuid:pk>/"),
    ("GET", P + "modules/<uuid:module_id>/module-issues/"),
    ("POST", P + "modules/<uuid:module_id>/module-issues/"),
    ("DELETE", P + "modules/<uuid:module_id>/module-issues/<uuid:issue_id>/"),
    ("POST", P + "modules/<uuid:pk>/archive/"),
    ("DELETE", P + "archived-modules/<uuid:pk>/unarchive/"),
    # intake
    ("GET", P + "intake-issues/"),
    ("POST", P + "intake-issues/"),
    ("GET", P + "intake-issues/<uuid:issue_id>/"),
    ("PATCH", P + "intake-issues/<uuid:issue_id>/"),
    ("DELETE", P + "intake-issues/<uuid:issue_id>/"),
)

_CONVERTER = re.compile(r"<(?:(\w+):)?(\w+)>")


def _template_regex(template: str) -> re.Pattern[str]:
    out, pos = [], 0
    for m in _CONVERTER.finditer(template):
        out.append(re.escape(template[pos : m.start()]))
        out.append(r"[0-9a-fA-F-]{36}" if m.group(1) == "uuid" else r"[^/]+?")
        pos = m.end()
    out.append(re.escape(template[pos:]))
    return re.compile("^" + "".join(out) + "$")


_COMPILED = tuple((method, _template_regex(t), t) for method, t in ROUTES)


class UnknownRouteError(RuntimeError):
    """The server tried to call a path that is not in ROUTES."""


def match_route(method: str, path: str) -> str:
    """Return the template `path` matches, or raise UnknownRouteError."""
    for route_method, regex, template in _COMPILED:
        if route_method == method and regex.match(path):
            return template
    raise UnknownRouteError(f"{method} {path} is not a declared route (see plane_fork_mcp/routes.py)")
