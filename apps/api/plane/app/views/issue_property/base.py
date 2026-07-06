# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
from decimal import Decimal, InvalidOperation

# Django imports
from django.db import transaction
from django.utils.dateparse import parse_datetime

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from .. import BaseViewSet, BaseAPIView
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import (
    IssuePropertySerializer,
    IssuePropertyOptionSerializer,
)
from plane.db.models import (
    Issue,
    IssueProperty,
    IssuePropertyOption,
    IssuePropertyValue,
    IssueType,
    Project,
    PropertyTypeEnum,
)


def assign_typed_value(value_obj, property, raw):
    """Store ``raw`` into the correct typed column of ``value_obj`` for the
    property's type. Returns the value object (unsaved). Raises ValueError on a
    value that cannot be coerced to the property type.
    """
    ptype = property.property_type
    if ptype in (PropertyTypeEnum.TEXT, PropertyTypeEnum.URL, PropertyTypeEnum.EMAIL, PropertyTypeEnum.FILE):
        value_obj.value_text = str(raw)
    elif ptype == PropertyTypeEnum.DECIMAL:
        try:
            value_obj.value_decimal = Decimal(str(raw))
        except (InvalidOperation, TypeError):
            raise ValueError(f"'{raw}' is not a valid number")
    elif ptype == PropertyTypeEnum.BOOLEAN:
        value_obj.value_boolean = str(raw).lower() in ("true", "1", "yes")
    elif ptype == PropertyTypeEnum.DATETIME:
        parsed = parse_datetime(str(raw))
        if parsed is None:
            raise ValueError(f"'{raw}' is not a valid datetime")
        value_obj.value_datetime = parsed
    elif ptype == PropertyTypeEnum.RELATION:
        value_obj.value_uuid = raw
    elif ptype == PropertyTypeEnum.OPTION:
        value_obj.value_option_id = raw
    return value_obj


def read_typed_value(value_obj):
    """Return the stored value of a property value row as a JSON-friendly scalar."""
    ptype = value_obj.property.property_type
    if ptype in (PropertyTypeEnum.TEXT, PropertyTypeEnum.URL, PropertyTypeEnum.EMAIL, PropertyTypeEnum.FILE):
        return value_obj.value_text
    if ptype == PropertyTypeEnum.DECIMAL:
        return str(value_obj.value_decimal) if value_obj.value_decimal is not None else None
    if ptype == PropertyTypeEnum.BOOLEAN:
        return value_obj.value_boolean
    if ptype == PropertyTypeEnum.DATETIME:
        return value_obj.value_datetime.isoformat() if value_obj.value_datetime else None
    if ptype == PropertyTypeEnum.RELATION:
        return str(value_obj.value_uuid) if value_obj.value_uuid else None
    if ptype == PropertyTypeEnum.OPTION:
        return str(value_obj.value_option_id) if value_obj.value_option_id else None
    return None


def default_values_payload(type_id):
    """Build a ``{property_id: [values]}`` payload from the declared defaults of
    every active property of ``type_id``.

    OPTION properties draw their defaults from options flagged ``is_default``;
    every other type uses the property's ``default_value`` list.
    """
    payload = {}
    for issue_property in IssueProperty.objects.filter(issue_type_id=type_id, is_active=True):
        if issue_property.property_type == PropertyTypeEnum.OPTION:
            values = [
                str(option_id)
                for option_id in IssuePropertyOption.objects.filter(
                    property_id=issue_property.id, is_default=True, is_active=True
                ).values_list("id", flat=True)
            ]
        else:
            default = issue_property.default_value or []
            values = default if isinstance(default, list) else [default]
        values = [v for v in values if v is not None and v != ""]
        if values:
            payload[str(issue_property.id)] = values
    return payload


