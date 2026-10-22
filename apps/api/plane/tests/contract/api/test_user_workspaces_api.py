# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""[FORK] mcp-server — contract tests for `users/me/workspaces/` and for using one
API token across several workspaces (what the MCP server relies on)."""

import pytest
from rest_framework import status

from plane.db.models import User, Workspace, WorkspaceMember

URL = "/api/v1/users/me/workspaces/"


def _workspace(owner, slug, name):
    return Workspace.objects.create(name=name, owner=owner, slug=slug)


@pytest.mark.contract
class TestUserWorkspacesAPI:
    @pytest.mark.django_db
    def test_lists_only_active_memberships(self, api_key_client, workspace, create_user):
        other_owner = User.objects.create(email="other@plane.so", username="other")
        second = _workspace(create_user, "second-ws", "Second")
        WorkspaceMember.objects.create(workspace=second, member=create_user, role=15)
        left = _workspace(other_owner, "left-ws", "Left")
        WorkspaceMember.objects.create(workspace=left, member=create_user, role=15, is_active=False)
        _workspace(other_owner, "foreign-ws", "Foreign")

        resp = api_key_client.get(URL)

        assert resp.status_code == status.HTTP_200_OK
        assert {w["slug"]: w["role"] for w in resp.data} == {"test-workspace": 20, "second-ws": 15}
        assert {"id", "slug", "name", "role"} <= set(resp.data[0])

    @pytest.mark.django_db
    def test_requires_authentication(self, api_client):
        assert api_client.get(URL).status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    @pytest.mark.django_db
    def test_one_token_reaches_every_member_workspace(self, api_key_client, workspace, create_user):
        second = _workspace(create_user, "second-ws", "Second")
        WorkspaceMember.objects.create(workspace=second, member=create_user, role=20)

        for slug in ("test-workspace", "second-ws"):
            resp = api_key_client.get(f"/api/v1/workspaces/{slug}/projects/")
            assert resp.status_code == status.HTTP_200_OK, (slug, resp.data)
