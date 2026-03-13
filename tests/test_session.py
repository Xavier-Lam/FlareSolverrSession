# -*- coding: utf-8 -*-

import datetime
import unittest

try:
    from unittest import mock
except ImportError:
    import mock  # Python 2 back-port

import warnings

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


class TestSessionRetry(unittest.TestCase):
    """Tests for the max_retries mechanism on Session."""

    def _make_challenge_error(self):
        return FlareSolverrChallengeError(
            "Challenge timeout",
            response_data={"status": "error", "message": "Challenge timeout"},
        )

    def test_retry_disabled(self):
        """max_retries=0: FlareSolverrChallengeError propagates."""
        rpc = _make_mock_rpc()
        rpc.request.get.side_effect = self._make_challenge_error()
        with _make_session(rpc=rpc, max_retries=0) as session:
            with self.assertRaises(FlareSolverrChallengeError):
                session.get("https://example.com/")

        self.assertEqual(rpc.request.get.call_count, 1)

    def test_retry_on_challenge_error(self):
        """With max_retries=2, session retries twice on FlareSolverrChallengeError."""
        error = self._make_challenge_error()
        rpc = _make_mock_rpc(get_response=_ok_response())
        rpc.request.get.side_effect = [error, error, _ok_response()]
        with mock.patch("flaresolverr_session.session.time") as mock_time:
            with _make_session(rpc=rpc, max_retries=2) as session:
                resp = session.get("https://example.com/")

        self.assertEqual(rpc.request.get.call_count, 3)
        self.assertEqual(mock_time.sleep.call_count, 2)
        mock_time.sleep.assert_called_with(1)

    def test_retry_exhausted_raises(self):
        """Error is re-raised once all max_retries are used."""
        error = self._make_challenge_error()
        rpc = _make_mock_rpc()
        rpc.request.get.side_effect = error
        with mock.patch("flaresolverr_session.session.time"):
            with _make_session(rpc=rpc, max_retries=1) as session:
                with self.assertRaises(FlareSolverrChallengeError):
                    session.get("https://example.com/")

        self.assertEqual(rpc.request.get.call_count, 2)

    def test_retry_sleeps_one_second(self):
        """There is a 1-second sleep between retry attempts."""
        error = self._make_challenge_error()
        rpc = _make_mock_rpc(get_response=_ok_response())
        rpc.request.get.side_effect = [error, _ok_response()]
        with mock.patch("flaresolverr_session.session.time") as mock_time:
            with _make_session(rpc=rpc, max_retries=1) as session:
                session.get("https://example.com/")

        mock_time.sleep.assert_called_once_with(1)

    def test_retry_post_on_challenge_error(self):
        """POST requests are also retried on FlareSolverrChallengeError."""
        error = self._make_challenge_error()
        rpc = _make_mock_rpc(post_response=_ok_response())
        rpc.request.post.side_effect = [error, _ok_response()]
        with mock.patch("flaresolverr_session.session.time") as mock_time:
            with _make_session(rpc=rpc, max_retries=1) as session:
                resp = session.post("https://example.com/", data="a=1")

        self.assertEqual(rpc.request.post.call_count, 2)
        mock_time.sleep.assert_called_once_with(1)
        self.assertIsInstance(resp, Response)

    def test_non_challenge_error_not_retried(self):
        """Non-challenge FlareSolverrResponseError is NOT retried."""
        error = FlareSolverrResponseError(
            "Server error",
            response_data={"status": "error", "message": "Server error"},
        )
        rpc = _make_mock_rpc()
        rpc.request.get.side_effect = error
        with mock.patch("flaresolverr_session.session.time"):
            with _make_session(rpc=rpc, max_retries=3) as session:
                with self.assertRaises(FlareSolverrResponseError) as ctx:
                    session.get("https://example.com/")

        self.assertEqual(rpc.request.get.call_count, 1)
        self.assertNotIsInstance(ctx.exception, FlareSolverrChallengeError)

    def test_max_retries_stored(self):
        """max_retries is stored on the session."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc, max_retries=4)
        self.assertEqual(session._max_retries, 4)
        session.close()


class TestSessionWithoutRPC(unittest.TestCase):
    """Session constructed without an explicit RPC instance creates its own RPC."""

    def test_session_created_without_rpc(self):
        """Session() with a URL creates an internal RPC and uses it."""
        with mock.patch("flaresolverr_session.session.RPC") as mock_rpc_cls:
            mock_rpc_instance = _make_mock_rpc()
            mock_rpc_cls.return_value = mock_rpc_instance

            session = Session("http://localhost:8191/v1")
            try:
                session.get("https://example.com/")
            finally:
                session.close()

        mock_rpc_cls.assert_called_once_with("http://localhost:8191/v1")
        mock_rpc_instance.request.get.assert_called_once()
        self.assertEqual(
            mock_rpc_instance.request.get.call_args[1]["url"], "https://example.com/"
        )


class TestThreadSafety(unittest.TestCase):
    """Session must serialize concurrent requests with a threading lock."""

    def test_concurrent_requests_are_serialized(self):
        """Two concurrent GET requests on the same session never interleave."""
        import threading

        order = []
        first_started = threading.Event()
        first_can_finish = threading.Event()
        call_count = [0]
        call_count_lock = threading.Lock()

        def controlled_get(**kwargs):
            with call_count_lock:
                call_count[0] += 1
                n = call_count[0]
            order.append(("start", n))
            if n == 1:
                first_started.set()
                first_can_finish.wait(timeout=5)
            order.append(("end", n))
            return _ok_response()

        rpc = _make_mock_rpc()
        rpc.request.get.side_effect = controlled_get

        errors = []

        session = _make_session(rpc=rpc)
        try:

            def worker():
                try:
                    session.get("https://example.com/")
                except Exception as e:
                    errors.append(e)

            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)

            t1.start()
            first_started.wait(timeout=5)  # t1 is now inside the RPC call

            t2.start()
            # Give t2 time to reach the lock and block on it
            import time as _time

            _time.sleep(0.1)

            # t2 must not have started the RPC call yet (still blocked on lock)
            started_count = len([x for x in order if x[0] == "start"])
            self.assertEqual(started_count, 1)

            first_can_finish.set()  # allow t1 to finish
            t1.join(timeout=5)
            t2.join(timeout=5)
        finally:
            session.close()

        self.assertEqual(errors, [])
        # Serialized order: t1 start, t1 end, t2 start, t2 end
        self.assertEqual(order, [("start", 1), ("end", 1), ("start", 2), ("end", 2)])


class TestSessionTTL(unittest.TestCase):
    """Tests for the ttl option on Session."""

    def test_default_ttl_is_none(self):
        """By default, no session_ttl_minutes is sent."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/")
        kwargs = rpc.request.get.call_args[1]
        self.assertNotIn("session_ttl_minutes", kwargs)

    def test_ttl_int_passed_to_rpc(self):
        """Integer ttl is forwarded as session_ttl_minutes."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc, ttl=10) as session:
            session.get("https://example.com/")
        kwargs = rpc.request.get.call_args[1]
        self.assertEqual(kwargs["session_ttl_minutes"], 10)

    def test_ttl_timedelta_passed_to_rpc(self):
        """timedelta ttl is converted to minutes and forwarded."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc, ttl=datetime.timedelta(minutes=15)) as session:
            session.get("https://example.com/")
        kwargs = rpc.request.get.call_args[1]
        self.assertEqual(kwargs["session_ttl_minutes"], 15)

    def test_ttl_timedelta_fractional_minutes_truncated(self):
        """timedelta with partial minutes is truncated to whole minutes."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc, ttl=datetime.timedelta(seconds=90)) as session:
            session.get("https://example.com/")
        kwargs = rpc.request.get.call_args[1]
        self.assertEqual(kwargs["session_ttl_minutes"], 1)

    def test_ttl_passed_on_post(self):
        """ttl is also forwarded on POST requests."""
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc, ttl=5) as session:
            session.post("https://example.com/submit", data="x=1")
        kwargs = rpc.request.post.call_args[1]
        self.assertEqual(kwargs["session_ttl_minutes"], 5)

    def test_ttl_stored_as_int_from_timedelta(self):
        """Session._ttl stores an int when initialised from a timedelta."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc, ttl=datetime.timedelta(minutes=20))
        self.assertIsInstance(session._ttl, int)
        self.assertEqual(session._ttl, 20)
        session.close()

    def test_ttl_stored_directly_as_int(self):
        """Session._ttl stores the int directly when given an int."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc, ttl=30)
        self.assertEqual(session._ttl, 30)
        session.close()


class TestExistsProperty(unittest.TestCase):
    """Tests for the Session.exists property."""

    def test_exists_false_when_no_session_id(self):
        """exists returns False immediately when _session_id is not set."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        # Never trigger session creation; _session_id stays None
        self.assertFalse(session.exists)
        rpc.session.list.assert_not_called()
        session.close()

    def test_exists_true_when_session_in_list(self):
        """exists returns True when the session id appears in rpc.session.list."""
        rpc = _make_mock_rpc(session_id="live-session")
        rpc.session.list.return_value = {"sessions": ["live-session", "other"]}
        session = Session(rpc=rpc, session_id="live-session")
        try:
            self.assertTrue(session.exists)
        finally:
            session.close()

    def test_exists_false_when_session_not_in_list(self):
        """exists returns False when the session id is absent from the list."""
        rpc = _make_mock_rpc(session_id="gone-session")
        rpc.session.list.return_value = {"sessions": ["other-session"]}
        session = Session(rpc=rpc, session_id="gone-session")
        try:
            self.assertFalse(session.exists)
        finally:
            session.close()

    def test_exists_calls_rpc_session_list(self):
        """exists delegates to rpc.session.list to check membership."""
        rpc = _make_mock_rpc(session_id="check-session")
        session = Session(rpc=rpc, session_id="check-session")
        try:
            _ = session.exists
        finally:
            session.close()
        rpc.session.list.assert_called_once()

    def test_exists_false_on_empty_list(self):
        """exists returns False when the server returns an empty sessions list."""
        rpc = _make_mock_rpc(session_id="any-session")
        rpc.session.list.return_value = {"sessions": []}
        session = Session(rpc=rpc, session_id="any-session")
        try:
            self.assertFalse(session.exists)
        finally:
            session.close()


