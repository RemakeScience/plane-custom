# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import pytest
from rest_framework import status

from plane.db.models import (
    Project,
    ProjectMember,
    WorkspaceMember,
    User,
    Issue,
    IssueType,
    ProjectIssueType,
)


class TestIssueTypeBase:
    """Shared helpers for the Work Item Type (issue type) app endpoints."""

    def create_project(self, workspace, user, role=20):
        """Create a project and make ``user`` a project member with ``role``."""
        project = Project.objects.create(name=f"Project {uuid.uuid4().hex[:6]}", identifier=uuid.uuid4().hex[:5].upper(), workspace=workspace)
        ProjectMember.objects.create(project=project, member=user, role=role, is_active=True)
        return project

    def list_url(self, slug, project_id):
        return f"/api/workspaces/{slug}/projects/{project_id}/issue-types/"

    def detail_url(self, slug, project_id, pk):
        return f"/api/workspaces/{slug}/projects/{project_id}/issue-types/{pk}/"

    def mark_default_url(self, slug, project_id, pk):
        return f"/api/workspaces/{slug}/projects/{project_id}/issue-types/{pk}/mark-default/"

    def default_url(self, slug, project_id):
        return f"/api/workspaces/{slug}/projects/{project_id}/default-issue-type/"

    def make_type(self, workspace, project, name="Type", is_epic=False, is_default=False):
        """Create an IssueType + its ProjectIssueType association directly in the DB."""
        issue_type = IssueType.objects.create(workspace=workspace, name=name, is_epic=is_epic, is_default=is_default)
        ProjectIssueType.objects.create(issue_type=issue_type, project=project, is_default=is_default)
        return issue_type


@pytest.mark.contract
class TestIssueTypeCreate(TestIssueTypeBase):
    @pytest.mark.django_db
    def test_create_issue_type_admin(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)

        response = session_client.post(
            self.list_url(workspace.slug, project.id),
            {"name": "Bug", "description": "A defect"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Bug"
        # A workspace-scoped IssueType and a project association are both created.
        issue_type = IssueType.objects.get(id=data["id"])
        assert issue_type.workspace_id == workspace.id
        assert issue_type.is_epic is False
        assert ProjectIssueType.objects.filter(issue_type=issue_type, project=project).exists()

    @pytest.mark.django_db
    def test_create_default_unsets_other_defaults(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        existing = self.make_type(workspace, project, name="Task", is_default=True)

        response = session_client.post(
            self.list_url(workspace.slug, project.id),
            {"name": "Story", "is_default": True},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        existing.refresh_from_db()
        assert existing.is_default is False
        assert IssueType.objects.get(id=response.json()["id"]).is_default is True

    @pytest.mark.django_db
    def test_create_cannot_set_is_epic(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)

        response = session_client.post(
            self.list_url(workspace.slug, project.id),
            {"name": "Sneaky", "is_epic": True},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert IssueType.objects.get(id=response.json()["id"]).is_epic is False

    @pytest.mark.django_db
    def test_create_guest_forbidden(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        guest = User.objects.create_user(email="guest@example.com", username="guest")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5, is_active=True)
        ProjectMember.objects.create(project=project, member=guest, role=5, is_active=True)
        session_client.force_authenticate(user=guest)

        response = session_client.post(
            self.list_url(workspace.slug, project.id),
            {"name": "Bug"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_create_unauthenticated(self, client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        response = client.post(self.list_url(workspace.slug, project.id), {"name": "Bug"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.contract
class TestIssueTypeList(TestIssueTypeBase):
    @pytest.mark.django_db
    def test_list_excludes_epics(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        self.make_type(workspace, project, name="Bug")
        self.make_type(workspace, project, name="Feature")
        self.make_type(workspace, project, name="Epic", is_epic=True)

        response = session_client.get(self.list_url(workspace.slug, project.id))

        assert response.status_code == status.HTTP_200_OK
        names = {t["name"] for t in response.json()}
        assert names == {"Bug", "Feature"}

    @pytest.mark.django_db
    def test_retrieve(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project, name="Bug")

        response = session_client.get(self.detail_url(workspace.slug, project.id, issue_type.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Bug"


@pytest.mark.contract
class TestIssueTypeUpdateDelete(TestIssueTypeBase):
    @pytest.mark.django_db
    def test_partial_update_admin(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project, name="Bug")

        response = session_client.patch(
            self.detail_url(workspace.slug, project.id, issue_type.id),
            {"name": "Defect"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        issue_type.refresh_from_db()
        assert issue_type.name == "Defect"

    @pytest.mark.django_db
    def test_partial_update_non_admin_forbidden(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project, name="Bug")
        member = User.objects.create_user(email="member@example.com", username="member")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15, is_active=True)
        ProjectMember.objects.create(project=project, member=member, role=15, is_active=True)
        session_client.force_authenticate(user=member)

        response = session_client.patch(
            self.detail_url(workspace.slug, project.id, issue_type.id),
            {"name": "Hacked"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_delete_non_default_nulls_issue_type(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project, name="Bug")
        issue = Issue.objects.create(name="A work item", project=project, type=issue_type, created_by=create_user)

        response = session_client.delete(self.detail_url(workspace.slug, project.id, issue_type.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueType.objects.filter(id=issue_type.id).exists()
        # Issue.type is SET_NULL: the work item survives, untyped.
        issue.refresh_from_db()
        assert issue.type_id is None

    @pytest.mark.django_db
    def test_delete_default_forbidden(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project, name="Task", is_default=True)

        response = session_client.delete(self.detail_url(workspace.slug, project.id, issue_type.id))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert IssueType.objects.filter(id=issue_type.id).exists()


@pytest.mark.contract
class TestIssueTypeDefaultAndMarkDefault(TestIssueTypeBase):
    @pytest.mark.django_db
    def test_mark_as_default_switches(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        current = self.make_type(workspace, project, name="Task", is_default=True)
        target = self.make_type(workspace, project, name="Bug", is_default=False)

        response = session_client.post(self.mark_default_url(workspace.slug, project.id, target.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        current.refresh_from_db()
        target.refresh_from_db()
        assert current.is_default is False
        assert target.is_default is True

    @pytest.mark.django_db
    def test_default_endpoint_creates_and_backfills(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        untyped = Issue.objects.create(name="Legacy item", project=project, created_by=create_user)
        assert untyped.type_id is None

        response = session_client.post(self.default_url(workspace.slug, project.id))

        assert response.status_code == status.HTTP_201_CREATED
        default_type = IssueType.objects.get(id=response.json()["id"])
        assert default_type.is_default is True
        # Existing untyped work items are attached to the new default type.
        untyped.refresh_from_db()
        assert untyped.type_id == default_type.id

    @pytest.mark.django_db
    def test_default_endpoint_is_idempotent(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        first = session_client.post(self.default_url(workspace.slug, project.id))
        assert first.status_code == status.HTTP_201_CREATED

        second = session_client.post(self.default_url(workspace.slug, project.id))
        # No duplicate default type is created on a second call.
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["id"] == first.json()["id"]
        assert IssueType.objects.filter(workspace=workspace, is_default=True, is_epic=False).count() == 1
