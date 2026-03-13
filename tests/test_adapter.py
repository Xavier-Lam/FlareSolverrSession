# -*- coding: utf-8 -*-

import logging
import time
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
    url="https://example.com/", cookies=None, ua="FlareSolverr-UA/1.0"
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
            "userAgent": ua,
        },
        "startTimestamp": 1000,
        "endTimestamp": 2000,
        "version": "3.0.0",
    }


def _make_rpc():
    rpc = mock.MagicMock()
    rpc.request = mock.MagicMock()
    return rpc


class TestAdapter(unittest.TestCase):
    def _setup(self, challenge_url=None, cookies=None, ua="FlareSolverr-UA/1.0"):
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "<html>Protected content</html>"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data(
            ua=ua, cookies=cookies
        )
        adapter = Adapter(
            rpc=mock_rpc, challenge_url=challenge_url, base_adapter=mock_base
        )
        return adapter, mock_base, mock_rpc

    # ------------------------------------------------------------------
    # challenge
    # ------------------------------------------------------------------

    def test_no_challenge_passthrough(self):
        normal_resp = _make_response(200, "<html>OK</html>")
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.return_value = normal_resp
        mock_rpc = _make_rpc()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)

        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            req = requests.Request("GET", "https://example.com").prepare()
            result = adapter.send(req)

        self.assertIs(result, normal_resp)
        self.assertEqual(mock_base.send.call_count, 1)
        mock_rpc.request.get.assert_not_called()

    def test_challenge_solved(self):
        adapter, mock_base, mock_rpc = self._setup()
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            result = adapter.send(req)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_base.send.call_count, 2)
        self.assertEqual(mock_rpc.request.get.call_count, 1)
        retry_req = mock_base.send.call_args_list[1][0][0]
        self.assertIn("cf_clearance=abc123", retry_req.headers.get("Cookie", ""))
        self.assertEqual(retry_req.headers["User-Agent"], "FlareSolverr-UA/1.0")
        self.assertEqual(
            mock_rpc.request.get.call_args[1]["url"], "https://example.com/page"
        )

    def test_challenge_url_override(self):
        adapter_path, _, rpc_path = self._setup(challenge_url="/")
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter_path.send(
                requests.Request("GET", "https://example.com/deep/page").prepare()
            )
        self.assertEqual(
            rpc_path.request.get.call_args[1]["url"], "https://example.com/"
        )

        adapter_full, _, rpc_full = self._setup(
            challenge_url="https://example.com/challenge"
        )
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter_full.send(
                requests.Request("GET", "https://example.com/page").prepare()
            )
        self.assertEqual(
            rpc_full.request.get.call_args[1]["url"], "https://example.com/challenge"
        )

    # ------------------------------------------------------------------
    # cookies
    # ------------------------------------------------------------------

    def test_cookie_request(self):
        cookies = [
            {
                "name": "cf_clearance",
                "value": "aaa",
                "domain": ".example.com",
                "path": "/",
            },
            {
                "name": "__cf_bm",
                "value": "bbb",
                "domain": ".example.com",
                "path": "/",
            },
        ]
        adapter, mock_base, _ = self._setup(cookies=cookies)
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            req = requests.Request("GET", "https://example.com/page").prepare()
            req.headers["Cookie"] = "existing=value"
            adapter.send(req)
        cookie_header = mock_base.send.call_args_list[1][0][0].headers.get("Cookie", "")
        self.assertIn("cf_clearance=aaa", cookie_header)
        self.assertIn("existing=value", cookie_header)
        self.assertNotIn("__cf_bm", cookie_header)

    def test_cookie_expiry(self):
        past_time = int(time.time()) - 3600
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "OK"),
            _make_response(200, "subsequent"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data(
            cookies=[
                {
                    "name": "cf_clearance",
                    "value": "expired_val",
                    "domain": ".example.com",
                    "path": "/",
                    "expiry": past_time,
                }
            ]
        )
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(requests.Request("GET", "https://example.com/page").prepare())
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            adapter.send(requests.Request("GET", "https://example.com/page2").prepare())
        self.assertNotIn(
            "cf_clearance",
            mock_base.send.call_args_list[2][0][0].headers.get("Cookie", ""),
        )

        future_time = int(time.time()) + 7200
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "OK"),
            _make_response(200, "subsequent"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data(
            cookies=[
                {
                    "name": "cf_clearance",
                    "value": "fresh_val",
                    "domain": ".example.com",
                    "path": "/",
                    "expiry": future_time,
                }
            ]
        )
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(requests.Request("GET", "https://example.com/page").prepare())
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            adapter.send(requests.Request("GET", "https://example.com/page2").prepare())
        self.assertIn(
            "cf_clearance=fresh_val",
            mock_base.send.call_args_list[2][0][0].headers.get("Cookie", ""),
        )

    def test_cookie_caching_and_re_solve(self):
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "OK 1"),
            _make_response(200, "OK 2"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(requests.Request("GET", "https://example.com/page1").prepare())
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            adapter.send(requests.Request("GET", "https://example.com/page2").prepare())
        self.assertIn(
            "cf_clearance=abc123",
            mock_base.send.call_args_list[2][0][0].headers.get("Cookie", ""),
        )

        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "c1"),
            _make_response(200, "OK 1"),
            _make_response(503, "c2"),
            _make_response(200, "OK 2"),
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
            side_effect=[True, False, True, False],
        ):
            r1 = adapter.send(
                requests.Request("GET", "https://example.com/page").prepare()
            )
            r2 = adapter.send(
                requests.Request("GET", "https://example.com/page").prepare()
            )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertIn(
            "cf_clearance=v2",
            mock_base.send.call_args_list[3][0][0].headers.get("Cookie", ""),
        )
        self.assertEqual(mock_rpc.request.get.call_count, 2)

    def _setup_solve(
        self, request_url, cookie_value="root_val", cookie_domain=".example.com"
    ):
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "OK"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data(
            cookies=[
                {
                    "name": "cf_clearance",
                    "value": cookie_value,
                    "domain": cookie_domain,
                    "path": "/secret",
                    "secure": True,
                }
            ]
        )
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(requests.Request("GET", request_url).prepare())
        return adapter, mock_base

    def test_cookie_root_domain_storage(self):
        def create_cookies(cookie_value):
            return [
                {
                    "name": "cf_clearance",
                    "value": cookie_value,
                    "domain": ".example.com",
                    "path": "/secret",
                    "secure": True,
                }
            ]

        adapter, mock_base, _ = self._setup()
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(
                requests.Request("GET", "https://www.example.com/page").prepare()
            )
        # Cookies keyed by root domain, not exact hostname
        self.assertIn("example.com", adapter._cf_cookies)
        self.assertNotIn("www.example.com", adapter._cf_cookies)

        # Solve for root domain; cookie applies to subdomain requests
        adapter, mock_base, _ = self._setup(cookies=create_cookies("zone"))
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(
                requests.Request("GET", "https://www.example.com/page").prepare()
            )
        self.assertIn(
            "cf_clearance=zone",
            mock_base.send.call_args[0][0].headers.get("Cookie", ""),
        )

        # Solve for subdomain; cookie applies to root domain requests
        adapter, mock_base, _ = self._setup(cookies=create_cookies("www"))
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(requests.Request("GET", "https://www.example.com/").prepare())
        mock_base.send.side_effect = None
        mock_base.send.return_value = _make_response(200, "root")
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            adapter.send(requests.Request("GET", "https://example.com/page").prepare())
        self.assertIn(
            "cf_clearance=www",
            mock_base.send.call_args[0][0].headers.get("Cookie", ""),
        )

    # ------------------------------------------------------------------
    # user agent
    # ------------------------------------------------------------------

    def test_ua_cached_and_applied(self):
        adapter, mock_base, mock_rpc = self._setup(ua="SolvedUA/2.0")
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(requests.Request("GET", "https://example.com/").prepare())
        self.assertEqual(adapter._user_agents.get("example.com"), "SolvedUA/2.0")
        self.assertEqual(
            mock_base.send.call_args_list[1][0][0].headers.get("User-Agent"),
            "SolvedUA/2.0",
        )

        mock_base.send.return_value = _make_response(200, "OK")
        mock_base.send.side_effect = None
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            adapter.send(requests.Request("GET", "https://example.com/page2").prepare())
        self.assertEqual(
            mock_base.send.call_args[0][0].headers.get("User-Agent"), "SolvedUA/2.0"
        )

    def test_ua_not_leaked_to_other_domain(self):
        adapter, mock_base, mock_rpc = self._setup(ua="UA/1.0")
        mock_base.send.return_value = _make_response(200, "OK")
        mock_base.send.side_effect = None
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            adapter.send(requests.Request("GET", "https://other.com/").prepare())
        self.assertNotEqual(
            mock_base.send.call_args[0][0].headers.get("User-Agent"), "UA/1.0"
        )

    # ------------------------------------------------------------------
    # proxy
    # ------------------------------------------------------------------

    def test_proxy(self):
        adapter, _, rpc = self._setup()
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(
                requests.Request("GET", "https://example.com/page").prepare(),
                proxies={"https": "http://user:pass@proxy:8080"},
            )
        call_kwargs = rpc.request.get.call_args[1]
        self.assertIn("proxy", call_kwargs)
        self.assertIn("user:pass@proxy:8080", call_kwargs["proxy"]["url"])

        adapter, _, rpc = self._setup()
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(requests.Request("GET", "https://example.com/page").prepare())
        self.assertNotIn("proxy", rpc.request.get.call_args[1])

    # ------------------------------------------------------------------
    # exception
    # ------------------------------------------------------------------

    def test_error_propagates(self):
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.return_value = _make_response(503, "challenge")
        adapter = Adapter(
            flaresolverr_url="http://localhost:8191/v1", base_adapter=mock_base
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
                with self.assertRaises(FlareSolverrResponseError) as ctx:
                    adapter.send(
                        requests.Request("GET", "https://example.com/page").prepare()
                    )
        self.assertIn("Challenge not solved", ctx.exception.message)


class TestAdapterLogging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestAdapterLogging, cls).setUpClass()
        logger = logging.getLogger("flaresolverr_session.adapter")
        logger.setLevel(logging.DEBUG)
        cls._log_handler = MockLoggingHandler(level=logging.DEBUG)
        logger.addHandler(cls._log_handler)
        cls._log_messages = cls._log_handler.messages

    def setUp(self):
        super(TestAdapterLogging, self).setUp()
        self._log_handler.reset()

    def _make_adapter_with_mocks(self):
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(200, "OK"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)
        return adapter, mock_base, mock_rpc

    def test_logging(self):
        # Debug log on plain request
        adapter, _, _ = self._make_adapter_with_mocks()
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge", return_value=False
        ):
            adapter.send(requests.Request("GET", "https://example.com/page").prepare())
        self.assertEqual(len(self._log_messages["debug"]), 1)
        self.assertIn("https://example.com/page", self._log_messages["debug"][0])
        self.assertIn("GET", self._log_messages["debug"][0])
        self.assertIn("receive", self._log_messages["debug"][0].lower())

        self._log_handler.reset()
        # Debug logs on challenge detected and solved
        adapter, _, _ = self._make_adapter_with_mocks()
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, False],
        ):
            adapter.send(requests.Request("GET", "https://example.com/page").prepare())
        self.assertEqual(len(self._log_messages["debug"]), 3)
        self.assertIn("detect", self._log_messages["debug"][1].lower())
        self.assertIn("solve", self._log_messages["debug"][2].lower())

        self._log_handler.reset()
        # Warning log when retry response is still a challenge
        mock_base = mock.MagicMock(spec=HTTPAdapter)
        mock_base.send.side_effect = [
            _make_response(503, "challenge"),
            _make_response(503, "still challenged"),
        ]
        mock_rpc = _make_rpc()
        mock_rpc.request.get.return_value = _flaresolverr_solved_data()
        adapter = Adapter(rpc=mock_rpc, base_adapter=mock_base)
        with mock.patch(
            "flaresolverr_session.adapter.is_cloudflare_challenge",
            side_effect=[True, True],
        ):
            adapter.send(requests.Request("GET", "https://example.com/page").prepare())
        self.assertEqual(len(self._log_messages["debug"]), 2)
        self.assertIn("detect", self._log_messages["debug"][1].lower())
        self.assertEqual(len(self._log_messages["warning"]), 1)
        self.assertIn("still", self._log_messages["warning"][0].lower())


class MockLoggingHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        self.messages = {
            "debug": [],
            "info": [],
            "warning": [],
            "error": [],
            "critical": [],
        }
        super(MockLoggingHandler, self).__init__(*args, **kwargs)

    def emit(self, record):
        try:
            self.messages[record.levelname.lower()].append(record.getMessage())
        except Exception:
            self.handleError(record)

    def reset(self):
        self.acquire()
        try:
            for message_list in self.messages.values():
                del message_list[:]
        finally:
            self.release()


if __name__ == "__main__":
    unittest.main()
