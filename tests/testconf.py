# -*- coding: utf-8 -*-
"""Configuration file for Flare Solverr session tests.

Add test entries to the lists below to cover additional sites.
Each entry is a dict with:
    - name (str): Test case name.
    - url (str): The target URL.
    - expected_keywords (list): Substrings expected in the response body.
    - expected_status (int): Expected HTTP status code (default 200).
    - expected_headers (dict): Header keys (lowercase) with expected
      substring values (or None to just assert presence).

The CHALLENGE_SITES list is for pages that present a Cloudflare (or
similar) challenge which FlareSolverr should solve.

The NO_CHALLENGE_SITES list is for pages that can be fetched without
encountering any challenge.

Note: FlareSolverr sometimes returns empty headers.
See https://github.com/FlareSolverr/FlareSolverr/issues/1162
"""

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
