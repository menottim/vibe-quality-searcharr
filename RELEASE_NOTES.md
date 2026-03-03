# Splintarr v1.0.2-alpha Release Notes

**Release Date:** 2026-03-02
**Status:** Alpha -- Ready for Testing

## What's New in v1.0.2-alpha

Code quality, security hardening, and UI polish.

### Code Simplification (PR #109)

- Consolidated two separate grab-rate DB queries into a single query with two aggregates
- Simplified `get_scheduler_status()` with early return pattern
- Replaced duplicated Discord/Prowlarr integration template rows with a Jinja2 `{% for %}` loop

### Security Hardening (PR #110)

- **Removed dead `?next=` redirect parameter** from both the server-side 401 handler (`main.py`) and the client-side fetch interceptor (`base.html`). The parameter was never consumed by the login page, creating a latent open redirect risk if anyone wired it up without validation.
- **Replaced `innerHTML` with DOM construction** in the setup wizard password strength meter (`setup/admin.html`). All dynamic DOM updates now consistently use `textContent` across the entire codebase.

### UI Fixes

- Dashboard stat card detail text now bottom-aligns across all cards (flex column with `margin-top: auto`)
- Grab rate moved inline with search stats (eliminates height difference between cards)

## Upgrading from v1.0.1-alpha

Pull the latest image and restart:

```bash
docker-compose pull
docker-compose up -d
```

No database migrations required. Existing data is preserved.

## Known Limitations

Same as v1.0.0-alpha — see [v1.0.0-alpha release notes](https://github.com/menottim/splintarr/releases/tag/v1.0.0-alpha).

## Feedback

Please report bugs and feedback at: https://github.com/menottim/splintarr/issues
