# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import (
    IssuePropertyViewSet,
    IssuePropertyOptionViewSet,
    IssuePropertyAndOptionEndpoint,
    IssuePropertyValueEndpoint,
    IssuePropertyValuesBulkEndpoint,
)


urlpatterns = [
    # Aggregated read of every property + options for the project.
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-property-types/",
        IssuePropertyAndOptionEndpoint.as_view(),
        name="project-issue-properties-and-options",
    ),
    # Property definitions scoped to an issue type.
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/<uuid:type_id>/properties/",
        IssuePropertyViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-type-properties",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/<uuid:type_id>/properties/<uuid:pk>/",
        IssuePropertyViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="project-issue-type-property",
    ),
    # Options scoped to a property.
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-properties/<uuid:property_id>/options/",
        IssuePropertyOptionViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-property-options",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-properties/<uuid:property_id>/options/<uuid:pk>/",
        IssuePropertyOptionViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="project-issue-property-option",
    ),
    # Custom property values for a single issue (bulk upsert).
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/property-values/",
        IssuePropertyValueEndpoint.as_view(),
        name="project-issue-property-values",
    ),
    # Custom property values for many issues at once (spreadsheet columns).
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/property-values/",
        IssuePropertyValuesBulkEndpoint.as_view(),
        name="project-issue-property-values-bulk",
    ),
]
