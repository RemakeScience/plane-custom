# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Module imports
from .base import BaseSerializer
from plane.db.models import IssueProperty, IssuePropertyOption, IssuePropertyValue


class IssuePropertyOptionSerializer(BaseSerializer):
    class Meta:
        model = IssuePropertyOption
        fields = [
            "id",
            "property",
            "name",
            "description",
            "logo_props",
            "is_active",
            "is_default",
            "sort_order",
            "parent",
            "external_source",
            "external_id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        # property/workspace/project are derived from the URL.
        read_only_fields = ["workspace", "project", "property"]


class IssuePropertySerializer(BaseSerializer):
    class Meta:
        model = IssueProperty
        fields = [
            "id",
            "issue_type",
            "name",
            "display_name",
            "description",
            "logo_props",
            "property_type",
            "relation_type",
            "is_required",
            "is_multi",
            "is_active",
            "default_value",
            "settings",
            "sort_order",
            "external_source",
            "external_id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        # issue_type/workspace/project are derived from the URL.
        read_only_fields = ["workspace", "project", "issue_type"]


class IssuePropertyValueSerializer(BaseSerializer):
    class Meta:
        model = IssuePropertyValue
        fields = [
            "id",
            "issue",
            "property",
            "value_text",
            "value_boolean",
            "value_decimal",
            "value_datetime",
            "value_uuid",
            "value_option",
            "external_source",
            "external_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["workspace", "project", "issue"]
