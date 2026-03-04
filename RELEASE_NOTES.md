# Splintarr v1.2.0 Release Notes

**Release Date:** 2026-03-04
**Theme:** Smart Searching

## What's New in v1.2.0

### Custom Strategy Filters (PR #119)

- **New "Custom" strategy** with dropdown filters for targeted searching:
  - **Year range** — filter by release year (e.g., 2020-2024)
  - **Quality profile** — target specific profiles from your library
  - **Series status** — filter by continuing, ended, or upcoming
- **Combined Missing + Cutoff Unmet** — explicit opt-in exception to strategy isolation, so you can search for both missing and upgradeable content in one queue
- **Quality profiles auto-populated** from your library data (no manual entry)
- **Dry run integration** — preview what custom filters will match before running
- **Edit support** — existing filter settings pre-populated in the edit modal
- 72 new tests (unit + integration)

### Scope Note

Features #21-23 (Indexer Budget Visibility, Quality-Aware Search Intelligence, Queue Scheduling Improvements) have been moved to v1.3.0.

## Upgrading from v1.1.1

Pull the latest image and restart:

```bash
docker-compose pull
docker-compose up -d
```

No database migrations required. The Custom strategy uses existing database columns.

## Feedback

Please report bugs and feedback at: https://github.com/menottim/splintarr/issues
