# -*- coding: utf-8 -*-
import base64
import json
import os
import sys
import unittest

try:
    from unittest import mock
except ImportError:
    import mock  # Python 2

if sys.version_info[0] >= 3:
    from io import StringIO
else:
    from StringIO import StringIO  # Python 2

from flaresolverr_session.cli import main
from flaresolverr_session import (
    FlareSolverrChallengeError,
    FlareSolverrResponseError,
    FlareSolverrError,
)


def _fake_rpc():
    rpc = mock.MagicMock()
    rpc.session.create.return_value = {
        "status": "ok",
        "message": "Session created successfully.",
        "session": "test-session",
        "version": "3.3.21",
        "startTimestamp": 100,
        "endTimestamp": 200,
    }
    rpc.session.list.return_value = {
        "status": "ok",
        "message": "",
        "sessions": ["s1", "s2"],
        "version": "3.3.21",
        "startTimestamp": 100,
        "endTimestamp": 200,
    }
    rpc.session.destroy.return_value = {
        "status": "ok",
        "message": "The session has been removed.",
        "version": "3.3.21",
        "startTimestamp": 100,
        "endTimestamp": 200,
    }
    rpc.session.clear.return_value = {
        "status": "ok",
        "message": "All sessions cleared successfully.",
        "sessions": ["s1", "s2"],
        "version": "3.3.21",
        "startTimestamp": 100,
        "endTimestamp": 200,
    }
    rpc.request.get.return_value = {
        "status": "ok",
        "message": "Challenge solved!",
        "solution": {
            "url": "https://example.com/",
            "status": 200,
            "headers": {},
            "response": "<html>Hello</html>",
            "screenshot": base64.b64encode(b"test").decode("ascii"),
            "cookies": [],
            "userAgent": "TestAgent",
        },
        "version": "3.3.21",
        "startTimestamp": 100,
        "endTimestamp": 200,
    }
    rpc.request.post.return_value = {
        "status": "ok",
        "message": "Challenge solved!",
        "solution": {
            "url": "https://example.com/",
            "status": 200,
            "headers": {},
            "response": "<html>Posted</html>",
            "cookies": [],
            "userAgent": "TestAgent",
        },
        "version": "3.3.21",
        "startTimestamp": 100,
        "endTimestamp": 200,
    }
    return rpc


def _run_cli(argv, rpc=None):
    if rpc is None:
        rpc = _fake_rpc()

    with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = captured_out = StringIO()
        sys.stderr = captured_err = StringIO()
        try:
            exit_code = main(argv)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    return exit_code, captured_out.getvalue(), captured_err.getvalue(), rpc


class TestSession(unittest.TestCase):
    def test_create(self):
        # No args: requires a session name
        with self.assertRaises(SystemExit):
            main(["session", "create"])

        # Single name
        code, out, _err, rpc = _run_cli(["session", "create", "my-sess"])
        self.assertEqual(code, 0)
        rpc.session.create.assert_called_once_with(session_id="my-sess", proxy=None)
        self.assertEqual(len(json.loads(out)), 1)

        # With proxy
        _, _, _, rpc = _run_cli(
            ["session", "create", "my-sess", "--proxy", "http://p:80"]
        )
        rpc.session.create.assert_called_once_with(
            session_id="my-sess", proxy="http://p:80"
        )

        # Multiple names
        code, out, _err, rpc = _run_cli(["session", "create", "a", "b"])
        self.assertEqual(code, 0)
        self.assertEqual(rpc.session.create.call_count, 2)
        rpc.session.create.assert_any_call(session_id="a", proxy=None)
        rpc.session.create.assert_any_call(session_id="b", proxy=None)
        self.assertEqual(len(json.loads(out)), 2)

        # -f flag forwarded to RPC constructor
        rpc = _fake_rpc()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc) as rpc_cls:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                main(["-f", "http://custom:9999/v1", "session", "create", "n1"])
            finally:
                sys.stdout = old_stdout
        rpc_cls.assert_called_once_with("http://custom:9999/v1")

    def test_list_destroy_clear(self):
        # list
        code, out, _err, rpc = _run_cli(["session", "list"])
        self.assertEqual(code, 0)
        rpc.session.list.assert_called_once()
        self.assertEqual(json.loads(out)["sessions"], ["s1", "s2"])

        # destroy
        code, out, _err, rpc = _run_cli(["session", "destroy", "s1"])
        self.assertEqual(code, 0)
        rpc.session.destroy.assert_called_once_with("s1")
        self.assertEqual(json.loads(out)["status"], "ok")

        # clear: calls list then destroys each session
        code, out, _err, rpc = _run_cli(["session", "clear"])
        self.assertEqual(code, 0)
        rpc.session.list.assert_called_once()
        self.assertEqual(rpc.session.destroy.call_count, 2)
        rpc.session.destroy.assert_any_call("s1")
        rpc.session.destroy.assert_any_call("s2")
        self.assertEqual(len(json.loads(out)), 2)


