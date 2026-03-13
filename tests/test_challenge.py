# -*- coding: utf-8 -*-

import unittest

from .test_rpc import RPCTestCase


# -----------------------------------------------------------------------
# Sites that present a challenge (FlareSolverr should solve them)
# -----------------------------------------------------------------------
CHALLENGE_SITES = [
    {
        "name": "scrapingcourse",
        "url": "https://www.scrapingcourse.com/cloudflare-challenge",
        "expected_keywords": ["You bypassed the Cloudflare challenge"],
        "expected_status": 200,
    },
]

# -----------------------------------------------------------------------
# Sites that do NOT present a challenge (plain fetch)
# -----------------------------------------------------------------------
NO_CHALLENGE_SITES = [
    {
        "name": "google",
        "url": "https://www.google.com/",
        "expected_keywords": ["google"],
        "expected_status": 200,
        # Comment out headers - FlareSolverr may return empty headers
        # "expected_headers": {"content-type": "text/html"},
    },
]


class ChallengeTestCase(RPCTestCase):

    def _assert_site_solution(self, result, entry):
        self._assert_ok(result)
        solution = result.get("solution", {})
        self._assert_solution(solution)

        expected_status = entry.get("expected_status", 200)
        self.assertEqual(
            solution.get("status"),
            expected_status,
            "Expected HTTP status %d, got %d"
            % (expected_status, solution.get("status")),
        )

        body = solution.get("response", "").lower()
        for kw in entry.get("expected_keywords", []):
            self.assertIn(
                kw.lower(),
                body,
                "Expected keyword %r not found in response body" % kw,
            )

        # Soft header assertions – FlareSolverr may return empty headers.
        # See https://github.com/FlareSolverr/FlareSolverr/issues/1162
        headers = {k.lower(): v for k, v in solution.get("headers", {}).items()}
        for header, expected_value in entry.get("expected_headers", {}).items():
            actual_value = headers.get(header.lower())
            if actual_value and expected_value is not None:
                self.assertIn(
                    expected_value.lower(),
                    actual_value.lower(),
                    "Header %r: expected %r in %r"
                    % (header, expected_value, actual_value),
                )


class TestChallengeSites(ChallengeTestCase):
    pass


class TestNoChallengeSites(ChallengeTestCase):
    pass


def _make_challenge_site_test(entry):
    def test(self):
        result = self.rpc.request.get(entry["url"])
        self._assert_site_solution(result, entry)
        self.assertIn("challenge solved", result.get("message", "").lower())

    return test


def _make_no_challenge_site_test(entry):
    def test(self):
        result = self.rpc.request.get(entry["url"])
        self._assert_site_solution(result, entry)
        self.assertNotIn("challenge solved", result.get("message", "").lower())

    return test


for _entry in CHALLENGE_SITES:
    setattr(
        TestChallengeSites,
        "test_challenge_%s" % _entry["name"],
        _make_challenge_site_test(_entry),
    )


for _entry in NO_CHALLENGE_SITES:
    setattr(
        TestNoChallengeSites,
        "test_no_challenge_%s" % _entry["name"],
        _make_no_challenge_site_test(_entry),
    )


if __name__ == "__main__":
    unittest.main()
