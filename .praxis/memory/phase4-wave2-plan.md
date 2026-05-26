# Phase 4 Wave 2 — Web Integration Plan

**Date:** 2026-05-25  
**Based on:** phase4-wave2-survey.md

---

## 1. Tool design

Single tool `WebResearch` with two actions, matching the existing integration pattern:

```python
SCHEMAS = {
    "WebResearch": {
        "name": "WebResearch",
        "description": "Web search and page fetch for research. Actions: search, fetch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["search", "fetch"]},
                "query": {"type": "string", "description": "Search query (for search action)"},
                "url": {"type": "string", "description": "URL to fetch (for fetch action)"},
                "n": {"type": "integer", "description": "Number of results (search, default 5)"},
                "max_chars": {"type": "integer", "description": "Max chars of fetched content (fetch, default 4000)"},
            },
            "required": ["action"],
        },
    },
}
```

## 2. Search provider: Brave Search API

- Endpoint: `https://api.search.brave.com/res/v1/web/search`
- Auth: `X-Subscription-Token` header with API key
- Env var: `PRAXIS_WEB_SEARCH_API_KEY`
- Response: JSON with `web.results[]` — each has `title`, `url`, `description`
- Return format: numbered list of `title | url | snippet` (concise, no full page content)

## 3. Fetch implementation

- `urllib.request.urlopen(url, timeout=15)` — built-in, no dependency
- Strip HTML tags via stdlib `html.parser.HTMLParser` subclass
- Truncate to `max_chars` (default 4000) to prevent context blowout
- Return: `"Fetched {url} ({n} chars):\n{clean_text}"` — never log full content
- Respect `Content-Type` — only process `text/html` and `text/plain`

## 4. §5 egress boundary extension

### Hook changes (escalation-boundary.py)

```python
# Change from:
ALLOWED_DOMAINS: frozenset[str] = frozenset()

# To:
_domains_str = os.environ.get("PRAXIS_ALLOWED_DOMAINS", "")
ALLOWED_DOMAINS: frozenset[str] = frozenset(
    d.strip() for d in _domains_str.split(",") if d.strip()
)
```

Add `WebResearch` handling in `main()`:

```python
if tool == "WebResearch":
    url = args.get("url", "")
    if url:
        domain = _extract_domain(url)
        if domain not in ALLOWED_DOMAINS:
            block(f"WebResearch fetch domain '{domain}' not in ALLOWED_DOMAINS")
    # For search action, the implementation validates the API endpoint domain
```

### Implementation-level validation (defense in depth)

`web.py` also checks `config.allowed_domains` before any HTTP request — both for fetch URLs and the search API endpoint. Double enforcement: hook blocks at tool-call level, implementation blocks at HTTP level.

## 5. API key flow

```bash
# User configures:
export PRAXIS_WEB_SEARCH_API_KEY=BSA...          # Brave Search API key
export PRAXIS_ALLOWED_DOMAINS=api.search.brave.com,docs.python.org,github.com
```

- `PRAXIS_WEB_SEARCH_API_KEY` → used in `Authorization` header
- `PRAXIS_ALLOWED_DOMAINS` → read by both hook AND Config, checked before every HTTP request
- Key added to `_redact_secrets()` in `tools.py` for output filtering
- No credentials in convergence.yaml — env vars only (same as GITHUB_TOKEN pattern)

## 6. Files to create/modify

| File | Change |
|------|--------|
| `praxis/integrations/web.py` | **NEW** — search + fetch implementation |
| `praxis/integrations/__init__.py` | Import and aggregate web module |
| `.claude/hooks/escalation-boundary.py` | Read PRAXIS_ALLOWED_DOMAINS, check WebResearch domains |
| `praxis/tools.py` | Add PRAXIS_WEB_SEARCH_API_KEY to _redact_secrets() |
| `tests/test_integrations.py` | Add TestWebResearch class |

## 7. Error cases

- Missing API key → `"Error: PRAXIS_WEB_SEARCH_API_KEY not set. Get a free key at https://brave.com/search/api/"`
- Domain not in allowlist → `"Error: domain 'example.com' not in PRAXIS_ALLOWED_DOMAINS"`
- Search API error → `"Error: Brave Search API returned {status}: {body}"`
- Fetch timeout → `"Error: fetch timed out after 15s"`
- Non-text content → `"Error: URL returned non-text content type: {ct}"`
- No results → `"No results found for: {query}"`

## 8. What stays the same

- All 261 existing tests pass unchanged
- Interactive mode, queue, daemon unchanged
- Other integrations (GitHub, Analyze, TestRunner, Dependencies) unchanged
- Runtime, convergence, token propagation unchanged
- §5 hook still blocks WebFetch/WebSearch (Claude Code native tools) unconditionally
