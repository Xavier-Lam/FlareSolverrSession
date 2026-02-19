# -*- coding: utf-8 -*-
"""Tests for the CLI module.

All tests mock :class:`flaresolverr_rpc.RPC` (and its sub-commands)
to verify that CLI arguments are correctly parsed and the right RPC
methods are invoked with the expected arguments.
"""

import base64
import json
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

from flaresolverr_session.cli import main, _truncate_response_body
from flaresolverr_session import (
    FlareSolverrResponseError,
    FlareSolverrError,
)


def _fake_rpc():
    """Return a mock RPC instance with session and request stubs.

    Returns:
        mock.MagicMock: A mock RPC with .session and .request attributes.
    """
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
    """Run the CLI main() with mocked RPC and capture stdout/stderr.

    Parameters:
        argv (list of str): CLI arguments.
        rpc (mock.MagicMock or None): Optional pre-built mock RPC.

    Returns:
        tuple: (exit_code, stdout_text, stderr_text, rpc_mock)
    """
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


class TestSessionCreate(unittest.TestCase):
    """Tests for 'session create' CLI command."""

    def test_create_no_args(self):
        """session create with no extra args."""
        code, out, _err, rpc = _run_cli(["session", "create"])
        self.assertEqual(code, 0)
        rpc.session.create.assert_called_once_with(session_id=None, proxy=None)
        data = json.loads(out)
        self.assertEqual(data["status"], "ok")

    def test_create_with_name(self):
        """session create with a session name."""
        code, out, _err, rpc = _run_cli(["session", "create", "my-sess"])
        self.assertEqual(code, 0)
        rpc.session.create.assert_called_once_with(session_id="my-sess", proxy=None)

    def test_create_with_proxy(self):
        """session create with --proxy."""
        code, out, _err, rpc = _run_cli(["session", "create", "--proxy", "http://p:80"])
        self.assertEqual(code, 0)
        rpc.session.create.assert_called_once_with(session_id=None, proxy="http://p:80")

    def test_create_with_name_and_proxy(self):
        """session create with name and proxy."""
        code, out, _err, rpc = _run_cli(
            ["session", "create", "sid", "--proxy", "http://p:80"]
        )
        self.assertEqual(code, 0)
        rpc.session.create.assert_called_once_with(
            session_id="sid", proxy="http://p:80"
        )

    def test_create_with_flaresolverr_url(self):
        """session create with -f flag."""
        rpc = _fake_rpc()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc) as rpc_cls:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                main(["-f", "http://custom:9999/v1", "session", "create"])
            finally:
                sys.stdout = old_stdout
            rpc_cls.assert_called_once_with("http://custom:9999/v1")


class TestSessionList(unittest.TestCase):
    """Tests for 'session list' CLI command."""

    def test_list(self):
        """session list returns session list."""
        code, out, _err, rpc = _run_cli(["session", "list"])
        self.assertEqual(code, 0)
        rpc.session.list.assert_called_once()
        data = json.loads(out)
        self.assertEqual(data["sessions"], ["s1", "s2"])


class TestSessionDestroy(unittest.TestCase):
    """Tests for 'session destroy' CLI command."""

    def test_destroy(self):
        """session destroy passes the session id."""
        code, out, _err, rpc = _run_cli(["session", "destroy", "s1"])
        self.assertEqual(code, 0)
        rpc.session.destroy.assert_called_once_with("s1")
        data = json.loads(out)
        self.assertEqual(data["status"], "ok")


class TestRequestDefault(unittest.TestCase):
    """Tests for the default request command (URL as first arg)."""

    def test_get_implicit(self):
        """URL as first arg sends a GET request."""
        code, out, _err, rpc = _run_cli(["https://example.com"])
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with("https://example.com")

    def test_get_explicit_request(self):
        """Explicit 'request' command sends a GET request."""
        code, out, _err, rpc = _run_cli(["request", "https://example.com"])
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with("https://example.com")

    def test_get_with_method_flag(self):
        """Explicit -m GET."""
        code, out, _err, rpc = _run_cli(["https://example.com", "-m", "GET"])
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with("https://example.com")

    def test_post_with_data(self):
        """Data provided implies POST."""
        code, out, _err, rpc = _run_cli(["https://example.com", "-d", "foo=bar"])
        self.assertEqual(code, 0)
        rpc.request.post.assert_called_once_with("https://example.com", data="foo=bar")

    def test_post_explicit_method(self):
        """Explicit -m POST with data."""
        code, out, _err, rpc = _run_cli(
            ["https://example.com", "-m", "POST", "-d", "x=1"]
        )
        self.assertEqual(code, 0)
        rpc.request.post.assert_called_once_with("https://example.com", data="x=1")

    def test_post_explicit_no_data(self):
        """Explicit -m POST without data."""
        code, out, _err, rpc = _run_cli(["https://example.com", "-m", "POST"])
        self.assertEqual(code, 0)
        rpc.request.post.assert_called_once_with("https://example.com", data=None)

    def test_get_explicit_method_override_data(self):
        """Explicit -m GET overrides implicit POST from data."""
        code, out, _err, rpc = _run_cli(
            ["https://example.com", "-m", "GET", "-d", "foo=bar"]
        )
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with("https://example.com")


