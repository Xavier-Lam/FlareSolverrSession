# -*- coding: utf-8 -*-

import unittest
import warnings

try:
    from unittest import mock
except ImportError:
    import mock  # Python 2 back-port

import requests
from requests.adapters import HTTPAdapter

from flaresolverr_session import (
    Adapter,
    FlareSolverrResponseError,
)


def _make_response(status_code=200, text="", headers=None):
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = text.encode("utf-8")
    resp.encoding = "utf-8"
    if headers:
        resp.headers.update(headers)
    return resp


def _flaresolverr_solved_data(
    url="https://example.com/", cookies=None, user_agent="FlareSolverr-UA/1.0"
):
    if cookies is None:
        cookies = [
            {
                "name": "cf_clearance",
                "value": "abc123",
                "domain": ".example.com",
                "path": "/",
                "expiry": 1803056005,
                "secure": True,
            }
        ]
    return {
        "status": "ok",
        "message": "Challenge solved!",
        "solution": {
            "url": url,
            "status": 200,
            "headers": {},
            "response": "<html><body>OK</body></html>",
            "cookies": cookies,
            "userAgent": user_agent,
        },
        "startTimestamp": 1000,
        "endTimestamp": 2000,
        "version": "3.0.0",
    }


def _make_rpc():
    rpc = mock.MagicMock()
    rpc.request = mock.MagicMock()
    return rpc


