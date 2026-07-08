# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# [FORK] work-item-types — external v1 serializers for work item types.

from .base import BaseSerializer
from plane.db.models import IssueType


class IssueTypeAPISerializer(BaseSerializer):
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
        # `is_epic` is managed only through the dedicated epic flow; workspace and
        # audit fields are server-owned.
        read_only_fields = [
            "id",
            "workspace",
            "is_epic",
            "level",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
