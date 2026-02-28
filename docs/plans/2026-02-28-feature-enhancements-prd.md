# Splintarr v0.3+ Feature Enhancements — Product Requirements Document

**Date:** 2026-02-28
**Builds on:** PRD v0.2 (docs/PRD-v0.2.md)
**Status:** Draft — awaiting review

---

## Context & Research

### Why Splintarr Exists

Sonarr and Radarr rely on **RSS feeds** for ongoing content acquisition — polling indexers every 15-60 minutes for newly posted releases. This handles *future* content efficiently but does nothing for existing backlogs. The built-in "Search All Missing" button sends all requests at once, overwhelming indexers with large libraries. There is no scheduled, throttled backlog search built into Sonarr or Radarr, and the developers have indicated this is by design.

### Community Pain Points (from research)

| Pain Point | Evidence |
|------------|----------|
| No scheduled backlog search | [Sonarr Forum: Scheduled Missing Search](https://forums.sonarr.tv/t/scheduled-missing-search/12641), [Trickle Mode request](https://forums.sonarr.tv/t/missing-episodes-backlog-scan-trickle-mode/3933) |
| "Search All" overwhelms indexers | [Sonarr #1359](https://github.com/Sonarr/Sonarr/issues/1359), [Sonarr #4907](https://github.com/Sonarr/Sonarr/issues/4907) — indexers close connections after 100-1,000 requests |
| No season pack option for bulk search | [Sonarr #4229](https://github.com/Sonarr/Sonarr/issues/4229) — individual episode searches fail for older content where only season packs exist |
| Can't combine or prioritize searches | [Sonarr #3657](https://github.com/Sonarr/Sonarr/issues/3657), [Radarr #10501](https://github.com/Radarr/Radarr/issues/10501) (won't fix) |
| No search-by-age prioritization | [Sonarr #3067](https://github.com/Sonarr/Sonarr/issues/3067) — items searched many times with no results should be deprioritized |
| Re-downloads of intentionally deleted content | Users who manually delete episodes find them re-downloaded by "missing" searches — unmonitoring is the only prevention |

### Competing Tools

| Tool | Approach | Limitations |
|------|----------|-------------|
| [Huntarr](https://github.com/plexguide/Huntarr.io) | Batch-based, hourly API caps, web GUI, Docker | No indexer-aware throttling, no season pack intelligence, no adaptive prioritization |
| [missarr](https://github.com/l3uddz/missarr) | CLI tool, config-file based | No GUI, no scheduling, no analytics |
| [n8n workflow](https://n8n.io/workflows/5927) | Automation workflow, per-season search | Requires n8n infrastructure, complex setup |

### Design Principle: Strategy Isolation

**Missing and Cutoff Unmet are fundamentally different intents and must never be combined or auto-selected.**

- "Missing" = content that doesn't exist on disk. Includes intentionally deleted content unless unmonitored.
- "Cutoff Unmet" = content that exists but is below the quality profile cutoff. Only upgrades quality, never re-downloads deleted content.
- All features below must respect this separation. Season pack searches, adaptive prioritization, and cooldown logic all behave differently depending on strategy.
- The UX must make the distinction clear to prevent users from accidentally triggering a strategy they didn't intend.

---

## Target User

Solo homelab operator managing 1-5 Sonarr/Radarr instances behind Prowlarr, with libraries of 100-5,000 items. Wants a "set and forget" solution that's smarter than cron + API calls but doesn't require n8n or custom scripting.

---

## Feature 10: Prowlarr Integration & Indexer-Aware Rate Limiting

**Priority:** High
**Effort:** Medium

**Problem:** Splintarr currently uses a blanket per-instance rate limit (5 req/sec) that doesn't account for individual indexer API limits. Each indexer (via Prowlarr) has different rate limits — some VIP accounts allow more, public indexers allow less. Being too aggressive gets you banned; being too conservative means missing content.

**User Stories:**
- *As a user with Prowlarr, I want Splintarr to read my indexer configurations so it knows each indexer's API limits and capabilities.*
- *As a user, I want Splintarr to automatically throttle searches based on the most restrictive indexer connected to a Sonarr/Radarr instance, so I never exceed any indexer's limits.*
- *As a user, I want to see which indexers are configured and their current rate limit usage on the dashboard.*

**Requirements:**
- Connect to Prowlarr API (URL + API key, same pattern as Sonarr/Radarr)
- Read indexer list with capabilities (API limits, categories supported)
- Map indexers to Sonarr/Radarr instances (Prowlarr knows which indexers are synced to which apps)
- Calculate effective rate limit per instance based on the most restrictive connected indexer
- Track API call count per indexer per time window (hourly/daily)
- Dashboard widget showing indexer health and usage
- Fallback: if Prowlarr is not configured, use the existing per-instance rate limit

**Data model changes:**
- New `prowlarr_config` table (id, url, api_key_encrypted, last_synced_at)
- New `indexers` table (id, prowlarr_id, name, api_limit_per_hour, api_limit_per_day, capabilities_json, linked_instance_ids)
- New `indexer_usage` table (id, indexer_id, period_start, api_calls_count)

---

## Feature 11: Season Pack Intelligence (Sonarr Only)

**Priority:** High
**Effort:** Medium

**Problem:** When multiple episodes from the same season are missing, Splintarr searches for each individually. For older content, individual episode releases are rare — season packs are the only option. This wastes API calls and finds nothing. Season pack searching is [one of the most requested Sonarr features](https://github.com/Sonarr/Sonarr/issues/4229).

**User Stories:**
- *As a user with older TV backlogs, when 3+ episodes from the same season are missing, I want Splintarr to first try a season pack search before falling back to per-episode searches.*
- *As a user running cutoff unmet searches, I want season pack intelligence to only look for quality upgrades, not re-download deleted episodes.*

**Requirements:**
- Before per-episode searching, group missing episodes by series + season
- If a season has N+ missing episodes (configurable threshold, default 3), issue a `SeasonSearch` command instead of individual `EpisodeSearch` commands
- For cutoff unmet: only apply season pack search when N+ episodes in the same season are below cutoff
- Track season-level searches separately in search_log (action: "SeasonSearch")
- Sonarr-only feature — Radarr has no equivalent (movies are single items)
- Configurable: enable/disable season pack mode per queue

**Strategy isolation:**
- Missing strategy: Season pack search downloads any missing episode in the season
- Cutoff unmet strategy: Season pack search only upgrades existing files below cutoff
- Both use the same Sonarr `SeasonSearch` command, which respects the monitored status and quality profile

---

## Feature 12: Adaptive Search Prioritization

**Priority:** High
**Effort:** Medium

**Problem:** Fixed search ordering means the same items get searched first every time. Items that have been searched 20+ times with no results still consume API calls. Recently aired content (most likely to be available) waits behind years-old missing episodes. This is [a known gap](https://github.com/Sonarr/Sonarr/issues/3067) in the Sonarr ecosystem.

**User Stories:**
- *As a user, I want recently aired/added content prioritized in searches because it's most likely to be available on indexers.*
- *As a user, I want items that have been searched many times with no results to be automatically deprioritized, saving API calls for content that's more likely to succeed.*
- *As a user, I want to see why an item was prioritized or deprioritized in the search log.*

**Requirements:**
- Score each item before searching based on:
  - **Recency**: Recently aired (Sonarr) or recently added (Radarr) episodes score higher
  - **Search history**: Items with many prior failed searches score lower (diminishing returns)
  - **Time since last search**: Items not searched recently score higher (spread coverage)
  - **Monitored status**: Only search monitored items (Sonarr/Radarr already filter this in the API)
- Sort the search queue by score before executing
- Log the score and reason in search_metadata for transparency
- Strategy-specific scoring:
  - Missing: weight recency (air date) and total search attempts
  - Cutoff unmet: weight quality gap (how far below cutoff) and time since last upgrade

**Data model changes:**
- Add `search_attempts` and `last_searched_at` to `library_items` table (updated after each search)
- Scoring algorithm configurable via settings (or use sensible defaults)

---

## Feature 13: Search Cooldown Intelligence

**Priority:** Medium
**Effort:** Low

**Problem:** The current 24-hour cooldown is a blunt instrument. Newly aired episodes should be searched more aggressively (content appears on indexers within hours of airing), while content that's been missing for years needs less frequent searching.

**User Stories:**
- *As a user, I want fresh content (aired in the last 7 days) searched every few hours, while old missing content is searched at most once per week.*
- *As a user, I want the cooldown to increase automatically for items that repeatedly return no results.*

**Requirements:**
- Tiered cooldown based on content age:
  - Aired/added within 24 hours: 2-hour cooldown
  - Aired/added within 7 days: 6-hour cooldown
  - Aired/added within 30 days: 24-hour cooldown (current default)
  - Aired/added 30+ days ago: 72-hour cooldown
  - Aired/added 1+ year ago: 7-day cooldown
- Exponential backoff for repeated failures: each consecutive search with no result doubles the cooldown (capped at 14 days)
- Reset cooldown when: content is newly aired, quality profile changes, or user manually triggers search
- Configurable: allow users to override with a flat cooldown if they prefer simplicity
- Display effective cooldown in search_log entries

---

## Feature 14: Notifications & Exclusion Lists

**Priority:** High (user-reported need)
**Effort:** Medium

### 14a: Discord Webhook Notifications

**Problem:** No way to know when searches find something or encounter failures without checking the dashboard.

**User Stories:**
- *As a user, I want to receive a Discord message when a search finds and grabs new content.*
- *As a user, I want to be alerted when a queue fails repeatedly or an instance goes down.*
- *As a user, I do NOT want notifications for routine empty searches — only meaningful events.*

**Requirements:**
- Discord webhook URL configuration in Settings
- Event types (each independently toggleable):
  - Search found content (episode grabbed, movie grabbed)
  - Queue failed (N consecutive failures)
  - Instance connection lost / recovered
  - Library sync completed (with summary: N items synced, N new, N removed)
- Rich Discord embeds: poster thumbnail, item title, quality, instance name
- Rate limit: max 1 notification per event type per 5 minutes (prevent spam during bulk operations)
- Test button in settings to verify webhook connectivity

**Data model changes:**
- New `notification_config` table (id, webhook_url_encrypted, events_enabled_json, is_active, last_sent_at)

### 14b: Content Exclusion Lists

**Problem:** Users have content they don't want searched — abandoned series, movies they don't care about upgrading, problematic releases. API calls are wasted on these items.

**User Stories:**
- *As a user browsing my library, I want to exclude a specific series or movie from all future searches with one click.*
- *As a user, I want temporary exclusions ("ignore for 30 days") for content I expect to become available later.*
- *As a user, I want to see all active exclusions in one place and remove them easily.*

**Requirements:**
- Exclude by: library item ID (series/movie), with reason field
- Temporary exclusions with configurable expiration (7/30/90 days, or permanent)
- "Exclude" button on library detail page and in search results
- Exclusion management page: view all, filter by instance/type, remove
- Exclusions checked before search execution (skip excluded items, log as "skipped: excluded")
- Bulk exclude: select multiple items from library grid

**Data model changes:**
- New `search_exclusions` table (id, instance_id, library_item_id, external_id, content_type, title, reason, expires_at, created_at)

---

## Feature 15: Search Result Feedback Loop

**Priority:** Medium
**Effort:** Medium

**Problem:** When Splintarr sends an `EpisodeSearch` command to Sonarr, it records "search sent" but never checks whether anything was actually grabbed. The "items_found" count in search history represents items *searched*, not items *downloaded*. True success rates are unknown.

**User Stories:**
- *As a user, I want to see actual download success rates — not just "searches triggered" but "episodes/movies actually grabbed."*
- *As a user, I want Splintarr to learn from search outcomes: if an item has been searched 10 times with no grabs, it should be deprioritized.*

**Requirements:**
- After triggering a search, poll the item's status after a configurable delay (default: 15 minutes)
- Compare episode_have/movie_hasFile before and after to determine if a grab occurred
- Track per-item: searches_triggered, grabs_confirmed, last_grab_at
- Feed grab data into adaptive prioritization (Feature 12) and cooldown intelligence (Feature 13)
- Dashboard metric: actual grab rate vs search rate
- Uses existing library sync data — no additional API calls needed if sync runs frequently

**Data model changes:**
- Add `grabs_confirmed` and `last_grab_at` to `library_items`
- Add `grab_confirmed` boolean to search_log entries (updated asynchronously)

---

## Implementation Priority Matrix

| # | Feature | Priority | Effort | Depends On |
|---|---------|----------|--------|------------|
| 14b | Exclusion Lists | High | Low | Library Overview (done) |
| 14a | Discord Notifications | High | Low | None |
| 10 | Prowlarr Integration | High | Medium | None |
| 12 | Adaptive Prioritization | High | Medium | Library Overview (done) |
| 11 | Season Pack Intelligence | High | Medium | Library Overview (done) |
| 13 | Cooldown Intelligence | Medium | Low | Adaptive Prioritization |
| 15 | Feedback Loop | Medium | Medium | Library Overview (done) |

**Suggested implementation order:**
1. Exclusion Lists (14b) — immediate value, low effort, you already want this
2. Discord Notifications (14a) — immediate value, low effort, you already want this
3. Prowlarr Integration (10) — enables indexer-aware rate limiting for all subsequent features
4. Adaptive Prioritization (12) — core search intelligence improvement
5. Season Pack Intelligence (11) — significant API call reduction for TV backlogs
6. Cooldown Intelligence (13) — builds on prioritization data
7. Feedback Loop (15) — closes the loop, enables learning

---

## Relationship to PRD v0.2 Features

| PRD v0.2 Feature | Status in This PRD |
|-------------------|--------------------|
| Feature 1: Library Overview | **Implemented** |
| Feature 2: Exclusion Lists | **Evolved** → Feature 14b (integrated with library, more UX detail) |
| Feature 3: Health Monitoring | Remains as-is in v0.2, independent of this PRD |
| Feature 4: Search Profiles | Remains as-is in v0.2, lower priority |
| Feature 5: WebSocket Activity | Remains as-is in v0.2, lower priority |
| Feature 6: Backup & Restore | Remains as-is in v0.2, lower priority |
| Feature 7: Notifications | **Evolved** → Feature 14a (Discord webhook, event-specific, rich embeds) |
| Feature 8: Smart Scheduling | **Superseded** by Features 12 + 13 (adaptive prioritization + cooldown intelligence) |
| Feature 9: Analytics | Remains as-is in v0.2, lower priority |

---

## Open Questions

1. **Prowlarr API stability:** Prowlarr's API is less documented than Sonarr/Radarr. Need to verify indexer rate limit fields are reliably available.
2. **Season pack threshold:** Default 3+ missing episodes triggers season search. Should this be configurable per queue or global?
3. **Feedback loop delay:** 15 minutes between search and status check. Too short (Sonarr may not have finished), too long (stale data)?
4. **Notification batching:** During a search run that finds 20 episodes, send 20 Discord messages or batch into 1 summary?
5. **Exclusion scope:** Should exclusions also prevent library sync from tracking the item, or just skip it during searches?
