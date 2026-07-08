# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for the external v1 API (PAT-authenticated) surface added by
the fork: epics, work item types, and custom properties."""

import pytest
from rest_framework import status

from plane.db.models import (
    Issue,
    IssueProperty,
    IssueType,
    Project,
    ProjectIssueType,
    ProjectMember,
)


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Types Project", identifier="TP", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


def _add_type(workspace, project, name, is_epic=False, is_default=False):
    issue_type = IssueType.objects.create(
        workspace=workspace, name=name, is_epic=is_epic, is_default=is_default, is_active=True
    )
    ProjectIssueType.objects.create(issue_type=issue_type, project=project, is_default=is_default)
    return issue_type


@pytest.fixture
def task_type(db, workspace, project):
    return _add_type(workspace, project, "Task", is_epic=False, is_default=True)


@pytest.fixture
def epic_type(db, workspace, project):
    return _add_type(workspace, project, "Epic", is_epic=True, is_default=True)


def _v1(workspace, project, suffix):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/{suffix}"


@pytest.mark.contract
class TestEpicsAPI:
    @pytest.mark.django_db
    def test_create_epic_forces_epic_type(self, api_key_client, workspace, project, epic_type):
        resp = api_key_client.post(_v1(workspace, project, "epics/"), {"name": "Migration"}, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["type_id"] == epic_type.id
        assert Issue.epic_objects.filter(id=resp.data["id"]).exists()

    @pytest.mark.django_db
    def test_create_epic_requires_epic_type(self, api_key_client, workspace, project, task_type):
        # No epic type on the project → 400
        resp = api_key_client.post(_v1(workspace, project, "epics/"), {"name": "Nope"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_list_scoped_to_epics(self, api_key_client, workspace, project, epic_type, task_type):
        epic = Issue.objects.create(name="E1", project=project, type=epic_type)
        regular = Issue.objects.create(name="R1", project=project, type=task_type)
        resp = api_key_client.get(_v1(workspace, project, "epics/"))
        assert resp.status_code == status.HTTP_200_OK
        ids = {r["id"] for r in resp.data["results"]}
        assert epic.id in ids and regular.id not in ids

    @pytest.mark.django_db
    def test_retrieve_and_delete_epic(self, api_key_client, workspace, project, epic_type):
        epic = Issue.objects.create(name="E", project=project, type=epic_type)
        assert api_key_client.get(_v1(workspace, project, f"epics/{epic.id}/")).status_code == status.HTTP_200_OK
        assert api_key_client.delete(_v1(workspace, project, f"epics/{epic.id}/")).status_code == (
            status.HTTP_204_NO_CONTENT
        )


@pytest.mark.contract
class TestWorkItemTypesAPI:
    @pytest.mark.django_db
    def test_list_excludes_epics(self, api_key_client, workspace, project, task_type, epic_type):
        resp = api_key_client.get(_v1(workspace, project, "issue-types/"))
        assert resp.status_code == status.HTTP_200_OK
        names = {r["name"] for r in resp.data["results"]}
        assert "Task" in names and "Epic" not in names

    @pytest.mark.django_db
    def test_create_type(self, api_key_client, workspace, project):
        resp = api_key_client.post(_v1(workspace, project, "issue-types/"), {"name": "Spike"}, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["is_epic"] is False
        assert ProjectIssueType.objects.filter(issue_type_id=resp.data["id"], project=project).exists()

    @pytest.mark.django_db
    def test_epic_type_read(self, api_key_client, workspace, project, epic_type):
        resp = api_key_client.get(_v1(workspace, project, "epic-type/"))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["id"] == epic_type.id and resp.data["is_epic"] is True

    @pytest.mark.django_db
    def test_epic_type_404_when_disabled(self, api_key_client, workspace, project, task_type):
        assert api_key_client.get(_v1(workspace, project, "epic-type/")).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
class TestCustomPropertiesAPI:
    @pytest.mark.django_db
    def test_create_property_and_value_roundtrip(self, api_key_client, workspace, project, task_type):
        # Create a TEXT property on the Task type
        resp = api_key_client.post(
            _v1(workspace, project, f"issue-types/{task_type.id}/properties/"),
            {"name": "note", "display_name": "Note", "property_type": "TEXT"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        prop_id = str(resp.data["id"])

        issue = Issue.objects.create(name="WI", project=project, type=task_type)
        url = _v1(workspace, project, f"work-items/{issue.id}/property-values/")
        assert api_key_client.post(url, {prop_id: ["hello"]}, format="json").status_code == status.HTTP_200_OK
        get_resp = api_key_client.get(url)
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.data[prop_id] == ["hello"]

    @pytest.mark.django_db
    def test_property_value_works_on_epic(self, api_key_client, workspace, project, task_type, epic_type):
        prop = IssueProperty.objects.create(
            workspace=workspace,
            project=project,
            issue_type=task_type,
            name="sev",
            display_name="Sev",
            property_type="TEXT",
        )
        epic = Issue.objects.create(name="E", project=project, type=epic_type)
        url = _v1(workspace, project, f"work-items/{epic.id}/property-values/")
        # The work item is resolved via Issue.objects, so an epic is not a 404.
        assert api_key_client.post(url, {str(prop.id): ["x"]}, format="json").status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    def test_property_value_invalid_work_item(self, api_key_client, workspace, project):
        from uuid import uuid4

        url = _v1(workspace, project, f"work-items/{uuid4()}/property-values/")
        assert api_key_client.post(url, {}, format="json").status_code == status.HTTP_404_NOT_FOUND
