# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import transaction

# Third party imports
from rest_framework.response import Response
from rest_framework import status

# Module imports
from .. import BaseViewSet
from plane.app.serializers import IssueTypeSerializer
from plane.app.permissions import ROLE, allow_permission
from plane.db.models import IssueType, ProjectIssueType, Project, Issue


class IssueTypeViewSet(BaseViewSet):
    serializer_class = IssueTypeSerializer
    model = IssueType

    def get_queryset(self):
        return (
            IssueType.objects.filter(workspace__slug=self.kwargs.get("slug"))
            .filter(project_issue_types__project_id=self.kwargs.get("project_id"))
            .filter(
                project_issue_types__project__project_projectmember__member=self.request.user,
                project_issue_types__project__project_projectmember__is_active=True,
                project_issue_types__project__archived_at__isnull=True,
            )
            .filter(is_epic=False)
            .select_related("workspace")
            .distinct()
        )

    def _unset_other_defaults(self, slug, project_id, exclude_pk=None):
        queryset = IssueType.objects.filter(
            workspace__slug=slug,
            project_issue_types__project_id=project_id,
            is_epic=False,
            is_default=True,
        )
        if exclude_pk:
            queryset = queryset.exclude(pk=exclude_pk)
        queryset.update(is_default=False)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id):
        issue_types = IssueTypeSerializer(self.get_queryset(), many=True).data
        return Response(issue_types, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def retrieve(self, request, slug, project_id, pk):
        issue_type = self.get_queryset().get(pk=pk)
        return Response(IssueTypeSerializer(issue_type).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)

        serializer = IssueTypeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Determine the level as the next available position for the project.
        last_level = (
            ProjectIssueType.objects.filter(project_id=project_id).order_by("-level").values_list("level", flat=True).first()
        )
        next_level = (last_level or 0) + 1

        with transaction.atomic():
            issue_type = serializer.save(workspace_id=project.workspace_id)
            # Associate the newly created type with the project.
            ProjectIssueType.objects.create(
                issue_type=issue_type,
                project_id=project_id,
                level=next_level,
                is_default=issue_type.is_default,
            )
            # Only one default type per project.
            if issue_type.is_default:
                self._unset_other_defaults(slug, project_id, exclude_pk=issue_type.pk)

        return Response(IssueTypeSerializer(issue_type).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN])
    def partial_update(self, request, slug, project_id, pk):
        issue_type = self.get_queryset().get(pk=pk)
        serializer = IssueTypeSerializer(issue_type, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            issue_type = serializer.save()
            if issue_type.is_default:
                self._unset_other_defaults(slug, project_id, exclude_pk=issue_type.pk)
                ProjectIssueType.objects.filter(project_id=project_id, issue_type=issue_type).update(is_default=True)

        return Response(IssueTypeSerializer(issue_type).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, project_id, pk):
        issue_type = self.get_queryset().get(pk=pk)

        if issue_type.is_default:
            return Response(
                {"error": "The default work item type cannot be deleted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Models are soft-deleted (deleted_at is set, the row stays), so the
            # DB-level SET_NULL on Issue.type never fires. Detach work items from
            # this type explicitly so none are left pointing at a hidden type.
            Issue.objects.filter(type=issue_type).update(type=None)
            issue_type.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN])
    def mark_as_default(self, request, slug, project_id, pk):
        # Ensure the type belongs to the project before marking it default.
        issue_type = self.get_queryset().get(pk=pk)

        with transaction.atomic():
            self._unset_other_defaults(slug, project_id)
            IssueType.objects.filter(pk=issue_type.pk).update(is_default=True)
            ProjectIssueType.objects.filter(project_id=project_id).update(is_default=False)
            ProjectIssueType.objects.filter(project_id=project_id, issue_type=issue_type).update(is_default=True)

        return Response(status=status.HTTP_204_NO_CONTENT)


class DefaultIssueTypeEndpoint(BaseViewSet):
    """Ensures a project has a default work item type.

    Called when the Work Item Types feature is enabled on a project. Creates a
    single default type if the project does not already have one, and returns
    the current default.
    """

    serializer_class = IssueTypeSerializer
    model = IssueType

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)

        existing_default = (
            IssueType.objects.filter(
                workspace__slug=slug,
                project_issue_types__project_id=project_id,
                is_epic=False,
                is_default=True,
            )
            .distinct()
            .first()
        )
        if existing_default:
            return Response(IssueTypeSerializer(existing_default).data, status=status.HTTP_200_OK)

        with transaction.atomic():
            issue_type = IssueType.objects.create(
                workspace_id=project.workspace_id,
                name="Task",
                description="Default work item type",
                is_default=True,
                is_active=True,
                level=0,
            )
            ProjectIssueType.objects.create(
                issue_type=issue_type,
                project_id=project_id,
                level=0,
                is_default=True,
            )
            # Backfill: attach existing untyped work items to the default type.
            Issue.objects.filter(project_id=project_id, type__isnull=True).update(type=issue_type)

        return Response(IssueTypeSerializer(issue_type).data, status=status.HTTP_201_CREATED)
