# Splintarr v1.1.0 Release Notes

**Release Date:** 2026-03-03
**Theme:** Visibility — see what's happening, what will happen, and what has happened

## What's New in v1.1.0

Six features completing the Visibility release, plus code quality and security hardening.

### WebSocket Real-Time Activity Feed (PR #111)

- **Single WebSocket connection** at `/ws/live` replaces all dashboard polling
- In-process event bus broadcasts search progress, item results, stats, system status, indexer health, and library sync events
- JWT cookie authentication on WebSocket upgrade with automatic reconnect (exponential backoff: 1s/2s/4s, then 60s reset)
- **Graceful fallback to polling** after 3 failed reconnect attempts
- Auto-connects on all `/dashboard/*` pages, cleanup on page unload

### Synthetic Demo Data Simulation (PR #112)

- **Demo mode** fills the dashboard with synthetic data before users connect real instances
- Background simulation loop emits 13 WebSocket events per ~2-minute cycle through the real event bus
- Five synthetic data generators matching exact API response shapes
- **Auto-disables** instantly when user creates both an instance AND a search queue
- Gold **Demo Mode** banner visible on all authenticated pages

### Search Progress & Live Queue View (PR #113)

- **Live progress panel** on queue detail page with determinate progress bar and streaming results table
- Per-item scores and reasons displayed as each search completes
- **Gold "currently running" banner** on dashboard showing queue name, strategy, and progress count
- Enriched `search.item_result` WebSocket events with `item_index` and `total_items`

### Search Dry Run / Preview Mode (PR #114)

- **"Preview Next Run" button** on queue detail page runs the full scoring/filtering pipeline without executing searches
- Shows what would be searched: items in priority order with scores and reasons
- Summary stats: eligible items, excluded, in cooldown, scored, batch size
- Season pack groupings shown when season pack mode is enabled

### Search History Analytics (PR #115)

- **"Last 7 Days" analytics card** on dashboard with week-over-week trend comparison
- Three metrics: Searches Run, Items Found, Grabs Confirmed — with colored trend arrows
- **Top 3 most-searched series** extracted from search execution metadata
- Refreshes on search completion via WebSocket events

### Bulk Queue Operations (PR #116)

- **Multi-select checkboxes** on queue cards with bulk action bar
- Bulk **Pause, Resume, Run Now, Delete** with confirmation dialogs
- Select All with indeterminate state and selection count indicator

### Code Quality & Security

- Code simplification pass: -34 lines net reduction across 6 files
- Security audit: 0 Critical, 0 High, 3 Medium findings (all addressed)
- WebSocket endpoint now verifies user exists and is active after token validation
- WebSocket error handler now logs exceptions instead of silently swallowing
- Documented single-admin broadcast design constraint

## Upgrading from v1.0.2-alpha

Pull the latest image and restart:

```bash
docker-compose pull
docker-compose up -d
```

No database migrations required. Existing data is preserved.

## Security Audit Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 3 | All addressed |
| Low | 5 | Documented |
| Informational | 2 | Acceptable |

Key Medium findings addressed: WebSocket user-active check added, broadcast design documented, CSRF tracked in existing roadmap.

## Feedback

Please report bugs and feedback at: https://github.com/menottim/splintarr/issues
