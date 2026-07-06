# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Module imports
from .base import BaseSerializer
from plane.db.models import IssueType, ProjectIssueType


class IssueTypeSerializer(BaseSerializer):
    class Meta:
        model = IssueType
        fields = [
            "id",
            "name",
            "description",
            "logo_props",
            "is_epic",
            "is_default",
            "is_active",
            "level",
            "workspace",
            "external_source",
            "external_id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        # `workspace` is derived from the URL/project and `is_epic` is managed
        # through the dedicated epic flow, so both are read-only here.
        read_only_fields = ["workspace", "is_epic"]


class IssueTypeLiteSerializer(BaseSerializer):
    class Meta:
        model = IssueType
        fields = ["id", "name", "logo_props", "is_epic", "is_default"]
        read_only_fields = fields


class ProjectIssueTypeSerializer(BaseSerializer):
    class Meta:
        model = ProjectIssueType
        fields = [
            "id",
            "issue_type",
            "project_id",
            "workspace_id",
            "level",
            "is_default",
        ]
        read_only_fields = ["workspace", "project"]
