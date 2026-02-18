# -*- coding: utf-8 -*-

import json

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

import requests
from requests.structures import CaseInsensitiveDict

__title__ = "flaresolverr-session"
__description__ = "A requests.Session that proxies through a FlareSolverr instance."
__url__ = "https://github.com/Xavier-Lam/FlareSolverrSession"
__version__ = "0.2.0"
__author__ = "Xavier-Lam"
__author_email__ = "xavierlam7@hotmail.com"

__all__ = ["Session", "FlareSolverr", "Response", "FlareSolverrError",
           "FlareSolverrResponseError", "FlareSolverrCaptchaError",
           "FlareSolverrTimeoutError", "FlareSolverrUnsupportedMethodError",
           "__version__",]


class FlareSolverrError(requests.RequestException):
    """Base exception for FlareSolverr errors."""


class FlareSolverrResponseError(FlareSolverrError):
    """Raised when FlareSolverr returns a non-ok response.

    Attributes:
        message (str): The error message from FlareSolverr.
        response_data (dict or None): The original FlareSolverr response dict.
    """

    def __init__(self, message, response_data=None, **kwargs):
        super(FlareSolverrResponseError, self).__init__(message, **kwargs)
        self.message = message or ""
        self.response_data = response_data


class FlareSolverrCaptchaError(FlareSolverrResponseError):
    """Raised when a CAPTCHA was encountered but could not be solved."""


class FlareSolverrTimeoutError(FlareSolverrResponseError):
    """Raised when FlareSolverr timed out while solving the challenge."""


class FlareSolverrUnsupportedMethodError(FlareSolverrError):
    """Raised when an unsupported HTTP method or content type is used."""


class Session(requests.Session):
    """A ``requests.Session`` subclass that routes requests through
    FlareSolverr.

    The response objects are instances of
    :class:`flaresolverr_session.Response`, which carry additional
    FlareSolverr-specific attributes.

    Parameters:
        flaresolverr_url (str): The FlareSolverr API endpoint
            (e.g. ``"http://localhost:8191/v1"``).
        session_id (str or None): An optional FlareSolverr session id.
            When *None* a new session is automatically created.
        proxy (str, dict or None): A proxy specification.
            When a *str*, it is interpreted as a URL.
            When a *dict*, it should contain ``"url"`` and optionally
            ``"username"`` and ``"password"`` keys.
        timeout (int or None): ``maxTimeout`` in **milliseconds**
            passed to FlareSolverr.  Defaults to *60000* (60 s).
        session (requests.Session or None): An optional pre-configured
            session to use for API calls.

    .. note::

        Only ``GET`` and ``x-www-form-urlencoded`` ``POST`` requests
        are supported by FlareSolverr.  Calling unsupported methods or
        passing ``json`` data will raise
        :class:`FlareSolverrUnsupportedMethodError`.
    """

    DEFAULT_TIMEOUT = 60000

    _SUPPORTED_METHODS = ("GET", "POST")

    def __init__(self, flaresolverr_url, session_id=None, proxy=None,
                 timeout=None, session=None):
        super(Session, self).__init__()
        self._flaresolverr_url = flaresolverr_url
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._proxy = self._normalise_proxy(proxy)

        self._session_id = session_id
        self._api_session = session or requests.Session()
        self._session_created = False

    @property
    def session_id(self):
        """The FlareSolverr session identifier."""
        if not self._session_created:
            self._create_session()
        return self._session_id

    def request(self, method, url, **kwargs):
        """Send a request through FlareSolverr.

        Parameters:
            method (str): HTTP method (``"GET"`` or ``"POST"``).
            url (str): Target URL.
            **kwargs: Keyword arguments.  Recognised keys include
                ``params`` (URL query parameters), ``data`` (for POST),
                ``cookies``, ``timeout`` (FlareSolverr ``maxTimeout``
                in ms).  Standard ``requests`` parameters such as
                ``headers`` are accepted but ignored -- the headless
                browser manages its own headers and navigation.

        Returns:
            Response: A response built from the FlareSolverr solution,
            with extra ``flaresolverr_*`` attributes.

        Raises:
            FlareSolverrUnsupportedMethodError: If *method* is not
                ``GET`` or ``POST``, or if ``json`` data is passed.
            FlareSolverrResponseError: If FlareSolverr returns a
                non-ok status for any reason (challenge not solved,
                timeout, session error, etc.).  The original response
                dict is available on the exception's ``response``
                attribute.
            FlareSolverrCaptchaError: If a CAPTCHA was detected.
            FlareSolverrTimeoutError: If FlareSolverr timed out.
        """
        method = method.upper()
        if method not in self._SUPPORTED_METHODS:
            raise FlareSolverrUnsupportedMethodError(
                "FlareSolverr only supports GET and POST requests. "
                "Method '%s' is not supported." % method
            )

        if kwargs.get("json") is not None:
            raise FlareSolverrUnsupportedMethodError(
                "FlareSolverr only supports x-www-form-urlencoded "
                "POST requests. JSON POST is not supported."
            )

        payload = self._build_payload(method, url, **kwargs)
        try:
            resp_data = self.send(payload)
        except FlareSolverrResponseError as e:
            if "captcha" in e.message.lower():
                raise FlareSolverrCaptchaError(e.message, response_data=e.response_data)
            elif "timeout" in e.message.lower():
                raise FlareSolverrTimeoutError(e.message, response_data=e.response_data)
            raise
        return Response(resp_data)

    def close(self):
        """Destroy the FlareSolverr session and close both the API
        session and the inherited ``requests.Session``."""
        try:
            if self._session_created:
                self._destroy_session()
        finally:
            self._api_session.close()
            super(Session, self).close()

    def _build_payload(self, method, url, **kwargs):
        params = kwargs.get("params")
        if params:
            if isinstance(params, dict):
                encoded_params = urlencode(params)
                if "?" in url:
                    url = url + "&" + encoded_params
                else:
                    url = url + "?" + encoded_params

        cmd = "request.get" if method == "GET" else "request.post"
        payload = {
            "cmd": cmd,
            "url": url,
            "session": self.session_id,
            "maxTimeout": kwargs.get("timeout", self._timeout),
        }

        # POST data
        if method == "POST":
            data = kwargs.get("data")
            if data is not None:
                if isinstance(data, dict):
                    data = urlencode(data)
                elif not isinstance(data, str):
                    # Python 2 unicode handling
                    try:
                        if isinstance(data, unicode):  # noqa: F821
                            data = data.encode("utf-8")
                    except NameError:
                        pass
                    data = str(data)
                payload["postData"] = data

        # Optional cookies
        cookies = kwargs.get("cookies")
        if cookies:
            payload["cookies"] = cookies

        return payload

    @staticmethod
    def _normalise_proxy(proxy):
        if proxy is None:
            return None
        if isinstance(proxy, dict):
            return proxy
        return {"url": proxy}

    def send(self, payload):
        headers = {"Content-Type": "application/json"}
        resp = self._api_session.post(
            self._flaresolverr_url,
            headers=headers,
            data=json.dumps(payload),
        )
        data = resp.json()
        status = data.get("status", "")
        if status != "ok":
            raise FlareSolverrResponseError(
                data.get("message"), data, response=resp)
        return data

    def _create_session(self):
        payload = {
            "cmd": "sessions.create",
        }
        if self._session_id:
            payload["session"] = self._session_id
        if self._proxy:
            payload["proxy"] = self._proxy

        data = self.send(payload)

        self._session_id = data.get("session", self._session_id)
        self._session_created = True

    def _destroy_session(self):
        if not self._session_id:
            return

        payload = {
            "cmd": "sessions.destroy",
            "session": self._session_id,
        }
        try:
            self.send(payload)
        except Exception:
            return  # Best-effort cleanup

        self._session_created = False


