# Splintarr v1.3.1 Release Notes

**Release Date:** 2026-03-05
**Theme:** Security Hardening & Bug Fixes

## Security Fixes (4 Advisories Resolved)

All four findings from the v1.3.0 security assessment have been fixed and published as GitHub Security Advisories:

- **GHSA-x58h-pwmm-vfpf** -- Container now drops to non-root user (appuser) via gosu before starting the application
- **GHSA-9wq6-96r6-j6p6** -- SSRF blocklist split: cloud metadata (169.254.x.x), multicast, and reserved ranges are always blocked even when `ALLOW_LOCAL_INSTANCES=true`
- **GHSA-j98q-225j-p8cf** -- Validation error responses no longer include raw input values (passwords stripped from error bodies and logs)
- **GHSA-g27f-2vx9-gvhr** -- WebSocket endpoint validates Origin header to prevent Cross-Site WebSocket Hijacking

### Additional Security Hardening

- Docker `read_only: true` and `cap_drop: ALL` enabled (Windows override file provided)
- `decrypt_if_needed()` logs a warning on failure instead of silently returning ciphertext
- WebSocket connection limit of 50 prevents resource exhaustion
- Config import rejects payloads over 1MB
- Registration endpoint has post-commit race condition check
- Webhook URLs validated against SSRF blocklist during config import
- GitHub CodeQL scanning: all 13 alerts triaged, 0 open

## Bug Fixes

- **"Every Noneh" display** -- Queue cards and detail pages now correctly show "Daily at HH:MM" or "Mon, Thu at HH:MM" for daily/weekly scheduled queues instead of rendering `None` as text
- **Edit modal schedule mode** -- Queue API response now includes `schedule_mode`, `schedule_time`, `schedule_days`, `jitter_minutes`, and `budget_aware` fields. Previously the edit modal always showed "Every N hours" regardless of saved schedule
- **Docker read_only compatibility** -- `/app/data` symlink created at build time in Dockerfile instead of at runtime in entrypoint

## New Documentation

- **[GitHub Pages site](https://menottim.github.io/splintarr/)** -- Landing page with feature overview, screenshots, and install steps
- **[Huntarr Lessons](docs/explanation/huntarr-lessons.md)** -- Comparison mapping all 21 Huntarr vulnerabilities to Splintarr's approach
- **[Security Assessment Prompt](docs/security-assessment-prompt.md)** -- Reusable, self-improving security assessment template

## Upgrading from v1.3.0

```bash
docker-compose pull
docker-compose up -d
```

If you previously created daily or weekly scheduled queues, they will now display correctly. No data migration needed.

## Feedback

Please report bugs and feedback at: https://github.com/menottim/splintarr/issues
