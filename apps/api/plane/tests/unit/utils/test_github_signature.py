# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the inbound GitHub webhook helpers: HMAC verification and the
work-item reference regex. Pure functions, no DB."""

import hashlib
import hmac

import pytest

from plane.utils.github_signature import verify_github_signature
from plane.bgtasks.github_webhook_task import WORK_ITEM_REF, EPHEMERAL_URL


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.unit
class TestVerifyGithubSignature:
    SECRET = "s3cr3t"
    BODY = b'{"action":"opened"}'

    def test_valid_signature(self):
        assert verify_github_signature(self.BODY, self.SECRET, _sign(self.BODY, self.SECRET)) is True

    def test_tampered_body(self):
        sig = _sign(self.BODY, self.SECRET)
        assert verify_github_signature(b'{"action":"closed"}', self.SECRET, sig) is False

    def test_wrong_secret(self):
        assert verify_github_signature(self.BODY, "other", _sign(self.BODY, self.SECRET)) is False

    def test_bad_header_format(self):
        raw = hmac.new(self.SECRET.encode(), self.BODY, hashlib.sha256).hexdigest()  # no "sha256=" prefix
        assert verify_github_signature(self.BODY, self.SECRET, raw) is False

    def test_empty_secret_or_header(self):
        assert verify_github_signature(self.BODY, "", _sign(self.BODY, self.SECRET)) is False
        assert verify_github_signature(self.BODY, self.SECRET, "") is False


@pytest.mark.unit
class TestWorkItemRef:
    def _refs(self, text):
        return [(i.upper(), int(s)) for i, s in WORK_ITEM_REF.findall(text)]

    def test_hash_prefixed_in_title(self):
        assert self._refs("Fix login #WIT-123") == [("WIT", 123)]

    def test_bare_ref_in_branch(self):
        assert self._refs("feat/WIT-123-foo") == [("WIT", 123)]

    def test_case_insensitive(self):
        assert self._refs("wit-7") == [("WIT", 7)]

    def test_longer_ident_is_its_own_candidate(self):
        # "ABWIT" is a valid candidate identifier; DB resolution decides validity.
        assert self._refs("ABWIT-123") == [("ABWIT", 123)]

    def test_no_match_when_glued_after_digits(self):
        # A ref welded onto preceding digits is not a reference.
        assert self._refs("123WIT-45") == []

    def test_trailing_digits_kept_whole(self):
        assert self._refs("WIT-1234") == [("WIT", 1234)]

    def test_multiple_refs(self):
        assert set(self._refs("#WIT-1 and API-2")) == {("WIT", 1), ("API", 2)}


@pytest.mark.unit
class TestEphemeralUrl:
    def test_matches_preview_url(self):
        m = EPHEMERAL_URL.search("Preview deployed: https://pr-123.preview.tld/ ok")
        assert m and m.group(0) == "https://pr-123.preview.tld/"

    def test_no_match_without_preview_keyword(self):
        assert EPHEMERAL_URL.search("Deployed to https://pr-123.staging.tld") is None