class TestRequestWithOptions(unittest.TestCase):
    """Tests for request command with various options."""

    def test_session_id(self):
        """Request with -s session-id."""
        code, out, _err, rpc = _run_cli(["https://example.com", "-s", "my-session"])
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with(
            "https://example.com", session_id="my-session"
        )

    def test_timeout(self):
        """Request with -t timeout."""
        code, out, _err, rpc = _run_cli(["https://example.com", "-t", "30000"])
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with(
            "https://example.com", max_timeout=30000
        )

    def test_proxy(self):
        """Request with --proxy."""
        code, out, _err, rpc = _run_cli(
            ["https://example.com", "--proxy", "http://p:80"]
        )
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with(
            "https://example.com", proxy="http://p:80"
        )

    def test_all_options(self):
        """Request with all options combined."""
        code, out, _err, rpc = _run_cli(
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

    def test_session_ttl_minutes(self):
        """Request with --session-ttl-minutes."""
        code, out, _err, rpc = _run_cli(
            ["https://example.com", "--session-ttl-minutes", "30"]
        )
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with(
            "https://example.com", session_ttl_minutes=30
        )

    def test_return_only_cookies(self):
        """Request with --return-only-cookies."""
        code, out, _err, rpc = _run_cli(
            ["https://example.com", "--return-only-cookies"]
        )
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with(
            "https://example.com", return_only_cookies=True
        )

    def test_return_screenshot(self):
        """Request with --return-screenshot."""
        code, out, _err, rpc = _run_cli(
            ["https://example.com", "--screenshot", "s.png"]
        )
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with(
            "https://example.com", return_screenshot=True
        )

    def test_wait_in_seconds(self):
        """Request with --wait."""
        code, out, _err, rpc = _run_cli(["https://example.com", "--wait", "5"])
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with(
            "https://example.com", wait_in_seconds=5
        )

    def test_disable_media(self):
        """Request with --disable-media."""
        code, out, _err, rpc = _run_cli(["https://example.com", "--disable-media"])
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with(
            "https://example.com", disable_media=True
        )

    def test_all_new_options_combined(self):
        """Request with all new option flags combined."""
        code, out, _err, rpc = _run_cli(
            [
                "https://example.com",
                "--session-ttl-minutes",
                "15",
                "--return-only-cookies",
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

    def test_flaresolverr_url_passed_to_rpc(self):
        """The -f flag is forwarded to RPC constructor."""
        rpc = _fake_rpc()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc) as rpc_cls:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                main(["-f", "http://custom:1234/v1", "https://example.com"])
            finally:
                sys.stdout = old_stdout
            rpc_cls.assert_called_once_with("http://custom:1234/v1")

    def test_flaresolverr_url_with_request_command(self):
        """The -f flag works with explicit request command."""
        rpc = _fake_rpc()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc) as rpc_cls:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                main(["-f", "http://custom:1234/v1", "request", "https://example.com"])
            finally:
                sys.stdout = old_stdout
            rpc_cls.assert_called_once_with("http://custom:1234/v1")


class TestRequestOutputFile(unittest.TestCase):
    """Tests for -o / --output flag."""

    def test_output_file(self):
        """Response body is written to file."""
        rpc = _fake_rpc()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc):
            m = mock.mock_open()
            with mock.patch(
                (
                    "flaresolverr_session.cli.open"
                    if sys.version_info[0] >= 3
                    else "__builtin__.open"
                ),
                m,
            ):
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                try:
                    main(["https://example.com", "-o", "out.html"])
                finally:
                    sys.stdout = old_stdout

        m.assert_called_once_with("out.html", "wb")
        handle = m()
        handle.write.assert_called_once_with(b"<html>Hello</html>")

    def test_screenshot_file(self):
        """Screenshot is written to file when --screenshot is provided."""
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
            with mock.patch(
                (
                    "flaresolverr_session.cli.open"
                    if sys.version_info[0] >= 3
                    else "__builtin__.open"
                ),
                m,
            ):
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                try:
                    main(["https://example.com", "--screenshot", "out.png"])
                finally:
                    sys.stdout = old_stdout

        m.assert_called_with("out.png", "wb")
        handle = m()
        handle.write.assert_called_once_with(png)


