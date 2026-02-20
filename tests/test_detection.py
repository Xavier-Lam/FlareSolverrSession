# -*- coding: utf-8 -*-

import glob
import io
import os
import unittest

try:
    import http.client as http_client
except ImportError:
    import httplib as http_client  # Python 2

from requests import Response
from requests.structures import CaseInsensitiveDict

from flaresolverr_session.detection import is_cloudflare_challenge

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_POSITIVE_DIR = os.path.join(_DATA_DIR, "challenge_positive")
_NEGATIVE_DIR = os.path.join(_DATA_DIR, "challenge_negative")


class _FakeSocket(object):
    def __init__(self, data):
        self._file = io.BytesIO(data)

    def makefile(self, *args, **kwargs):
        return self._file


def response_from_raw(raw):
    sock = _FakeSocket(raw)
    http_resp = http_client.HTTPResponse(sock)
    http_resp.begin()

    resp = Response()
    resp.status_code = http_resp.status
    resp.reason = http_resp.reason
    resp.headers = CaseInsensitiveDict(http_resp.getheaders())
    resp._content = http_resp.read()
    resp.encoding = "utf-8"
    resp.raw = http_resp
    return resp


def _load_response(path):
    with open(path, "rb") as fh:
        return response_from_raw(fh.read())


class TestChallengeDetectionPositive(unittest.TestCase):
    pass


class TestChallengeDetectionNegative(unittest.TestCase):
    pass


def _make_positive_test(path):
    def test(self):
        resp = _load_response(path)
        self.assertTrue(
            is_cloudflare_challenge(resp),
            "Expected challenge detection for: %s" % os.path.basename(path),
        )

    test.__doc__ = "Positive challenge: %s" % os.path.basename(path)
    return test


def _make_negative_test(path):
    def test(self):
        resp = _load_response(path)
        self.assertFalse(
            is_cloudflare_challenge(resp),
            "Incorrectly detected challenge for: %s" % os.path.basename(path),
        )

    test.__doc__ = "Negative challenge: %s" % os.path.basename(path)
    return test


for _path in sorted(glob.glob(os.path.join(_POSITIVE_DIR, "*.html"))):
    _name = "test_" + os.path.splitext(os.path.basename(_path))[0]
    setattr(TestChallengeDetectionPositive, _name, _make_positive_test(_path))

for _path in sorted(glob.glob(os.path.join(_NEGATIVE_DIR, "*.html"))):
    _name = "test_" + os.path.splitext(os.path.basename(_path))[0]
    setattr(TestChallengeDetectionNegative, _name, _make_negative_test(_path))


if __name__ == "__main__":
    unittest.main()
