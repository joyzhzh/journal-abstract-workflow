"""Shared portable configuration and polite API transport (Python standard library)."""
import email.utils
import http.client
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
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


def _origin(url):
    parts = urllib.parse.urlsplit(url)
    if parts.username or parts.password:
        raise ValueError("userinfo is not an API origin")
    return parts.scheme.lower(), (parts.hostname or "").lower(), parts.port or (443 if parts.scheme.lower() == "https" else 80)


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep every redirect on its original origin, including scheme and port.

    urllib's default handler forwards Authorization and x-api-key to other hosts.
    Refusing the redirect before constructing its request prevents that disclosure,
    as well as HTTPS-to-HTTP downgrades and contact-address query forwarding.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            same_origin = _origin(req.full_url) == _origin(newurl)
        except (TypeError, ValueError):
            same_origin = False
        if not same_origin:
            raise APIError("API redirect to a different origin or insecure scheme refused") from None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# Local to this module; never replaces urllib's process-wide default opener.
_opener = urllib.request.build_opener(SafeRedirectHandler())


def preserve_cache(path):
    """Keep the exact pre-repair bytes before replacing a cache with invalid entries."""
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    folder = path.parent / "history"
    folder.mkdir(exist_ok=True)
    destination = folder / (digest.hexdigest() + "-" + path.name)
    if not destination.exists():
        shutil.copyfile(path, destination)
    return destination


def valid_semantic_scholar_paper(value):
    """A batch null is an explicit miss; a paper must contain a typed abstract field.

    Older saved projections need not carry every currently requested field, but an
    error object, omitted abstract, or malformed field is never a successful empty paper.
    """
    if value is None:
        return True
    if not isinstance(value, dict) or "error" in value or "errors" in value or "abstract" not in value:
        return False
    if value["abstract"] is not None and not isinstance(value["abstract"], str):
        return False
    for field in ("title", "paperId"):
        if field in value and value[field] is not None and not isinstance(value[field], str):
            return False
    identifiers = value.get("externalIds")
    if identifiers is not None and not isinstance(identifiers, dict):
        return False
    doi = (identifiers or {}).get("DOI")
    return doi is None or isinstance(doi, str)


def valid_openalex_work(value):
    """Validate the OpenAlex fields consumed downstream without demanding newer fields."""
    if not isinstance(value, dict) or "error" in value or "errors" in value:
        return False
    if not isinstance(value.get("id"), str) or not re.fullmatch(r"(?:https?://openalex\.org/)?W\d+", value["id"]):
        return False
    for field in ("doi", "display_name", "type", "language"):
        if value.get(field) is not None and not isinstance(value[field], str):
            return False
    index = value.get("abstract_inverted_index")
    if index is not None:
        if not isinstance(index, dict):
            return False
        for word, positions in index.items():
            if not isinstance(word, str) or not isinstance(positions, list) or any(type(p) is not int or p < 0 for p in positions):
                return False
    references = value.get("referenced_works")
    if references is not None and (not isinstance(references, list) or any(not isinstance(x, str) for x in references)):
        return False
    authorships = value.get("authorships")
    if authorships is not None:
        if not isinstance(authorships, list):
            return False
        for author in authorships:
            if not isinstance(author, dict):
                return False
            institutions = author.get("institutions")
            if institutions is not None:
                if not isinstance(institutions, list):
                    return False
                for institution in institutions:
                    if not isinstance(institution, dict) or any(institution.get(k) is not None and not isinstance(institution[k], str) for k in ("display_name", "country_code")):
                        return False
    topic = value.get("primary_topic")
    if topic is not None:
        if not isinstance(topic, dict) or (topic.get("display_name") is not None and not isinstance(topic["display_name"], str)):
            return False
        field = topic.get("field")
        if field is not None and (not isinstance(field, dict) or (field.get("display_name") is not None and not isinstance(field["display_name"], str))):
            return False
    return True


def valid_openalex_record(value, allow_legacy=False):
    if not isinstance(value, dict) or not isinstance(value.get("doi"), str) or not value["doi"]:
        return False
    if "response" not in value:
        return False
    if value.get("status") == "not_found":
        return value["response"] is None
    if value.get("status") == "ok" or (allow_legacy and "status" not in value):
        return valid_openalex_work(value["response"])
    return False


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
    credential = {"openalex": "OPENALEX_API_KEY", "semanticscholar": "SEMANTIC_SCHOLAR_API_KEY"}.get(provider)
    key = os.environ.get(credential, "") if credential else ""
    if key:
        if any(not 33 <= ord(character) <= 126 for character in key):
            raise APIError(f"{provider}: invalid API key format; remove whitespace and non-ASCII characters from {credential}")
        headers["Authorization" if provider == "openalex" else "x-api-key"] = "Bearer " + key if provider == "openalex" else key
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
            with _opener.open(request, timeout=120) as response:
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
        except (ValueError, UnicodeError, http.client.HTTPException):
            # Header/URL validation exceptions can contain the complete credential.
            raise APIError(f"{provider}: invalid HTTP request or response; details withheld") from None
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
