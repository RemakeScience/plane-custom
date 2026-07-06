# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import pytest
from rest_framework import status

from plane.db.models import (
    Issue,
    IssueProperty,
    IssuePropertyOption,
    IssuePropertyValue,
    IssueType,
    Project,
    ProjectIssueType,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)


class TestIssuePropertyBase:
    def create_project(self, workspace, user, role=20):
        project = Project.objects.create(
            name=f"Project {uuid.uuid4().hex[:6]}",
            identifier=uuid.uuid4().hex[:5].upper(),
            workspace=workspace,
        )
        ProjectMember.objects.create(project=project, member=user, role=role, is_active=True)
        State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace, default=True)
        return project

    def make_type(self, workspace, project, name="Task"):
        issue_type = IssueType.objects.create(workspace=workspace, name=name, is_default=True)
        ProjectIssueType.objects.create(issue_type=issue_type, project=project, is_default=True)
        return issue_type

    def make_property(self, workspace, project, issue_type, **kwargs):
        defaults = dict(
            name="severity",
            display_name="Severity",
            property_type="TEXT",
        )
        defaults.update(kwargs)
        return IssueProperty.objects.create(
            workspace=workspace, project=project, issue_type=issue_type, **defaults
        )

    def make_issue(self, workspace, project, name="Issue"):
        return Issue.objects.create(
            name=name,
            project=project,
            workspace=workspace,
            state=State.objects.filter(project=project).first(),
        )

    def properties_url(self, slug, project_id, type_id):
        return f"/api/workspaces/{slug}/projects/{project_id}/issue-types/{type_id}/properties/"

    def property_detail_url(self, slug, project_id, type_id, pk):
        return f"/api/workspaces/{slug}/projects/{project_id}/issue-types/{type_id}/properties/{pk}/"

    def options_url(self, slug, project_id, property_id):
        return f"/api/workspaces/{slug}/projects/{project_id}/issue-properties/{property_id}/options/"

    def aggregate_url(self, slug, project_id):
        return f"/api/workspaces/{slug}/projects/{project_id}/issue-property-types/"

    def values_url(self, slug, project_id, issue_id):
        return f"/api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/property-values/"