class TestPublicCreateMethod(unittest.TestCase):
    """Tests for the public Session.create() method."""

    def test_create_calls_rpc_session_create(self):
        """create() invokes rpc.session.create once."""
        rpc = _make_mock_rpc(session_id="new-id")
        session = Session(rpc=rpc)
        try:
            session.create()
            rpc.session.create.assert_called_once()
        finally:
            session.close()

    def test_create_sets_session_created_flag(self):
        """create() sets _session_created to True."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        self.assertFalse(session._session_created)
        try:
            session.create()
            self.assertTrue(session._session_created)
        finally:
            session.close()

    def test_create_updates_session_id_from_rpc(self):
        """create() stores the session id returned by rpc.session.create."""
        rpc = _make_mock_rpc(session_id="rpc-assigned-id")
        session = Session(rpc=rpc)
        try:
            session.create()
            self.assertEqual(session._session_id, "rpc-assigned-id")
        finally:
            session.close()

    def test_create_force_destroys_existing_session(self):
        """create(force=True) calls destroy() before creating a new session."""
        rpc = _make_mock_rpc(session_id="existing-id")
        session = Session(rpc=rpc, session_id="existing-id")
        try:
            session.create()  # establish _session_created = True
            rpc.session.destroy.reset_mock()
            session.create(force=True)
            rpc.session.destroy.assert_called_once_with("existing-id")
        finally:
            session.close()

    def test_create_force_without_session_id_skips_destroy(self):
        """create(force=True) does not call destroy() when no session id is set."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        try:
            session.create(force=True)
            rpc.session.destroy.assert_not_called()
        finally:
            session.close()

    def test_create_no_force_does_not_destroy(self):
        """create(force=False) never calls destroy() regardless of existing session."""
        rpc = _make_mock_rpc(session_id="keep-me")
        session = Session(rpc=rpc, session_id="keep-me")
        try:
            session.create()  # first create
            rpc.session.destroy.reset_mock()
            session.create(force=False)  # second create, no force
            rpc.session.destroy.assert_not_called()
        finally:
            session.close()

    def test_create_passes_proxy_to_rpc(self):
        """create() forwards the proxy to rpc.session.create."""
        rpc = _make_mock_rpc()
        proxy = {"url": "http://proxy.example.com:8080"}
        session = Session(rpc=rpc, proxy=proxy)
        try:
            session.create()
            _, kwargs = rpc.session.create.call_args
            self.assertEqual(kwargs.get("proxy"), proxy)
        finally:
            session.close()

    def test_create_passes_session_id_to_rpc(self):
        """create() forwards an explicit session_id to rpc.session.create."""
        rpc = _make_mock_rpc(session_id="explicit-create")
        session = Session(rpc=rpc, session_id="explicit-create")
        try:
            session.create()
            _, kwargs = rpc.session.create.call_args
            self.assertEqual(kwargs.get("session_id"), "explicit-create")
        finally:
            session.close()


