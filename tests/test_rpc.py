# -*- coding: utf-8 -*-

import os
import time
import unittest

import requests

from flaresolverr_session import RPC

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
        proxy_url = os.environ.get("FLARESOLVERR_PROXY")
        if proxy_url:
            session.proxies.update(
                {
                    "http": proxy_url,
                    "https": proxy_url,
                }
            )
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


class TestSessionCreate(RPCTestCase):
    def test_create_returns_ok(self):
        """session.create() returns status ok."""
        result = self.rpc.session.create()
        self._assert_ok(result)
        self.assertIn("session", result, "Missing 'session' key in create response")
        # clean up
        self.rpc.session.destroy(result["session"])

    def test_create_with_explicit_id(self):
        """session.create(session_id=...) honours the requested id."""
        sid = "test-rpc-explicit-session"
        result = self.rpc.session.create(session_id=sid)
        self._assert_ok(result)
        self.assertEqual(
            result["session"],
            sid,
            "Expected session id %r, got %r" % (sid, result["session"]),
        )
        # clean up
        self.rpc.session.destroy(sid)


class TestSessionList(RPCTestCase):
    def test_list_returns_ok(self):
        """session.list() returns status ok."""
        result = self.rpc.session.list()
        self._assert_ok(result)
        self.assertIn("sessions", result, "Missing 'sessions' key")
        self.assertIsInstance(
            result["sessions"], list, "Expected sessions to be a list"
        )

    def test_created_session_appears_in_list(self):
        """A created session appears in the session list."""
        created = self.rpc.session.create()
        sid = created["session"]
        try:
            listed = self.rpc.session.list()
            self.assertIn(
                sid,
                listed["sessions"],
                "Session %r not found in list: %r" % (sid, listed["sessions"]),
            )
        finally:
            self.rpc.session.destroy(sid)

    def test_destroyed_session_not_in_list(self):
        """A destroyed session is removed from the session list."""
        created = self.rpc.session.create()
        sid = created["session"]
        self.rpc.session.destroy(sid)
        listed = self.rpc.session.list()
        self.assertNotIn(
            sid,
            listed["sessions"],
            "Destroyed session %r still in list: %r" % (sid, listed["sessions"]),
        )


class TestSessionDestroy(RPCTestCase):
    def test_destroy_returns_ok(self):
        """session.destroy() returns status ok."""
        created = self.rpc.session.create()
        sid = created["session"]
        result = self.rpc.session.destroy(sid)
        self._assert_ok(result)


