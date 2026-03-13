# -*- coding: utf-8 -*-

import time
import unittest

try:
    from unittest import mock
except ImportError:
    import mock  # Python 2 back-port

import requests

from flaresolverr_session import (
    RPC,
    FlareSolverrChallengeError,
    FlareSolverrResponseError,
)

try:
    string_types = basestring  # Python 2
except NameError:
    string_types = str

# A publicly accessible URL that never returns a Cloudflare challenge
_PLAIN_URL = "https://httpbin.org/get"
_PLAIN_POST_URL = "https://httpbin.org/post"


class RPCTestCase(unittest.TestCase):
    def setUp(self):
        session = requests.Session()
        session.trust_env = False
        self.rpc = RPC(api_session=session)

    def _assert_ok(self, response):
        self.assertIsInstance(response, dict, "Expected dict, got %r" % type(response))
        self.assertEqual(
            response.get("status"),
            "ok",
            "Expected status 'ok', got %r (message: %r)"
            % (response.get("status"), response.get("message")),
        )
        self.assertIn("version", response, "Missing 'version' key in response")
        self.assertIn(
            "startTimestamp", response, "Missing 'startTimestamp' key in response"
        )
        self.assertIn(
            "endTimestamp", response, "Missing 'endTimestamp' key in response"
        )

    def _assert_solution(self, solution):
        self.assertIsInstance(
            solution, dict, "Expected solution dict, got %r" % type(solution)
        )
        self.assertIn("url", solution, "Missing 'url' in solution")
        self.assertIn("status", solution, "Missing 'status' in solution")
        self.assertIn("userAgent", solution, "Missing 'userAgent' in solution")
        self.assertIn("cookies", solution, "Missing 'cookies' in solution")
        self.assertIsInstance(
            solution.get("cookies"),
            list,
            "Expected cookies to be a list, got %r" % type(solution.get("cookies")),
        )


class TestSession(RPCTestCase):
    def test_session_lifecycle(self):
        result = self.rpc.session.create()
        self._assert_ok(result)
        self.assertIn("session", result, "Missing 'session' key in create response")
        sid = result["session"]

        listed = self.rpc.session.list()
        self._assert_ok(listed)
        self.assertIn("sessions", listed)
        self.assertIsInstance(listed["sessions"], list)
        self.assertIn(sid, listed["sessions"])

        destroy_result = self.rpc.session.destroy(sid)
        self._assert_ok(destroy_result)
        after = self.rpc.session.list()
        self.assertNotIn(sid, after["sessions"])

    def test_session_with_explicit_id(self):
        sid = "test-rpc-explicit-session"
        result = self.rpc.session.create(session_id=sid)
        self._assert_ok(result)
        self.assertEqual(
            result["session"],
            sid,
            "Expected session id %r, got %r" % (sid, result["session"]),
        )
        self.rpc.session.destroy(sid)


class TestRequest(RPCTestCase):
    def test_get(self):
        result = self.rpc.request.get(_PLAIN_URL)
        self._assert_ok(result)
        self.assertIn("solution", result, "Missing 'solution' key")
        solution = result["solution"]
        self._assert_solution(solution)
        self.assertTrue(solution["url"], "Expected non-empty solution url")
        self.assertTrue(solution["response"], "Expected non-empty solution.response")
        ua = solution["userAgent"]
        self.assertTrue(
            ua and isinstance(ua, string_types), "Expected non-empty string userAgent"
        )

    def test_get_with_options(self):
        created = self.rpc.session.create()
        sid = created["session"]
        try:
            result = self.rpc.request.get(_PLAIN_URL, session_id=sid)
            self._assert_ok(result)
            self._assert_solution(result["solution"])
        finally:
            self.rpc.session.destroy(sid)

        result = self.rpc.request.get(_PLAIN_URL, return_only_cookies=True)
        self._assert_ok(result)
        body = result["solution"].get("response", "")
        self.assertTrue(
            body == "" or body is None,
            "Expected empty body with return_only_cookies=True",
        )

        result = self.rpc.request.get(_PLAIN_URL, return_screenshot=True)
        self._assert_ok(result)
        screenshot = result["solution"].get("screenshot")
        self.assertTrue(screenshot and isinstance(screenshot, string_types))

        cookies = [{"name": "test_cookie", "value": "hello"}]
        result = self.rpc.request.get(_PLAIN_URL, cookies=cookies)
        self._assert_ok(result)
        self.assertIn("test_cookie=hello", result["solution"].get("response", ""))

        for kwargs in [
            {"disable_media": True},
            {"session_ttl_minutes": 30},
            {"max_timeout": 30000},
        ]:
            r = self.rpc.request.get(_PLAIN_URL, **kwargs)
            self._assert_ok(r)
            self._assert_solution(r["solution"])

    def test_get_wait_in_seconds(self):
        now = time.time()
        result = self.rpc.request.get(_PLAIN_URL, wait_in_seconds=1)
        self.assertGreaterEqual(
            time.time(), now + 1, "Expected at least 1 second delay"
        )
        self._assert_ok(result)
        self._assert_solution(result["solution"])

    def test_post(self):
        result = self.rpc.request.post(
            _PLAIN_POST_URL, data={"foo": "bar", "baz": "qux"}
        )
        self._assert_ok(result)
        self.assertIn("solution", result)
        self._assert_solution(result["solution"])

        for data in ["key=value&other=123", None]:
            r = self.rpc.request.post(_PLAIN_POST_URL, data=data)
            self._assert_ok(r)
            self._assert_solution(r["solution"])

        result = self.rpc.request.post(
            _PLAIN_POST_URL, data="x=1", return_only_cookies=True
        )
        self._assert_ok(result)
        body = result["solution"].get("response", "")
        self.assertTrue(body == "" or body is None)

        result = self.rpc.request.post(_PLAIN_POST_URL, data="x=1", disable_media=True)
        self._assert_ok(result)
        self._assert_solution(result["solution"])


class TestRPCErrorHandling(unittest.TestCase):
    def test_error_handling(self):
        error_data = {
            "status": "error",
            "message": "Internal error",
            "startTimestamp": 0,
            "endTimestamp": 0,
            "version": "0.0.0",
        }
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = error_data

        rpc = RPC("http://localhost:8191/v1")
        rpc._api_session = mock.MagicMock()
        rpc._api_session.post.return_value = mock_resp

        with self.assertRaises(FlareSolverrResponseError) as ctx:
            rpc.send({"cmd": "request.get", "url": "https://example.com"})
        self.assertEqual(ctx.exception.message, "Internal error")
        self.assertEqual(ctx.exception.response_data, error_data)

        challenge_data = {
            "status": "error",
            "message": "Captcha challenge failed",
            "startTimestamp": 0,
            "endTimestamp": 0,
            "version": "0.0.0",
        }
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = challenge_data
        rpc2 = RPC("http://localhost:8191/v1")
        rpc2._api_session = mock.MagicMock()
        rpc2._api_session.post.return_value = mock_resp

        with self.assertRaises(FlareSolverrChallengeError) as ctx2:
            rpc2.request.get("https://example.com")
        self.assertEqual(ctx2.exception.message, "Captcha challenge failed")
        self.assertIs(ctx2.exception.response, mock_resp)


if __name__ == "__main__":
    unittest.main()
