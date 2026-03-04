# Series Completion Cards — Design Document

**Feature #25** | **Target Release**: v1.3.0
**Date**: 2026-03-04

## Problem

Users have no at-a-glance view of library completion progress. The existing poster grid shows all items equally — no way to quickly see what's closest to complete, what has the most gaps, or which recently aired content is still missing.

## Scope

### 1. Dashboard — Compact Summary Card

New "Completion Progress" card on the main dashboard:
- 3 horizontal bars showing: Most Incomplete (bottom 3), Closest to Complete (90-99%), Recently Aired incomplete
- Each bar: 32px poster thumbnail, title (truncated), progress bar, "X/Y" count
- "View all" link to Library page
- Uses same Pico CSS card styling as existing dashboard cards

### 2. Library Page — Full Completion Section

Collapsible section above the existing poster grid:
- Horizontal scrollable row of completion cards
- Card: 48px poster, title, year, progress bar, "X of Y episodes", status badge
- Sort/filter tabs: "Most Incomplete", "Closest to Complete", "Recently Aired"
- 10 cards per view, horizontally scrollable
- Each card links to `/dashboard/library/{item_id}`

### 3. API Endpoint

`GET /api/library/completion` — returns 3 sorted lists:

```json
{
  "most_incomplete": [
    {"id": 1, "title": "...", "year": 2020, "episode_count": 50, "episode_have": 10, "completion_pct": 20.0, "poster_path": "...", "status": "continuing"}
  ],
  "closest_to_complete": [...],
  "recently_aired": [...]
}
```

- `most_incomplete`: sorted by `completion_pct` ASC, where `episode_have < episode_count`, limit 10
- `closest_to_complete`: sorted by `completion_pct` DESC, where `completion_pct >= 50 AND completion_pct < 100`, limit 10
- `recently_aired`: sorted by `added_at` DESC, where `episode_have < episode_count`, limit 10
- All filtered to current user's instances
- Rate-limited: 30/minute

## Architecture

- No new models or database changes
- Single new API endpoint using existing `_base_library_query` helper
- Dashboard card loaded via JS fetch on page load (same pattern as analytics card)
- Library section rendered server-side in Jinja2 template (data passed from route handler)

## Not Building
- Completion velocity/trends (needs time-series data)
- Per-instance breakdown
- Movie-specific handling (movies are always 0% or 100%)