class TestNoChallengePassthrough(unittest.TestCase):
    """When no challenge is detected the adapter returns the original
    response unmodified and does NOT call FlareSolverr."""

    def test_normal_response_passes_through(self):
        """A 200 response is returned as-is."""
        normal_resp = _make_response(200, "<html>OK</html>")
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.return_value = normal_resp

        adapter = Adapter(
            flaresolverr_url="http://localhost:8191/v1",
            base_adapter=mock_base,
        )

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            req = requests.Request("GET", "https://example.com").prepare()
            result = adapter.send(req)

        self.assertIs(result, normal_resp)
        self.assertEqual(mock_base.send.call_count, 1)

    def test_flaresolverr_not_contacted(self):
        """FlareSolverr RPC is never called when there is no challenge."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.return_value = _make_response(200, "<html>OK</html>")
        mock_rpc = _make_rpc()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            req = requests.Request("GET", "https://example.com").prepare()
            adapter.send(req)

        mock_rpc.request.get.assert_not_called()

    def test_403_without_cf_markers_passes_through(self):
        """A 403 without Cloudflare markers is returned unchanged."""
        resp = _make_response(403, "<html><title>Forbidden</title></html>")
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.return_value = resp

        adapter = Adapter(
            flaresolverr_url="http://localhost:8191/v1",
            base_adapter=mock_base,
        )

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            req = requests.Request("GET", "https://example.com").prepare()
            result = adapter.send(req)

        self.assertIs(result, resp)
        self.assertEqual(mock_base.send.call_count, 1)


class TestChallengeSolvedAdapter(unittest.TestCase):
    """Challenge is detected, FlareSolverr solves it, request retried."""

    def _setup(self, challenge_url=None, proxies=None):
        """Return (adapter, mock_base, mock_rpc) ready for a solve cycle."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "<html>Protected content</html>"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data()

        adapter = Adapter(
            rpc=mock_rpc,
            challenge_url=challenge_url,
            base_adapter=mock_base,
        )
        return adapter, mock_base, mock_rpc

    def test_challenge_solved_returns_success(self):
        """After solving, the second (retried) response is returned."""
        adapter, mock_base, mock_rpc = self._setup()

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            result = adapter.send(req)

        self.assertEqual(result.status_code, 200)
        self.assertIn("Protected content", result.text)
        self.assertEqual(mock_base.send.call_count, 2)
        self.assertEqual(mock_rpc.request.get.call_count, 1)

    def test_cookies_applied_on_retry(self):
        """cf_clearance cookie is present in the retry request."""
        adapter, mock_base, _ = self._setup()

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            adapter.send(req)

        retry_req = mock_base.send.call_args_list[1][0][0]
        self.assertIn("cf_clearance=abc123", retry_req.headers.get("Cookie", ""))

    def test_user_agent_applied_on_retry(self):
        """FlareSolverr's User-Agent is used in the retry request."""
        adapter, mock_base, mock_rpc = self._setup()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data(
            user_agent="TestBrowser/2.0"
        )

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            adapter.send(req)

        retry_req = mock_base.send.call_args_list[1][0][0]
        self.assertEqual(retry_req.headers["User-Agent"], "TestBrowser/2.0")

    def test_flaresolverr_receives_blocked_url(self):
        """Without challenge_url the blocked URL is sent to FlareSolverr."""
        adapter, _, mock_rpc = self._setup()

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/deep/page").prepare()
            adapter.send(req)

        call_kwargs = mock_rpc.request.get.call_args[1]
        self.assertEqual(call_kwargs["url"], "https://example.com/deep/page")

    def test_challenge_url_absolute_path(self):
        """challenge_url='/' is resolved against the blocked URL's domain."""
        adapter, _, mock_rpc = self._setup(challenge_url="/")

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/deep/page").prepare()
            adapter.send(req)

        call_kwargs = mock_rpc.request.get.call_args[1]
        self.assertEqual(call_kwargs["url"], "https://example.com/")

    def test_challenge_url_full(self):
        """A full challenge_url is sent to FlareSolverr as-is."""
        adapter, _, mock_rpc = self._setup(
            challenge_url="https://example.com/challenge"
        )

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            adapter.send(req)

        call_kwargs = mock_rpc.request.get.call_args[1]
        self.assertEqual(call_kwargs["url"], "https://example.com/challenge")

    def test_only_cf_clearance_cached(self):
        """Only the cf_clearance cookie is cached, others are ignored."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "OK"),
        ]
        cookies = [
            {
                "name": "cf_clearance",
                "value": "aaa",
                "domain": ".example.com",
                "path": "/",
            },
            {"name": "__cf_bm", "value": "bbb", "domain": ".example.com", "path": "/"},
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data(cookies=cookies)
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            adapter.send(req)

        retry_req = mock_base.send.call_args_list[1][0][0]
        cookie_header = retry_req.headers.get("Cookie", "")
        self.assertIn("cf_clearance=aaa", cookie_header)
        self.assertNotIn("__cf_bm", cookie_header)

    def test_proxy_forwarded_to_rpc(self):
        """Proxy URL is selected and forwarded to FlareSolverr."""
        adapter, mock_base, mock_rpc = self._setup()
        proxies = {"https": "http://user:pass@proxy:8080"}

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            adapter.send(req, proxies=proxies)

        call_kwargs = mock_rpc.request.get.call_args[1]
        self.assertIn("proxy", call_kwargs)
        # The proxy URL is passed as-is (with credentials embedded).
        self.assertIn("user:pass@proxy:8080", call_kwargs["proxy"]["url"])

    def test_no_proxy_not_forwarded(self):
        """When no proxies are given, proxy is not passed to RPC."""
        adapter, _, mock_rpc = self._setup()

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            adapter.send(req)

        call_kwargs = mock_rpc.request.get.call_args[1]
        self.assertNotIn("proxy", call_kwargs)


class TestChallengeNotSolved(unittest.TestCase):
    """FlareSolverr fails to solve the challenge — error propagates."""

    def test_flaresolverr_error_propagates(self):
        """FlareSolverrResponseError raised when challenge unsolved."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.return_value = _make_response(503, "challenge")
        adapter = Adapter(
            flaresolverr_url="http://localhost:8191/v1",
            base_adapter=mock_base,
        )

        error_data = {
            "status": "error",
            "message": "Challenge not solved",
            "solution": {},
            "startTimestamp": 0,
            "endTimestamp": 0,
            "version": "0.0.0",
        }
        mock_api_resp = mock.MagicMock()
        mock_api_resp.json.return_value = error_data

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=True
        ):
            with mock.patch.object(
                adapter._rpc._api_session, "post", return_value=mock_api_resp
            ):
                req = requests.Request("GET", "https://example.com/page").prepare()
                with self.assertRaises(FlareSolverrResponseError) as ctx:
                    adapter.send(req)
                self.assertIn("Challenge not solved", ctx.exception.message)

        self.assertEqual(mock_base.send.call_count, 1)