class TestRequest(unittest.TestCase):
    def tearDown(self):
        os.path.exists("ss.png") and os.remove("ss.png")

    def test_get_routing(self):
        # URL as first arg → GET
        _, _, _, rpc = _run_cli(["https://example.com"])
        rpc.request.get.assert_called_once_with("https://example.com")

        # http:// prefix also treated as request
        _, _, _, rpc = _run_cli(["http://example.com"])
        rpc.request.get.assert_called_once_with("http://example.com")

        # explicit 'request' keyword
        _, _, _, rpc = _run_cli(["request", "https://example.com"])
        rpc.request.get.assert_called_once_with("https://example.com")

        # explicit -m GET
        _, _, _, rpc = _run_cli(["https://example.com", "-m", "GET"])
        rpc.request.get.assert_called_once_with("https://example.com")

        # -f before URL
        rpc = _fake_rpc()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc) as rpc_cls:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                main(["-f", "http://srv:8191/v1", "https://target.com"])
            finally:
                sys.stdout = old_stdout
        rpc_cls.assert_called_once_with("http://srv:8191/v1")
        rpc.request.get.assert_called_once_with("https://target.com")

        # -f after URL
        rpc = _fake_rpc()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc) as rpc_cls:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                main(["https://target.com", "-f", "http://srv:8191/v1"])
            finally:
                sys.stdout = old_stdout
        rpc_cls.assert_called_once_with("http://srv:8191/v1")
        rpc.request.get.assert_called_once_with("https://target.com")

    def test_post_routing(self):
        # -d implies POST
        _, _, _, rpc = _run_cli(["https://example.com", "-d", "foo=bar"])
        rpc.request.post.assert_called_once_with("https://example.com", data="foo=bar")

        # -m POST explicit with data
        _, _, _, rpc = _run_cli(["https://example.com", "-m", "POST", "-d", "x=1"])
        rpc.request.post.assert_called_once_with("https://example.com", data="x=1")

        # -m POST without data
        _, _, _, rpc = _run_cli(["https://example.com", "-m", "POST"])
        rpc.request.post.assert_called_once_with("https://example.com", data=None)

        # -m GET overrides implicit POST from data
        _, _, _, rpc = _run_cli(["https://example.com", "-m", "GET", "-d", "foo=bar"])
        rpc.request.get.assert_called_once_with("https://example.com")

        # 'request' keyword with data
        _, _, _, rpc = _run_cli(["request", "https://example.com", "-d", "k=v"])
        rpc.request.post.assert_called_once_with("https://example.com", data="k=v")

    def test_request_options(self):
        # session_id via -s, --session, --session-id
        for flag, val in [
            ("-s", "my-session"),
            ("--session", "another"),
            ("--session-id", "third"),
        ]:
            _, _, _, rpc = _run_cli(["https://example.com", flag, val])
            rpc.request.get.assert_called_once_with(
                "https://example.com", session_id=val
            )

        # timeout
        _, _, _, rpc = _run_cli(["https://example.com", "-t", "30000"])
        rpc.request.get.assert_called_once_with(
            "https://example.com", max_timeout=30000
        )

        # proxy
        _, _, _, rpc = _run_cli(["https://example.com", "--proxy", "http://p:80"])
        rpc.request.get.assert_called_once_with(
            "https://example.com", proxy="http://p:80"
        )

        # args before URL
        _, _, _, rpc = _run_cli(["--proxy", "http://p:80", "https://example.com"])
        rpc.request.get.assert_called_once_with(
            "https://example.com", proxy="http://p:80"
        )

        # session-ttl-minutes
        _, _, _, rpc = _run_cli(["https://example.com", "--session-ttl-minutes", "30"])
        rpc.request.get.assert_called_once_with(
            "https://example.com", session_ttl_minutes=30
        )

        # cookies-only
        _, _, _, rpc = _run_cli(["https://example.com", "--cookies-only"])
        rpc.request.get.assert_called_once_with(
            "https://example.com", return_only_cookies=True
        )

        # cookies list
        _, _, _, rpc = _run_cli(
            ["https://example.com", "--cookies", "a=cookie1", "--cookies", "b=cookie2"]
        )
        rpc.request.get.assert_called_once_with(
            "https://example.com",
            cookies=[
                {"name": "a", "value": "cookie1"},
                {"name": "b", "value": "cookie2"},
            ],
        )

        # wait
        _, _, _, rpc = _run_cli(["https://example.com", "--wait", "5"])
        rpc.request.get.assert_called_once_with(
            "https://example.com", wait_in_seconds=5
        )

        # disable-media
        _, _, _, rpc = _run_cli(["https://example.com", "--disable-media"])
        rpc.request.get.assert_called_once_with(
            "https://example.com", disable_media=True
        )

        # all options combined
        code, _, _, rpc = _run_cli(
            [
                "https://example.com",
                "-s",
                "sid",
                "-t",
                "5000",
                "--proxy",
                "http://p:80",
                "-d",
                "a=b",
            ]
        )
        self.assertEqual(code, 0)
        rpc.request.post.assert_called_once_with(
            "https://example.com",
            data="a=b",
            session_id="sid",
            max_timeout=5000,
            proxy="http://p:80",
        )

        # all new options combined
        code, _, _, rpc = _run_cli(
            [
                "https://example.com",
                "--session-ttl-minutes",
                "15",
                "--cookies-only",
                "--screenshot",
                "ss.png",
                "--wait",
                "3",
                "--disable-media",
            ]
        )
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with(
            "https://example.com",
            session_ttl_minutes=15,
            return_only_cookies=True,
            return_screenshot=True,
            wait_in_seconds=3,
            disable_media=True,
        )

    def test_output(self):
        # output file written
        rpc = _fake_rpc()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc):
            m = mock.mock_open()
            open = (
                "flaresolverr_session.cli.open"
                if sys.version_info[0] >= 3
                else "__builtin__.open"
            )
            with mock.patch(open, m):
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                try:
                    main(["https://example.com", "-o", "out.html"])
                finally:
                    sys.stdout = old_stdout
        m.assert_called_once_with("out.html", "wb")
        m().write.assert_called_once_with(b"<html>Hello</html>")

    def test_screenshot_output(self):
        # screenshot decoded and written
        rpc = _fake_rpc()
        png = b"PNGDATA"
        b64 = base64.b64encode(png).decode("ascii")
        rpc.request.get.return_value = {
            "status": "ok",
            "message": "",
            "solution": {
                "url": "https://example.com/",
                "status": 200,
                "headers": {},
                "response": "<html>Hello</html>",
                "cookies": [],
                "userAgent": "TestAgent",
                "screenshot": b64,
            },
            "version": "3.3.21",
            "startTimestamp": 100,
            "endTimestamp": 200,
        }
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc):
            m = mock.mock_open()
            open = (
                "flaresolverr_session.cli.open"
                if sys.version_info[0] >= 3
                else "__builtin__.open"
            )
            with mock.patch(open, m):
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                try:
                    main(["https://example.com", "--screenshot", "out.png"])
                finally:
                    sys.stdout = old_stdout
        m.assert_called_with("out.png", "wb")
        m().write.assert_called_once_with(png)

    def test_no_args_and_help(self):
        # no-args and help flags exit 0
        for argv in [[], ["-h"], ["--help"]]:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                code = main(argv)
            finally:
                sys.stdout = old_stdout
            self.assertEqual(code, 0)

        # request --help raises SystemExit
        with self.assertRaises(SystemExit):
            _run_cli(["request", "--help"])

    def test_retry(self):
        rpc = _fake_rpc()
        challenge_error = self._make_challenge_error()
        success = rpc.request.get.return_value
        rpc.request.get.side_effect = [challenge_error, challenge_error, success]
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc):
            with mock.patch("flaresolverr_session.cli.time") as mock_time:
                code = main(["https://example.com/", "--retries", "2"])
        self.assertEqual(code, 0)
        self.assertEqual(rpc.request.get.call_count, 3)
        self.assertEqual(mock_time.sleep.call_count, 2)
        mock_time.sleep.assert_called_with(1)

        # POST requests are also retried
        rpc = _fake_rpc()
        challenge_error = self._make_challenge_error()
        post_success = rpc.request.post.return_value
        rpc.request.post.side_effect = [challenge_error, post_success]
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc):
            with mock.patch("flaresolverr_session.cli.time") as mock_time:
                code = main(["-d", "a=1", "https://example.com/", "--retries", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(rpc.request.post.call_count, 2)
        mock_time.sleep.assert_called_once_with(1)

        # Exhausted: all retries used up → exit 1
        rpc = _fake_rpc()
        rpc.request.get.side_effect = self._make_challenge_error()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc):
            with mock.patch("flaresolverr_session.cli.time"):
                code = main(["https://example.com/", "--retries", "1"])
        self.assertEqual(code, 1)
        self.assertEqual(rpc.request.get.call_count, 2)

        # Disabled (default, no --retries): exits 1 on first call
        rpc = _fake_rpc()
        rpc.request.get.side_effect = self._make_challenge_error()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc):
            code = main(["https://example.com/"])
        self.assertEqual(code, 1)
        self.assertEqual(rpc.request.get.call_count, 1)

        # non-challenge error: not retried, exits 1 immediately
        rpc = _fake_rpc()
        rpc.request.get.side_effect = FlareSolverrResponseError(
            "Server error",
            response_data={"status": "error", "message": "Server error"},
        )
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc):
            with mock.patch("flaresolverr_session.cli.time"):
                code = main(["https://example.com/", "--retries", "3"])
        self.assertEqual(code, 1)
        self.assertEqual(rpc.request.get.call_count, 1)

    def _make_challenge_error(self):
        return FlareSolverrChallengeError(
            "Challenge timeout",
            response_data={"status": "error", "message": "Challenge timeout"},
        )