def build_property_values(project, issue_id, payload, enforce_required=True):
    """Validate ``payload`` (``{property_id: values}``) and build unsaved
    ``IssuePropertyValue`` rows grouped by property.

    Returns ``(to_write, error)``; ``error`` is a message string on the first
    validation failure (and ``to_write`` is ``None``), otherwise ``None``.
    """
    properties = {
        str(p.id): p
        for p in IssueProperty.objects.filter(project_id=project.id, id__in=list(payload.keys()))
    }
    to_write = {}  # property_id -> list[IssuePropertyValue]
    for property_id, raw_values in payload.items():
        issue_property = properties.get(str(property_id))
        if issue_property is None:
            return None, f"Unknown property {property_id}."
        value_list = raw_values if isinstance(raw_values, list) else [raw_values]
        value_list = [v for v in value_list if v is not None and v != ""]
        if enforce_required and issue_property.is_required and len(value_list) == 0:
            return None, f"'{issue_property.display_name}' is required."
        if not issue_property.is_multi and len(value_list) > 1:
            return None, f"'{issue_property.display_name}' does not accept multiple values."
        built = []
        for raw in value_list:
            value_obj = IssuePropertyValue(
                project_id=project.id,
                workspace_id=project.workspace_id,
                issue_id=issue_id,
                property_id=property_id,
            )
            try:
                assign_typed_value(value_obj, issue_property, raw)
            except ValueError as e:
                return None, str(e)
            built.append(value_obj)
        to_write[str(property_id)] = built
    return to_write, None


def persist_property_values(issue_id, to_write):
    """Hard-replace the stored values for each property in ``to_write``."""
    with transaction.atomic():
        for property_id, new_values in to_write.items():
            IssuePropertyValue.objects.filter(issue_id=issue_id, property_id=property_id).delete(soft=False)
            IssuePropertyValue.objects.bulk_create(new_values, batch_size=50)


def write_property_values_for_issue(
    project, issue, inline_payload=None, apply_defaults=False, enforce_required=True
):
    """Persist property values for ``issue`` from an optional inline payload,
    optionally backfilling each property's declared default first (inline values
    override defaults). Returns an error message string, or ``None`` on success.
    """
    payload = {}
    if apply_defaults and issue.type_id:
        payload.update(default_values_payload(issue.type_id))
    if isinstance(inline_payload, dict):
        payload.update(inline_payload)
    if not payload:
        return None
    to_write, error = build_property_values(project, issue.id, payload, enforce_required=enforce_required)
    if error:
        return error
    persist_property_values(issue.id, to_write)
    return None


