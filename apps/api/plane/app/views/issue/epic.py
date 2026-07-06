# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.db.models import Issue, IssueType
from .base import IssueViewSet


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
