# -*- coding: utf-8 -*-

import unittest

from flaresolverr_rpc import RPC

# Python 2/3 compatible string type check
try:
    string_types = basestring  # Python 2
except NameError:
    string_types = str  # Python 3

# A publicly accessible URL that never returns a Cloudflare challenge
_PLAIN_URL = "https://httpbin.org/get"
_PLAIN_POST_URL = "https://httpbin.org/post"


def _assert_ok(response):
    """Assert that the FlareSolverr response envelope is successful.

    Parameters:
        response (dict): The response dict from FlareSolverr.
    """
    assert isinstance(response, dict), "Expected dict, got %r" % type(response)
    assert (
        response.get("status") == "ok"
    ), "Expected status 'ok', got %r (message: %r)" % (
        response.get("status"),
        response.get("message"),
    )
    assert "version" in response, "Missing 'version' key in response"
    assert "startTimestamp" in response, "Missing 'startTimestamp' key in response"
    assert "endTimestamp" in response, "Missing 'endTimestamp' key in response"


def _assert_solution(solution):
    """Assert that a solution dict has the required fields.

    Parameters:
        solution (dict): The solution dict from FlareSolverr response.
    """
    assert isinstance(solution, dict), "Expected solution dict, got %r" % type(solution)
    assert "url" in solution, "Missing 'url' in solution"
    assert "status" in solution, "Missing 'status' in solution"
    assert "userAgent" in solution, "Missing 'userAgent' in solution"
    assert "cookies" in solution, "Missing 'cookies' in solution"
    assert isinstance(
        solution["cookies"], list
    ), "Expected cookies to be a list, got %r" % type(solution["cookies"])


class RPCTestCase(unittest.TestCase):
    def setUp(self):
        self.rpc = RPC()


class TestSessionCreate(RPCTestCase):
    def test_create_returns_ok(self):
        """session.create() returns status ok."""
        result = self.rpc.session.create()
        _assert_ok(result)
        assert "session" in result, "Missing 'session' key in create response"
        # clean up
        self.rpc.session.destroy(result["session"])

    def test_create_with_explicit_id(self):
        """session.create(session_id=...) honours the requested id."""
        sid = "test-rpc-explicit-session"
        result = self.rpc.session.create(session_id=sid)
        _assert_ok(result)
        assert result["session"] == sid, "Expected session id %r, got %r" % (
            sid,
            result["session"],
        )
        # clean up
        self.rpc.session.destroy(sid)


class TestSessionList(RPCTestCase):
    def test_list_returns_ok(self):
        """session.list() returns status ok."""
        result = self.rpc.session.list()
        _assert_ok(result)
        assert "sessions" in result, "Missing 'sessions' key"
        assert isinstance(result["sessions"], list), "Expected sessions to be a list"

    def test_created_session_appears_in_list(self):
        """A created session appears in the session list."""
        created = self.rpc.session.create()
        sid = created["session"]
        try:
            listed = self.rpc.session.list()
            assert sid in listed["sessions"], "Session %r not found in list: %r" % (
                sid,
                listed["sessions"],
            )
        finally:
            self.rpc.session.destroy(sid)

    def test_destroyed_session_not_in_list(self):
        """A destroyed session is removed from the session list."""
        created = self.rpc.session.create()
        sid = created["session"]
        self.rpc.session.destroy(sid)
        listed = self.rpc.session.list()
        assert (
            sid not in listed["sessions"]
        ), "Destroyed session %r still in list: %r" % (sid, listed["sessions"])


class TestSessionDestroy(RPCTestCase):
    def test_destroy_returns_ok(self):
        """session.destroy() returns status ok."""
        created = self.rpc.session.create()
        sid = created["session"]
        result = self.rpc.session.destroy(sid)
        _assert_ok(result)


