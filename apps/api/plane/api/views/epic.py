# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# [FORK] work-item-types — external (v1, PAT-authenticated) API for Epics.
# An epic is an Issue whose type has is_epic=True, served only through
# Issue.epic_objects (Issue.issue_objects excludes epics). Mirrors the app
# EpicViewSet: list/create (create forces the project's epic type) + reuses the
# v1 work item detail (retrieve/update/delete) scoped to epics.

# Django imports
from django.db.models import F, Func, OuterRef, Subquery

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.api.serializers import IssueSerializer
from plane.db.models import CycleIssue, FileAsset, Issue, IssueLink, IssueType
from .issue import IssueDetailAPIEndpoint, IssueListCreateAPIEndpoint


def _get_epic_type(slug, project_id):
    """Return the project's epic type (IssueType with is_epic=True), or None."""
    return (
        IssueType.objects.filter(
            workspace__slug=slug,
            project_issue_types__project_id=project_id,
            is_epic=True,
        )
        .distinct()
        .first()
    )


class EpicListCreateAPIEndpoint(IssueListCreateAPIEndpoint):
    """List epics and create an epic (external v1 API)."""

    def get_queryset(self):
        return (
            Issue.epic_objects.annotate(
                sub_issues_count=Issue.issue_objects.filter(parent=OuterRef("id"))
                .order_by()
                .annotate(count=Func(F("id"), function="Count"))
                .values("count")
            )
            .filter(project_id=self.kwargs.get("project_id"))
            .filter(workspace__slug=self.kwargs.get("slug"))
            .select_related("project", "workspace", "state", "parent")
            .prefetch_related("assignees", "labels")
            .order_by(self.kwargs.get("order_by", "-created_at"))
            .distinct()
        )

    def get(self, request, slug, project_id):
        # Direct lookup by external id/source (Issue.objects → includes epics).
        external_id = request.GET.get("external_id")
        external_source = request.GET.get("external_source")
        if external_id and external_source:
            epic = Issue.objects.get(
                external_id=external_id,
                external_source=external_source,
                workspace__slug=slug,
                project_id=project_id,
            )
            return Response(
                IssueSerializer(epic, fields=self.fields, expand=self.expand).data,
                status=status.HTTP_200_OK,
            )

        epic_queryset = (
            self.get_queryset()
            .annotate(
                cycle_id=Subquery(
                    CycleIssue.objects.filter(issue=OuterRef("id"), deleted_at__isnull=True).values("cycle_id")[:1]
                )
            )
            .annotate(
                link_count=IssueLink.objects.filter(issue=OuterRef("id"))
                .order_by()
                .annotate(count=Func(F("id"), function="Count"))
                .values("count")
            )
            .annotate(
                attachment_count=FileAsset.objects.filter(
                    issue_id=OuterRef("id"),
                    entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
                )
                .order_by()
                .annotate(count=Func(F("id"), function="Count"))
                .values("count")
            )
            .order_by(request.GET.get("order_by", "-created_at"))
        )
        total_count_queryset = Issue.epic_objects.filter(project_id=project_id, workspace__slug=slug)
        return self.paginate(
            request=request,
            queryset=epic_queryset,
            total_count_queryset=total_count_queryset,
            on_results=lambda epics: IssueSerializer(epics, many=True, fields=self.fields, expand=self.expand).data,
        )

    def post(self, request, slug, project_id):
        epic_type = _get_epic_type(slug, project_id)
        if epic_type is None:
            return Response(
                {"error": "Epics are not enabled for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Force the epic type regardless of what the client sends: an epic is an
        # issue whose type is the project's epic type. Reuse the full work item
        # create flow (external_id 409, activity, webhook).
        data = request.data
        if hasattr(data, "_mutable"):
            previous_mutable = data._mutable
            data._mutable = True
            data["type_id"] = str(epic_type.id)
            data._mutable = previous_mutable
        else:
            data["type_id"] = str(epic_type.id)
        return super().post(request, slug, project_id)


class EpicDetailAPIEndpoint(IssueDetailAPIEndpoint):
    """Retrieve, update or delete an epic (external v1 API)."""

    def get_queryset(self):
        return (
            Issue.epic_objects.annotate(
                sub_issues_count=Issue.issue_objects.filter(parent=OuterRef("id"))
                .order_by()
                .annotate(count=Func(F("id"), function="Count"))
                .values("count")
            )
            .filter(project_id=self.kwargs.get("project_id"))
            .filter(workspace__slug=self.kwargs.get("slug"))
            .select_related("project", "workspace", "state", "parent")
            .prefetch_related("assignees", "labels")
            .distinct()
        )

    def get(self, request, slug, project_id, pk):
        # Scope the retrieve to epics (the inherited retrieve uses issue_objects,
        # which excludes epics → 404).
        epic = (
            Issue.epic_objects.annotate(
                sub_issues_count=Issue.issue_objects.filter(parent=OuterRef("id"))
                .order_by()
                .annotate(count=Func(F("id"), function="Count"))
                .values("count")
            )
            .get(workspace__slug=slug, project_id=project_id, pk=pk)
        )
        return Response(
            IssueSerializer(epic, fields=self.fields, expand=self.expand).data,
            status=status.HTTP_200_OK,
        )

    # patch / delete are inherited from IssueDetailAPIEndpoint — they resolve the
    # target via Issue.objects (which includes epics), so they work on epics.
