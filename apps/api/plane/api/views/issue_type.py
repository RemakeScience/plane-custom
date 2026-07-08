# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# [FORK] work-item-types — external (v1, PAT-authenticated) API for work item
# types. Read (list/retrieve, incl. the epic type) is open to project members;
# schema writes (create/update/delete of type definitions) are admin-only, per
# the application API. Mirrors app IssueTypeViewSet.

# Django imports
from django.db import transaction

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.api.serializers import IssueTypeAPISerializer
from plane.app.permissions import ProjectEntityPermission
from plane.db.models import Issue, IssueType, Project, ProjectIssueType, ProjectMember
from .base import BaseAPIView


def _is_project_admin(request, slug, project_id):
    return ProjectMember.objects.filter(
        workspace__slug=slug,
        project_id=project_id,
        member=request.user,
        role=20,
        is_active=True,
    ).exists()


ADMIN_ONLY = Response(
    {"error": "Only project admins can manage work item type definitions."},
    status=status.HTTP_403_FORBIDDEN,
)


def _regular_types(slug, project_id):
    return (
        IssueType.objects.filter(workspace__slug=slug)
        .filter(project_issue_types__project_id=project_id)
        .filter(is_epic=False)
        .select_related("workspace")
        .order_by("level")
        .distinct()
    )


def _unset_other_defaults(slug, project_id, exclude_pk):
    IssueType.objects.filter(
        workspace__slug=slug,
        project_issue_types__project_id=project_id,
        is_epic=False,
        is_default=True,
    ).exclude(pk=exclude_pk).update(is_default=False)


class IssueTypeListCreateAPIEndpoint(BaseAPIView):
    """List work item types and create a new type (external v1 API)."""

    serializer_class = IssueTypeAPISerializer
    model = IssueType
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return _regular_types(self.kwargs.get("slug"), self.kwargs.get("project_id"))

    def get(self, request, slug, project_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda types: IssueTypeAPISerializer(
                types, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    def post(self, request, slug, project_id):
        if not _is_project_admin(request, slug, project_id):
            return ADMIN_ONLY
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        serializer = IssueTypeAPISerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        external_id = request.data.get("external_id")
        external_source = request.data.get("external_source")
        if external_id and external_source:
            existing = (
                IssueType.objects.filter(
                    workspace__slug=slug,
                    project_issue_types__project_id=project_id,
                    external_source=external_source,
                    external_id=external_id,
                )
                .distinct()
                .first()
            )
            if existing is not None:
                return Response(
                    {
                        "error": "Work item type with the same external id and external source already exists",
                        "id": str(existing.id),
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        last_level = (
            ProjectIssueType.objects.filter(project_id=project_id)
            .order_by("-level")
            .values_list("level", flat=True)
            .first()
        )
        with transaction.atomic():
            issue_type = serializer.save(workspace_id=project.workspace_id)
            ProjectIssueType.objects.create(
                issue_type=issue_type,
                project_id=project_id,
                level=(last_level or 0) + 1,
                is_default=issue_type.is_default,
            )
            if issue_type.is_default:
                _unset_other_defaults(slug, project_id, exclude_pk=issue_type.pk)
        return Response(IssueTypeAPISerializer(issue_type).data, status=status.HTTP_201_CREATED)


class IssueTypeDetailAPIEndpoint(BaseAPIView):
    """Retrieve, update or delete a work item type (external v1 API)."""

    serializer_class = IssueTypeAPISerializer
    model = IssueType
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return _regular_types(self.kwargs.get("slug"), self.kwargs.get("project_id"))

    def get(self, request, slug, project_id, pk):
        issue_type = self.get_queryset().get(pk=pk)
        return Response(IssueTypeAPISerializer(issue_type).data, status=status.HTTP_200_OK)

    def patch(self, request, slug, project_id, pk):
        if not _is_project_admin(request, slug, project_id):
            return ADMIN_ONLY
        issue_type = self.get_queryset().get(pk=pk)
        serializer = IssueTypeAPISerializer(issue_type, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            issue_type = serializer.save()
            if issue_type.is_default:
                _unset_other_defaults(slug, project_id, exclude_pk=issue_type.pk)
                ProjectIssueType.objects.filter(project_id=project_id, issue_type=issue_type).update(is_default=True)
        return Response(IssueTypeAPISerializer(issue_type).data, status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id, pk):
        if not _is_project_admin(request, slug, project_id):
            return ADMIN_ONLY
        issue_type = self.get_queryset().get(pk=pk)
        if issue_type.is_default:
            return Response(
                {"error": "The default work item type cannot be deleted"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            # Soft-delete never fires the DB-level SET_NULL, so detach work items
            # (Issue.objects → includes epics) before deleting the type.
            Issue.objects.filter(type=issue_type).update(type=None)
            issue_type.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EpicTypeAPIEndpoint(BaseAPIView):
    """Read the project's epic type (external v1 API) so agents can discover its
    id (to filter epics, etc.). Creating the epic type stays in the app UI."""

    serializer_class = IssueTypeAPISerializer
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get(self, request, slug, project_id):
        epic_type = (
            IssueType.objects.filter(
                workspace__slug=slug,
                project_issue_types__project_id=project_id,
                is_epic=True,
            )
            .distinct()
            .first()
        )
        if epic_type is None:
            return Response(
                {"error": "Epics are not enabled for this project."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(IssueTypeAPISerializer(epic_type).data, status=status.HTTP_200_OK)
