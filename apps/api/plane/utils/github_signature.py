# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import hashlib
import hmac


def verify_github_signature(payload_body: bytes, secret: str, signature_header: str) -> bool:
    """Verify the ``X-Hub-Signature-256`` header GitHub sends with each webhook.

    GitHub signs the *raw request body bytes* (not a re-serialized JSON), so the
    caller MUST pass ``request.body`` unchanged. The header is of the form
    ``sha256=<hexdigest>``. Comparison is constant-time to avoid timing attacks.

    Mirrors the outbound HMAC used in ``plane/bgtasks/webhook_task.py``.
    """
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)
