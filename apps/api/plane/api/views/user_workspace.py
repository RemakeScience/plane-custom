# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# [FORK] mcp-server — lets an API token holder discover their workspaces, so one
# MCP connector can work across every workspace the user belongs to.

# Third party imports
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.api.views.base import BaseAPIView
from plane.db.models import WorkspaceMember


class UserWorkspacesEndpoint(BaseAPIView):
    """Workspaces the authenticated user is an active member of."""

    use_read_replica = True

    @extend_schema(
        operation_id="list_my_workspaces",
        summary="List my workspaces",
        tags=["Users"],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        memberships = (
            WorkspaceMember.objects.filter(member=request.user, is_active=True)
            .select_related("workspace")
            .order_by("workspace__name")
        )
        return Response(
            [
                {
                    "id": str(m.workspace_id),
                    "slug": m.workspace.slug,
                    "name": m.workspace.name,
                    "role": m.role,
                }
                for m in memberships
            ],
            status=status.HTTP_200_OK,
        )
