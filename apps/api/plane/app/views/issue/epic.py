# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db.models import Count, OuterRef, Subquery

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.db.models import CycleIssue, FileAsset, Issue, IssueLink, IssueType
from .base import IssuePaginatedViewSet, IssueViewSet


class EpicViewSet(IssueViewSet):
    """Work item viewset restricted to epics.

    Reuses the full IssueViewSet machinery (list grouping, annotations,
    partial_update, destroy, activity tracking) but scopes every read to
    issues whose type has ``is_epic=True`` (via ``Issue.epic_objects``) and
    forces new work items to be created with the project's epic type.
    """

    def get_queryset(self):
        return (
            Issue.epic_objects.filter(
                project_id=self.kwargs.get("project_id"),
                workspace__slug=self.kwargs.get("slug"),
            ).distinct()
        )

    def _get_epic_type(self, slug, project_id):
        return (
            IssueType.objects.filter(
                workspace__slug=slug,
                project_issue_types__project_id=project_id,
                is_epic=True,
            )
            .distinct()
            .first()
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id):
        epic_type = self._get_epic_type(slug, project_id)
        if epic_type is None:
            return Response(
                {"error": "Epics are not enabled for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Force the epic type regardless of what the client sends: an epic is an
        # issue whose type is the project's epic type.
        data = request.data
        if hasattr(data, "_mutable"):
            previous_mutable = data._mutable
            data._mutable = True
            data["type_id"] = str(epic_type.id)
            data._mutable = previous_mutable
        else:
            data["type_id"] = str(epic_type.id)

        # Pass slug/project_id as keywords: the inherited create is wrapped by
        # allow_permission, which reads them from kwargs.
        return super().create(request, slug=slug, project_id=project_id)


class EpicPaginatedViewSet(IssuePaginatedViewSet):
    """Paginated (v2) epics list. Same as the issues v2 endpoint but scoped to
    epics via ``Issue.epic_objects`` (used by the front-end sync fetch).

    The queryset mirrors IssuePaginatedViewSet.get_queryset with the same
    annotations; only the base manager differs (epic_objects vs issue_objects),
    because the parent already excludes every epic.
    """

    def get_queryset(self):
        workspace_slug = self.kwargs.get("slug")
        project_id = self.kwargs.get("project_id")

        return (
            Issue.epic_objects.filter(workspace__slug=workspace_slug, project_id=project_id)
            .select_related("state")
            .annotate(cycle_id=Subquery(CycleIssue.objects.filter(issue=OuterRef("id")).values("cycle_id")[:1]))
            .annotate(
                link_count=Subquery(
                    IssueLink.objects.filter(issue=OuterRef("id"))
                    .values("issue")
                    .annotate(count=Count("id"))
                    .values("count")
                )
            )
            .annotate(
                attachment_count=Subquery(
                    FileAsset.objects.filter(
                        issue_id=OuterRef("id"),
                        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
                    )
                    .values("issue_id")
                    .annotate(count=Count("id"))
                    .values("count")
                )
            )
            .annotate(
                sub_issues_count=Subquery(
                    Issue.issue_objects.filter(parent=OuterRef("id"))
                    .values("parent")
                    .annotate(count=Count("id"))
                    .values("count")
                )
            )
        )
