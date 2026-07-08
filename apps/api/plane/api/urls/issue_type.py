# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# [FORK] work-item-types — external v1 API routes for work item types.

from django.urls import path

from plane.api.views import (
    IssueTypeListCreateAPIEndpoint,
    IssueTypeDetailAPIEndpoint,
    EpicTypeAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/",
        IssueTypeListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="issue-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/<uuid:pk>/",
        IssueTypeDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="issue-types-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epic-type/",
        EpicTypeAPIEndpoint.as_view(http_method_names=["get"]),
        name="epic-type",
    ),
]