class TestCookieExpiry(unittest.TestCase):
    """Expired cookies trigger a new solve cycle."""

    def test_resolves_on_second_challenge(self):
        """When cached cookies expire, the adapter re-solves and succeeds."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "c1"),
            _make_response(200, "<html>OK 1</html>"),
            _make_response(503, "c2"),
            _make_response(200, "<html>OK 2</html>"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.side_effect = [
            _flaresolverr_solved_data(
                cookies=[
                    {
                        "name": "cf_clearance",
                        "value": "v1",
                        "domain": ".example.com",
                        "path": "/",
                    }
                ]
            ),
            _flaresolverr_solved_data(
                cookies=[
                    {
                        "name": "cf_clearance",
                        "value": "v2",
                        "domain": ".example.com",
                        "path": "/",
                    }
                ]
            ),
        ]
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, True],
        ):
            req1 = requests.Request("GET", "https://example.com/page").prepare()
            result1 = adapter.send(req1)
            self.assertEqual(result1.status_code, 200)

            req2 = requests.Request("GET", "https://example.com/page").prepare()
            result2 = adapter.send(req2)
            self.assertEqual(result2.status_code, 200)

        retry2_req = mock_base.send.call_args_list[3][0][0]
        self.assertIn("cf_clearance=v2", retry2_req.headers.get("Cookie", ""))
        self.assertEqual(mock_rpc.request.get.call_count, 2)

    def test_cached_cookies_used_for_subsequent_requests(self):
        """After solving once, subsequent requests carry the cookie."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "<html>OK 1</html>"),
            _make_response(200, "<html>OK 2</html>"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req1 = requests.Request("GET", "https://example.com/page1").prepare()
            adapter.send(req1)

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            req2 = requests.Request("GET", "https://example.com/page2").prepare()
            adapter.send(req2)

        second_req = mock_base.send.call_args_list[2][0][0]
        self.assertIn("cf_clearance=abc123", second_req.headers.get("Cookie", ""))


class TestChallengeURLResolution(unittest.TestCase):
    """Validate _get_challenge_url logic."""

    def test_none_returns_original(self):
        adapter = Adapter(
            flaresolverr_url="http://localhost:8191/v1", challenge_url=None
        )
        self.assertEqual(
            adapter._get_challenge_url("https://example.com/path?q=1"),
            "https://example.com/path?q=1",
        )

    def test_absolute_path(self):
        adapter = Adapter(
            flaresolverr_url="http://localhost:8191/v1", challenge_url="/"
        )
        self.assertEqual(
            adapter._get_challenge_url("https://example.com/path"),
            "https://example.com/",
        )

    def test_absolute_path_with_subpath(self):
        adapter = Adapter(
            flaresolverr_url="http://localhost:8191/v1", challenge_url="/challenge"
        )
        self.assertEqual(
            adapter._get_challenge_url("https://example.com:8443/path"),
            "https://example.com:8443/challenge",
        )

    def test_full_url(self):
        adapter = Adapter(
            flaresolverr_url="http://localhost:8191/v1",
            challenge_url="https://other.com/solve",
        )
        self.assertEqual(
            adapter._get_challenge_url("https://example.com/path"),
            "https://other.com/solve",
        )


class TestConstructorWarnings(unittest.TestCase):
    """Validate constructor parameter interactions."""

    def test_warns_when_both_rpc_and_url(self):
        """Warning emitted when both rpc and URL are supplied."""
        mock_rpc = _make_rpc()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Adapter(flaresolverr_url="http://localhost:8191/v1", rpc=mock_rpc)
        self.assertEqual(len(w), 1)
        self.assertIn("rpc", str(w[0].message))

    def test_rpc_used_when_both(self):
        """When both provided, the given RPC is used."""
        mock_rpc = _make_rpc()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            adapter = Adapter(flaresolverr_url="http://localhost:8191/v1", rpc=mock_rpc)
        self.assertIs(adapter._rpc, mock_rpc)

    def test_no_warning_with_url_only(self):
        """No warning when only flaresolverr_url is given."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Adapter(flaresolverr_url="http://localhost:8191/v1")
        self.assertEqual(len(w), 0)

    def test_no_warning_with_rpc_only(self):
        """No warning when only rpc is given."""
        mock_rpc = _make_rpc()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Adapter(rpc=mock_rpc)
        self.assertEqual(len(w), 0)

    def test_default_base_adapter_is_http_adapter(self):
        adapter = Adapter(flaresolverr_url="http://localhost:8191/v1")
        self.assertIsInstance(adapter._base_adapter, HTTPAdapter)

    def test_custom_base_adapter(self):
        custom = mock.MagicMock(spec=HTTPAdapter)
        adapter = Adapter(
            flaresolverr_url="http://localhost:8191/v1", base_adapter=custom
        )
        self.assertIs(adapter._base_adapter, custom)


class TestExistingCookiesPreserved(unittest.TestCase):
    """Pre-existing request cookies survive the CF cookie injection."""

    def test_existing_cookies_merged(self):
        """Pre-existing cookies are merged with CF cookies on retry."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "OK"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            req.headers["Cookie"] = "existing=value"
            adapter.send(req)

        retry_req = mock_base.send.call_args_list[1][0][0]
        cookie_header = retry_req.headers.get("Cookie", "")
        self.assertIn("existing=value", cookie_header)
        self.assertIn("cf_clearance=abc123", cookie_header)


class TestUserAgentPerSite(unittest.TestCase):
    """UA is cached per hostname and not leaked between sites."""

    def _solve_for(self, adapter, url, ua="UA/1.0"):
        """Drive one full challenge-solve cycle for *url*.

        Parameters:
            adapter (Adapter): The adapter under test.
            url (str): The URL to request.
            ua (str): User-Agent that FlareSolverr returns.
        """
        mock_base = adapter._base_adapter
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "OK"),
        ]
        adapter._rpc.request.get.return_value = _flaresolverr_solved_data(
            url=url, user_agent=ua
        )
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", url).prepare()
            adapter.send(req)

    def test_ua_cached_after_solve(self):
        """After solving, the UA is stored keyed by hostname."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_rpc = _make_rpc()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        self._solve_for(adapter, "https://example.com/", ua="SolvedUA/2.0")

        self.assertEqual(adapter._user_agents.get("example.com"), "SolvedUA/2.0")

    def test_ua_applied_on_retry(self):
        """The solved UA is applied to the retry request."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_rpc = _make_rpc()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        self._solve_for(adapter, "https://example.com/", ua="SolvedUA/2.0")

        retry_req = mock_base.send.call_args_list[1][0][0]
        self.assertEqual(retry_req.headers.get("User-Agent"), "SolvedUA/2.0")

    def test_ua_not_leaked_to_other_domain(self):
        """UA obtained for one domain is not applied to a different domain."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_rpc = _make_rpc()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        # Solve for example.com.
        self._solve_for(adapter, "https://example.com/", ua="ExampleUA/1.0")

        # Now send a plain request to other.com.
        mock_base.send.return_value = _make_response(200, "OK")
        mock_base.send.side_effect = None
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            req = requests.Request("GET", "https://other.com/").prepare()
            adapter.send(req)

        req_to_other = mock_base.send.call_args[0][0]
        # The User-Agent header should NOT be ExampleUA/1.0.
        self.assertNotEqual(req_to_other.headers.get("User-Agent"), "ExampleUA/1.0")

    def test_ua_applied_to_subsequent_non_challenge_requests(self):
        """Once cached, UA is applied to every request to that domain."""
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_rpc = _make_rpc()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        self._solve_for(adapter, "https://example.com/page1", ua="SolvedUA/3.0")

        # Subsequent request — no challenge.
        mock_base.send.return_value = _make_response(200, "OK")
        mock_base.send.side_effect = None
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            req = requests.Request("GET", "https://example.com/page2").prepare()
            adapter.send(req)

        last_req = mock_base.send.call_args[0][0]
        self.assertEqual(last_req.headers.get("User-Agent"), "SolvedUA/3.0")


if __name__ == "__main__":
    unittest.main()
