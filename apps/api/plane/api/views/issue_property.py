# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# [FORK] work-item-types — external (v1, PAT-authenticated) API for custom
# properties. Property/option DEFINITIONS are admin-only (schema management);
# per-work-item property VALUES can be read/written by project members. Reuses
# the application-side value helpers so validation/typing/persistence stay
# identical across both APIs.

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.api.serializers import IssuePropertyAPISerializer, IssuePropertyOptionAPISerializer
from plane.app.permissions import ProjectEntityPermission
from plane.app.views.issue_property.base import (
    build_property_values,
    persist_property_values,
    read_typed_value,
)
from plane.db.models import (
    Issue,
    IssueProperty,
    IssuePropertyOption,
    IssuePropertyValue,
    IssueType,
    Project,
    ProjectMember,
)
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
    {"error": "Only project admins can manage custom property definitions."},
    status=status.HTTP_403_FORBIDDEN,
)


# --------------------------------------------------------------------------- #
# Property definitions (scoped to a work item type)
# --------------------------------------------------------------------------- #
class IssuePropertyListCreateAPIEndpoint(BaseAPIView):
    """List and create custom property definitions for a work item type."""

    serializer_class = IssuePropertyAPISerializer
    model = IssueProperty
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            IssueProperty.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
                issue_type_id=self.kwargs.get("type_id"),
            )
            .order_by("sort_order")
            .distinct()
        )

    def get(self, request, slug, project_id, type_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda props: IssuePropertyAPISerializer(
                props, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    def post(self, request, slug, project_id, type_id):
        if not _is_project_admin(request, slug, project_id):
            return ADMIN_ONLY
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        issue_type = IssueType.objects.filter(
            pk=type_id, project_issue_types__project_id=project_id, workspace__slug=slug
        ).first()
        if issue_type is None:
            return Response({"error": "Invalid work item type."}, status=status.HTTP_404_NOT_FOUND)
        serializer = IssuePropertyAPISerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(project_id=project_id, workspace_id=project.workspace_id, issue_type_id=type_id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IssuePropertyDetailAPIEndpoint(BaseAPIView):
    """Retrieve, update or delete a custom property definition."""

    serializer_class = IssuePropertyAPISerializer
    model = IssueProperty
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return IssueProperty.objects.filter(
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
            issue_type_id=self.kwargs.get("type_id"),
        )

    def get(self, request, slug, project_id, type_id, pk):
        issue_property = self.get_queryset().get(pk=pk)
        return Response(IssuePropertyAPISerializer(issue_property).data, status=status.HTTP_200_OK)

    def patch(self, request, slug, project_id, type_id, pk):
        if not _is_project_admin(request, slug, project_id):
            return ADMIN_ONLY
        issue_property = self.get_queryset().get(pk=pk)
        serializer = IssuePropertyAPISerializer(issue_property, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id, type_id, pk):
        if not _is_project_admin(request, slug, project_id):
            return ADMIN_ONLY
        issue_property = self.get_queryset().get(pk=pk)
        issue_property.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Property options (scoped to an OPTION property)
# --------------------------------------------------------------------------- #
class IssuePropertyOptionListCreateAPIEndpoint(BaseAPIView):
    """List and create options for a custom property."""

    serializer_class = IssuePropertyOptionAPISerializer
    model = IssuePropertyOption
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return (
            IssuePropertyOption.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
                property_id=self.kwargs.get("property_id"),
            )
            .order_by("sort_order")
            .distinct()
        )

    def get(self, request, slug, project_id, property_id):
        return self.paginate(
            request=request,
            queryset=self.get_queryset(),
            on_results=lambda options: IssuePropertyOptionAPISerializer(
                options, many=True, fields=self.fields, expand=self.expand
            ).data,
        )

    def post(self, request, slug, project_id, property_id):
        if not _is_project_admin(request, slug, project_id):
            return ADMIN_ONLY
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        issue_property = IssueProperty.objects.filter(
            pk=property_id, project_id=project_id, workspace__slug=slug
        ).first()
        if issue_property is None:
            return Response({"error": "Invalid custom property."}, status=status.HTTP_404_NOT_FOUND)
        serializer = IssuePropertyOptionAPISerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(project_id=project_id, workspace_id=project.workspace_id, property_id=property_id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IssuePropertyOptionDetailAPIEndpoint(BaseAPIView):
    """Retrieve, update or delete a custom property option."""

    serializer_class = IssuePropertyOptionAPISerializer
    model = IssuePropertyOption
    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def get_queryset(self):
        return IssuePropertyOption.objects.filter(
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
            property_id=self.kwargs.get("property_id"),
        )

    def get(self, request, slug, project_id, property_id, pk):
        option = self.get_queryset().get(pk=pk)
        return Response(IssuePropertyOptionAPISerializer(option).data, status=status.HTTP_200_OK)

    def patch(self, request, slug, project_id, property_id, pk):
        if not _is_project_admin(request, slug, project_id):
            return ADMIN_ONLY
        option = self.get_queryset().get(pk=pk)
        serializer = IssuePropertyOptionAPISerializer(option, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, slug, project_id, property_id, pk):
        if not _is_project_admin(request, slug, project_id):
            return ADMIN_ONLY
        option = self.get_queryset().get(pk=pk)
        option.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Property VALUES on a single work item (read + upsert)
# --------------------------------------------------------------------------- #
class IssuePropertyValueAPIEndpoint(BaseAPIView):
    """Read and bulk-upsert custom property values for a single work item.

    GET  -> ``{ property_id: [values...] }``.
    POST accepts the same shape and replaces the values for each property sent.
    Resolves the work item via ``Issue.objects`` so it also works on epics.
    """

    permission_classes = [ProjectEntityPermission]
    use_read_replica = True

    def _serialize_values(self, slug, project_id, issue_id):
        values = IssuePropertyValue.objects.filter(
            workspace__slug=slug, project_id=project_id, issue_id=issue_id
        ).select_related("property")
        result = {}
        for value in values:
            result.setdefault(str(value.property_id), []).append(read_typed_value(value))
        return result

    def get(self, request, slug, project_id, issue_id):
        return Response(self._serialize_values(slug, project_id, issue_id), status=status.HTTP_200_OK)

    def post(self, request, slug, project_id, issue_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        issue = Issue.objects.filter(pk=issue_id, project_id=project_id).first()
        if issue is None:
            return Response({"error": "Invalid work item."}, status=status.HTTP_404_NOT_FOUND)
        payload = request.data or {}
        if not isinstance(payload, dict):
            return Response(
                {"error": "Expected an object of property values."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Fully validate before touching the DB (no partial writes on a bad value).
        to_write, error = build_property_values(project, issue_id, payload, enforce_required=True)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        persist_property_values(issue_id, to_write)
        return Response(self._serialize_values(slug, project_id, issue_id), status=status.HTTP_200_OK)