class TestTruncateResponseBody(unittest.TestCase):
    """Tests for _truncate_response_body."""

    def test_short_body_unchanged(self):
        """Short body is not truncated."""
        data = {"solution": {"response": "short"}}
        result = _truncate_response_body(data, max_length=200)
        self.assertEqual(result["solution"]["response"], "short")

    def test_long_body_truncated(self):
        """Long body is truncated with letter count."""
        body = "a" * 500
        data = {"solution": {"response": body}}
        result = _truncate_response_body(data, max_length=100)
        self.assertIn("...[500 letters]", result["solution"]["response"])
        self.assertTrue(result["solution"]["response"].startswith("a" * 100))

    def test_empty_response(self):
        """Empty response string is not truncated."""
        data = {"solution": {"response": ""}}
        result = _truncate_response_body(data)
        self.assertEqual(result["solution"]["response"], "")


class TestOutputIsJson(unittest.TestCase):
    """Verify that CLI output is valid JSON."""

    def test_session_list_json(self):
        """session list output is valid JSON."""
        code, out, _err, rpc = _run_cli(["session", "list"])
        data = json.loads(out)
        self.assertIn("sessions", data)

    def test_request_output_json(self):
        """request output is valid JSON."""
        code, out, _err, rpc = _run_cli(["https://example.com"])
        data = json.loads(out)
        self.assertIn("solution", data)

    def test_long_response_truncated_in_output(self):
        """Long response bodies are truncated in JSON output."""
        rpc = _fake_rpc()
        rpc.request.get.return_value = {
            "status": "ok",
            "message": "",
            "solution": {
                "url": "https://example.com/",
                "status": 200,
                "headers": {},
                "response": "x" * 1000,
                "cookies": [],
                "userAgent": "TestAgent",
            },
            "version": "3.3.21",
            "startTimestamp": 100,
            "endTimestamp": 200,
        }
        code, out, _err, _ = _run_cli(["https://example.com"], rpc=rpc)
        data = json.loads(out)
        self.assertIn("...[1000 letters]", data["solution"]["response"])