class TestErrorHandling(unittest.TestCase):
    def _make_rpc_raising(self, exc):
        rpc = _fake_rpc()
        rpc.request.get.side_effect = exc
        rpc.request.post.side_effect = exc
        return rpc

    def test_error_exits_nonzero(self):
        # ResponseError → exit 1, stderr is JSON with all fields, stdout empty
        fake_resp = {
            "status": "error",
            "message": "Challenge not solved",
            "version": "3.3.21",
            "startTimestamp": 100,
            "endTimestamp": 200,
        }
        exc = FlareSolverrResponseError("Challenge not solved", response_data=fake_resp)
        rpc = self._make_rpc_raising(exc)
        code, out, err, _ = _run_cli(["https://example.com"], rpc=rpc)
        self.assertEqual(code, 1)
        self.assertEqual(out.strip(), "")
        data = json.loads(err)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Challenge not solved")
        self.assertEqual(data["version"], "3.3.21")

        # Various error messages still exit 1 with stderr JSON
        for msg in ["Captcha detected", "Error: Timeout reached"]:
            fake_resp = {"status": "error", "message": msg}
            exc = FlareSolverrResponseError(msg, response_data=fake_resp)
            code, _, err, _ = _run_cli(
                ["https://example.com"], rpc=self._make_rpc_raising(exc)
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(err)["message"], msg)

        # Session command error
        fake_resp = {"status": "error", "message": "Session not found"}
        exc = FlareSolverrResponseError("Session not found", response_data=fake_resp)
        rpc = _fake_rpc()
        rpc.session.destroy.side_effect = exc
        code, _, err, _ = _run_cli(["session", "destroy", "s1"], rpc=rpc)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err)["message"], "Session not found")

        # POST request error
        fake_resp = {"status": "error", "message": "Challenge not solved"}
        exc = FlareSolverrResponseError("Challenge not solved", response_data=fake_resp)
        rpc = _fake_rpc()
        rpc.request.post.side_effect = exc
        code, _, err, _ = _run_cli(["https://example.com", "-d", "foo=bar"], rpc=rpc)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err)["status"], "error")

        # Generic FlareSolverrError propagates (not caught by CLI)
        exc = FlareSolverrError("Connection refused")
        with self.assertRaises(FlareSolverrError):
            _run_cli(["https://example.com"], rpc=self._make_rpc_raising(exc))


if __name__ == "__main__":
    unittest.main()
