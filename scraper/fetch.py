import ssl
import time
import urllib.error
import urllib.request

from scraper.config import BASE_URL, REQUEST_DELAY_SECONDS

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_last_request_at = 0.0


def fetch(path: str, *, delay: bool = True) -> str:
    """Fetch a page from towerbells.org/data/. `path` may be a filename or full URL."""
    global _last_request_at

    if delay and REQUEST_DELAY_SECONDS > 0:
        elapsed = time.monotonic() - _last_request_at
        if elapsed < REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS - elapsed)

    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "towerbells-remake-scraper/0.1 (+educational/noncommercial)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=_SSL_CTX) as resp:
            html = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
    finally:
        _last_request_at = time.monotonic()

    return html.decode("latin-1", errors="replace")
