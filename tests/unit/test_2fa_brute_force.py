"""
Unit tests for 2FA pending token brute-force lockout (#135).

Verifies that after MAX_2FA_ATTEMPTS failed TOTP verifications against the
same pending token, the token is blacklisted and further attempts are rejected.
"""

from datetime import datetime, timedelta

import jwt
import pytest

from splintarr.config import settings
from splintarr.core.auth import (
    MAX_2FA_ATTEMPTS,
    TokenError,
    _2fa_failed_attempts,
    _access_token_blacklist,
    check_2fa_attempts_exceeded,
    create_2fa_pending_token,
    record_2fa_failure,
    verify_2fa_pending_token,
)


class TestRecord2faFailure:
    """Tests for record_2fa_failure helper."""

    def setup_method(self):
        _2fa_failed_attempts.clear()
        _access_token_blacklist.clear()

    def test_first_failure_returns_false(self):
        token = create_2fa_pending_token(1, "testuser")
        assert record_2fa_failure(token) is False

    def test_second_failure_returns_false(self):
        token = create_2fa_pending_token(1, "testuser")
        record_2fa_failure(token)
        assert record_2fa_failure(token) is False

    def test_third_failure_returns_true_and_blacklists(self):
        token = create_2fa_pending_token(1, "testuser")
        record_2fa_failure(token)
        record_2fa_failure(token)
        assert record_2fa_failure(token) is True

        # Token should now be blacklisted
        payload = jwt.decode(
            token, settings.get_secret_key(), algorithms=[settings.algorithm]
        )
        assert payload["jti"] in _access_token_blacklist

    def test_subsequent_failures_still_return_true(self):
        token = create_2fa_pending_token(1, "testuser")
        for _ in range(MAX_2FA_ATTEMPTS):
            record_2fa_failure(token)
        # 4th attempt
        assert record_2fa_failure(token) is True

    def test_invalid_token_returns_false(self):
        assert record_2fa_failure("garbage") is False

    def test_separate_tokens_tracked_independently(self):
        token1 = create_2fa_pending_token(1, "user1")
        token2 = create_2fa_pending_token(2, "user2")

        # Exhaust token1
        for _ in range(MAX_2FA_ATTEMPTS):
            record_2fa_failure(token1)

        # token2 should still be fine
        assert record_2fa_failure(token2) is False
        assert check_2fa_attempts_exceeded(token2) is False
        assert check_2fa_attempts_exceeded(token1) is True


class TestCheck2faAttemptsExceeded:
    """Tests for check_2fa_attempts_exceeded helper."""

    def setup_method(self):
        _2fa_failed_attempts.clear()
        _access_token_blacklist.clear()

    def test_fresh_token_not_exceeded(self):
        token = create_2fa_pending_token(1, "testuser")
        assert check_2fa_attempts_exceeded(token) is False

    def test_below_threshold_not_exceeded(self):
        token = create_2fa_pending_token(1, "testuser")
        for _ in range(MAX_2FA_ATTEMPTS - 1):
            record_2fa_failure(token)
        assert check_2fa_attempts_exceeded(token) is False

    def test_at_threshold_is_exceeded(self):
        token = create_2fa_pending_token(1, "testuser")
        for _ in range(MAX_2FA_ATTEMPTS):
            record_2fa_failure(token)
        assert check_2fa_attempts_exceeded(token) is True

    def test_invalid_token_returns_false(self):
        assert check_2fa_attempts_exceeded("garbage") is False


class TestBruteForceBlacklistIntegration:
    """End-to-end: after lockout, verify_2fa_pending_token rejects the token."""

    def setup_method(self):
        _2fa_failed_attempts.clear()
        _access_token_blacklist.clear()

    def test_locked_out_token_rejected_by_verify(self):
        token = create_2fa_pending_token(1, "testuser")

        # Should verify fine before lockout
        payload = verify_2fa_pending_token(token)
        assert payload["sub"] == "1"

        # Simulate 3 failed TOTP attempts
        for _ in range(MAX_2FA_ATTEMPTS):
            record_2fa_failure(token)

        # Now verify should reject
        with pytest.raises(TokenError, match="already been used"):
            verify_2fa_pending_token(token)

    def test_fresh_token_works_after_lockout(self):
        token1 = create_2fa_pending_token(1, "testuser")
        for _ in range(MAX_2FA_ATTEMPTS):
            record_2fa_failure(token1)

        # New login produces a new token -- should work fine
        token2 = create_2fa_pending_token(1, "testuser")
        payload = verify_2fa_pending_token(token2)
        assert payload["sub"] == "1"