class TestRequestGet(RPCTestCase):
    def test_get_returns_ok(self):
        """request.get() returns status ok."""
        result = self.rpc.request.get(_PLAIN_URL)
        _assert_ok(result)
        assert "solution" in result, "Missing 'solution' key"
        _assert_solution(result["solution"])

    def test_get_solution_url(self):
        """solution.url reflects the final URL."""
        result = self.rpc.request.get(_PLAIN_URL)
        assert result["solution"]["url"], "Expected non-empty solution url"

    def test_get_solution_response(self):
        """solution.response contains non-empty HTML/text."""
        result = self.rpc.request.get(_PLAIN_URL)
        assert result["solution"]["response"], "Expected non-empty solution.response"

    def test_get_solution_user_agent(self):
        """solution.userAgent is a non-empty string."""
        result = self.rpc.request.get(_PLAIN_URL)
        ua = result["solution"]["userAgent"]
        assert ua and isinstance(ua, string_types), (
            "Expected non-empty string userAgent, got %r" % ua
        )

    def test_get_with_session(self):
        """request.get() with an existing session_id succeeds."""
        created = self.rpc.session.create()
        sid = created["session"]
        try:
            result = self.rpc.request.get(_PLAIN_URL, session_id=sid)
            _assert_ok(result)
            _assert_solution(result["solution"])
        finally:
            self.rpc.session.destroy(sid)

    def test_get_return_only_cookies(self):
        """return_only_cookies=True omits the response body."""
        result = self.rpc.request.get(_PLAIN_URL, return_only_cookies=True)
        _assert_ok(result)
        # When returnOnlyCookies is True, solution.response should be empty
        response_body = result["solution"].get("response", "")
        assert (
            response_body == "" or response_body is None
        ), "Expected empty response body with return_only_cookies=True, got: %r" % (
            response_body[:200] if response_body else response_body,
        )

    def test_get_return_screenshot(self):
        """return_screenshot=True includes a Base64 screenshot."""
        result = self.rpc.request.get(_PLAIN_URL, return_screenshot=True)
        _assert_ok(result)
        screenshot = result["solution"].get("screenshot")
        assert screenshot, "Expected non-empty screenshot with return_screenshot=True"
        assert isinstance(
            screenshot, string_types
        ), "Expected screenshot to be a string, got %r" % type(screenshot)

    def test_get_wait_in_seconds(self):
        """wait_in_seconds adds extra delay but still returns ok."""
        result = self.rpc.request.get(_PLAIN_URL, wait_in_seconds=2)
        _assert_ok(result)
        _assert_solution(result["solution"])

    def test_get_disable_media(self):
        """disable_media=True still returns a valid response."""
        result = self.rpc.request.get(_PLAIN_URL, disable_media=True)
        _assert_ok(result)
        _assert_solution(result["solution"])

    def test_get_session_ttl_minutes(self):
        """session_ttl_minutes is passed and request succeeds."""
        result = self.rpc.request.get(_PLAIN_URL, session_ttl_minutes=30)
        _assert_ok(result)
        _assert_solution(result["solution"])

    def test_get_with_cookies(self):
        """Extra cookies are accepted without error."""
        cookies = [{"name": "test_cookie", "value": "hello"}]
        result = self.rpc.request.get(_PLAIN_URL, cookies=cookies)
        _assert_ok(result)
        _assert_solution(result["solution"])

    def test_get_with_max_timeout(self):
        """Custom max_timeout is accepted."""
        result = self.rpc.request.get(_PLAIN_URL, max_timeout=30000)
        _assert_ok(result)
        _assert_solution(result["solution"])


class TestRequestPost(RPCTestCase):
    def test_post_returns_ok(self):
        """request.post() returns status ok."""
        result = self.rpc.request.post(_PLAIN_POST_URL, data={"key": "value"})
        _assert_ok(result)
        assert "solution" in result
        _assert_solution(result["solution"])

    def test_post_with_dict_data(self):
        """request.post() with dict data URL-encodes it correctly."""
        result = self.rpc.request.post(
            _PLAIN_POST_URL, data={"foo": "bar", "baz": "qux"}
        )
        _assert_ok(result)
        _assert_solution(result["solution"])

    def test_post_with_string_data(self):
        """request.post() with a pre-encoded string passes it through."""
        result = self.rpc.request.post(_PLAIN_POST_URL, data="key=value&other=123")
        _assert_ok(result)
        _assert_solution(result["solution"])

    def test_post_no_data(self):
        """request.post() without data sends empty postData and succeeds."""
        result = self.rpc.request.post(_PLAIN_POST_URL)
        _assert_ok(result)
        _assert_solution(result["solution"])

    def test_post_return_only_cookies(self):
        """return_only_cookies=True omits response body in POST."""
        result = self.rpc.request.post(
            _PLAIN_POST_URL, data="x=1", return_only_cookies=True
        )
        _assert_ok(result)
        response_body = result["solution"].get("response", "")
        assert (
            response_body == "" or response_body is None
        ), "Expected empty response body with return_only_cookies=True"

    def test_post_disable_media(self):
        """disable_media=True still returns valid POST response."""
        result = self.rpc.request.post(_PLAIN_POST_URL, data="x=1", disable_media=True)
        _assert_ok(result)
        _assert_solution(result["solution"])


if __name__ == "__main__":
    unittest.main()
