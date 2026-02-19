# -*- coding: utf-8 -*-

from flaresolverr_session.exceptions import (
    FlareSolverrError,
    FlareSolverrResponseError,
    FlareSolverrChallengeError,
    FlareSolverrUnsupportedMethodError,
)
from flaresolverr_session.rpc import RPC
from flaresolverr_session.session import Session, Response

__title__ = "flaresolverr-session"
__description__ = "A requests.Session that proxies through a FlareSolverr instance."
__url__ = "https://github.com/Xavier-Lam/FlareSolverrSession"
__version__ = "0.2.2"
__author__ = "Xavier-Lam"
__author_email__ = "xavierlam7@hotmail.com"

__all__ = [
    "Session",
    "Response",
    "RPC",
    "FlareSolverrError",
    "FlareSolverrResponseError",
    "FlareSolverrChallengeError",
    "FlareSolverrUnsupportedMethodError",
    "__version__",
]
