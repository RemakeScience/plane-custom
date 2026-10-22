# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# [FORK] mcp-server — external v1 API route listing the caller's workspaces.

from django.urls import path

from plane.api.views import UserWorkspacesEndpoint

urlpatterns = [
    path(
        "users/me/workspaces/",
        UserWorkspacesEndpoint.as_view(http_method_names=["get"]),
        name="user-workspaces",
    ),
]