@pytest.mark.contract
class TestIssuePropertyCRUD(TestIssuePropertyBase):
    @pytest.mark.django_db
    def test_create_property(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)

        response = session_client.post(
            self.properties_url(workspace.slug, project.id, issue_type.id),
            {"name": "severity", "display_name": "Severity", "property_type": "TEXT", "is_required": True},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        prop = IssueProperty.objects.get(id=response.json()["id"])
        assert prop.issue_type_id == issue_type.id
        assert prop.workspace_id == workspace.id
        assert prop.is_required is True

    @pytest.mark.django_db
    def test_list_properties(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        self.make_property(workspace, project, issue_type)

        response = session_client.get(self.properties_url(workspace.slug, project.id, issue_type.id))

        assert response.status_code == status.HTTP_200_OK
        assert {p["name"] for p in response.json()} == {"severity"}

    @pytest.mark.django_db
    def test_guest_cannot_create_property(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        guest = User.objects.create_user(email="guest@example.com", username="guest")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5, is_active=True)
        ProjectMember.objects.create(project=project, member=guest, role=5, is_active=True)
        session_client.force_authenticate(user=guest)

        response = session_client.post(
            self.properties_url(workspace.slug, project.id, issue_type.id),
            {"name": "x", "display_name": "X", "property_type": "TEXT"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_update_and_delete_property(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        prop = self.make_property(workspace, project, issue_type)

        patch = session_client.patch(
            self.property_detail_url(workspace.slug, project.id, issue_type.id, prop.id),
            {"display_name": "Renamed"},
            format="json",
        )
        assert patch.status_code == status.HTTP_200_OK
        prop.refresh_from_db()
        assert prop.display_name == "Renamed"

        delete = session_client.delete(
            self.property_detail_url(workspace.slug, project.id, issue_type.id, prop.id)
        )
        assert delete.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueProperty.objects.filter(id=prop.id).exists()


@pytest.mark.contract
class TestIssuePropertyOptions(TestIssuePropertyBase):
    @pytest.mark.django_db
    def test_create_option_and_aggregate(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        prop = self.make_property(workspace, project, issue_type, name="priority", property_type="OPTION")

        response = session_client.post(
            self.options_url(workspace.slug, project.id, prop.id),
            {"name": "High"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert IssuePropertyOption.objects.filter(property=prop, name="High").exists()

        # Aggregated endpoint exposes the property with its option nested.
        agg = session_client.get(self.aggregate_url(workspace.slug, project.id))
        assert agg.status_code == status.HTTP_200_OK
        prop_row = next(p for p in agg.json() if p["id"] == str(prop.id))
        assert {o["name"] for o in prop_row["options"]} == {"High"}


@pytest.mark.contract
class TestIssuePropertyValues(TestIssuePropertyBase):
    @pytest.mark.django_db
    def test_set_and_read_text_value(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        prop = self.make_property(workspace, project, issue_type, property_type="TEXT")
        issue = self.make_issue(workspace, project)

        response = session_client.post(
            self.values_url(workspace.slug, project.id, issue.id),
            {str(prop.id): ["critical"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[str(prop.id)] == ["critical"]
        assert IssuePropertyValue.objects.filter(issue=issue, property=prop).count() == 1

    @pytest.mark.django_db
    def test_option_value(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        prop = self.make_property(workspace, project, issue_type, property_type="OPTION")
        option = IssuePropertyOption.objects.create(workspace=workspace, project=project, property=prop, name="High")
        issue = self.make_issue(workspace, project)

        response = session_client.post(
            self.values_url(workspace.slug, project.id, issue.id),
            {str(prop.id): [str(option.id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[str(prop.id)] == [str(option.id)]

    @pytest.mark.django_db
    def test_required_value_rejected_when_empty(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        prop = self.make_property(workspace, project, issue_type, is_required=True)
        issue = self.make_issue(workspace, project)

        response = session_client.post(
            self.values_url(workspace.slug, project.id, issue.id),
            {str(prop.id): []},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_single_value_rejects_multiple(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        prop = self.make_property(workspace, project, issue_type, is_multi=False)
        issue = self.make_issue(workspace, project)

        response = session_client.post(
            self.values_url(workspace.slug, project.id, issue.id),
            {str(prop.id): ["a", "b"]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_multi_value_accepts_multiple(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        prop = self.make_property(workspace, project, issue_type, is_multi=True)
        issue = self.make_issue(workspace, project)

        response = session_client.post(
            self.values_url(workspace.slug, project.id, issue.id),
            {str(prop.id): ["a", "b"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert set(response.json()[str(prop.id)]) == {"a", "b"}
        assert IssuePropertyValue.objects.filter(issue=issue, property=prop).count() == 2

    @pytest.mark.django_db
    def test_invalid_decimal_rejected(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        prop = self.make_property(workspace, project, issue_type, property_type="DECIMAL")
        issue = self.make_issue(workspace, project)

        response = session_client.post(
            self.values_url(workspace.slug, project.id, issue.id),
            {str(prop.id): ["not-a-number"]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_upsert_replaces_previous_values(self, session_client, workspace, create_user):
        project = self.create_project(workspace, create_user)
        issue_type = self.make_type(workspace, project)
        prop = self.make_property(workspace, project, issue_type, property_type="TEXT")
        issue = self.make_issue(workspace, project)

        session_client.post(
            self.values_url(workspace.slug, project.id, issue.id),
            {str(prop.id): ["first"]},
            format="json",
        )
        second = session_client.post(
            self.values_url(workspace.slug, project.id, issue.id),
            {str(prop.id): ["second"]},
            format="json",
        )
        assert second.status_code == status.HTTP_200_OK
        assert second.json()[str(prop.id)] == ["second"]
        assert IssuePropertyValue.objects.filter(issue=issue, property=prop).count() == 1