class TestPublicDestroyMethod(unittest.TestCase):
    """Tests for the public Session.destroy() method."""

    def test_destroy_calls_rpc_session_destroy(self):
        """destroy() calls rpc.session.destroy with the current session id."""
        rpc = _make_mock_rpc(session_id="kill-me")
        session = Session(rpc=rpc, session_id="kill-me")
        try:
            session.create()
            session.destroy()
            rpc.session.destroy.assert_called_once_with("kill-me")
        finally:
            session.close()

    def test_destroy_clears_session_created_flag(self):
        """destroy() sets _session_created to False."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        try:
            session.create()
            self.assertTrue(session._session_created)
            session.destroy()
            self.assertFalse(session._session_created)
        finally:
            session.close()

    def test_destroy_clears_session_id_for_auto_session(self):
        """destroy() sets _session_id to None when no custom session_id was given."""
        rpc = _make_mock_rpc(session_id="auto-gen")
        session = Session(rpc=rpc)
        session.create()
        self.assertEqual(session._session_id, "auto-gen")
        session.destroy()
        self.assertIsNone(session._session_id)
        session.close()

    def test_destroy_preserves_session_id_for_custom_session(self):
        """destroy() does NOT clear _session_id when a custom session_id was given."""
        rpc = _make_mock_rpc(session_id="my-fixed-id")
        session = Session(rpc=rpc, session_id="my-fixed-id")
        try:
            session.create()
            session.destroy()
            self.assertEqual(session._session_id, "my-fixed-id")
        finally:
            session.close()

    def test_destroy_does_nothing_when_no_session_id(self):
        """destroy() is a no-op when _session_id is None."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        # Do not call create(); _session_id is None
        session.destroy()
        rpc.session.destroy.assert_not_called()
        session.close()

    def test_destroy_propagates_rpc_exceptions(self):
        """destroy() does not swallow exceptions from rpc.session.destroy."""
        rpc = _make_mock_rpc(session_id="boom-id")
        rpc.session.destroy.side_effect = RuntimeError("RPC failure")
        session = Session(rpc=rpc, session_id="boom-id")
        session.create()
        with self.assertRaises(RuntimeError):
            session.destroy()
        session._session_created = False  # prevent close() from re-raising
        session.close()


