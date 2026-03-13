# -*- coding: utf-8 -*-

import datetime
import unittest

try:
    from unittest import mock
except ImportError:
    import mock  # Python 2 back-port

from flaresolverr_session import (
    FlareSolverrChallengeError,
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


class TestSession(unittest.TestCase):

    # ------------------------------------------------------------------
    # request handling tests
    # ------------------------------------------------------------------

    def test_get(self):
        rpc = _make_mock_rpc(
            session_id="my-session",
            get_response=_ok_response(body="<html>Hello</html>"),
        )
        with _make_session(rpc=rpc) as session:
            resp = session.get("https://example.com/page", timeout=30000)
        rpc.request.get.assert_called_once()
        kwargs = rpc.request.get.call_args[1]
        self.assertEqual(kwargs["url"], "https://example.com/page")
        self.assertEqual(kwargs["session_id"], "my-session")
        self.assertEqual(kwargs["max_timeout"], 30000)
        self.assertIsInstance(resp, Response)
        self.assertIn("Hello", resp.text)
        self.assertEqual(resp.flaresolverr.status, "ok")

        cookies = [{"name": "tok", "value": "abc"}]
        with _make_session(rpc=rpc, timeout=45000) as session:
            session.get("https://example.com/", cookies=cookies)
        kw2 = rpc.request.get.call_args[1]
        self.assertEqual(kw2["max_timeout"], 45000)
        self.assertEqual(kw2["cookies"], cookies)

    def test_post(self):
        rpc = _make_mock_rpc(
            session_id="post-session",
            post_response=_ok_response(body="<html>Posted</html>"),
        )
        with _make_session(rpc=rpc) as session:
            resp_str = session.post("https://example.com/submit", data="foo=bar")
        self.assertIsInstance(resp_str, Response)
        self.assertIn("Posted", resp_str.text)
        calls = rpc.request.post.call_args_list
        self.assertEqual(calls[0][1]["data"], "foo=bar")
        self.assertEqual(calls[0][1]["session_id"], "post-session")

    def test_params_handling(self):
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/get", params={"foo": "bar"})
            session.get("https://example.com/get?existing=1", params={"new": "2"})
            session.get("https://example.com/page")
        calls = rpc.request.get.call_args_list
        url0, url1, url2 = [c[1]["url"] for c in calls]
        self.assertIn("foo=bar", url0)
        self.assertIn("existing=1", url1)
        self.assertIn("new=2", url1)
        self.assertEqual(url2, "https://example.com/page")

        with _make_session(rpc=rpc) as session:
            session.post("https://example.com/", params={"q": "test"}, data="x=1")
        self.assertIn("q=test", rpc.request.post.call_args[1]["url"])

    def test_supported_post_types(self):
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            resp1 = session.post("https://example.com/", data="foo=bar&baz=qux")
            resp2 = session.post("https://example.com/", data={"foo": "bar"})
        self.assertEqual(rpc.request.post.call_count, 2)
        self.assertEqual(resp1.flaresolverr.status, "ok")
        self.assertEqual(resp2.flaresolverr.status, "ok")

        # unsupported
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            for method in ("PUT", "DELETE", "PATCH"):
                with self.assertRaises(FlareSolverrUnsupportedMethodError):
                    session.request(method, "https://example.com")
            with self.assertRaises(FlareSolverrUnsupportedMethodError):
                session.post("https://example.com", json={"key": "value"})
        rpc.request.get.assert_not_called()
        rpc.request.post.assert_not_called()

    # ------------------------------------------------------------------
    #  lifecycle tests
    # ------------------------------------------------------------------

    def test_session_reuse_across_requests(self):
        rpc = _make_mock_rpc(session_id="reuse-id")
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/1")
            session.get("https://example.com/2")
            session.post("https://example.com/", data="x=1")
        ids = [c[1]["session_id"] for c in rpc.request.get.call_args_list]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[0], "reuse-id")
        self.assertEqual(rpc.request.post.call_args[1]["session_id"], "reuse-id")

    # ------------------------------------------------------------------
    #  session management
    # ------------------------------------------------------------------

    def test_exists(self):
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        self.assertFalse(session.exists)
        rpc.session.list.assert_not_called()
        session.close()

        rpc = _make_mock_rpc(session_id="live-session")
        rpc.session.list.return_value = {"sessions": ["live-session", "other"]}
        session = Session(rpc=rpc, session_id="live-session")
        try:
            self.assertTrue(session.exists)
        finally:
            session.close()

        rpc = _make_mock_rpc(session_id="gone-session")
        rpc.session.list.return_value = {"sessions": []}
        session = Session(rpc=rpc, session_id="gone-session")
        try:
            self.assertFalse(session.exists)
            rpc.session.list.assert_called_once()
        finally:
            session.close()

    def test_create(self):
        rpc = _make_mock_rpc(session_id="rpc-assigned-id")
        session = Session(rpc=rpc)
        try:
            self.assertFalse(session._session_created)
            session.create()
            rpc.session.create.assert_called_once()
            self.assertTrue(session._session_created)
            self.assertEqual(session._session_id, "rpc-assigned-id")
        finally:
            session.close()

        # force
        rpc = _make_mock_rpc(session_id="existing-id")
        session = Session(rpc=rpc, session_id="existing-id")
        try:
            session.create()
            rpc.session.destroy.reset_mock()
            session.create(force=True)
            rpc.session.destroy.assert_called_once_with("existing-id")
        finally:
            session.close()

        # proxy
        rpc = _make_mock_rpc()
        session = Session(rpc=rpc)
        try:
            session.create(force=True)
            rpc.session.destroy.assert_not_called()
        finally:
            session.close()
        proxy = {"url": "http://proxy.example.com:8080"}

        session = Session(rpc=rpc, session_id="explicit-create", proxy=proxy)
        try:
            session.create()
            _, kwargs = rpc.session.create.call_args
            self.assertEqual(kwargs.get("proxy"), proxy)
            self.assertEqual(kwargs.get("session_id"), "explicit-create")
        finally:
            session.close()

    def test_destroy(self):
        rpc = _make_mock_rpc(session_id="kill-me")
        session = Session(rpc=rpc, session_id="kill-me")
        try:
            session.create()
            self.assertTrue(session._session_created)
            session.destroy()
            rpc.session.destroy.assert_called_once_with("kill-me")
            self.assertFalse(session._session_created)
        finally:
            session.close()

        # test destroy() clears session_id for auto-created sessions, but not for user-provided ids
        rpc = _make_mock_rpc(session_id="auto-gen")
        session = Session(rpc=rpc)
        session.create()
        self.assertEqual(session._session_id, "auto-gen")
        session.destroy()
        self.assertIsNone(session._session_id)
        session.close()

    # ------------------------------------------------------------------
    #  retry
    # ------------------------------------------------------------------

    def _make_challenge_error(self):
        return FlareSolverrChallengeError(
            "Challenge timeout",
            response_data={"status": "error", "message": "Challenge timeout"},
        )

    def test_retry_on_challenge_error(self):
        error = self._make_challenge_error()
        rpc = _make_mock_rpc(get_response=_ok_response())
        rpc.request.get.side_effect = [error, error, _ok_response()]
        with mock.patch("flaresolverr_session.session.time") as mock_time:
            with _make_session(rpc=rpc, max_retries=2) as session:
                resp = session.get("https://example.com/")
        self.assertEqual(rpc.request.get.call_count, 3)
        self.assertEqual(mock_time.sleep.call_count, 2)
        mock_time.sleep.assert_called_with(1)
        self.assertIsInstance(resp, Response)

    def test_retry_exhausted_and_disabled(self):
        error = self._make_challenge_error()
        rpc = _make_mock_rpc()
        rpc.request.get.side_effect = error
        with mock.patch("flaresolverr_session.session.time"):
            with _make_session(rpc=rpc, max_retries=1) as session:
                with self.assertRaises(FlareSolverrChallengeError):
                    session.get("https://example.com/")
        self.assertEqual(rpc.request.get.call_count, 2)

        rpc = _make_mock_rpc()
        rpc.request.get.side_effect = self._make_challenge_error()
        with _make_session(rpc=rpc, max_retries=0) as session:
            with self.assertRaises(FlareSolverrChallengeError):
                session.get("https://example.com/")
        self.assertEqual(rpc.request.get.call_count, 1)

    def test_non_challenge_error_not_retried(self):
        error = FlareSolverrResponseError(
            "Server error", response_data={"status": "error", "message": "Server error"}
        )
        rpc = _make_mock_rpc()
        rpc.request.get.side_effect = error
        with mock.patch("flaresolverr_session.session.time"):
            with _make_session(rpc=rpc, max_retries=3) as session:
                with self.assertRaises(FlareSolverrResponseError) as ctx:
                    session.get("https://example.com/")
        self.assertEqual(rpc.request.get.call_count, 1)
        self.assertNotIsInstance(ctx.exception, FlareSolverrChallengeError)

    # ------------------------------------------------------------------
    #  construction
    # ------------------------------------------------------------------

    def test_explicit_session_id(self):
        rpc = _make_mock_rpc(session_id="explicit-id")
        session = Session(rpc=rpc, session_id="explicit-id")
        self.assertEqual(session.session_id, "explicit-id")
        session.close()
        rpc.session.destroy.assert_called_once_with("explicit-id")

    def test_session_created_without_rpc(self):
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

    def test_session_created_lazily_and_destroyed(self):
        rpc = _make_mock_rpc(session_id="to-destroy")
        session = Session(rpc=rpc)
        rpc.session.create.assert_not_called()
        session.get("https://example.com/")
        rpc.session.create.assert_called_once()
        _ = session.session_id
        rpc.session.create.assert_called_once()  # second access must not re-create
        session.close()
        rpc.session.destroy.assert_called_once_with("to-destroy")

    def test_ttl_handling(self):
        rpc = _make_mock_rpc()
        with _make_session(rpc=rpc) as session:
            session.get("https://example.com/")
        self.assertNotIn("session_ttl_minutes", rpc.request.get.call_args[1])

        with _make_session(rpc=rpc, ttl=10) as session:
            session.get("https://example.com/")
            session.post("https://example.com/submit", data="x=1")
        self.assertEqual(rpc.request.get.call_args[1]["session_ttl_minutes"], 10)
        self.assertEqual(rpc.request.post.call_args[1]["session_ttl_minutes"], 10)

        # time delta
        session = Session(rpc=rpc, ttl=datetime.timedelta(minutes=15))
        self.assertIsInstance(session._ttl, int)
        self.assertEqual(session._ttl, 15)
        session.close()

        with _make_session(rpc=rpc, ttl=datetime.timedelta(seconds=90)) as session:
            session.get("https://example.com/")
        self.assertEqual(rpc.request.get.call_args[1]["session_ttl_minutes"], 1)

    # ------------------------------------------------------------------
    #  destruction and cleanup
    # ------------------------------------------------------------------

    def test_destroy_not_called_if_never_created(self):
        rpc = _make_mock_rpc()
        Session(rpc=rpc).close()
        rpc.session.destroy.assert_not_called()


class TestResponse(unittest.TestCase):
    def test_response_construction(self):
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


class TestThreadSafety(unittest.TestCase):
    def test_concurrent_requests_are_serialized(self):
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


if __name__ == "__main__":
    unittest.main()
