# FlareSolverr Session

[![PyPI version](https://badge.fury.io/py/flaresolverr-session.svg)](https://pypi.org/project/flaresolverr-session/)
[![CI](https://github.com/Xavier-Lam/FlareSolverrSession/actions/workflows/ci.yml/badge.svg)](https://github.com/Xavier-Lam/FlareSolverrSession/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Xavier-Lam/FlareSolverrSession/branch/master/graph/badge.svg)](https://codecov.io/gh/Xavier-Lam/FlareSolverrSession)

A [`requests.Session`](https://docs.python-requests.org/) that transparently routes all HTTP requests through a [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) instance, allowing you to bypass Cloudflare protection with a familiar Python API.

This project is not responsible for solving challenges itself, it only forwards requests to *FlareSolverr*. If *FlareSolverr* fails to solve a challenge, it will raise an exception. Any issues related to challenge solving should be reported to the *FlareSolverr* project.

## Installation

```bash
pip install flaresolverr-session
```

## Prerequisites

You need a running [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) instance. The quickest way is via Docker:

```bash
docker run -d --name=flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest
```

## Usage

### Basic Usage

```python
from flaresolverr_session import Session

with Session("http://localhost:8191/v1") as session:
    response = session.get("https://example.com")
    print(response.status_code)
    print(response.text)
```

It is recommended to set a persistent `session_id`.

```python
session = Session(
    "http://localhost:8191/v1",
    session_id="my-persistent-session",
)
```

### Command-Line Interface

After installation, you can use the `flaresolverr-session` command:

```bash
flaresolverr-session https://example.com -f http://127.0.0.1:8191/v1 -o output.html
```

If the FlareSolverr URL is not provided, it will look for the `FLARESOLVERR_URL` environment variable.

#### CLI Examples

```bash
# Use persistent session
flaresolverr-session https://example.com -s my-session -o output.html

# POST request
flaresolverr-session https://example.com -m POST -d "key=value&foo=bar" -o output.html
```

### Response Object
A `FlareSolverr` object is attached to the `response` as `response.flaresolverr`. It contains metadata about the request and challenge solving process returned by *FlareSolverr*.

| Attribute | Description |
|---|---|
| `flaresolverr.status` | `"ok"` on success |
| `flaresolverr.message` | Message from FlareSolverr (e.g. challenge status) |
| `flaresolverr.user_agent` | User-Agent used by FlareSolverr's browser |
| `flaresolverr.start` / `flaresolverr.end` | Request timestamps (ms) |
| `flaresolverr.version` | FlareSolverr server version |

### Exception Handling

| Exception | Description |
|---|---|
| `FlareSolverrError` | Base exception. Inherits from `requests.exceptions.RequestException`. |
| `FlareSolverrChallengeError` | Challenge could not be solved. |  
| `FlareSolverrCaptchaError` | CAPTCHA detected. Inherits from `FlareSolverrChallengeError`. |
| `FlareSolverrTimeoutError` | Request timed out. |
| `FlareSolverrSessionError` | Session creation/destruction failed. |
| `FlareSolverrUnsupportedMethodError` | Unsupported HTTP method or content type. |

## Limitations

- **Only GET and  `application/x-www-form-urlencoded` POST** are supported. Otherwise, it will raise `FlareSolverrUnsupportedMethodError`. 
- **Headers returned by FlareSolverr** may be empty for some sites, depending on the FlareSolverr version and configuration. Empty HTTP status will be regarded as `200`. See [FlareSolverr#1162](https://github.com/FlareSolverr/FlareSolverr/issues/1162).