# v0.2.0 Implementation Plan: Exclusion Lists & Discord Notifications

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship v0.2.0 with Content Exclusion Lists and Discord Webhook Notifications.

**Architecture:** Two independent features sharing no data models. Exclusion Lists add a new `search_exclusions` table, a service for CRUD + search-time lookup, API routes for management, and UI (new Exclusions nav page + "Exclude" button on library detail). Discord Notifications add a `notification_config` table, a stateless webhook service, hooks in search execution/queue failure/instance health, and a Settings section for webhook configuration.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy/SQLCipher, Jinja2/Pico CSS, httpx (for Discord webhooks), structlog

---

## Task 1: SearchExclusion Data Model

**Files:**
- Create: `src/splintarr/models/exclusion.py`
- Modify: `src/splintarr/models/__init__.py`
- Modify: `src/splintarr/models/instance.py` (add relationship)
- Modify: `src/splintarr/models/user.py` (add relationship)
- Modify: `src/splintarr/database.py` (add to init_db imports)

**Step 1:** Create `src/splintarr/models/exclusion.py` with `SearchExclusion` model:
- Columns: id, user_id (FK users.id CASCADE), instance_id (FK instances.id CASCADE), library_item_id (nullable int), external_id (int, indexed), content_type (enum series/movie), title (String 500), reason (Text nullable), expires_at (DateTime nullable, indexed), created_at (server_default=func.now())
- Relationships: user, instance
- Properties: `is_active` (checks expires_at vs utcnow), `expiry_label` ("Permanent" or date string)
- Follow exact patterns from `models/library.py`: comment= on every column, __repr__, etc.

**Step 2:** Add `SearchExclusion` to `models/__init__.py` exports and `database.py` init_db imports.

**Step 3:** Add `search_exclusions` relationship to `Instance` model (cascade delete) and `User` model.

**Step 4:** Run lint: `.venv/bin/ruff check src/splintarr/models/exclusion.py`

**Step 5:** Commit: `feat: add SearchExclusion data model`

---

## Task 2: Exclusion Service

**Files:**
- Create: `src/splintarr/services/exclusion.py`

**Step 1:** Create `ExclusionService` class with `db_session_factory` constructor (same pattern as `LibrarySyncService`).

**Step 2:** Implement methods:
- `get_active_exclusion_keys(user_id, instance_id)` → `set[tuple[int, str]]` — loads active (unexpired) exclusion (external_id, content_type) pairs in one query. Called once per search run.
- `create_exclusion(user_id, instance_id, external_id, content_type, title, library_item_id=None, reason=None, duration="permanent")` — idempotent (refreshes expiry if exists). Duration: "permanent", "7d", "30d", "90d".
- `delete_exclusion(exclusion_id, user_id)` → bool
- `list_exclusions(user_id, instance_id=None, include_expired=False)` → list
- `cleanup_expired(user_id=None)` — delete all expired exclusions

**Step 3:** Add structlog logging at every operation (info for create/delete, debug for list/load).

**Step 4:** Lint and commit: `feat: add ExclusionService for search exclusion management`

---

## Task 3: Integrate Exclusions into Search Execution

**Files:**
- Modify: `src/splintarr/services/search_queue.py`

**Step 1:** In `_search_paginated_records`, before the record iteration loop:
- Load exclusion keys via `ExclusionService.get_active_exclusion_keys()`
- Need to pass user_id through — get it from the Instance's user_id

**Step 2:** Inside the record loop, before cooldown check:
- Check if `(external_id, content_type)` is in the exclusion set
- If excluded: append to search_log with `action: "skipped", reason: "excluded"`, continue
- Log at debug level: `item_excluded`

**Step 3:** The ExclusionService needs access to db_session_factory. Pass it through from SearchQueueManager, or instantiate per-call since it's lightweight.

**Step 4:** Run tests to verify no regression: `.venv/bin/python -m pytest tests/unit/ --no-cov -q --ignore=tests/unit/test_config.py`

**Step 5:** Commit: `feat: integrate exclusion checks into search execution`

---

## Task 4: Exclusion API Routes

**Files:**
- Create: `src/splintarr/api/exclusions.py`
- Modify: `src/splintarr/main.py` (register router)

**Step 1:** Create `src/splintarr/api/exclusions.py` with routes:

HTML pages:
- `GET /dashboard/exclusions` — list all active exclusions with filters (instance, content_type). `active_page="exclusions"`.
- Template: `dashboard/exclusions.html`

JSON API:
- `POST /api/exclusions` — create exclusion (body: instance_id, external_id, content_type, title, library_item_id, reason, duration)
- `POST /api/exclusions/bulk` — bulk create (body: items list + duration)
- `DELETE /api/exclusions/{exclusion_id}` — delete exclusion
- All scoped by `current_user.id`
- Rate limited: 30/minute for list, 10/minute for create/delete

**Step 2:** Register router in `main.py`.

**Step 3:** Lint and commit: `feat: add exclusion API routes`

---

## Task 5: Exclusion Templates & Nav

**Files:**
- Create: `src/splintarr/templates/dashboard/exclusions.html`
- Modify: `src/splintarr/templates/base.html` (add nav item)
- Modify: `src/splintarr/templates/dashboard/library_detail.html` (add Exclude button)
- Modify: `src/splintarr/templates/dashboard/library.html` (add excluded badge)

