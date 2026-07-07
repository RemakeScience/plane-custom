# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for the inbound GitHub webhook endpoint (HMAC gate + enqueue)."""

import hashlib
import hmac

import pytest

WEBHOOK_URL = "/api/workspaces/ws-gh/github/webhook/"
SECRET = "webhook-s3cret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.contract
class TestGithubWebhookEndpoint:
    def _patches(self, mocker):
        mocker.patch(
            "plane.app.views.external.github.receiver.get_configuration_value",
            return_value=(SECRET,),
        )
        return mocker.patch("plane.app.views.external.github.receiver.github_webhook_task.delay")

    def test_valid_signature_enqueues_and_returns_202(self, api_client, mocker):
        delay = self._patches(mocker)
        body = b'{"action":"opened"}'
        resp = api_client.post(
            WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_sign(body),
            HTTP_X_GITHUB_EVENT="pull_request",
            HTTP_X_GITHUB_DELIVERY="d-1",
        )
        assert resp.status_code == 202
        assert delay.called

    def test_invalid_signature_returns_401(self, api_client, mocker):
        delay = self._patches(mocker)
        body = b'{"action":"opened"}'
        resp = api_client.post(
            WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=deadbeef",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert resp.status_code == 401
        assert not delay.called

    def test_ping_returns_200_without_enqueue(self, api_client, mocker):
        delay = self._patches(mocker)
        body = b'{"zen":"hi"}'
        resp = api_client.post(
            WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_sign(body),
            HTTP_X_GITHUB_EVENT="ping",
        )
        assert resp.status_code == 200
        assert not delay.called

    def test_missing_secret_returns_503(self, api_client, mocker):
        mocker.patch(
            "plane.app.views.external.github.receiver.get_configuration_value",
            return_value=(None,),
        )
        resp = api_client.post(
            WEBHOOK_URL,
            data=b"{}",
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert resp.status_code == 503