class TestRequestGet(RPCTestCase):
    def test_get_returns_ok(self):
        """request.get() returns status ok."""
        result = self.rpc.request.get(_PLAIN_URL)
        self._assert_ok(result)
        self.assertIn("solution", result, "Missing 'solution' key")
        self._assert_solution(result["solution"])

    def test_get_solution_url(self):
        """solution.url reflects the final URL."""
        result = self.rpc.request.get(_PLAIN_URL)
        self.assertTrue(result["solution"]["url"], "Expected non-empty solution url")

    def test_get_solution_response(self):
        """solution.response contains non-empty HTML/text."""
        result = self.rpc.request.get(_PLAIN_URL)
        self.assertTrue(
            result["solution"]["response"], "Expected non-empty solution.response"
        )

    def test_get_solution_user_agent(self):
        """solution.userAgent is a non-empty string."""
        result = self.rpc.request.get(_PLAIN_URL)
        ua = result["solution"]["userAgent"]
        self.assertTrue(
            ua and isinstance(ua, string_types),
            "Expected non-empty string userAgent, got %r" % ua,
        )

    def test_get_with_session(self):
        """request.get() with an existing session_id succeeds."""
        created = self.rpc.session.create()
        sid = created["session"]
        try:
            result = self.rpc.request.get(_PLAIN_URL, session_id=sid)
            self._assert_ok(result)
            self._assert_solution(result["solution"])
        finally:
            self.rpc.session.destroy(sid)

    def test_get_return_only_cookies(self):
        """return_only_cookies=True omits the response body."""
        result = self.rpc.request.get(_PLAIN_URL, return_only_cookies=True)
        self._assert_ok(result)
        # When returnOnlyCookies is True, solution.response should be empty
        response_body = result["solution"].get("response", "")
        self.assertTrue(
            response_body == "" or response_body is None,
            "Expected empty response body with return_only_cookies=True, got: %r"
            % (response_body[:200] if response_body else response_body,),
        )

    def test_get_return_screenshot(self):
        """return_screenshot=True includes a Base64 screenshot."""
        result = self.rpc.request.get(_PLAIN_URL, return_screenshot=True)
        self._assert_ok(result)
        screenshot = result["solution"].get("screenshot")
        self.assertTrue(
            screenshot, "Expected non-empty screenshot with return_screenshot=True"
        )
        self.assertIsInstance(
            screenshot,
            string_types,
            "Expected screenshot to be a string, got %r" % type(screenshot),
        )

    def test_get_wait_in_seconds(self):
        """wait_in_seconds adds extra delay but still returns ok."""
        now = time.time()
        result = self.rpc.request.get(_PLAIN_URL, wait_in_seconds=1)
        self.assertGreaterEqual(
            time.time(),
            now + 1,
            "Expected at least 1 second delay with wait_in_seconds=1",
        )
        self._assert_ok(result)
        self._assert_solution(result["solution"])

    def test_get_disable_media(self):
        """disable_media=True still returns a valid response."""
        result = self.rpc.request.get(_PLAIN_URL, disable_media=True)
        self._assert_ok(result)
        self._assert_solution(result["solution"])

    def test_get_session_ttl_minutes(self):
        """session_ttl_minutes is passed and request succeeds."""
        result = self.rpc.request.get(_PLAIN_URL, session_ttl_minutes=30)
        self._assert_ok(result)
        self._assert_solution(result["solution"])

    def test_get_with_cookies(self):
        """Extra cookies are accepted without error."""
        cookies = [{"name": "test_cookie", "value": "hello"}]
        result = self.rpc.request.get(_PLAIN_URL, cookies=cookies)
        self._assert_ok(result)
        self._assert_solution(result["solution"])
        self.assertIn(
            "test_cookie=hello",
            result["solution"].get("response", ""),
            "Expected test_cookie in response when sent in request",
        )

    def test_get_with_max_timeout(self):
        """Custom max_timeout is accepted."""
        result = self.rpc.request.get(_PLAIN_URL, max_timeout=30000)
        self._assert_ok(result)
        self._assert_solution(result["solution"])


class TestRequestPost(RPCTestCase):
    def test_post_returns_ok(self):
        """request.post() returns status ok."""
        result = self.rpc.request.post(_PLAIN_POST_URL, data={"key": "value"})
        self._assert_ok(result)
        self.assertIn("solution", result)
        self._assert_solution(result["solution"])

    def test_post_with_dict_data(self):
        """request.post() with dict data URL-encodes it correctly."""
        result = self.rpc.request.post(
            _PLAIN_POST_URL, data={"foo": "bar", "baz": "qux"}
        )
        self._assert_ok(result)
        self._assert_solution(result["solution"])

    def test_post_with_string_data(self):
        """request.post() with a pre-encoded string passes it through."""
        result = self.rpc.request.post(_PLAIN_POST_URL, data="key=value&other=123")
        self._assert_ok(result)
        self._assert_solution(result["solution"])

    def test_post_no_data(self):
        """request.post() without data sends empty postData and succeeds."""
        result = self.rpc.request.post(_PLAIN_POST_URL)
        self._assert_ok(result)
        self._assert_solution(result["solution"])

    def test_post_return_only_cookies(self):
        """return_only_cookies=True omits response body in POST."""
        result = self.rpc.request.post(
            _PLAIN_POST_URL, data="x=1", return_only_cookies=True
        )
        self._assert_ok(result)
        response_body = result["solution"].get("response", "")
        self.assertTrue(
            response_body == "" or response_body is None,
            "Expected empty response body with return_only_cookies=True",
        )

    def test_post_disable_media(self):
        """disable_media=True still returns valid POST response."""
        result = self.rpc.request.post(_PLAIN_POST_URL, data="x=1", disable_media=True)
        self._assert_ok(result)
        self._assert_solution(result["solution"])


if __name__ == "__main__":
    unittest.main()
