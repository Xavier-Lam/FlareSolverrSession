# -*- coding: utf-8 -*-

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

_DEFAULT_SESSION_ID = "mock-session-id"


def _ok_response(
    url="https://example.com/",
    body="<html>OK</html>",
    status=200,
    user_agent="MockAgent/1.0",
    message="Challenge not detected!",
):
    """Build a minimal FlareSolverr 'ok' response dict."""
    return {
        "status": "ok",
        "message": message,
        "solution": {
            "status": status,
            "url": url,
            "headers": {"content-type": "text/html"},
            "response": body,
            "cookies": [],
            "userAgent": user_agent,
        },
        "startTimestamp": 1000,
        "endTimestamp": 2000,
        "version": "1.0.0",
    }


def _make_mock_rpc(
    session_id=_DEFAULT_SESSION_ID, get_response=None, post_response=None
):
    """Return a mock RPC object with sensible defaults."""
    rpc = mock.MagicMock()
    rpc.session.create.return_value = {"session": session_id}
    rpc.session.destroy.return_value = {"status": "ok", "message": ""}
    rpc.session.list.return_value = {"sessions": [session_id]}
    rpc.request.get.return_value = get_response or _ok_response()
    rpc.request.post.return_value = post_response or _ok_response()
    return rpc


def _make_session(rpc=None, **kwargs):
    """Create a Session backed by a mock RPC."""
    if rpc is None:
        rpc = _make_mock_rpc()
    return Session(rpc=rpc, **kwargs)


