# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import pytest
from rest_framework import status

from plane.db.models import (
    Issue,
    IssueType,
    Project,
    ProjectIssueType,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)


class TestEpicBase:
    """Shared helpers for the Epic app endpoints."""

    def create_project(self, workspace, user, role=20):
        """Create a project (with a default state) and add ``user`` as member."""
        project = Project.objects.create(
            name=f"Project {uuid.uuid4().hex[:6]}",
            identifier=uuid.uuid4().hex[:5].upper(),
            workspace=workspace,
        )
        ProjectMember.objects.create(project=project, member=user, role=role, is_active=True)
        # Issues (and epics) are excluded from the manager querysets when they
        # have no state, so give the project a usable default state.
        State.objects.create(
            name="Backlog",
            group="backlog",
            project=project,
            workspace=workspace,
            default=True,
        )
        return project

    def enable_epics(self, workspace, project):
        """Create the project's epic type directly, as the enable endpoint does."""
        epic_type = IssueType.objects.create(
            workspace=workspace, name="Epic", is_epic=True, is_default=True, is_active=True
        )
        ProjectIssueType.objects.create(issue_type=epic_type, project=project, is_default=True)
        return epic_type

    def make_issue(self, workspace, project, name="Issue", issue_type=None):
        """Create an Issue (optionally typed) directly in the DB."""
        issue = Issue.objects.create(
            name=name,
            project=project,
            workspace=workspace,
            state=State.objects.filter(project=project).first(),
            type=issue_type,
        )
        return issue

    def epic_list_url(self, slug, project_id):
        return f"/api/workspaces/{slug}/projects/{project_id}/epics/"

    def epic_detail_url(self, slug, project_id, pk):
        return f"/api/workspaces/{slug}/projects/{project_id}/epics/{pk}/"

    def issue_list_url(self, slug, project_id):
        return f"/api/workspaces/{slug}/projects/{project_id}/issues/"


@pytest.mark.contract
class TestEpicCreate(TestEpicBase):
    @pytest.mark.django_db
    def test_create_epic_forces_epic_type(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        epic_type = self.enable_epics(workspace, project)

        response = session_client.post(
            self.epic_list_url(workspace.slug, project.id),
            {"name": "Q3 Launch"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        epic = Issue.all_objects.get(id=response.json()["id"])
        # The epic type is forced regardless of the payload.
        assert epic.type_id == epic_type.id

    @pytest.mark.django_db
    def test_create_epic_ignores_client_type(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        epic_type = self.enable_epics(workspace, project)
        # A non-epic type the client might try to sneak in.
        other = IssueType.objects.create(workspace=workspace, name="Bug", is_epic=False)
        ProjectIssueType.objects.create(issue_type=other, project=project)

        response = session_client.post(
            self.epic_list_url(workspace.slug, project.id),
            {"name": "Epic", "type_id": str(other.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        epic = Issue.all_objects.get(id=response.json()["id"])
        assert epic.type_id == epic_type.id

    @pytest.mark.django_db
    def test_create_epic_without_epic_type_returns_400(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        # Epics not enabled: no epic type exists.

        response = session_client.post(
            self.epic_list_url(workspace.slug, project.id),
            {"name": "Epic"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Issue.all_objects.count() == 0

    @pytest.mark.django_db
    def test_guest_cannot_create_epic(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        self.enable_epics(workspace, project)
        # A dedicated guest (role 5 at both workspace and project level) so the
        # workspace-admin override does not apply.
        guest = User.objects.create_user(email="guest@example.com", username="guest")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5, is_active=True)
        ProjectMember.objects.create(project=project, member=guest, role=5, is_active=True)
        session_client.force_authenticate(user=guest)

        response = session_client.post(
            self.epic_list_url(workspace.slug, project.id),
            {"name": "Epic"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
class TestEpicList(TestEpicBase):
    @pytest.mark.django_db
    def test_list_returns_only_epics(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        epic_type = self.enable_epics(workspace, project)
        epic = self.make_issue(workspace, project, name="Epic A", issue_type=epic_type)
        # A regular work item (untyped) must not show up in the epics list.
        self.make_issue(workspace, project, name="Regular")

        response = session_client.get(self.epic_list_url(workspace.slug, project.id))

        assert response.status_code == status.HTTP_200_OK
        ids = {row["id"] for row in response.json()["results"]}
        assert ids == {str(epic.id)}

    @pytest.mark.django_db
    def test_epics_excluded_from_work_item_list(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        epic_type = self.enable_epics(workspace, project)
        self.make_issue(workspace, project, name="Epic A", issue_type=epic_type)
        regular = self.make_issue(workspace, project, name="Regular")

        response = session_client.get(self.issue_list_url(workspace.slug, project.id))

        assert response.status_code == status.HTTP_200_OK
        ids = {row["id"] for row in response.json()["results"]}
        # The regular work item list must exclude epics (regression guard).
        assert ids == {str(regular.id)}


@pytest.mark.contract
class TestEpicManagers(TestEpicBase):
    @pytest.mark.django_db
    def test_managers_partition_epics_and_issues(self, workspace, create_user):
        project = self.create_project(workspace, create_user)
        epic_type = self.enable_epics(workspace, project)
        epic = self.make_issue(workspace, project, name="Epic", issue_type=epic_type)
        regular = self.make_issue(workspace, project, name="Regular")

        issue_ids = set(Issue.issue_objects.values_list("id", flat=True))
        epic_ids = set(Issue.epic_objects.values_list("id", flat=True))

        # issue_objects excludes epics; epic_objects contains only epics.
        assert regular.id in issue_ids and epic.id not in issue_ids
        assert epic.id in epic_ids and regular.id not in epic_ids


@pytest.mark.contract
class TestEpicDetail(TestEpicBase):
    @pytest.mark.django_db
    def test_retrieve_epic(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        epic_type = self.enable_epics(workspace, project)
        epic = self.make_issue(workspace, project, name="Epic", issue_type=epic_type)

        response = session_client.get(self.epic_detail_url(workspace.slug, project.id, epic.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(epic.id)

    @pytest.mark.django_db
    def test_update_epic(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        epic_type = self.enable_epics(workspace, project)
        epic = self.make_issue(workspace, project, name="Epic", issue_type=epic_type)

        response = session_client.patch(
            self.epic_detail_url(workspace.slug, project.id, epic.id),
            {"name": "Renamed Epic"},
            format="json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        epic.refresh_from_db()
        assert epic.name == "Renamed Epic"

    @pytest.mark.django_db
    def test_delete_epic(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        epic_type = self.enable_epics(workspace, project)
        epic = self.make_issue(workspace, project, name="Epic", issue_type=epic_type)

        response = session_client.delete(self.epic_detail_url(workspace.slug, project.id, epic.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Issue.epic_objects.filter(id=epic.id).exists()

    @pytest.mark.django_db
    def test_epic_child_relationship(self, session_client, workspace, create_user):
        """An epic can parent regular work items via the existing parent FK."""
        project = self.create_project(workspace, create_user)
        epic_type = self.enable_epics(workspace, project)
        epic = self.make_issue(workspace, project, name="Epic", issue_type=epic_type)
        child = self.make_issue(workspace, project, name="Child")
        child.parent = epic
        child.save()

        # The child is a regular work item (still in issue_objects) parented to
        # the epic, while the epic itself stays out of the regular list.
        assert child.id in set(Issue.issue_objects.values_list("id", flat=True))
        assert set(Issue.issue_objects.filter(parent=epic).values_list("id", flat=True)) == {child.id}
