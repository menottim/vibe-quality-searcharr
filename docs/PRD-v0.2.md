# Splintarr v0.2 — Product Requirements Document

## Target User

Solo homelab operator managing 3-5 Sonarr/Radarr instances. Simplicity over configurability. Multi-user is out of scope.

## Current State (v0.1.0-alpha)

Splintarr is a Docker-first homelab application that automates intelligent backlog searching for Sonarr and Radarr instances. It currently provides:

- Multi-instance Sonarr/Radarr management with encrypted API keys
- 4 automated search strategies (missing, cutoff_unmet, recent, custom)
- Background job scheduling via APScheduler
- JWT authentication with 2FA (TOTP), account lockout, token rotation
- SQLCipher-encrypted database
- Server-rendered dashboard with Pico CSS
- Search history tracking and statistics
- CLI for admin password resets

---

## v0.2.0 — Ship First

### Feature 1: Sonarr/Radarr Sync & Library Overview

**Priority:** High
**Effort:** Medium

**Problem:** Users can't see what's in their Sonarr/Radarr libraries from within Splintarr. They must switch between apps to understand what's missing and what's been found.

**Use case:** Full library browsing — poster art, episode lists, quality status — without switching apps. A read-only mirror of Sonarr/Radarr data inside Splintarr.

**Requirements:**
- Pull and cache series/movie lists from connected instances
- Library overview page: total series/movies, percent complete, recently added
- Per-series/movie detail: which episodes are missing, quality status, last searched date
- "Missing content" view: aggregated list across all instances of what hasn't been found
- Show series/movie poster art (cached locally from instance)
- Refresh button and configurable auto-sync interval (default: every 6 hours)
- Responsive grid layout with poster cards

**Data model changes:** New `library_items` table (id, instance_id, content_type, external_id, title, year, status, quality_profile, episode_count, episode_have, metadata_json, poster_path, last_synced_at). New `library_episodes` table for per-episode tracking (Sonarr only).

---

### Feature 2: Content Exclusion Lists

**Priority:** High
**Effort:** Low

**Problem:** Users have content they don't want Splintarr searching for — abandoned series, movies they don't care about upgrading, problematic releases. Currently there's no way to skip specific items.

**Requirements:**
- Per-instance or global exclusion lists
- Exclude by: series/movie ID, title pattern (regex), tag
- Temporary exclusions with expiration date ("ignore for 30 days")
- Exclusion applies across all search strategies for the instance
- UI to manage exclusions: add from library view or search results, bulk add
- Simple list management (add, remove, view active exclusions)

**Data model changes:** New `search_exclusions` table (id, instance_id, exclusion_type, value, reason, expires_at, created_at)

---

### Feature 3: Health Monitoring & Auto-Recovery

**Priority:** High
**Effort:** Medium

**Problem:** When a Sonarr/Radarr instance goes down, queues fail silently until the user notices. The current 5-failure auto-deactivation burns through the failure budget and doesn't auto-recover when the instance comes back.

**Requirements:**
- Periodic health checks: ping each instance every N minutes (configurable, default 5)
- Auto-pause queues when instance is unreachable (instead of burning through failure budget)
- Auto-resume queues when instance recovers, with a backoff period
- Dashboard health indicator: green/yellow/red per instance with tooltip showing last check time and latency
- Connection quality metrics: average response time, timeout rate, error rate over last 24h
- Health status timeline: show uptime/downtime history per instance

**Data model changes:** New `health_checks` table (instance_id, checked_at, success, response_time_ms, error_message). Add `health_check_interval_minutes` to `instances`.

---

## v0.2.1 — Ship Next

### Feature 4: Search Profiles & Templates

**Priority:** Medium
**Effort:** Low

**Problem:** Creating search queues is repetitive with 3-5 instances. Same strategy, same interval, same filters — configured manually each time.

**Requirements:**
- Search profile templates: save a queue configuration as a reusable template
- Built-in defaults: "Aggressive Missing" (hourly, missing strategy), "Weekly Upgrade" (weekly, cutoff_unmet), "New Releases" (every 4 hours, recent)
- Apply template to multiple instances at once (batch queue creation)
- Import/export profiles as JSON for sharing between Splintarr installations
- Clone existing queue as a starting point for a new one

**Data model changes:** New `search_profiles` table (id, user_id, name, strategy, interval_hours, filters, is_builtin, created_at)

---

### Feature 5: Real-Time Activity Feed with WebSocket

**Priority:** Medium
**Effort:** Medium