class TestTwoPassParsing(unittest.TestCase):
    """Edge cases for the two-pass argument parser."""

    def test_url_starting_with_http(self):
        """URL starting with http:// is treated as request."""
        code, out, _err, rpc = _run_cli(["http://example.com"])
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with("http://example.com")

    def test_url_starting_with_https(self):
        """URL starting with https:// is treated as request."""
        code, out, _err, rpc = _run_cli(["https://example.com"])
        self.assertEqual(code, 0)
        rpc.request.get.assert_called_once_with("https://example.com")

    def test_request_keyword_explicit(self):
        """Explicit 'request' keyword works."""
        code, out, _err, rpc = _run_cli(["request", "https://example.com", "-d", "k=v"])
        self.assertEqual(code, 0)
        rpc.request.post.assert_called_once_with("https://example.com", data="k=v")

    def test_f_flag_before_command(self):
        """-f before session command."""
        rpc = _fake_rpc()
        with mock.patch("flaresolverr_session.cli.RPC", return_value=rpc) as rpc_cls:
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                main(["-f", "http://srv:8191/v1", "session", "list"])
            finally:
                sys.stdout = old_stdout
            rpc_cls.assert_called_once_with("http://srv:8191/v1")

    def test_f_flag_before_url(self):
        """-f before URL (implicit request)."""
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

    def test_f_flag_after_url(self):
        """-f after URL (implicit request)."""
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

    def test_no_args_shows_help_exit_zero(self):
        """No arguments shows help and exits with code 0."""
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            code = main([])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(code, 0)

    def test_dash_h_shows_help_exit_zero(self):
        """-h shows help and exits with code 0."""
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            code = main(["-h"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(code, 0)

    def test_double_dash_help_exit_zero(self):
        """--help shows help and exits with code 0."""
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            code = main(["--help"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(code, 0)


class TestCliErrorHandling(unittest.TestCase):
    """Tests for CLI error handling when FlareSolverr returns errors."""

    def _make_rpc_raising(self, exc):
        """Return a fake RPC whose request.get raises exc.

        Parameters:
            exc (Exception): The exception to raise.

        Returns:
            mock.MagicMock: Mocked RPC instance.
        """
        rpc = _fake_rpc()
        rpc.request.get.side_effect = exc
        rpc.request.post.side_effect = exc
        return rpc

    def test_response_error_exits_nonzero(self):
        """FlareSolverrResponseError causes exit code 1."""
        fake_resp = {"status": "error", "message": "Challenge not solved"}
        exc = FlareSolverrResponseError("Challenge not solved", response_data=fake_resp)
        rpc = self._make_rpc_raising(exc)
        code, out, err, _ = _run_cli(["https://example.com"], rpc=rpc)
        self.assertEqual(code, 1)

    def test_response_error_prints_response_json_to_stderr(self):
        """When exc.response is set, its JSON is printed to stderr."""
        fake_resp = {"status": "error", "message": "Challenge not solved"}
        exc = FlareSolverrResponseError("Challenge not solved", response_data=fake_resp)
        rpc = self._make_rpc_raising(exc)
        code, out, err, _ = _run_cli(["https://example.com"], rpc=rpc)
        self.assertEqual(code, 1)
        # Stdout should be empty (no normal output)
        self.assertEqual(out.strip(), "")
        # Stderr should contain the JSON response
        data = json.loads(err)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Challenge not solved")

    def test_error_without_response_prints_message_to_stderr(self):
        """When exc.response is None, the error message is printed to stderr."""
        exc = FlareSolverrError("Connection refused")
        rpc = self._make_rpc_raising(exc)
        with self.assertRaises(FlareSolverrError) as ctx:
            _run_cli(["https://example.com"], rpc=rpc)
        e = ctx.exception
        self.assertEqual(str(e), "Connection refused")

    def test_captcha_error_exits_nonzero(self):
        """FlareSolverrResponseError with captcha message causes exit code 1."""
        fake_resp = {"status": "error", "message": "Captcha detected"}
        exc = FlareSolverrResponseError("Captcha detected", response_data=fake_resp)
        rpc = self._make_rpc_raising(exc)
        code, out, err, _ = _run_cli(["https://example.com"], rpc=rpc)
        self.assertEqual(code, 1)
        data = json.loads(err)
        self.assertEqual(data["message"], "Captcha detected")

    def test_timeout_error_exits_nonzero(self):
        """FlareSolverrResponseError with timeout message causes exit code 1."""
        fake_resp = {"status": "error", "message": "Error: Timeout reached"}
        exc = FlareSolverrResponseError(
            "Error: Timeout reached", response_data=fake_resp
        )
        rpc = self._make_rpc_raising(exc)
        code, out, err, _ = _run_cli(["https://example.com"], rpc=rpc)
        self.assertEqual(code, 1)
        data = json.loads(err)
        self.assertIn("Timeout", data["message"])

    def test_session_command_error_exits_nonzero(self):
        """FlareSolverrResponseError during session command exits 1."""
        fake_resp = {"status": "error", "message": "Session not found"}
        exc = FlareSolverrResponseError("Session not found", response_data=fake_resp)
        rpc = _fake_rpc()
        rpc.session.destroy.side_effect = exc
        code, out, err, _ = _run_cli(["session", "destroy", "s1"], rpc=rpc)
        self.assertEqual(code, 1)
        data = json.loads(err)
        self.assertEqual(data["message"], "Session not found")

    def test_post_error_exits_nonzero(self):
        """FlareSolverrResponseError on POST request exits 1."""
        fake_resp = {"status": "error", "message": "Challenge not solved"}
        exc = FlareSolverrResponseError("Challenge not solved", response_data=fake_resp)
        rpc = _fake_rpc()
        rpc.request.post.side_effect = exc
        code, out, err, _ = _run_cli(["https://example.com", "-d", "foo=bar"], rpc=rpc)
        self.assertEqual(code, 1)
        data = json.loads(err)
        self.assertEqual(data["status"], "error")

    def test_stderr_is_json_with_full_response(self):
        """All fields from the response dict appear in stderr JSON."""
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
        data = json.loads(err)
        self.assertEqual(data["version"], "3.3.21")
        self.assertEqual(data["startTimestamp"], 100)
        self.assertEqual(data["endTimestamp"], 200)

    def test_stdout_empty_on_error(self):
        """On error, nothing is written to stdout."""
        fake_resp = {"status": "error", "message": "oops"}
        exc = FlareSolverrResponseError("oops", response_data=fake_resp)
        rpc = self._make_rpc_raising(exc)
        code, out, err, _ = _run_cli(["https://example.com"], rpc=rpc)
        self.assertEqual(out.strip(), "")


if __name__ == "__main__":
    unittest.main()
