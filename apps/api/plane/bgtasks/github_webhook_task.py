# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json
import re

# Third party imports
from celery import shared_task

# Django imports
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.dateparse import parse_datetime

# Module imports
from plane.db.models import (
    GithubPullRequest,
    GithubRepositoryMap,
    Issue,
    Project,
    State,
)
from plane.bgtasks.issue_activities_task import issue_activity
from plane.utils.exception_logger import log_exception


# ---------------------------------------------------------------------------
# Reference parsing
# ---------------------------------------------------------------------------
# IDENT = project.identifier: starts with a letter, letters/digits, max 12
# (project.py). Case-insensitive. Optional leading '#'. Negative look-behind
# stops matching inside a longer token (e.g. "ABWIT-123") and the trailing
# negative look-ahead stops grabbing extra digits (e.g. "WIT-1234" -> 1234, not
# a partial). Matches inside a branch ref such as "feat/WIT-123-foo".
WORK_ITEM_REF = re.compile(r"(?<![A-Za-z0-9])#?([A-Za-z][A-Za-z0-9]{0,11})-(\d+)(?![0-9])")

# Ephemeral-environment preview URL heuristic: an http(s) URL that contains the
# word "preview". Kept deliberately permissive; can be moved to instance config.
EPHEMERAL_URL = re.compile(r"https?://[^\s)>\]]*preview[^\s)>\]]*", re.IGNORECASE)


def _resolve_issues(slug, *texts):
    """Return a list of unique Issue objects referenced as ``#IDENT-seq`` in any
    of the given text blobs (PR title / head branch / body), scoped to the
    workspace ``slug``."""
    seen = set()
    issues = []
    for text in texts:
        if not text:
            continue
        for identifier, seq in WORK_ITEM_REF.findall(text):
            key = (identifier.upper(), int(seq))
            if key in seen:
                continue
            seen.add(key)
            project = Project.objects.filter(identifier__iexact=identifier, workspace__slug=slug).first()
            if project is None:
                continue
            issue = Issue.objects.filter(project=project, sequence_id=int(seq)).first()
            if issue is not None:
                issues.append(issue)
    return issues


def _pr_state(pr):
    """Map a GitHub pull_request payload to our stored state."""
    if pr.get("merged"):
        return GithubPullRequest.PullRequestState.MERGED
    if pr.get("state") == "closed":
        return GithubPullRequest.PullRequestState.CLOSED
    return GithubPullRequest.PullRequestState.OPEN


def _resolve_repository_map(repository, project):
    """Best-effort lookup of a repo<->project mapping. Returns None when no
    mapping was configured (linking by reference still works)."""
    repository_id = repository.get("id")
    if repository_id is None:
        return None
    return GithubRepositoryMap.objects.filter(repository_id=repository_id, project=project).first()


def _move_issue_to_completed(issue):
    """Move an issue to the project's completed-group state (lowest sequence),
    recording a normal 'state' activity in the feed. No-op if already completed."""
    if issue.state_id is not None:
        current_state = State.all_state_objects.filter(pk=issue.state_id).first()
        if current_state is not None and current_state.group == "completed":
            return

    target_state = (
        State.objects.filter(project_id=issue.project_id, group="completed").order_by("sequence").first()
    )
    if target_state is None or target_state.id == issue.state_id:
        return

    old_state_id = str(issue.state_id) if issue.state_id else None
    issue.state = target_state
    issue.save(update_fields=["state", "updated_at"])

    # Drive track_state via the standard activity pipeline so the merge shows up
    # in the work item's activity feed as a normal state change.
    issue_activity.delay(
        type="issue.activity.updated",
        requested_data=json.dumps({"state_id": str(target_state.id)}),
        actor_id=None,
        issue_id=str(issue.id),
        project_id=str(issue.project_id),
        current_instance=json.dumps({"state_id": old_state_id}, cls=DjangoJSONEncoder),
        epoch=int(timezone.now().timestamp()),
        notification=False,
        origin=None,
    )


def _handle_pull_request(slug, payload):
    action = payload.get("action")
    pr = payload.get("pull_request") or {}
    repository = payload.get("repository") or {}

    repo_full_name = repository.get("full_name") or ""
    pr_number = pr.get("number")
    if pr_number is None or not repo_full_name:
        return

    head_ref = (pr.get("head") or {}).get("ref")
    issues = _resolve_issues(slug, pr.get("title"), head_ref, pr.get("body"))
    if not issues:
        return

    merged_at = pr.get("merged_at")
    defaults = {
        "pr_number": pr_number,
        "repository_full_name": repo_full_name,
        "title": (pr.get("title") or "")[:500],
        "url": pr.get("html_url") or "",
        "state": _pr_state(pr),
        "merged": bool(pr.get("merged")),
        "author_login": ((pr.get("user") or {}).get("login") or "")[:255],
        "github_pr_id": pr.get("id"),
        "merged_at": parse_datetime(merged_at) if merged_at else None,
    }

    for issue in issues:
        repository_map = _resolve_repository_map(repository, issue.project)
        obj, created = GithubPullRequest.objects.update_or_create(
            issue=issue,
            repository_full_name=repo_full_name,
            pr_number=pr_number,
            defaults={
                **defaults,
                "project_id": issue.project_id,
                "repository_map": repository_map,
            },
        )

        # When the PR is merged, move the linked work item to completed.
        if action == "closed" and pr.get("merged"):
            _move_issue_to_completed(issue)


def _handle_issue_comment(slug, payload):
    if payload.get("action") != "created":
        return

    issue_ref = payload.get("issue") or {}
    # issue_comment fires for both issues and PRs; only PR comments carry this.
    if not issue_ref.get("pull_request"):
        return

    comment_body = (payload.get("comment") or {}).get("body") or ""
    match = EPHEMERAL_URL.search(comment_body)
    if not match:
        return

    repository = payload.get("repository") or {}
    repo_full_name = repository.get("full_name") or ""
    pr_number = issue_ref.get("number")
    if pr_number is None or not repo_full_name:
        return

    GithubPullRequest.objects.filter(
        repository_full_name=repo_full_name,
        pr_number=pr_number,
    ).update(ephemeral_env_url=match.group(0)[:800])


@shared_task
def github_webhook_task(event, delivery_id, slug, payload):
    """Process a verified GitHub webhook payload (see receiver for HMAC check).

    Upserts are idempotent (unique per issue/repo/pr_number) so redelivered
    events are safe to reprocess.
    """
    try:
        if event == "pull_request":
            _handle_pull_request(slug, payload)
        elif event == "issue_comment":
            _handle_issue_comment(slug, payload)
        # other events (pull_request_review, push, ...) ignored for the MVP
    except Exception as e:
        log_exception(e)
    return