class TestCloseErrorHandling(unittest.TestCase):
    """close() must issue a warning when destroy() raises, then still close."""

    def test_close_warns_on_destroy_error(self):
        """close() issues a UserWarning when rpc.session.destroy raises."""
        rpc = _make_mock_rpc(session_id="warn-id")
        rpc.session.destroy.side_effect = RuntimeError("destroy failed")
        session = Session(rpc=rpc)
        session.create()
        with self.assertWarns(UserWarning):
            session.close()

    def test_close_warning_contains_session_id(self):
        """The warning message includes the session id for diagnostics."""
        rpc = _make_mock_rpc(session_id="diag-id")
        rpc.session.destroy.side_effect = RuntimeError("network error")
        session = Session(rpc=rpc, session_id="diag-id")
        session.create()
        with self.assertWarns(UserWarning) as cm:
            session.close()
        self.assertIn("diag-id", str(cm.warning))

    def test_close_completes_after_destroy_error(self):
        """close() finishes successfully (calls super) even when destroy() raises."""
        rpc = _make_mock_rpc(session_id="safe-close")
        rpc.session.destroy.side_effect = RuntimeError("transient error")
        session = Session(rpc=rpc)
        session.create()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Must not raise despite destroy() failing
            try:
                session.close()
            except Exception as exc:
                self.fail("close() raised unexpectedly: %s" % exc)

    def test_close_no_warning_on_success(self):
        """close() does not warn when destroy() succeeds."""
        rpc = _make_mock_rpc(session_id="clean-close")
        session = Session(rpc=rpc)
        session.create()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            session.close()
        self.assertEqual(len(w), 0)


class TestCustomSessionIdTracking(unittest.TestCase):
    """_custom_session_id stores the caller-supplied session_id."""

    def test_custom_session_id_stored_when_given(self):
        """_custom_session_id equals the session_id passed at construction."""
        rpc = _make_mock_rpc(session_id="user-provided")
        session = Session(rpc=rpc, session_id="user-provided")
        try:
            self.assertEqual(session._custom_session_id, "user-provided")
        finally:
            session.close()

    def test_custom_session_id_is_none_when_not_given(self):
        """_custom_session_id is None when no session_id is passed."""
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        try:
            self.assertIsNone(session._custom_session_id)
        finally:
            session.close()

    def test_custom_session_id_unchanged_after_create(self):
        """_custom_session_id is not mutated when create() assigns a new session id."""
        rpc = _make_mock_rpc(session_id="server-assigned")
        session = Session(rpc=rpc)
        try:
            session.create()
            self.assertIsNone(session._custom_session_id)
            self.assertEqual(session._session_id, "server-assigned")
        finally:
            session.close()

    def test_custom_session_id_unchanged_after_destroy(self):
        """_custom_session_id is preserved even after destroy() clears _session_id."""
        rpc = _make_mock_rpc(session_id="fixed-id")
        session = Session(rpc=rpc, session_id="fixed-id")
        try:
            session.create()
            session.destroy()
            self.assertEqual(session._custom_session_id, "fixed-id")
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
