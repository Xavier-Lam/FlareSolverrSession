# FlareSolverr Session

[![PyPI version](https://badge.fury.io/py/flaresolverr-session.svg)](https://pypi.org/project/flaresolverr-session/)
[![CI](https://github.com/Xavier-Lam/FlareSolverrSession/actions/workflows/ci.yml/badge.svg)](https://github.com/Xavier-Lam/FlareSolverrSession/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Xavier-Lam/FlareSolverrSession/branch/master/graph/badge.svg)](https://codecov.io/gh/Xavier-Lam/FlareSolverrSession)

A [`requests.Session`](https://docs.python-requests.org/) that transparently routes all HTTP requests through a [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) instance, allowing you to bypass Cloudflare protection with a familiar Python API.

The project ships with a RPC client for direct access to the FlareSolverr JSON API, and a command-line interface (CLI) for quick requests and session management.

This project is not responsible for solving challenges itself, it only forwards requests to *FlareSolverr*. If *FlareSolverr* fails to solve a challenge, it will raise an exception. Any issues related to challenge solving should be reported to the *FlareSolverr* project.


## Installation

```bash
pip install flaresolverr-session
```

or

```bash
pip install flaresolverr-cli
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

#### Response Object
A `FlareSolverr` object is attached to the `response` as `response.flaresolverr`. It contains metadata about the request and challenge solving process returned by *FlareSolverr*.

| Attribute | Description |
|---|---|
| `flaresolverr.status` | `"ok"` on success |
| `flaresolverr.message` | Message from FlareSolverr (e.g. challenge status) |
| `flaresolverr.user_agent` | User-Agent used by FlareSolverr's browser |
| `flaresolverr.start` / `flaresolverr.end` | Request timestamps (ms) |
| `flaresolverr.version` | FlareSolverr server version |

#### Exception Handling
All exceptions defined in the module based on `FlareSolverrError`, which inherits from `requests.RequestException`. The inheritance hierarchy is as follows:

    requests.RequestException
    └── FlareSolverrError
        ├── FlareSolverrResponseError
        │   ├── FlareSolverrCaptchaError
        │   └── FlareSolverrTimeoutError
        └── FlareSolverrUnsupportedMethodError


| Exception | Description |
|---|---|
| `FlareSolverrResponseError` | FlareSolverr returned an error response. The response dict is available as `response_data` attribute. |
| `FlareSolverrCaptchaError` | CAPTCHA detected. |
| `FlareSolverrTimeoutError` | Request timed out. |
| `FlareSolverrUnsupportedMethodError` | Unsupported HTTP method or content type. |

### Command-Line Interface

After installation, you can use the `flaresolverr-cli` command. It is a convenient CLI tool to send HTTP requests through FlareSolverr and manage sessions.

It will output json response from FlareSolverr. If the FlareSolverr URL is not provided via `-f`, it will use the `FLARESOLVERR_URL` environment variable (defaulting to `http://localhost:8191/v1`).

#### Sending requests

The `request` command is the default — you can omit the word `request`:

```bash
flaresolverr-cli https://example.com -o output.html

# GET with a custom FlareSolverr URL
flaresolverr-cli -f http://localhost:8191/v1 https://example.com

# POST with form data (data implies POST)
flaresolverr-cli https://example.com -d "key=value&foo=bar"
```

#### Managing sessions

```bash
# Create a session (auto-generated name)
flaresolverr-cli -f http://localhost:8191/v1 session create my-session

# List all active sessions
flaresolverr-cli session list

# Destroy a session
flaresolverr-cli session destroy my-session
```

### RPC Tool

The `flaresolverr_rpc` module provides a programmatic interface to the FlareSolverr JSON API, useful when you need low-level access to the raw API responses.

```python
from flaresolverr_rpc import RPC

with RPC("http://localhost:8191/v1") as rpc:
    # Session management
    rpc.session.create(session_id="my-session", proxy="http://proxy:8080")
    sessions = rpc.session.list()
    print(sessions["sessions"])

    # HTTP requests
    result = rpc.request.get("https://example.com", session_id="my-session")
    print(result["solution"]["url"])
    print(result["solution"]["response"])  # HTML body

    result = rpc.request.post(
        "https://example.com",
        data="key=value",
        session_id="my-session",
    )

    # Cleanup
    rpc.session.destroy("my-session")
```

All methods return the raw JSON response dict from FlareSolverr.


## Limitations

- **Only GET and  `application/x-www-form-urlencoded` POST** are supported. Otherwise, it will raise `FlareSolverrUnsupportedMethodError`. 
- **Headers returned by FlareSolverr** may be empty for some sites, depending on the FlareSolverr version and configuration. Empty HTTP status will be regarded as `200`. See [FlareSolverr#1162](https://github.com/FlareSolverr/FlareSolverr/issues/1162).