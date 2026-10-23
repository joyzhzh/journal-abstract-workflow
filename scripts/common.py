"""Shared portable configuration and polite API transport (Python standard library)."""
import email.utils
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "journal-abstract-workflow/0.1 (research metadata; Python urllib)"
DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / "config" / "journals.json"
TRANSIENT = {408, 429, 500, 502, 503, 504}
_lock = threading.Lock()
_next = {}


class APIError(RuntimeError):
    """A failed request; never represented as a valid empty API response."""


def normalize_doi(value):
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)\s*", "", (value or "").strip(), flags=re.I).lower()


def validate_slug(slug):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("journal slug must contain lowercase letters, digits and hyphens")
    return slug


def load_registry(path=None):
    path = Path(path or DEFAULT_REGISTRY)
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    entries = data["journals"] if isinstance(data, dict) else data
    seen = set()
    for entry in entries:
        slug = validate_slug(entry["slug"])
        if slug in seen:
            raise ValueError(f"duplicate registry slug: {slug}")
        seen.add(slug)
        for key in ("title", "publisher"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                raise ValueError(f"{slug}: missing {key}")
        if not entry.get("issns") or not all(re.fullmatch(r"\d{4}-\d{3}[\dX]", x) for x in entry["issns"]):
            raise ValueError(f"{slug}: invalid ISSNs")
        if len(entry["issns"]) != len(set(entry["issns"])):
            raise ValueError(f"{slug}: duplicate ISSNs")
        for key in ("utd24", "ft50_2016", "ft50_2026"):
            if not isinstance(entry.get(key), bool):
                raise ValueError(f"{slug}: {key} must be a boolean")
    return entries


def retry_after(headers):
    value = (headers.get("Retry-After") or "").strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, email.utils.parsedate_to_datetime(value).timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return 0.0


def _throttle(provider, interval):
    with _lock:
        now = time.monotonic()
        start = max(now, _next.get(provider, 0.0))
        _next[provider] = start + interval
    if start > now:
        time.sleep(start - now)


def request_bytes(url, provider, data=None, allow_not_found=False, attempts=7):
    """Bounded retries for transient errors, honoring Retry-After and withholding secrets.

    Credentials are read only from environment. Logs/errors name the provider and HTTP
    status, never a URL, response body, exception string, API key or contact address.
    Pacing applies within one process; avoid parallel pipeline processes on one address.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if provider == "openalex" and os.environ.get("OPENALEX_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["OPENALEX_API_KEY"]
    if provider == "semanticscholar" and os.environ.get("SEMANTIC_SCHOLAR_API_KEY"):
        headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
    if provider == "crossref" and os.environ.get("CROSSREF_MAILTO"):
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parts.query)
        query.append(("mailto", os.environ["CROSSREF_MAILTO"]))
        url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
    interval = 3.0 if provider == "semanticscholar" else 1.0
    for attempt in range(attempts):
        _throttle(provider, interval)
        try:
            request = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404 and allow_not_found:
                return None
            if error.code not in TRANSIENT:
                raise APIError(f"{provider}: HTTP {error.code}; check API access or request parameters") from None
            delay = max(retry_after(error.headers), min(60.0, 2 ** attempt))
            problem = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError, OSError):
            delay, problem = min(60.0, 2 ** attempt), "network or timeout error"
        if attempt + 1 < attempts:
            # Retry-After is a minimum, never clipped to a shorter delay.
            with _lock:
                _next[provider] = max(_next.get(provider, 0.0), time.monotonic() + delay)
    raise APIError(f"{provider}: {problem}; stopped after {attempts} attempts; rerun to resume") from None


def request_json(url, provider, **kwargs):
    body = request_bytes(url, provider, **kwargs)
    if body is None:
        return None
    try:
        return json.loads(body)
    except (ValueError, UnicodeError):
        raise APIError(f"{provider}: invalid JSON response; nothing cached") from None
