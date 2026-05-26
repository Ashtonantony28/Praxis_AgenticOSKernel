# Phase 4 Wave 2 — Web Search API Survey

**Date:** 2026-05-25  
**Purpose:** Evaluate web search APIs for Praxis web research integration.

---

## 1. Search API comparison

| Provider | Free tier | Credit card? | Rate limit | Result quality | Notes |
|----------|-----------|-------------|------------|----------------|-------|
| **Brave Search** | 2,000 queries/month | No | 1 req/sec (free) | Good | REST API, JSON responses, well-documented |
| **Tavily** | 1,000 queries/month | No | Reasonable | Excellent for AI | Returns pre-extracted, AI-ready text snippets |
| **Serper** | 2,500 queries (one-time credit) | No (free tier) | Fast | Good (Google) | One-time credit, not recurring |
| **SerpAPI** | 100 queries/month | No | Varies | Excellent (Google) | Very low free quota |
| **DuckDuckGo** | Unlimited (unofficial) | No | Aggressive throttling | Moderate | No official API; `duckduckgo-search` scrapes — fragile |
| **Google Custom Search** | 100 queries/day | No (GCP project) | 100/day | Excellent | Complex GCP setup, low quota |

### Assessment

- **Brave Search** is the best option: highest free monthly quota, no credit card, proper REST API, good docs. Endpoint: `https://api.search.brave.com/res/v1/web/search`.
- **Tavily** is the best alternative for AI workloads — returns clean extracted text, purpose-built for agents. Lower quota but excellent quality. Endpoint: `https://api.tavily.com/search`.
- **DuckDuckGo unofficial** tempting (no key needed) but fragile — scraping library breaks on DDG HTML changes, aggressive rate limits, no SLA. Not suitable for a tool that subagents depend on.
- **SerpAPI/Serper** — good quality but low/non-recurring free tiers.

---

## 2. Web fetch (URL → clean text)

No external API needed. Python stdlib handles this:

- `urllib.request.urlopen()` — built-in HTTP client, no dependency
- `html.parser.HTMLParser` — built-in HTML tag stripping
- Token-limit the output (truncate to ~4000 chars to avoid context blowout)
- Must check domain against ALLOWED_DOMAINS before fetching

No need for `requests` or `beautifulsoup4` — keeps the integration dependency-free.

---

## 3. MCP server assessment

Community MCP servers exist for some providers (tavily-mcp-server, brave-search-mcp), but:

- Praxis has its own tool dispatch system — MCP adds unnecessary indirection
- Same conclusion as Wave 1 survey: direct API via integration module is simpler, testable, and follows the existing pattern
- **Recommendation: direct API, not MCP**

---

## 4. §5 egress boundary impact

Current state:
- `ALLOWED_DOMAINS: frozenset[str] = frozenset()` hardcoded empty in escalation-boundary.py
- `WebFetch`/`WebSearch` blocked unconditionally
- `Config` already parses `PRAXIS_ALLOWED_DOMAINS` env var → `config.allowed_domains`

Gap: the hook doesn't read `PRAXIS_ALLOWED_DOMAINS`. It needs to be extended to:
1. Read `PRAXIS_ALLOWED_DOMAINS` env var (same source as Config)
2. For the new `WebResearch` tool: validate target domains against the allowlist
3. For `fetch` action: extract domain from user-provided URL, check allowlist
4. For `search` action: the search API domain (e.g., `api.search.brave.com`) must be in allowlist

This is a **policy extension**, not a bypass — the hook still enforces, just with a configurable allowlist instead of a hardcoded empty set.

---

## 5. Recommendation

- **Primary search**: Brave Search API (env var: `PRAXIS_WEB_SEARCH_API_KEY`)
- **Web fetch**: `urllib.request` (stdlib, zero deps)
- **HTML stripping**: `html.parser` (stdlib)
- **Approach**: Direct API call from `praxis/integrations/web.py`, same pattern as other integrations
- **§5 extension**: Hook reads `PRAXIS_ALLOWED_DOMAINS`, validates domains for `WebResearch` tool
- **Config flow**: Search API domain added to `PRAXIS_ALLOWED_DOMAINS` by the user; API key in `PRAXIS_WEB_SEARCH_API_KEY`
