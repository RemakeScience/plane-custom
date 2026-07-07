# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.views.base import BaseAPIView
from plane.app.permissions import ProjectEntityPermission, WorkspaceEntityPermission
from plane.app.serializers import GithubPullRequestSerializer, GithubRepositoryMapSerializer
from plane.db.models import GithubPullRequest, GithubRepositoryMap, Project


class GithubRepositoryMapEndpoint(BaseAPIView):
    """Admin-facing CRUD to wire GitHub repositories to Plane projects."""

    permission_classes = [WorkspaceEntityPermission]

    def get(self, request, slug):
        maps = GithubRepositoryMap.objects.filter(workspace__slug=slug).order_by("-created_at")
        serializer = GithubRepositoryMapSerializer(maps, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, slug):
        project_id = request.data.get("project_id")
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        serializer = GithubRepositoryMapSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project_id=project.id, workspace_id=project.workspace_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug, pk):
        repository_map = GithubRepositoryMap.objects.get(pk=pk, workspace__slug=slug)
        repository_map.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GithubPullRequestListEndpoint(BaseAPIView):
    """Read-only list of GitHub pull requests linked to a work item."""

    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id, issue_id):
        pull_requests = (
            GithubPullRequest.objects.filter(
                workspace__slug=slug,
                project_id=project_id,
                issue_id=issue_id,
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
                project__archived_at__isnull=True,
            )
            .order_by("-created_at")
            .distinct()
        )
        serializer = GithubPullRequestSerializer(pull_requests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