class TestGetRouting(unittest.TestCase):
    """session.get() must forward a correctly built call to rpc.request.get."""

    def test_get_calls_rpc(self):
        """session.get() invokes rpc.request.get exactly once."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/page")
        rpc.request.get.assert_called_once()
        kwargs = rpc.request.get.call_args[1]
        self.assertEqual(kwargs["url"], "https://example.com/page")

    def test_get_passes_session_id(self):
        """rpc.request.get receives the FlareSolverr session id."""
        rpc = _make_mock_rpc(session_id="my-session")
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/")
        kwargs = rpc.request.get.call_args[1]
        self.assertEqual(kwargs["session_id"], "my-session")

    def test_get_returns_response(self):
        """session.get() returns a Response built from rpc data."""
        rpc = _make_mock_rpc(get_response=_ok_response(body="<html>Hello</html>"))
        with _make_session(rpc=rpc) as session:
            resp = session.get("https://example.com/")
        self.assertIsInstance(resp, Response)
        self.assertIn("Hello", resp.text)
        self.assertEqual(resp.flaresolverr.status, "ok")

    def test_get_passes_custom_timeout(self):
        """Explicit timeout kwarg is forwarded as max_timeout."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/", timeout=30000)
        kwargs = rpc.request.get.call_args[1]
        self.assertEqual(kwargs["max_timeout"], 30000)

    def test_get_uses_session_default_timeout(self):
        """Session-level timeout is used when no per-request timeout given."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc, timeout=45000) as session:
            session.get("https://example.com/")
        kwargs = rpc.request.get.call_args[1]
        self.assertEqual(kwargs["max_timeout"], 45000)

    def test_get_passes_cookies(self):
        """Cookies kwarg is forwarded to rpc.request.get."""
        rpc = _make_mock_rpc()
        cookies = [{"name": "tok", "value": "abc"}]
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/", cookies=cookies)
        kwargs = rpc.request.get.call_args[1]
        self.assertEqual(kwargs["cookies"], cookies)


class TestPostRouting(unittest.TestCase):
    """session.post() must forward a correctly built call to rpc.request.post."""

    def test_post_calls_rpc(self):
        """session.post() invokes rpc.request.post exactly once."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.post("https://example.com/submit", data="a=1")
        rpc.request.post.assert_called_once()

    def test_post_passes_url(self):
        """rpc.request.post receives the target URL."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.post("https://example.com/submit", data="a=1")
        kwargs = rpc.request.post.call_args[1]
        self.assertEqual(kwargs["url"], "https://example.com/submit")

    def test_post_passes_string_data(self):
        """String post data is forwarded unchanged."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.post("https://example.com/", data="foo=bar")
        kwargs = rpc.request.post.call_args[1]
        self.assertEqual(kwargs["data"], "foo=bar")

    def test_post_passes_dict_data(self):
        """Dict post data is forwarded; encoding is handled by the RPC layer."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.post("https://example.com/", data={"x": "1"})
        kwargs = rpc.request.post.call_args[1]
        self.assertEqual(kwargs["data"], {"x": "1"})

    def test_post_passes_session_id(self):
        """rpc.request.post receives the FlareSolverr session id."""
        rpc = _make_mock_rpc(session_id="post-session")
        with _make_session(rpc=rpc) as session:
            session.post("https://example.com/", data="x=1")
        kwargs = rpc.request.post.call_args[1]
        self.assertEqual(kwargs["session_id"], "post-session")

    def test_post_returns_response(self):
        """session.post() returns a Response built from rpc data."""
        rpc = _make_mock_rpc(post_response=_ok_response(body="<html>Posted</html>"))
        with _make_session(rpc=rpc) as session:
            resp = session.post("https://example.com/", data="x=1")
        self.assertIsInstance(resp, Response)
        self.assertIn("Posted", resp.text)


class TestUnsolvedChallenge(unittest.TestCase):
    """rpc.request.get raising FlareSolverrResponseError triggers the right exceptions."""

    def _make_error_rpc(self, message):
        rpc = _make_mock_rpc()
        fake_data = {
            "status": "error",
            "message": message,
            "solution": {},
            "startTimestamp": 0,
            "endTimestamp": 0,
            "version": "0.0.0",
        }
        rpc.request.get.side_effect = FlareSolverrResponseError(message, fake_data)
        return rpc, fake_data

    def test_challenge_not_solved(self):
        """FlareSolverrChallengeError raised on failed challenge."""
        rpc, fake_data = self._make_error_rpc("Challenge not solved")
        with _make_session(rpc=rpc) as session:
            with self.assertRaises(FlareSolverrChallengeError) as ctx:
                session.get("https://example.com")
        self.assertEqual(ctx.exception.response_data, fake_data)
        self.assertIsInstance(ctx.exception, FlareSolverrResponseError)
        self.assertEqual(ctx.exception.message, "Challenge not solved")

    def test_challenge_failed(self):
        """FlareSolverrChallengeError raised when captcha is detected."""
        messages = (
            "Captcha detected but no automatic solver is configured.",
            "Error: Timeout reached",
        )
        for msg in messages:
            rpc, fake_data = self._make_error_rpc(msg)
            with _make_session(rpc=rpc) as session:
                with self.assertRaises(FlareSolverrChallengeError) as ctx:
                    session.get("https://example.com")
            self.assertEqual(ctx.exception.response_data, fake_data)
            self.assertEqual(ctx.exception.message, msg)

    def test_non_challenge_error_not_wrapped(self):
        """A non-challenge FlareSolverrResponseError is re-raised as-is."""
        rpc = _make_mock_rpc()
        fake_data = {"status": "error", "message": "Internal server error"}
        rpc.request.get.side_effect = FlareSolverrResponseError(
            "Internal server error", fake_data
        )
        with _make_session(rpc=rpc) as session:
            with self.assertRaises(FlareSolverrResponseError) as ctx:
                session.get("https://example.com")
        # Must NOT be re-wrapped as FlareSolverrChallengeError
        self.assertNotIsInstance(ctx.exception, FlareSolverrChallengeError)


class TestNetworkError(unittest.TestCase):
    """Verify that a network error from the RPC layer propagates correctly."""

    def test_connection_error_on_session_create(self):
        """ConnectionError from rpc.session.create propagates out of session_id."""
        rpc = _make_mock_rpc()
        rpc.session.create.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )
        session = Session(rpc=rpc)
        with self.assertRaises(requests.exceptions.RequestException):
            _ = session.session_id

    def test_connection_error_on_request(self):
        """ConnectionError from rpc.request.get propagates out of session.get()."""
        rpc = _make_mock_rpc()
        rpc.request.get.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )
        with Session(rpc=rpc) as session:
            with self.assertRaises(requests.exceptions.RequestException):
                session.get("https://example.com")


class TestSessionLifecycle(unittest.TestCase):
    """Validate session creation and destruction around the RPC layer."""

    def test_session_created_on_first_access(self):
        """rpc.session.create is called exactly once on first session_id access."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        try:
            _ = session.session_id
            _ = session.session_id  # second access must not re-create
        finally:
            session.close()
        rpc.session.create.assert_called_once()

    def test_session_created_lazily_by_request(self):
        """rpc.session.create is called when the first request triggers it."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        rpc.session.create.assert_not_called()
        session.get("https://example.com/")
        rpc.session.create.assert_called_once()
        session.close()

    def test_session_destroyed_on_close(self):
        """close() calls rpc.session.destroy with the correct session id."""
        rpc = _make_mock_rpc(session_id="to-destroy")
        session = Session(rpc=rpc)
        sid = session.session_id
        session.close()
        rpc.session.destroy.assert_called_once_with(sid)

    def test_destroy_not_called_if_never_created(self):
        """close() does not call rpc.session.destroy if no session was created."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        session.close()
        rpc.session.destroy.assert_not_called()

    def test_destroy_with_given_session_id(self):
        """Explicit session_id is destroyed on close()."""
        rpc = _make_mock_rpc(session_id="explicit-id")
        session = Session(rpc=rpc, session_id="explicit-id")
        sid = session.session_id
        self.assertEqual(sid, "explicit-id")
        session.close()
        rpc.session.destroy.assert_called_once_with("explicit-id")


