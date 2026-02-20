# FlareSolverr Session

[![PyPI version](https://badge.fury.io/py/flaresolverr-session.svg)](https://pypi.org/project/flaresolverr-session/)
[![CI](https://github.com/Xavier-Lam/FlareSolverrSession/actions/workflows/ci.yml/badge.svg)](https://github.com/Xavier-Lam/FlareSolverrSession/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Xavier-Lam/FlareSolverrSession/branch/master/graph/badge.svg)](https://codecov.io/gh/Xavier-Lam/FlareSolverrSession)

A [`requests.Session`](https://docs.python-requests.org/) that transparently routes all HTTP requests through a [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) instance, allowing you to bypass Cloudflare protection with a familiar Python API.

The package also provides a more powerful [Adapter](#adapter) to handle complex requests if the `Session` is not sufficient.

The project ships with a command-line interface (CLI) for requests and session management, and an RPC client for direct access to the FlareSolverr JSON API.

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
A `FlareSolverr` metadata object is attached to the `response` as `response.flaresolverr`. It contains details about the request and the challenge solving process returned by *FlareSolverr*.

| Attribute | Description |
|---|---|
| `flaresolverr.status` | `"ok"` on success |
| `flaresolverr.message` | Message from FlareSolverr (e.g. challenge status) |
| `flaresolverr.user_agent` | User-Agent used by FlareSolverr's browser |
| `flaresolverr.start` / `flaresolverr.end` | Request timestamps (ms) |
| `flaresolverr.version` | FlareSolverr server version |

#### Exception Handling
If `FlareSolverr` returns an error response, the session will raise a `FlareSolverrResponseError` exception.

All exceptions defined in the module are based on `FlareSolverrError`, which inherits from `requests.RequestException`. The hierarchy is as follows:

    requests.RequestException
    └── FlareSolverrError
        ├── FlareSolverrResponseError
        │   └── FlareSolverrChallengeError
        └── FlareSolverrUnsupportedMethodError

Exception Details:

| Exception | Description |
|---|---|
| `FlareSolverrResponseError` | FlareSolverr returned an error response. The response dict is available as `response_data` attribute. |
| `FlareSolverrChallengeError` | Challenge solving failed, raised only in `Session`. |
| `FlareSolverrUnsupportedMethodError` | Unsupported HTTP method or content type. |

#### Limitations

- **Only GET and  `application/x-www-form-urlencoded` POST** are supported. Otherwise, it will raise `FlareSolverrUnsupportedMethodError`. 
- **Headers returned by FlareSolverr may be empty** for some sites, depending on the FlareSolverr version and configuration. An empty HTTP status will be treated as `200`. See [FlareSolverr#1162](https://github.com/FlareSolverr/FlareSolverr/issues/1162).

> If you need more control over the requests or want to use unsupported methods/content types, consider using the [Adapter](#adapter) instead.

### Command-Line Interface

After installation, you can use the `flaresolverr-cli` command. It is a convenient CLI tool to send HTTP requests through FlareSolverr and manage sessions.

It prints the json response from FlareSolverr. If the FlareSolverr URL is not provided via `-f`, it will use the `FLARESOLVERR_URL` environment variable (defaulting to `http://localhost:8191/v1`).

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
# Create a session
flaresolverr-cli -f http://localhost:8191/v1 session create my-session

# Create multiple sessions at once
flaresolverr-cli session create session1 session2 session3

# List all active sessions
flaresolverr-cli session list

# Destroy a session
flaresolverr-cli session destroy my-session

# Clear all sessions
flaresolverr-cli session clear
```

### Adapter
If your requests are more complex than standard `GET` or form `POST`, the module provides an adapter to retrieve Cloudflare challenge solutions from *FlareSolverr* and apply them to your requests without modifying your existing codebase.

```python
import requests
from flaresolverr_session import Adapter

adapter = Adapter("http://localhost:8191/v1")

session = requests.Session()
session.mount("https://nowsecure.nl", adapter)

response = session.get("https://protected-site.com/page")
print(response.text)
```

It is recommended only mount the adapter to specific origins that require Cloudflare bypass. Read the [caveats section](#caveats) before using it.

> Don't use the `Session` provided by `flaresolverr_session` here.

#### Caveats

* The *FlareSolverr* instance and the machine running the adapter **must share the same public IP** (or use the same proxy with a consistent public IP). Otherwise the cookies obtained from *FlareSolverr* will not be accepted by Cloudflare.
* The proxy used for the original request is automatically applied to the *FlareSolverr* request for the reason mentioned above.
* The adapter automatically sends a `GET` request to the original URL to solve the challenge. You can provide a custom `challenge_url` to override this behavior.
* Cloudflare cookies are tied to the `User-Agent` used during challenge solving. The adapter automatically sets the `User-Agent` returned by FlareSolverr.
* The adapter is less reliable than using the [Session](#basic-usage) directly.

#### How It Works

1. The adapter first attempts to send the request normally through its base adapter.
2. If it detects a Cloudflare challenge, the adapter forwards the URL to a FlareSolverr instance.
3. FlareSolverr solves the challenge and returns cookies and a `User-Agent`.
4. The adapter retries the original request using the returned credentials.


### RPC Tool

The `flaresolverr_rpc` module provides a programmatic interface to the FlareSolverr JSON API, ideal for low-level access to raw API responses.

```python
from flaresolverr_session import RPC

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
