# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json
import os

# Third party imports
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

# Module imports
from plane.bgtasks.github_webhook_task import github_webhook_task
from plane.license.utils.instance_value import get_configuration_value
from plane.utils.exception_logger import log_exception
from plane.utils.github_signature import verify_github_signature


class GithubWebhookEndpoint(APIView):
    """Inbound receiver for GitHub App webhooks.

    Unauthenticated: GitHub cannot present a Plane session/token, so authenticity
    is established by verifying the ``X-Hub-Signature-256`` HMAC over the raw
    request body (constant-time) against ``GITHUB_WEBHOOK_SECRET``. The endpoint
    only verifies + enqueues, returning fast so GitHub's ~10s timeout is met; all
    parsing/DB work happens in ``github_webhook_task``.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, slug):
        (github_webhook_secret,) = get_configuration_value(
            [{"key": "GITHUB_WEBHOOK_SECRET", "default": os.environ.get("GITHUB_WEBHOOK_SECRET")}]
        )
        if not github_webhook_secret:
            return Response(
                {"error": "GitHub webhook secret is not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        signature = request.headers.get("X-Hub-Signature-256", "")
        # request.body is the exact bytes GitHub signed — must not be re-serialized.
        if not verify_github_signature(request.body, github_webhook_secret, signature):
            return Response({"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        event = request.headers.get("X-GitHub-Event", "")
        delivery_id = request.headers.get("X-GitHub-Delivery", "")

        # Health check GitHub sends when the webhook is created.
        if event == "ping":
            return Response({"message": "pong"}, status=status.HTTP_200_OK)

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return Response({"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            github_webhook_task.delay(event=event, delivery_id=delivery_id, slug=slug, payload=payload)
        except Exception as e:
            log_exception(e)
            return Response(
                {"error": "Failed to enqueue webhook"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"message": "accepted"}, status=status.HTTP_202_ACCEPTED)
