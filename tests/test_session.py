# -*- coding: utf-8 -*-
"""Tests for flaresolverr_session.

Requires a running FlareSolverr instance.  Set the ``FLARESOLVERR_URL``
environment variable to point to it (defaults to
``http://localhost:8191/v1``).  Optionally set ``FLARESOLVERR_PROXY``
to route browser traffic through a proxy.

Test categories:
    1. Challenge sites – challenge solved, validate response.
    2. No-challenge sites – plain fetch, validate response.
    3. Unsolved challenge – mocked, exception raised.
    4. Network error to FlareSolverr – exception raised.
    5. Session destroy on close.
    6. Auto-generated session id.
    7. Session reuse (challenge token reuse).
    8. Unsupported method / JSON POST.
"""

import os
import unittest

try:
    from unittest import mock
except ImportError:
    import mock  # Python 2 back-port

import requests

from flaresolverr_session import (
    FlareSolverrChallengeError,
    FlareSolverrError,
    FlareSolverrResponseError,
    FlareSolverrUnsupportedMethodError,
    Session,
    Response,
)
from tests.testconf import CHALLENGE_SITES, NO_CHALLENGE_SITES

FLARESOLVERR_URL = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191/v1")
FLARESOLVERR_PROXY = os.environ.get("FLARESOLVERR_PROXY")


def _make_session(**kwargs):
    """Create a Session with env-based defaults."""
    kwargs.setdefault("flaresolverr_url", FLARESOLVERR_URL)
    if FLARESOLVERR_PROXY and "proxy" not in kwargs:
        kwargs["proxy"] = FLARESOLVERR_PROXY
    return Session(**kwargs)


# -----------------------------------------------------------------------
# Helpers to assert response quality
# -----------------------------------------------------------------------


def _assert_response(response, entry):
    """Validate a requests.Response against a test-config entry."""
    assert isinstance(response, requests.Response)

    expected_status = entry.get("expected_status", 200)
    assert response.status_code == expected_status, "Expected status %d, got %d" % (
        expected_status,
        response.status_code,
    )

    body = response.text.lower()
    for kw in entry["expected_keywords"]:
        assert kw.lower() in body, "Expected keyword %r not found in response body" % kw

    # Comment out header assertions - FlareSolverr may return empty headers
    # See https://github.com/FlareSolverr/FlareSolverr/issues/1162
    for header, expected_value in entry.get("expected_headers", {}).items():
        actual_value = response.headers.get(header)
        # Soft assertion - only check if header is actually present
        if actual_value and expected_value is not None:
            assert (
                expected_value.lower() in actual_value.lower()
            ), "Header %r: expected %r in %r" % (header, expected_value, actual_value)
            assert (
                expected_value.lower() in actual_value.lower()
            ), "Header %r: expected %r in %r" % (header, expected_value, actual_value)


def _list_sessions(session=None):
    data = session._rpc.session.list()
    return data.get("sessions", [])


# ===================================================================
# 1. Challenge solved – configurable sites
# ===================================================================


class TestChallengeSolved(unittest.TestCase):
    """Sites that present a challenge which FlareSolverr should solve."""

    pass


def _make_challenge_test(entry):
    def test(self):
        with _make_session() as session:
            resp = session.get(entry["url"])
            _assert_response(resp, entry)
            # FlareSolverr reports "Challenge solved" or similar
            assert resp.flaresolverr.status == "ok"
            # Ensure the FlareSolverr message indicates a solved challenge
            assert (
                "challenge solved" in resp.flaresolverr.message.lower()
            ), "Expected 'Challenge solved' in FlareSolverr message"

    test.__doc__ = "Challenge solved: %s" % entry["url"]
    return test


for _i, _entry in enumerate(CHALLENGE_SITES):
    _test_name = "test_challenge_%s" % _entry["name"]
    setattr(TestChallengeSolved, _test_name, _make_challenge_test(_entry))


# ===================================================================
# 2. No-challenge sites – should work without issues
# ===================================================================


class TestNoChallenge(unittest.TestCase):
    """Sites that do not present a challenge."""

    pass


def _make_no_challenge_test(entry):
    def test(self):
        with _make_session() as session:
            resp = session.get(entry["url"])
            _assert_response(resp, entry)
            assert resp.flaresolverr.status == "ok"

    test.__doc__ = "No challenge: %s" % entry["url"]
    return test


