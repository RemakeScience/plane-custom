# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Module imports
from .base import BaseSerializer
from plane.db.models import GithubPullRequest, GithubRepositoryMap


class GithubPullRequestSerializer(BaseSerializer):
    class Meta:
        model = GithubPullRequest
        fields = [
            "id",
            "issue",
            "pr_number",
            "repository_full_name",
            "title",
            "url",
            "state",
            "merged",
            "author_login",
            "ephemeral_env_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class GithubRepositoryMapSerializer(BaseSerializer):
    class Meta:
        model = GithubRepositoryMap
        fields = "__all__"
        read_only_fields = [
            "workspace",
            "project",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
