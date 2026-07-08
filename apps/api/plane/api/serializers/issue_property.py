# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# [FORK] work-item-types — external v1 serializers for custom properties.

from .base import BaseSerializer
from plane.db.models import IssueProperty, IssuePropertyOption


class IssuePropertyAPISerializer(BaseSerializer):
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
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "issue_type",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class IssuePropertyOptionAPISerializer(BaseSerializer):
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
        read_only_fields = [
            "id",
            "workspace",
            "project",
            "property",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