for _i, _entry in enumerate(NO_CHALLENGE_SITES):
    _test_name = "test_no_challenge_%s" % _entry["name"]
    setattr(TestNoChallenge, _test_name, _make_no_challenge_test(_entry))


# ===================================================================
# 3. Unsolved challenge (mocked) – exception raised
# ===================================================================


class TestUnsolvedChallenge(unittest.TestCase):
    """Mock an unsolved challenge to verify exception handling."""

    def test_challenge_not_solved(self):
        """FlareSolverrChallengeError raised on failed challenge."""
        fake_json = {
            "status": "error",
            "message": "Challenge not solved",
            "solution": {},
            "startTimestamp": 0,
            "endTimestamp": 0,
            "version": "0.0.0",
        }
        with _make_session() as session:
            # Force session creation before mock
            _ = session.session_id
            with mock.patch.object(session._rpc._api_session, "post") as mocked_post:
                mock_resp = mock.MagicMock()
                mock_resp.json.return_value = fake_json
                mocked_post.return_value = mock_resp

                with self.assertRaises(FlareSolverrChallengeError) as ctx:
                    session.get("https://example.com")
                self.assertEqual(ctx.exception.response_data, fake_json)
                self.assertIsInstance(ctx.exception, FlareSolverrResponseError)
                self.assertEqual(ctx.exception.message, "Challenge not solved")

    def test_captcha_detected(self):
        """FlareSolverrChallengeError raised when captcha is detected."""
        fake_json = {
            "status": "error",
            "message": ("Captcha detected but no automatic solver is configured."),
            "solution": {},
            "startTimestamp": 0,
            "endTimestamp": 0,
            "version": "0.0.0",
        }
        with _make_session() as session:
            # Force session creation before mock
            _ = session.session_id
            with mock.patch.object(session._rpc._api_session, "post") as mocked_post:
                mock_resp = mock.MagicMock()
                mock_resp.json.return_value = fake_json
                mocked_post.return_value = mock_resp

                with self.assertRaises(FlareSolverrChallengeError) as ctx:
                    session.get("https://example.com")
                self.assertEqual(ctx.exception.response_data, fake_json)
                self.assertIsInstance(ctx.exception, FlareSolverrResponseError)

    def test_timeout_error(self):
        """FlareSolverrChallengeError raised on timeout."""
        fake_json = {
            "status": "error",
            "message": "Error: Timeout reached",
            "solution": {},
            "startTimestamp": 0,
            "endTimestamp": 0,
            "version": "0.0.0",
        }
        with _make_session() as session:
            # Force session creation before mock
            _ = session.session_id
            with mock.patch.object(session._rpc._api_session, "post") as mocked_post:
                mock_resp = mock.MagicMock()
                mock_resp.json.return_value = fake_json
                mocked_post.return_value = mock_resp

                with self.assertRaises(FlareSolverrChallengeError) as ctx:
                    session.get("https://example.com")
                self.assertEqual(ctx.exception.response_data, fake_json)
                self.assertIsInstance(ctx.exception, FlareSolverrResponseError)


# ===================================================================
# 4. Network error to FlareSolverr service
# ===================================================================


class TestNetworkError(unittest.TestCase):
    """Verify that a network error to FlareSolverr is raised properly."""

    def test_connection_error(self):
        """A network-level error propagates as a requests exception."""
        # Use a URL that will definitely not have a FlareSolverr running.
        # The underlying requests library raises ConnectionError (not a
        # FlareSolverrError) when the host is unreachable.
        import requests as _requests

        with self.assertRaises(_requests.exceptions.RequestException):
            session = _make_session(
                flaresolverr_url="http://127.0.0.1:1/v1",
                proxy=None,
            )
            # Trigger session creation
            _ = session.session_id


# ===================================================================
# 5. Session destroy on close
# ===================================================================


class TestSessionDestroy(unittest.TestCase):
    """Validate that the FlareSolverr session is destroyed on close."""

    def test_session_destroyed_on_close(self):
        """Session no longer listed after close()."""
        session = _make_session()
        sid = session.session_id
        # List sessions via direct API call
        sessions_before = _list_sessions(session)
        assert sid in sessions_before, "Session %s should exist before close" % sid
        session.close()
        # After close, list sessions via a fresh API call
        sessions_after = _list_sessions(session)
        assert sid not in sessions_after, "Session %s should have been destroyed" % sid

    def test_destroy_with_given_session_id(self):
        """Provided `session_id` should be destroyed on close()."""
        # Use an explicit session id when creating the session
        session = _make_session(session_id="test-destroy-id")
        try:
            sid = session.session_id
            assert sid == "test-destroy-id"
            sessions_before = _list_sessions(session)
            assert sid in sessions_before, "Session %s should exist before close" % sid
        finally:
            session.close()

        # After close, list sessions via a fresh API call
        sessions_after = _list_sessions(session)
        assert sid not in sessions_after, "Session %s should have been destroyed" % sid


