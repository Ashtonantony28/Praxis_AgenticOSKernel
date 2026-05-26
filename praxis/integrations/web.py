"""Web research integration — search and fetch via Brave Search API + urllib."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any, Callable

from ..config import Config
from ..tools import _redact_secrets

SCHEMAS: dict[str, dict[str, Any]] = {
    "WebResearch": {
        "name": "WebResearch",
        "description": (
            "Web search and page fetch for research. "
            "Actions: search (query the web), fetch (retrieve a page as clean text)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "fetch"],
                    "description": "The web research operation to perform",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (required for search action)",
                },
                "url": {
                    "type": "string",
                    "description": "URL to fetch (required for fetch action)",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of search results to return (default: 5, max: 20)",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters of fetched page content (default: 4000)",
                },
            },
            "required": ["action"],
        },
    },
}

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_API_DOMAIN = "api.search.brave.com"


# ---------- HTML stripping ----------


class _HTMLTextExtractor(HTMLParser):
    """Strip HTML tags, return plain text."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse whitespace runs but preserve paragraph breaks
        lines = raw.splitlines()
        cleaned = []
        for line in lines:
            stripped = " ".join(line.split())
            if stripped:
                cleaned.append(stripped)
        return "\n".join(cleaned)


def _strip_html(html: str) -> str:
    """Convert HTML to plain text."""
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


# ---------- Domain validation ----------


def _extract_domain(url: str) -> str:
    """Extract domain from a URL."""
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname or ""


def _check_domain(domain: str, config: Config) -> str | None:
    """Return error string if domain is not in allowed_domains, else None."""
    if not domain:
        return "Error: could not extract domain from URL"
    if domain not in config.allowed_domains:
        return (
            f"Error: domain '{domain}' not in PRAXIS_ALLOWED_DOMAINS. "
            f"Add it to the PRAXIS_ALLOWED_DOMAINS env var to allow access."
        )
    return None


# ---------- Search ----------


def _search(query: str, n: int, config: Config) -> str:
    """Search the web using Brave Search API."""
    api_key = os.environ.get("PRAXIS_WEB_SEARCH_API_KEY", "")
    if not api_key:
        return (
            "Error: PRAXIS_WEB_SEARCH_API_KEY not set. "
            "Get a free key at https://brave.com/search/api/"
        )

    # Validate search API domain is in allowlist
    domain_err = _check_domain(BRAVE_API_DOMAIN, config)
    if domain_err:
        return domain_err

    n = max(1, min(n, 20))
    params = urllib.parse.urlencode({"q": query, "count": n})
    url = f"{BRAVE_API_URL}?{params}"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("X-Subscription-Token", api_key)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        return _redact_secrets(
            f"Error: Brave Search API returned {exc.code}: {body[:200]}"
        )
    except urllib.error.URLError as exc:
        return f"Error: could not reach Brave Search API: {exc.reason}"
    except TimeoutError:
        return "Error: Brave Search API request timed out after 15s"

    results = data.get("web", {}).get("results", [])
    if not results:
        return f"No results found for: {query}"

    lines = []
    for i, r in enumerate(results[:n], 1):
        title = r.get("title", "(no title)")
        link = r.get("url", "")
        snippet = r.get("description", "")
        lines.append(f"{i}. {title}\n   {link}\n   {snippet}")

    return "\n\n".join(lines)


# ---------- Fetch ----------


def _fetch(url: str, max_chars: int, config: Config) -> str:
    """Fetch a URL and return clean text content."""
    domain = _extract_domain(url)
    domain_err = _check_domain(domain, config)
    if domain_err:
        return domain_err

    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Praxis/1.0 (web research agent)")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ct = resp.headers.get("Content-Type", "")
            if not any(t in ct for t in ("text/html", "text/plain", "application/json")):
                return f"Error: URL returned non-text content type: {ct}"

            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return f"Error: fetch returned HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return f"Error: could not fetch URL: {exc.reason}"
    except TimeoutError:
        return "Error: fetch timed out after 15s"

    if "text/html" in ct:
        text = _strip_html(raw)
    else:
        text = raw

    text = text[:max_chars]
    return _redact_secrets(f"Fetched {url} ({len(text)} chars):\n{text}")


# ---------- Dispatch ----------


def execute_web_research(args: dict[str, Any], config: Config) -> str:
    action = args.get("action", "")

    if action == "search":
        query = args.get("query", "")
        if not query:
            return "Error: 'query' is required for search action"
        n = args.get("n", 5)
        return _search(query, n, config)

    elif action == "fetch":
        url = args.get("url", "")
        if not url:
            return "Error: 'url' is required for fetch action"
        max_chars = args.get("max_chars", 4000)
        return _fetch(url, max_chars, config)

    else:
        return f"Error: unknown WebResearch action '{action}'"


IMPLEMENTATIONS: dict[str, Callable[[dict[str, Any], Config], str]] = {
    "WebResearch": execute_web_research,
}