**Step 1:** Add "Exclusions" nav item to `base.html` between Library and Queues:
```html
<li>
    <a href="/dashboard/exclusions" class="{{ 'active' if active_page == 'exclusions' else '' }}">
        <span class="nav-icon">&#10007;</span>
        <span class="nav-label">Exclusions</span>
    </a>
</li>
```

**Step 2:** Create `exclusions.html` template:
- Table listing: Title, Instance, Type, Reason, Expires, Created, Delete button
- Filters: instance dropdown, content type, show expired toggle
- Empty state: "No exclusions. Exclude items from the Library page."

**Step 3:** Add "Exclude" button to `library_detail.html`:
- Button/dialog below the item metadata
- Fields: reason (optional), duration dropdown (permanent/7d/30d/90d)
- AJAX POST to `/api/exclusions`
- Show success notification

**Step 4:** In `library.html` poster grid, show an "excluded" badge overlay on cards where the item is excluded. This requires passing exclusion data to the template — query excluded external_ids in the library route.

**Step 5:** Commit: `feat: add exclusion UI — nav page, library integration, badges`

---

## Task 6: NotificationConfig Data Model

**Files:**
- Create: `src/splintarr/models/notification.py`
- Modify: `src/splintarr/models/__init__.py`
- Modify: `src/splintarr/database.py`

**Step 1:** Create `NotificationConfig` model:
- Columns: id, user_id (FK users.id CASCADE), webhook_url (Text, Fernet-encrypted), events_enabled (Text, JSON string), is_active (Boolean default True), last_sent_at (DateTime nullable), created_at, updated_at
- events_enabled stores JSON: `{"search_triggered": true, "queue_failed": true, "instance_health": true, "library_sync": true}`

**Step 2:** Add to `__init__.py` and `database.py` init_db.

**Step 3:** Commit: `feat: add NotificationConfig data model`

---

## Task 7: Discord Notification Service

**Files:**
- Create: `src/splintarr/services/discord.py`

**Step 1:** Create `DiscordNotificationService`:
- Stateless class (no singleton needed)
- Constructor takes `webhook_url: str` (decrypted)
- `send_search_summary(search_name, instance_name, strategy, items_searched, items_found, search_log)` — one embed per run
- `send_queue_failed(queue_name, instance_name, error, consecutive_failures)`
- `send_instance_health(instance_name, status, error)`
- `send_test_message()` — sends a test embed

**Step 2:** Each method builds a Discord embed dict and POSTs to the webhook URL via httpx:
```python
async def _send_embed(self, embed: dict) -> bool:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            self.webhook_url,
            json={"embeds": [embed]},
            timeout=10.0,
        )
        return response.status_code == 204
```

**Step 3:** Embed format: title, description, color (green=success, red=failure, blue=info), fields for details, timestamp. Poster thumbnail if available.

**Step 4:** Add rate limiting: track last_sent_at per event type, skip if < 5 minutes.

**Step 5:** Comprehensive structlog logging.

**Step 6:** Commit: `feat: add Discord webhook notification service`

---

## Task 8: Hook Notifications into Search Execution

**Files:**
- Modify: `src/splintarr/services/search_queue.py`

**Step 1:** After `history.mark_completed()` in `execute_queue()`, check if user has an active notification config.

**Step 2:** If notifications enabled for `search_triggered` and `items_found > 0`, call `send_search_summary()` with the search results.

**Step 3:** In the exception handler (search failed), if `queue_failed` enabled, call `send_queue_failed()`.

**Step 4:** Notifications are fire-and-forget — wrap in try/except, log errors but never fail the search.

**Step 5:** Commit: `feat: hook Discord notifications into search execution`

---

## Task 9: Notification Settings UI

**Files:**
- Modify: `src/splintarr/templates/dashboard/settings.html`
- Create or modify: `src/splintarr/api/notifications.py` or add to existing settings routes

**Step 1:** Add "Notifications" section to settings.html (between 2FA and Danger Zone):
- Webhook URL input field
- Event toggles: checkboxes for each event type
- Enable/disable master toggle
- "Test Notification" button
- "Save" button

**Step 2:** API endpoints:
- `GET /api/notifications/config` — get current config (URL masked)
- `POST /api/notifications/config` — save config (encrypt URL)
- `POST /api/notifications/test` — send test message
- All scoped by user_id

**Step 3:** Commit: `feat: add notification settings UI with webhook config and test button`

---

## Task 10: Final Integration & Testing

**Step 1:** Run full test suite: `.venv/bin/python -m pytest tests/unit/ tests/integration/ tests/security/ --no-cov -q --ignore=tests/unit/test_config.py`

**Step 2:** Run lint: `.venv/bin/ruff check src/splintarr/`

**Step 3:** Build and start Docker container for manual UX testing

**Step 4:** Walk through:
- Create an exclusion from library detail page
- Verify it appears on the Exclusions page
- Verify excluded badge shows on library grid
- Verify search execution skips excluded items (check search log)
- Configure Discord webhook in settings
- Send test notification
- Verify notification settings persist

**Step 5:** Tear down Docker

**Step 6:** Create PRs (separate for exclusions and notifications)

---

## PR Breakdown

| PR | Scope | Tasks |
|----|-------|-------|
| PR A | Exclusion Lists: model + service + search integration | Tasks 1-3 |
| PR B | Exclusion Lists: API routes + templates + nav | Tasks 4-5 |
| PR C | Discord Notifications: model + service | Tasks 6-7 |
| PR D | Discord Notifications: search hooks + settings UI | Tasks 8-9 |

Each PR is independently reviewable and testable. PRs A and C can be developed in parallel.