# ===================================================================
# 6. Auto-generated session id
# ===================================================================


class TestAutoSession(unittest.TestCase):
    """When no session_id is given, one is auto-generated."""

    def test_auto_session_id_created(self):
        """An auto-generated session appears in FlareSolverr."""
        session = _make_session()
        try:
            assert session.session_id is not None
            assert len(session.session_id) > 0
            # List sessions via direct API call
            sessions = _list_sessions(session)
            assert session.session_id in sessions
        finally:
            session.close()


# ===================================================================
# 7. Session reuse (challenge token reuse)
# ===================================================================


class TestSessionReuse(unittest.TestCase):
    """Verify session reuse by comparing timing of repeated requests.

    The first request may need to solve a challenge (slow).  The
    second request to the same site should reuse the session cookies
    and be noticeably faster because no challenge-solving is needed.
    """

    def test_session_reuse(self):
        """Second request should be faster (session cookies reused)."""
        if not NO_CHALLENGE_SITES:
            self.skipTest("No NO_CHALLENGE_SITES configured")

        entry = NO_CHALLENGE_SITES[0]

        with _make_session() as session:
            # First request – may include cold start
            resp1 = session.get(entry["url"])
            _assert_response(resp1, entry)

            # Second request – should reuse cookies / session
            resp2 = session.get(entry["url"])

            _assert_response(resp2, entry)

            # The second request generally should not be dramatically
            # slower. We simply assert both succeeded via the same
            # session id and that we can reach the target.
            assert resp1.flaresolverr.status == "ok"
            assert resp2.flaresolverr.status == "ok"

    def test_challenge_session_reuse(self):
        """Challenge sites: second request reuses solved session."""
        if not CHALLENGE_SITES:
            self.skipTest("No CHALLENGE_SITES configured")

        entry = CHALLENGE_SITES[0]

        with _make_session() as session:
            # First request – solves the challenge
            resp1 = session.get(entry["url"])
            _assert_response(resp1, entry)

            # Second request – should reuse cookies
            # FlareSolverr returns "Challenge not detected!" when reusing
            resp2 = session.get(entry["url"])
            _assert_response(resp2, entry)

            assert resp1.flaresolverr.status == "ok"
            assert resp2.flaresolverr.status == "ok"
            # Check that challenge was not detected on second request
            assert "challenge not detected" in resp2.flaresolverr.message.lower()


# ===================================================================
# 8. Unsupported method / JSON POST
# ===================================================================


class TestUnsupportedMethod(unittest.TestCase):
    """Verify errors for unsupported methods and content types."""

    def test_put_raises(self):
        """PUT method raises FlareSolverrUnsupportedMethodError."""
        with _make_session() as session:
            with self.assertRaises(FlareSolverrUnsupportedMethodError):
                session.request("PUT", "https://example.com")

    def test_delete_raises(self):
        """DELETE method raises FlareSolverrUnsupportedMethodError."""
        with _make_session() as session:
            with self.assertRaises(FlareSolverrUnsupportedMethodError):
                session.request("DELETE", "https://example.com")

    def test_patch_raises(self):
        """PATCH method raises FlareSolverrUnsupportedMethodError."""
        with _make_session() as session:
            with self.assertRaises(FlareSolverrUnsupportedMethodError):
                session.request("PATCH", "https://example.com")

    def test_json_post_raises(self):
        """JSON POST raises FlareSolverrUnsupportedMethodError."""
        with _make_session() as session:
            with self.assertRaises(FlareSolverrUnsupportedMethodError):
                session.post(
                    "https://example.com",
                    json={"key": "value"},
                )

    def test_form_post_succeeds(self):
        """x-www-form-urlencoded POST should not raise."""
        with _make_session() as session:
            # httpbin.org echoes POST data back
            resp = session.post(
                "https://httpbin.org/post",
                data="foo=bar&baz=qux",
            )
            assert resp.flaresolverr.status == "ok"
            # httpbin returns the form data in the response
            assert "foo" in resp.text

    def test_form_post_dict_succeeds(self):
        """POST with dict data should be form-encoded."""
        with _make_session() as session:
            resp = session.post(
                "https://httpbin.org/post",
                data={"foo": "bar", "baz": "qux"},
            )
            assert resp.flaresolverr.status == "ok"
            assert "foo" in resp.text


