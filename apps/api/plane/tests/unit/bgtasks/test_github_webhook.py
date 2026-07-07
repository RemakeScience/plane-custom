# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""DB-backed tests for the GitHub webhook event handlers: linking PRs to work
items via ``#IDENT-seq`` references, moving a work item to completed on merge,
and capturing an ephemeral-environment URL from a PR comment."""

from unittest.mock import patch

import pytest

from plane.db.models import GithubPullRequest, Issue, Project, State, StateGroup, Workspace, WorkspaceMember
from plane.tests.factories import UserFactory
from plane.bgtasks.github_webhook_task import _handle_issue_comment, _handle_pull_request


@pytest.fixture
def project_setup(db):
    user = UserFactory()
    workspace = Workspace.objects.create(name="WS", owner=user, slug="ws-gh")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=20)
    project = Project.objects.create(name="Proj GH", workspace=workspace, identifier="WIT")

    backlog = State.objects.create(
        name="Backlog", color="#000", group=StateGroup.BACKLOG.value, default=True, project=project
    )
    done = State.objects.create(
        name="Done", color="#0f0", group=StateGroup.COMPLETED.value, project=project
    )

    issue = Issue.objects.create(name="Login bug", project=project, state=backlog)
    issue.sequence_id = 123
    issue.save()

    return {"workspace": workspace, "project": project, "issue": issue, "backlog": backlog, "done": done}


def _pr_payload(action, *, merged=False, title="Fix #WIT-123", branch="feat/other", state="open"):
    return {
        "action": action,
        "repository": {"id": 555, "full_name": "acme/api"},
        "pull_request": {
            "id": 999,
            "number": 42,
            "title": title,
            "html_url": "https://github.com/acme/api/pull/42",
            "state": state,
            "merged": merged,
            "merged_at": "2026-07-07T10:00:00Z" if merged else None,
            "user": {"login": "octocat"},
            "head": {"ref": branch},
            "body": "",
        },
    }


@pytest.mark.unit
class TestPullRequestHandler:
    @patch("plane.bgtasks.github_webhook_task.issue_activity")
    def test_opened_links_pr(self, _activity, project_setup):
        _handle_pull_request("ws-gh", _pr_payload("opened"))

        pr = GithubPullRequest.objects.get(issue=project_setup["issue"], pr_number=42)
        assert pr.repository_full_name == "acme/api"
        assert pr.state == GithubPullRequest.PullRequestState.OPEN
        assert pr.author_login == "octocat"
        assert pr.url == "https://github.com/acme/api/pull/42"

    @patch("plane.bgtasks.github_webhook_task.issue_activity")
    def test_reference_in_branch(self, _activity, project_setup):
        _handle_pull_request(
            "ws-gh", _pr_payload("opened", title="No ref here", branch="feat/WIT-123-login")
        )
        assert GithubPullRequest.objects.filter(issue=project_setup["issue"], pr_number=42).exists()

    @patch("plane.bgtasks.github_webhook_task.issue_activity")
    def test_unknown_ref_creates_nothing(self, _activity, project_setup):
        _handle_pull_request("ws-gh", _pr_payload("opened", title="Fix #NOPE-999", branch="feat/x"))
        assert GithubPullRequest.objects.count() == 0

    @patch("plane.bgtasks.github_webhook_task.issue_activity")
    def test_merge_moves_issue_to_completed(self, _activity, project_setup):
        _handle_pull_request("ws-gh", _pr_payload("opened"))
        _handle_pull_request("ws-gh", _pr_payload("closed", merged=True, state="closed"))

        issue = Issue.objects.get(pk=project_setup["issue"].pk)
        assert issue.state_id == project_setup["done"].id

        pr = GithubPullRequest.objects.get(issue=issue, pr_number=42)
        assert pr.state == GithubPullRequest.PullRequestState.MERGED
        assert pr.merged is True
        # state-change activity was dispatched
        assert _activity.delay.called

    @patch("plane.bgtasks.github_webhook_task.issue_activity")
    def test_upsert_is_idempotent(self, _activity, project_setup):
        _handle_pull_request("ws-gh", _pr_payload("opened"))
        _handle_pull_request("ws-gh", _pr_payload("synchronize"))
        assert GithubPullRequest.objects.filter(issue=project_setup["issue"], pr_number=42).count() == 1

    @patch("plane.bgtasks.github_webhook_task.issue_activity")
    def test_merge_cascades_to_all_descendants(self, _activity, project_setup):
        project = project_setup["project"]
        backlog = project_setup["backlog"]
        done = project_setup["done"]
        parent = project_setup["issue"]  # WIT-123, referenced by the PR

        cancelled = State.objects.create(
            name="Cancelled", color="#999", group=StateGroup.CANCELLED.value, project=project
        )
        child_a = Issue.objects.create(name="child a", project=project, state=backlog, parent=parent)
        child_b = Issue.objects.create(name="child b", project=project, state=backlog, parent=parent)
        grandchild = Issue.objects.create(name="grandchild", project=project, state=backlog, parent=child_a)
        cancelled_child = Issue.objects.create(
            name="cancelled child", project=project, state=cancelled, parent=parent
        )

        _handle_pull_request("ws-gh", _pr_payload("closed", merged=True, state="closed"))

        # parent + every descendant moved to the completed state
        for node in (parent, child_a, child_b, grandchild):
            node.refresh_from_db()
            assert node.state_id == done.id, f"{node.name} should be completed"
        # an already-cancelled child is left untouched
        cancelled_child.refresh_from_db()
        assert cancelled_child.state_id == cancelled.id


@pytest.mark.unit
class TestIssueCommentHandler:
    @patch("plane.bgtasks.github_webhook_task.issue_activity")
    def test_preview_url_captured(self, _activity, project_setup):
        _handle_pull_request("ws-gh", _pr_payload("opened"))

        _handle_issue_comment(
            "ws-gh",
            {
                "action": "created",
                "repository": {"id": 555, "full_name": "acme/api"},
                "issue": {"number": 42, "pull_request": {"url": "https://api.github.com/..."}},
                "comment": {"body": "Preview deployed: https://pr-42.preview.tld/"},
            },
        )

        pr = GithubPullRequest.objects.get(issue=project_setup["issue"], pr_number=42)
        assert pr.ephemeral_env_url == "https://pr-42.preview.tld/"

    @patch("plane.bgtasks.github_webhook_task.issue_activity")
    def test_non_pr_comment_ignored(self, _activity, project_setup):
        _handle_pull_request("ws-gh", _pr_payload("opened"))
        _handle_issue_comment(
            "ws-gh",
            {
                "action": "created",
                "repository": {"id": 555, "full_name": "acme/api"},
                "issue": {"number": 42},  # no "pull_request" key -> plain issue comment
                "comment": {"body": "Preview deployed: https://pr-42.preview.tld/"},
            },
        )
        pr = GithubPullRequest.objects.get(issue=project_setup["issue"], pr_number=42)
        assert pr.ephemeral_env_url is None