class FlareSolverr(object):
    """
    Attributes:
        status (str): ``"ok"`` on success.
        message (str): Message from FlareSolverr (e.g.
            challenge status).
        user_agent (str): User-Agent used by the headless
            browser.
        start (int): Start timestamp (ms).
        end (int): End timestamp (ms).
        version (str): FlareSolverr server version.
    """

    def __init__(self, status="", message="", user_agent="",
                 start=0, end=0, version=""):
        self.status = status
        self.message = message
        self.user_agent = user_agent
        self.start = start
        self.end = end
        self.version = version

    def __repr__(self):
        return "FlareSolverr(status=%r, message=%r, version=%r)" % (
            self.status, self.message, self.version)


class Response(requests.Response):
    """
    Attributes:
        flaresolverr (FlareSolverr): FlareSolverr metadata
            associated with this response.
    """

    def __init__(self, flaresolverr_data):
        """Initialize from FlareSolverr JSON response."""
        super(Response, self).__init__()

        solution = flaresolverr_data.get("solution", {})

        self.status_code = solution.get("status", 200)
        self.url = solution.get("url", "")
        self.headers = CaseInsensitiveDict(solution.get("headers", {}))

        content = solution.get("response", "")
        if isinstance(content, bytes):
            self._content = content
        else:
            self._content = content.encode("utf-8")
        self.encoding = "utf-8"

        # Cookies
        for cookie in solution.get("cookies", []):
            self.cookies.set(
                cookie.get("name", ""),
                cookie.get("value", ""),
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )

        self.flaresolverr = FlareSolverr(
            status=flaresolverr_data.get("status", ""),
            message=flaresolverr_data.get("message", ""),
            user_agent=solution.get("userAgent", ""),
            start=flaresolverr_data.get("startTimestamp", 0),
            end=flaresolverr_data.get("endTimestamp", 0),
            version=flaresolverr_data.get("version", ""),
        )
