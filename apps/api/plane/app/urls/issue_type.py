# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import IssueTypeViewSet, DefaultIssueTypeEndpoint, DefaultEpicTypeEndpoint


urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/",
        IssueTypeViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/<uuid:pk>/",
        IssueTypeViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="project-issue-type",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/<uuid:pk>/mark-default/",
        IssueTypeViewSet.as_view({"post": "mark_as_default"}),
        name="project-issue-type-mark-default",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/default-issue-type/",
        DefaultIssueTypeEndpoint.as_view({"post": "create"}),
        name="project-default-issue-type",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/default-epic-type/",
        # [FORK] work-item-types — GET added so the type switcher can read the epic type (convert to/from epic)
        DefaultEpicTypeEndpoint.as_view({"post": "create", "get": "list"}),
        name="project-default-epic-type",
    ),
]
