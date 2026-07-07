# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports

# Django imports
from django.db import models

# Module imports
from plane.db.models.project import ProjectBaseModel


class GithubRepositoryMap(ProjectBaseModel):
    """Maps a GitHub repository to a Plane project.

    Multiple repositories (e.g. a front-end repo and an API repo) can map to
    the same project. The mapping is used to scope inbound webhook events and,
    later, to authenticate outbound GitHub API calls via the App installation.
    """

    repository_id = models.BigIntegerField(help_text="GitHub numeric repository id (stable across renames)")
    full_name = models.CharField(max_length=500, help_text='"org/repo"')
    installation_id = models.BigIntegerField(db_index=True, help_text="GitHub App installation id")

    def __str__(self):
        return f"{self.full_name} <{self.project.name}>"

    class Meta:
        unique_together = ["repository_id", "project", "deleted_at"]
        verbose_name = "Github Repository Map"
        verbose_name_plural = "Github Repository Maps"
        db_table = "github_repository_maps"
        ordering = ("-created_at",)


class GithubPullRequest(ProjectBaseModel):
    """A GitHub Pull Request surfaced on a Plane work item.

    Dedicated model (not IssueLink) so we can hold live PR state and a
    structured ephemeral-environment URL.
    """

    class PullRequestState(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        MERGED = "MERGED", "Merged"

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="github_pull_requests")
    repository_map = models.ForeignKey(
        "db.GithubRepositoryMap",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pull_requests",
    )
    pr_number = models.IntegerField()
    repository_full_name = models.CharField(max_length=500, help_text='denormalized "org/repo" for display/link')
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=800)
    state = models.CharField(max_length=30, choices=PullRequestState.choices, default=PullRequestState.OPEN)
    merged = models.BooleanField(default=False)
    author_login = models.CharField(max_length=255, blank=True)
    ephemeral_env_url = models.URLField(max_length=800, null=True, blank=True)
    github_pr_id = models.BigIntegerField(null=True, blank=True, help_text="GitHub global PR id, for idempotent upsert")
    merged_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.repository_full_name}#{self.pr_number} -> {self.issue_id}"

    class Meta:
        unique_together = ["issue", "repository_full_name", "pr_number", "deleted_at"]
        verbose_name = "Github Pull Request"
        verbose_name_plural = "Github Pull Requests"
        db_table = "github_pull_requests"
        ordering = ("-created_at",)
