# §5 Hook Patch — Optional Enhancement

The WebResearch tool enforces domain restrictions at the implementation level
via `config.allowed_domains`. This is sufficient because the orchestrator
always calls the implementation through `_execute_with_hook()`.

For defense-in-depth, you can optionally update `.claude/hooks/escalation-boundary.py`
to also check WebResearch domains at the hook level. Apply these two changes manually:

## Change 1: Read PRAXIS_ALLOWED_DOMAINS (line 40)

Replace:
```python
ALLOWED_DOMAINS: frozenset[str] = frozenset()
```

With:
```python
_domains_str = os.environ.get("PRAXIS_ALLOWED_DOMAINS", "")
ALLOWED_DOMAINS: frozenset[str] = frozenset(
    d.strip() for d in _domains_str.split(",") if d.strip()
)
```

## Change 2: Add WebResearch check (after the Bash check in main(), ~line 184)

Add before `sys.exit(0)`:
```python
    if tool == "WebResearch":
        url = args.get("url", "")
        if url:
            from urllib.parse import urlparse
            domain = urlparse(url).hostname or ""
            if domain and domain not in ALLOWED_DOMAINS:
                block(
                    f"WebResearch fetch domain '{domain}' not in ALLOWED_DOMAINS"
                )
```
