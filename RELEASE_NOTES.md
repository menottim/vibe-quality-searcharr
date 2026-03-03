# Splintarr v1.1.0-alpha Release Notes

**Release Date:** 2026-03-03
**Status:** Alpha -- Ready for Testing

## What's New in v1.1.0-alpha

Real-time WebSocket updates and a synthetic demo mode for new installs. This is the first release in the **v1.1.0 Visibility** series.

### WebSocket Real-Time Activity Feed (PR #111)

- **Single WebSocket connection** at `/ws/live` replaces all dashboard polling
- In-process event bus broadcasts search progress, item results, stats, system status, indexer health, and library sync events
- JWT cookie authentication on WebSocket upgrade with automatic reconnect (exponential backoff: 1s/2s/4s, then 60s reset)
- **Graceful fallback to polling** after 3 failed reconnect attempts
- WebSocket cleanup on page unload prevents stale connections
- Auto-connects on all `/dashboard/*` pages

### Synthetic Demo Data Simulation (PR #112)

- **Demo mode** fills the dashboard with synthetic data before users connect real instances
- Background simulation loop emits 13 WebSocket events per ~2-minute cycle through the real event bus
- Five synthetic data generators matching exact API response shapes: dashboard stats, activity, system status, library stats, indexer health
- **Auto-disables** instantly when user creates both an instance AND a search queue
- Gold **Demo Mode** banner visible on all authenticated pages with dismiss button and links to Instances/Queues pages
- All synthetic payloads include `"demo": true` for consumer differentiation

### Additional Improvements

- Added rate limiting (`30/minute`) to `api_dashboard_stats` and `api_dashboard_activity` endpoints
- Added DEBUG logging to all dashboard API handlers (both real and demo paths)

## Upgrading from v1.0.2-alpha

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