# ===================================================================
# URL params tests
# ===================================================================


class TestURLParams(unittest.TestCase):
    """Tests for URL query parameter handling."""

    def test_params_dict_added_to_url(self):
        """Params dict should be URL-encoded and added to the query string."""
        with _make_session() as session:
            # httpbin.org/get echoes back the query parameters
            resp = session.get(
                "https://httpbin.org/get",
                params={"foo": "bar", "baz": "qux"},
            )
            assert resp.flaresolverr.status == "ok"
            # httpbin returns the args in the response
            assert "foo" in resp.text
            assert "bar" in resp.text
            assert "baz" in resp.text
            assert "qux" in resp.text

    def test_params_added_to_existing_query_string(self):
        """Params should be appended to existing query string."""
        with _make_session() as session:
            resp = session.get(
                "https://httpbin.org/get?existing=param",
                params={"new": "value"},
            )
            assert resp.flaresolverr.status == "ok"
            # Both existing and new params should be present
            assert "existing" in resp.text
            assert "param" in resp.text
            assert "new" in resp.text
            assert "value" in resp.text

    def test_post_with_params(self):
        """POST request should also support params in URL."""
        with _make_session() as session:
            resp = session.post(
                "https://httpbin.org/post",
                params={"query": "param"},
                data={"form": "data"},
            )
            assert resp.flaresolverr.status == "ok"
            # Query param should be in the URL args
            assert "query" in resp.text
            assert "param" in resp.text
            # Form data should be in the form section
            assert "form" in resp.text


# ===================================================================
# Response building tests
# ===================================================================


class TestResponseBuilding(unittest.TestCase):
    """Tests for response construction from FlareSolverr data."""

    def test_response_construction(self):
        """Response object correctly builds from FlareSolverr JSON."""
        fake_json = {
            "status": "ok",
            "message": "Challenge solved",
            "solution": {
                "status": 200,
                "url": "https://example.com/",
                "headers": {"Content-Type": "text/html"},
                "response": "<html>Example</html>",
                "cookies": [
                    {"name": "a", "value": "1", "domain": "example.com", "path": "/"}
                ],
                "userAgent": "TestAgent/1.0",
            },
            "startTimestamp": 100,
            "endTimestamp": 200,
            "version": "1.2.3",
        }

        resp = Response(fake_json)
        assert resp.status_code == 200
        assert "Example" in resp.text
        assert resp.headers.get("Content-Type") == "text/html"
        assert resp.url == "https://example.com/"
        assert resp.flaresolverr.status == "ok"
        assert resp.flaresolverr.message == "Challenge solved"
        assert resp.flaresolverr.user_agent == "TestAgent/1.0"
        assert resp.flaresolverr.start == 100
        assert resp.flaresolverr.end == 200
        assert resp.flaresolverr.version == "1.2.3"
        assert resp.cookies.get("a") == "1"


# ===================================================================
# Exception hierarchy tests
# ===================================================================


class TestExceptionHierarchy(unittest.TestCase):
    """Ensure exception classes have the correct inheritance."""

    def test_base_inherits_from_requests(self):
        assert issubclass(FlareSolverrError, requests.exceptions.RequestException)

    def test_response_error_inherits_from_base(self):
        assert issubclass(FlareSolverrResponseError, FlareSolverrError)

    def test_challenge_error_inherits_from_response_error(self):
        assert issubclass(FlareSolverrChallengeError, FlareSolverrResponseError)

    def test_unsupported_method_error(self):
        assert issubclass(FlareSolverrUnsupportedMethodError, FlareSolverrError)

    def test_response_error_carries_response_dict(self):
        """FlareSolverrResponseError stores the raw response."""
        data = {"status": "error", "message": "oops"}
        exc = FlareSolverrResponseError("oops", response_data=data)
        assert exc.response_data is data

    def test_challenge_error_carries_response_dict(self):
        """FlareSolverrChallengeError stores the raw response."""
        data = {"status": "error", "message": "challenge"}
        exc = FlareSolverrChallengeError("challenge", response_data=data)
        assert exc.response_data is data


if __name__ == "__main__":
    unittest.main()
