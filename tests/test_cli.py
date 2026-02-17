# -*- coding: utf-8 -*-
"""Tests for the CLI tool."""

from __future__ import print_function

import os
import sys
import tempfile
import unittest

try:
    from unittest import mock
except ImportError:
    import mock  # Python 2 back-port

try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3

import cli
from tests.testconf import NO_CHALLENGE_SITES

FLARESOLVERR_URL = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191/v1")


class TestCLI(unittest.TestCase):
    """Test CLI functionality."""

    def test_basic_request(self):
        """Test basic GET request."""
        site = NO_CHALLENGE_SITES[0]

        # Capture stderr (metadata output)
        old_stderr = sys.stderr
        old_stdout = sys.stdout
        try:
            sys.stderr = StringIO()
            sys.stdout = StringIO()

            # Mock sys.argv
            with mock.patch.object(
                sys,
                "argv",
                ["flaresolverr-session", site["url"], "-f", FLARESOLVERR_URL],
            ):
                result = cli.main()

            stderr_output = sys.stderr.getvalue()
            stdout_output = sys.stdout.getvalue()
        finally:
            sys.stderr = old_stderr
            sys.stdout = old_stdout

        # Print stderr for debugging if test fails
        if result != 0:
            print("STDERR:", stderr_output, file=old_stderr)

        self.assertEqual(result, 0)
        self.assertIn("Status: 200", stderr_output)
        self.assertIn("FlareSolverr Metadata", stderr_output)

    def test_output_file(self):
        """Test writing output to file."""
        site = NO_CHALLENGE_SITES[0]

        # Create temporary file
        fd, temp_path = tempfile.mkstemp(suffix=".html")
        os.close(fd)

        try:
            old_stderr = sys.stderr
            try:
                sys.stderr = StringIO()

                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "flaresolverr-session",
                        site["url"],
                        "-f",
                        FLARESOLVERR_URL,
                        "-o",
                        temp_path,
                    ],
                ):
                    result = cli.main()

                stderr_output = sys.stderr.getvalue()
            finally:
                sys.stderr = old_stderr

            self.assertEqual(result, 0)
            self.assertIn("Response body written to:", stderr_output)

            # Check file contents
            with open(temp_path, "rb") as f:
                content = f.read()

            # Python 2/3 compatible string check
            if sys.version_info[0] >= 3:
                content_str = content.decode("utf-8")
            else:
                content_str = content

            for keyword in site["expected_keywords"]:
                self.assertIn(keyword.lower(), content_str.lower())

        finally:
            # Clean up temp file
            try:
                os.remove(temp_path)
            except:
                pass

    def test_method_argument(self):
        """Test specifying HTTP method."""
        site = NO_CHALLENGE_SITES[0]

        old_stderr = sys.stderr
        old_stdout = sys.stdout
        try:
            sys.stderr = StringIO()
            sys.stdout = StringIO()

            with mock.patch.object(
                sys,
                "argv",
                [
                    "flaresolverr-session",
                    site["url"],
                    "-f",
                    FLARESOLVERR_URL,
                    "-m",
                    "GET",
                ],
            ):
                result = cli.main()

            stderr_output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
            sys.stdout = old_stdout

        self.assertEqual(result, 0)
        self.assertIn("Status: 200", stderr_output)

    def test_environment_variable(self):
        """Test using FLARESOLVERR_URL environment variable."""
        site = NO_CHALLENGE_SITES[0]

        old_stderr = sys.stderr
        old_stdout = sys.stdout
        try:
            sys.stderr = StringIO()
            sys.stdout = StringIO()

            # Mock environment variable
            with mock.patch.dict(os.environ, {"FLARESOLVERR_URL": FLARESOLVERR_URL}):
                # Don't pass -f option, should use env var
                with mock.patch.object(
                    sys,
                    "argv",
                    ["flaresolverr-session", site["url"]],
                ):
                    result = cli.main()

            stderr_output = sys.stderr.getvalue()
            stdout_output = sys.stdout.getvalue()
        finally:
            sys.stderr = old_stderr
            sys.stdout = old_stdout

        self.assertEqual(result, 0)
        self.assertIn("Status: 200", stderr_output)
        self.assertIn("FlareSolverr Metadata", stderr_output)


if __name__ == "__main__":
    unittest.main()