**Problem:** The dashboard uses AJAX polling (every 30 seconds) for updates. There's always a delay between an action and seeing the result. Watching searches happen live would be satisfying and useful for debugging.

**Requirements:**
- WebSocket endpoint at `/ws/activity` for real-time updates
- Events streamed: search started, search completed, search failed, instance health changed, queue status changed
- Dashboard auto-updates without page refresh when WebSocket connected
- Graceful fallback to polling if WebSocket connection fails
- Connection indicator in dashboard header (green dot = live, grey = polling)
- Per-search live progress: items scanned / total, currently searching episode/movie name

**Technical notes:** FastAPI natively supports WebSocket. Use a simple in-process event bus (no need for Redis at single-worker scale). JWT cookie auth for WebSocket connection.

---

### Feature 6: Backup & Restore

**Priority:** Medium
**Effort:** Low

**Problem:** The SQLCipher-encrypted database is a single point of failure. No way to recover from corruption or hardware failure.

**Use case:** Disaster recovery — scheduled automatic backups with restore capability.

**Requirements:**
- Full backup: encrypted database dump downloadable from settings page
- Scheduled automatic backups: daily, keep last N backups (configurable, default 7)
- Backup storage: local path (Docker volume mount)
- Restore wizard: upload backup file, verify integrity, restore
- Database integrity check: run `PRAGMA integrity_check` on demand
- Configuration-only export as JSON (instances, queues, settings — API keys excluded)

**Data model changes:** New `backups` table (id, backup_type, file_path, file_size, created_at, status). Add settings for backup schedule and retention.

**Deferred:** S3-compatible external storage, config import wizard.

---

## v0.3.0+ — Deferred

### Feature 7: Webhook Notifications

**Priority:** Low
**Effort:** Medium

**Problem:** No way to know when searches fail or find content without checking the dashboard.

**Approach:** Use Apprise library for 80+ notification service support. Global notification settings (not per-instance). Events: search failed, new content found, queue paused, instance connection lost. Failures + content found only — no noise on routine empty searches.

**Data model changes:** New `notification_config` table (id, apprise_url, events_filter, is_active)

---

### Feature 8: Smart Search Scheduling

**Priority:** Low
**Effort:** Medium

**Problem:** Fixed intervals are wasteful for shows with known release schedules and insufficient for newly-aired content.

**Approach:** Calendar-aware scheduling, blackout windows, adaptive intervals based on Sonarr calendar data. Keep simple "every X hours" as default. Current fixed intervals work fine for now.

---

### Feature 9: Search Analytics Dashboard

**Priority:** Low
**Effort:** Medium

**Problem:** Current dashboard shows basic counts but no trends, strategy comparison, or instance performance data.

**Approach:** Time-series charts, strategy comparison, instance comparison. Lightweight chart library bundled locally (no CDN). Somewhat useful for occasional glancing but not a daily need.

---

## Implementation Priority Matrix

| # | Feature | Priority | Effort | Release |
|---|---------|----------|--------|---------|
| 1 | Library Overview | High | Medium | v0.2.0 |
| 2 | Exclusion Lists | High | Low | v0.2.0 |
| 3 | Health Monitoring | High | Medium | v0.2.0 |
| 4 | Search Profiles | Medium | Low | v0.2.1 |
| 5 | WebSocket Activity | Medium | Medium | v0.2.1 |
| 6 | Backup & Restore | Medium | Low | v0.2.1 |
| 7 | Notifications | Low | Medium | v0.3.0+ |
| 8 | Smart Scheduling | Low | Medium | v0.3.0+ |
| 9 | Analytics Dashboard | Low | Medium | v0.3.0+ |

## Open Questions

1. **Library sync frequency:** How often should we pull series/movie lists? Every 6 hours by default, but large libraries could be expensive. Consider incremental sync (only fetch changes since last sync) using Sonarr/Radarr's `since` parameter.
2. **Poster storage:** Cache poster images locally (disk usage) or proxy them through Splintarr on demand (adds latency)? Local cache is more resilient when instances are down.
3. **Exclusion granularity:** Should exclusions work at the episode level (e.g., "skip S01 but search S02+") or only at the series/movie level?
4. **Health check scope:** Should health checks test just connectivity (`/api/v3/system/status`) or also verify API key validity and instance configuration hasn't drifted?
5. **Backup encryption:** Should config-only JSON exports be encrypted? Users may want to edit the JSON, but API keys (even excluded) could leak if the file is shared.
