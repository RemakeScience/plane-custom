# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# [FORK] work-item-types — external v1 API routes for custom properties.

from django.urls import path

from plane.api.views import (
    IssuePropertyListCreateAPIEndpoint,
    IssuePropertyDetailAPIEndpoint,
    IssuePropertyOptionListCreateAPIEndpoint,
    IssuePropertyOptionDetailAPIEndpoint,
    IssuePropertyValueAPIEndpoint,
)

urlpatterns = [
    # Property definitions (scoped to a work item type)
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/<uuid:type_id>/properties/",
        IssuePropertyListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="issue-properties",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/<uuid:type_id>/properties/<uuid:pk>/",
        IssuePropertyDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="issue-properties-detail",
    ),
    # Options (scoped to an OPTION property)
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-properties/<uuid:property_id>/options/",
        IssuePropertyOptionListCreateAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="issue-property-options",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-properties/<uuid:property_id>/options/<uuid:pk>/",
        IssuePropertyOptionDetailAPIEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="issue-property-options-detail",
    ),
    # Property values on a single work item
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>/property-values/",
        IssuePropertyValueAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="issue-property-values",
    ),
]