class IssuePropertyViewSet(BaseViewSet):
    """CRUD of custom property definitions scoped to an issue type."""

    serializer_class = IssuePropertySerializer
    model = IssueProperty

    def get_queryset(self):
        return IssueProperty.objects.filter(
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
            issue_type_id=self.kwargs.get("type_id"),
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id, type_id):
        properties = IssuePropertySerializer(self.get_queryset(), many=True).data
        return Response(properties, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def retrieve(self, request, slug, project_id, type_id, pk):
        issue_property = self.get_queryset().get(pk=pk)
        return Response(IssuePropertySerializer(issue_property).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug, project_id, type_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        # Ensure the type belongs to the project.
        issue_type = IssueType.objects.filter(
            pk=type_id, project_issue_types__project_id=project_id
        ).first()
        if issue_type is None:
            return Response({"error": "Invalid work item type."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = IssuePropertySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        issue_property = serializer.save(
            project_id=project_id,
            workspace_id=project.workspace_id,
            issue_type_id=type_id,
        )
        return Response(IssuePropertySerializer(issue_property).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN])
    def partial_update(self, request, slug, project_id, type_id, pk):
        issue_property = self.get_queryset().get(pk=pk)
        serializer = IssuePropertySerializer(issue_property, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, project_id, type_id, pk):
        issue_property = self.get_queryset().get(pk=pk)
        issue_property.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssuePropertyOptionViewSet(BaseViewSet):
    """CRUD of options for an OPTION-typed property."""

    serializer_class = IssuePropertyOptionSerializer
    model = IssuePropertyOption

    def get_queryset(self):
        return IssuePropertyOption.objects.filter(
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
            property_id=self.kwargs.get("property_id"),
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id, property_id):
        options = IssuePropertyOptionSerializer(self.get_queryset(), many=True).data
        return Response(options, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def retrieve(self, request, slug, project_id, property_id, pk):
        option = self.get_queryset().get(pk=pk)
        return Response(IssuePropertyOptionSerializer(option).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug, project_id, property_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        issue_property = IssueProperty.objects.filter(pk=property_id, project_id=project_id).first()
        if issue_property is None:
            return Response({"error": "Invalid property."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = IssuePropertyOptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        option = serializer.save(
            project_id=project_id,
            workspace_id=project.workspace_id,
            property_id=property_id,
        )
        return Response(IssuePropertyOptionSerializer(option).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN])
    def partial_update(self, request, slug, project_id, property_id, pk):
        option = self.get_queryset().get(pk=pk)
        serializer = IssuePropertyOptionSerializer(option, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, project_id, property_id, pk):
        option = self.get_queryset().get(pk=pk)
        option.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssuePropertyAndOptionEndpoint(BaseAPIView):
    """Aggregated read of every custom property (with its options) for a project.

    Backs the WORK_ITEM_TYPES_PROPERTIES_AND_OPTIONS front-end fetch key.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        properties = IssueProperty.objects.filter(workspace__slug=slug, project_id=project_id)
        options = IssuePropertyOption.objects.filter(workspace__slug=slug, project_id=project_id)

        options_by_property = {}
        for option in options:
            options_by_property.setdefault(str(option.property_id), []).append(
                IssuePropertyOptionSerializer(option).data
            )

        result = []
        for issue_property in properties:
            data = IssuePropertySerializer(issue_property).data
            data["options"] = options_by_property.get(str(issue_property.id), [])
            result.append(data)
        return Response(result, status=status.HTTP_200_OK)


class IssuePropertyValueEndpoint(BaseAPIView):
    """Read and bulk-upsert custom property values for a single issue.

    GET  returns ``{ property_id: [values...] }``.
    POST accepts the same shape and replaces the values for each property sent.
    """

    def _serialize_values(self, slug, project_id, issue_id):
        values = IssuePropertyValue.objects.filter(
            workspace__slug=slug, project_id=project_id, issue_id=issue_id
        ).select_related("property")
        result = {}
        for value in values:
            result.setdefault(str(value.property_id), []).append(read_typed_value(value))
        return result

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        return Response(self._serialize_values(slug, project_id, issue_id), status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, issue_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        issue = Issue.objects.filter(pk=issue_id, project_id=project_id).first()
        if issue is None:
            return Response({"error": "Invalid work item."}, status=status.HTTP_404_NOT_FOUND)

        payload = request.data or {}
        if not isinstance(payload, dict):
            return Response({"error": "Expected an object of property values."}, status=status.HTTP_400_BAD_REQUEST)

        # Fully validate and build every value object BEFORE touching the DB, so a
        # bad value never leaves partially-written state behind.
        to_write, error = build_property_values(project, issue_id, payload, enforce_required=True)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        persist_property_values(issue_id, to_write)
        return Response(self._serialize_values(slug, project_id, issue_id), status=status.HTTP_200_OK)


class IssuePropertyValuesBulkEndpoint(BaseAPIView):
    """Read custom property values for many issues in a single request.

    POST ``{"issue_ids": [...]}`` -> ``{issue_id: {property_id: [values...]}}``.
    Backs the spreadsheet columns without an N+1 per-row fetch.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def post(self, request, slug, project_id):
        issue_ids = request.data.get("issue_ids") or []
        if not isinstance(issue_ids, list):
            return Response({"error": "'issue_ids' must be a list."}, status=status.HTTP_400_BAD_REQUEST)
        if not issue_ids:
            return Response({}, status=status.HTTP_200_OK)

        values = IssuePropertyValue.objects.filter(
            workspace__slug=slug, project_id=project_id, issue_id__in=issue_ids
        ).select_related("property")
        result = {}
        for value in values:
            issue_bucket = result.setdefault(str(value.issue_id), {})
            issue_bucket.setdefault(str(value.property_id), []).append(read_typed_value(value))
        return Response(result, status=status.HTTP_200_OK)
