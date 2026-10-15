"""
Plain HTTP GET with the standard library.

The fetch functions take the getter as a parameter, so tests replace it with a
fake and never reach the network.
"""

import gzip
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping

TIMEOUT_S = 60

HttpGet = Callable[[str, Mapping[str, str]], bytes]


class HttpError(RuntimeError):
    """A response with a status other than 200, or no response at all (status None)."""

    def __init__(self, url: str, status: int | None, detail: str = ""):
        outcome = status if status is not None else "no response"
        super().__init__(f"GET {url} failed: {outcome} {detail}".strip())
        self.url = url
        self.status = status


def decode_body(body: bytes, content_encoding: str | None) -> bytes:
    if (content_encoding or "").lower() == "gzip":
        return gzip.decompress(body)
    return body


def urllib_get(url: str, headers: Mapping[str, str]) -> bytes:
    request = urllib.request.Request(url, headers={**headers, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return decode_body(response.read(), response.headers.get("Content-Encoding"))
    except urllib.error.HTTPError as e:
        raise HttpError(url, e.code, e.reason) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise HttpError(url, None, str(e)) from e
