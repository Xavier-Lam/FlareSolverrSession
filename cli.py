#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Command-line interface for FlareSolverr Session."""

from __future__ import print_function

import argparse
import os
import sys

from flaresolverr_session import Session


def main():
    """Run the CLI."""
    parser = argparse.ArgumentParser(
        description="Make HTTP requests through FlareSolverr",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  flaresolverr-session https://example.com
  flaresolverr-session https://example.com -f http://localhost:8191/v1
  flaresolverr-session https://example.com -s my-session -o output.html
  flaresolverr-session https://example.com --proxy http://proxy:8080
        """,
    )

    parser.add_argument(
        "url",
        help="URL to request",
    )

    parser.add_argument(
        "-f",
        "--flaresolverr",
        dest="flaresolverr_url",
        default=os.environ.get("FLARESOLVERR_URL", "http://localhost:8191/v1"),
        help="FlareSolverr API endpoint (default: FLARESOLVERR_URL env var or http://localhost:8191/v1)",
    )

    parser.add_argument(
        "-s",
        "--session-id",
        dest="session_id",
        help="FlareSolverr session ID (default: auto-generated)",
    )

    parser.add_argument(
        "--proxy",
        help="Proxy URL (e.g., http://proxy:8080)",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        help="Request timeout in milliseconds (default: 60000)",
    )

    parser.add_argument(
        "-o",
        "--output",
        dest="output_file",
        help="Write response body to file",
    )

    parser.add_argument(
        "-m",
        "--method",
        default="GET",
        choices=["GET", "POST"],
        help="HTTP method (default: GET)",
    )

    parser.add_argument(
        "-d",
        "--data",
        help="POST data (x-www-form-urlencoded)",
    )

    args = parser.parse_args()

    # Build session kwargs
    session_kwargs = {
        "flaresolverr_url": args.flaresolverr_url,
    }

    if args.session_id:
        session_kwargs["session_id"] = args.session_id

    if args.proxy:
        session_kwargs["proxy"] = args.proxy

    if args.timeout:
        session_kwargs["timeout"] = args.timeout

    # Build request kwargs
    request_kwargs = {}
    if args.data:
        request_kwargs["data"] = args.data

    try:
        with Session(**session_kwargs) as session:
            print("Requesting %s..." % args.url, file=sys.stderr)
            response = session.request(args.method, args.url, **request_kwargs)

            # Print metadata to stderr
            print("\n--- Response ---", file=sys.stderr)
            print("Status: %d" % response.status_code, file=sys.stderr)
            print("URL: %s" % response.url, file=sys.stderr)

            print("\n--- Headers ---", file=sys.stderr)
            for key, value in response.headers.items():
                print("%s: %s" % (key, value), file=sys.stderr)

            print("\n--- Cookies ---", file=sys.stderr)
            for cookie in response.cookies:
                print("%s=%s" % (cookie.name, cookie.value), file=sys.stderr)

            print("\n--- FlareSolverr Metadata ---", file=sys.stderr)
            print("Status: %s" % response.flaresolverr.status, file=sys.stderr)
            print("Message: %s" % response.flaresolverr.message, file=sys.stderr)
            print("User-Agent: %s" % response.flaresolverr.user_agent, file=sys.stderr)
            print("Version: %s" % response.flaresolverr.version, file=sys.stderr)
            print(
                "Duration: %d ms"
                % (response.flaresolverr.end - response.flaresolverr.start),
                file=sys.stderr,
            )

            # Write output
            if args.output_file:
                with open(args.output_file, "wb") as f:
                    f.write(response.content)
                print(
                    "\nResponse body written to: %s" % args.output_file,
                    file=sys.stderr,
                )

            return 0

    except Exception as e:
        print("Error: %s" % str(e), file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main())
