# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.external.github import (
    GithubWebhookEndpoint,
    GithubRepositoryMapEndpoint,
    GithubPullRequestListEndpoint,
)


urlpatterns = [
    # Inbound webhook receiver (unauthenticated, HMAC-verified)
    path(
        "workspaces/<str:slug>/github/webhook/",
        GithubWebhookEndpoint.as_view(),
        name="github-webhook",
    ),
    # Repo <-> project mapping (admin settings)
    path(
        "workspaces/<str:slug>/github/repositories/",
        GithubRepositoryMapEndpoint.as_view(),
        name="github-repository-maps",
    ),
    path(
        "workspaces/<str:slug>/github/repositories/<uuid:pk>/",
        GithubRepositoryMapEndpoint.as_view(),
        name="github-repository-map-detail",
    ),
    # Pull requests linked to a work item (read-only, frontend)
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/github/pull-requests/",
        GithubPullRequestListEndpoint.as_view(),
        name="github-pull-requests",
    ),
]