class TestAutoSession(unittest.TestCase):
    """When no session_id is given, one is returned by rpc.session.create."""

    def test_auto_session_id_returned_from_rpc(self):
        """session_id is taken from the rpc.session.create response."""
        rpc = _make_mock_rpc(session_id="auto-abc-123")
        session = Session(rpc=rpc)
        try:
            sid = session.session_id
            self.assertEqual(sid, "auto-abc-123")
        finally:
            session.close()

    def test_session_id_is_stable(self):
        """Repeated access to session_id always returns the same value."""
        rpc = _make_mock_rpc(session_id="stable-id")
        session = Session(rpc=rpc)
        try:
            self.assertEqual(session.session_id, session.session_id)
        finally:
            session.close()


class TestSessionReuse(unittest.TestCase):
    """Both RPC calls within one Session must carry the same session_id."""

    def test_get_reuses_session_id(self):
        """Two subsequent GET calls share the same session_id."""
        rpc = _make_mock_rpc(session_id="reuse-id")
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/1")
            session.get("https://example.com/2")

        calls = rpc.request.get.call_args_list
        self.assertEqual(len(calls), 2)
        ids = [c[1]["session_id"] for c in calls]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[0], "reuse-id")

    def test_post_reuses_session_id(self):
        """A GET followed by a POST share the same session_id."""
        rpc = _make_mock_rpc(session_id="reuse-post")
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/")
            session.post("https://example.com/", data="x=1")

        get_sid = rpc.request.get.call_args[1]["session_id"]
        post_sid = rpc.request.post.call_args[1]["session_id"]
        self.assertEqual(get_sid, post_sid)
        self.assertEqual(get_sid, "reuse-post")


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

    def test_unsupported_method_does_not_call_rpc(self):
        """RPC must not be invoked for unsupported methods."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            try:
                session.request("PUT", "https://example.com")
            except FlareSolverrUnsupportedMethodError:
                pass
        rpc.request.get.assert_not_called()
        rpc.request.post.assert_not_called()

    def test_form_post_string_calls_rpc(self):
        """String-body POST reaches rpc.request.post without raising."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            resp = session.post("https://example.com/", data="foo=bar&baz=qux")
        rpc.request.post.assert_called_once()
        self.assertEqual(resp.flaresolverr.status, "ok")

    def test_form_post_dict_calls_rpc(self):
        """Dict-body POST reaches rpc.request.post without raising."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            resp = session.post("https://example.com/", data={"foo": "bar"})
        rpc.request.post.assert_called_once()
        self.assertEqual(resp.flaresolverr.status, "ok")


class TestURLParams(unittest.TestCase):
    """Tests for URL query parameter handling."""

    def _get_url(self, rpc):
        """Return the URL forwarded to rpc.request.get."""
        return rpc.request.get.call_args[1]["url"]

    def _post_url(self, rpc):
        """Return the URL forwarded to rpc.request.post."""
        return rpc.request.post.call_args[1]["url"]

    def test_params_dict_appended_to_clean_url(self):
        """Params dict is URL-encoded and appended with '?'."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/get", params={"foo": "bar"})
        url = self._get_url(rpc)
        self.assertIn("?", url)
        self.assertIn("foo=bar", url)

    def test_params_dict_appended_to_existing_query(self):
        """Params are appended with '&' when the URL already has a query."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/get?existing=1", params={"new": "2"})
        url = self._get_url(rpc)
        self.assertIn("existing=1", url)
        self.assertIn("new=2", url)
        self.assertIn("&", url)

    def test_no_params_url_unchanged(self):
        """URL is passed through unchanged when no params given."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/page")
        url = self._get_url(rpc)
        self.assertEqual(url, "https://example.com/page")

    def test_post_with_params(self):
        """POST also supports params in the URL."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.post("https://example.com/", params={"q": "test"}, data="x=1")
        url = self._post_url(rpc)
        self.assertIn("q=test", url)


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
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Example", resp.text)
        self.assertEqual(resp.headers.get("Content-Type"), "text/html")
        self.assertEqual(resp.url, "https://example.com/")
        self.assertEqual(resp.flaresolverr.status, "ok")
        self.assertEqual(resp.flaresolverr.message, "Challenge solved")
        self.assertEqual(resp.flaresolverr.user_agent, "TestAgent/1.0")
        self.assertEqual(resp.flaresolverr.start, 100)
        self.assertEqual(resp.flaresolverr.end, 200)
        self.assertEqual(resp.flaresolverr.version, "1.2.3")
        self.assertEqual(resp.cookies.get("a"), "1")


class TestExceptionHierarchy(unittest.TestCase):
    """Ensure exception classes have the correct inheritance."""

    def test_base_inherits_from_requests(self):
        self.assertTrue(
            issubclass(FlareSolverrError, requests.exceptions.RequestException)
        )

    def test_response_error_inherits_from_base(self):
        self.assertTrue(issubclass(FlareSolverrResponseError, FlareSolverrError))

    def test_challenge_error_inherits_from_response_error(self):
        self.assertTrue(
            issubclass(FlareSolverrChallengeError, FlareSolverrResponseError)
        )

    def test_unsupported_method_error(self):
        self.assertTrue(
            issubclass(FlareSolverrUnsupportedMethodError, FlareSolverrError)
        )

    def test_response_error_carries_response_dict(self):
        """FlareSolverrResponseError stores the raw response."""
        data = {"status": "error", "message": "oops"}
        exc = FlareSolverrResponseError("oops", response_data=data)
        self.assertIs(exc.response_data, data)

    def test_challenge_error_carries_response_dict(self):
        """FlareSolverrChallengeError stores the raw response."""
        data = {"status": "error", "message": "challenge"}
        exc = FlareSolverrChallengeError("challenge", response_data=data)
        self.assertIs(exc.response_data, data)


if __name__ == "__main__":
    unittest.main()
