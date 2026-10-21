"""Contract: every route the MCP server calls exists in the fork's v1 API.

Reads `apps/api/plane/api/urls/*.py` and `views/*.py` statically (no Django
needed), resolves each URL to its view class, and checks the view (or one of
its bases) implements the HTTP method. If an API change breaks a tool, this
fails in CI before the image ships.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from plane_fork_mcp.routes import ROUTES, UnknownRouteError, match_route

API_DIR = pathlib.Path(__file__).resolve().parents[2] / "api" / "plane" / "api"

pytestmark = pytest.mark.skipif(not API_DIR.exists(), reason="apps/api not available (image build context)")


def _url_map() -> dict[str, str]:
    """URL template -> view class name."""
    out: dict[str, str] = {}
    for file in (API_DIR / "urls").glob("*.py"):
        for node in ast.walk(ast.parse(file.read_text())):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "path" and len(node.args) >= 2):
                continue
            template, view = node.args[0], node.args[1]
            if not (isinstance(template, ast.Constant) and isinstance(view, ast.Call)):
                continue
            func = view.func
            if isinstance(func, ast.Attribute) and func.attr == "as_view" and isinstance(func.value, ast.Name):
                out[template.value] = func.value.id
    return out


def _view_methods() -> dict[str, set[str]]:
    """View class name -> HTTP methods it implements, inherited ones included."""
    own: dict[str, set[str]] = {}
    bases: dict[str, list[str]] = {}
    for file in (API_DIR / "views").glob("*.py"):
        for node in ast.parse(file.read_text()).body:
            if isinstance(node, ast.ClassDef):
                own[node.name] = {
                    item.name.upper()
                    for item in node.body
                    if isinstance(item, ast.FunctionDef) and item.name in ("get", "post", "patch", "put", "delete")
                }
                bases[node.name] = [b.id for b in node.bases if isinstance(b, ast.Name)]

    def resolve(name: str, seen: frozenset[str] = frozenset()) -> set[str]:
        if name in seen or name not in own:
            return set()
        methods = set(own[name])
        for base in bases[name]:
            methods |= resolve(base, seen | {name})
        return methods

    return {name: resolve(name) for name in own}


URLS = _url_map() if API_DIR.exists() else {}
METHODS = _view_methods() if API_DIR.exists() else {}


@pytest.mark.parametrize(("method", "template"), ROUTES, ids=[f"{m} {t}" for m, t in ROUTES])
def test_route_exists_in_api(method: str, template: str) -> None:
    assert template in URLS, f"{template} is not routed in apps/api/plane/api/urls"
    view = URLS[template]
    assert method in METHODS.get(view, set()), f"{view} does not implement {method} for {template}"


def test_routes_are_unique() -> None:
    assert len(set(ROUTES)) == len(ROUTES)


def test_match_route_rejects_undeclared_paths() -> None:
    uid = "11111111-1111-1111-1111-111111111111"
    assert match_route("GET", f"workspaces/acme/projects/{uid}/work-items/") is not None
    with pytest.raises(UnknownRouteError):
        match_route("GET", f"workspaces/acme/projects/{uid}/work-item-types/")
    with pytest.raises(UnknownRouteError):
        match_route("DELETE", f"workspaces/acme/projects/{uid}/")
