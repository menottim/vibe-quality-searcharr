# Custom Strategy Filters Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the "Custom" search strategy with dropdown filters for year range, quality profile, series status, and combined missing + cutoff unmet sources.

**Architecture:** The custom strategy replaces its stub with a multi-source fetch (missing + cutoff APIs), deduplication, and a filter step applied against LibraryItem data before the existing scoring/cooldown/exclusion pipeline. The `filters` JSON column on SearchQueue already exists. UI adds a conditional filter section to the queue creation modal.

**Tech Stack:** Pydantic (filter schema validation), SQLAlchemy (quality profile query), Jinja2 (filter UI), httpx (Sonarr API), existing scoring pipeline

---

### Task 1: CustomFilterConfig Pydantic Model + Schema Changes

**Files:**
- Modify: `src/splintarr/schemas/search.py:16` (add "custom" to SearchStrategy)
- Modify: `src/splintarr/schemas/search.py:70-73` (replace dict filters with CustomFilterConfig)
- Test: `tests/unit/test_custom_filter_schema.py`

**Step 1: Write failing tests**

Create `tests/unit/test_custom_filter_schema.py`:

```python
"""Tests for CustomFilterConfig schema validation."""

import pytest
from pydantic import ValidationError

from splintarr.schemas.search import CustomFilterConfig, SearchQueueCreate


class TestCustomFilterConfig:
    """Validate filter schema."""

    def test_valid_minimal(self):
        config = CustomFilterConfig(sources=["missing"])
        assert config.sources == ["missing"]
        assert config.year_min is None
        assert config.year_max is None
        assert config.quality_profiles == []
        assert config.statuses == []

    def test_valid_full(self):
        config = CustomFilterConfig(
            sources=["missing", "cutoff_unmet"],
            year_min=2020,
            year_max=2026,
            quality_profiles=["HD-1080p", "Ultra-HD"],
            statuses=["continuing", "ended"],
        )
        assert config.sources == ["missing", "cutoff_unmet"]
        assert config.year_min == 2020

    def test_empty_sources_rejected(self):
        with pytest.raises(ValidationError):
            CustomFilterConfig(sources=[])

    def test_invalid_source_rejected(self):
        with pytest.raises(ValidationError):
            CustomFilterConfig(sources=["invalid"])

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            CustomFilterConfig(sources=["missing"], statuses=["bogus"])

    def test_year_min_greater_than_max_rejected(self):
        with pytest.raises(ValidationError):
            CustomFilterConfig(sources=["missing"], year_min=2026, year_max=2020)


class TestSearchQueueCreateCustomStrategy:
    """Validate custom strategy requires filters."""

    def test_custom_strategy_accepted(self):
        data = SearchQueueCreate(
            instance_id=1,
            name="Test Custom",
            strategy="custom",
            filters=CustomFilterConfig(sources=["missing"]),
        )
        assert data.strategy == "custom"
        assert data.filters is not None

    def test_custom_strategy_without_filters_rejected(self):
        with pytest.raises(ValidationError):
            SearchQueueCreate(
                instance_id=1,
                name="Test Custom",
                strategy="custom",
                filters=None,
            )

    def test_non_custom_strategy_with_filters_rejected(self):
        with pytest.raises(ValidationError):
            SearchQueueCreate(
                instance_id=1,
                name="Test",
                strategy="missing",
                filters=CustomFilterConfig(sources=["missing"]),
            )
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_custom_filter_schema.py -v --no-cov`
Expected: ImportError — `CustomFilterConfig` does not exist.

**Step 3: Implement schema changes**

In `src/splintarr/schemas/search.py`:

1. Add "custom" to `SearchStrategy` (line 16):
```python
SearchStrategy = Literal["missing", "cutoff_unmet", "recent", "custom"]
```

2. Add `CustomFilterConfig` model before `SearchQueueCreate`:
```python
class CustomFilterConfig(BaseModel):
    """Configuration for custom strategy filters."""

    sources: list[Literal["missing", "cutoff_unmet"]] = Field(
        ..., min_length=1, description="Data sources to fetch from"
    )
    year_min: int | None = Field(None, ge=1900, le=2100, description="Minimum year")
    year_max: int | None = Field(None, ge=1900, le=2100, description="Maximum year")
    quality_profiles: list[str] = Field(
        default_factory=list, description="Quality profile names to include (empty = all)"
    )
    statuses: list[Literal["continuing", "ended", "upcoming", "deleted"]] = Field(
        default_factory=list, description="Series statuses to include (empty = all)"
    )

    @model_validator(mode="after")
    def validate_year_range(self) -> "CustomFilterConfig":
        if self.year_min and self.year_max and self.year_min > self.year_max:
            raise ValueError("year_min must be <= year_max")
        return self
```

3. Change `filters` field type in `SearchQueueCreate` (line 70-73):
```python
    filters: CustomFilterConfig | None = Field(
        None, description="Custom filter configuration (required when strategy='custom')"
    )
```

4. Add validator to `SearchQueueCreate`:
```python
    @model_validator(mode="after")
    def validate_custom_strategy_filters(self) -> "SearchQueueCreate":
        if self.strategy == "custom" and self.filters is None:
            raise ValueError("Custom strategy requires filters")
        if self.strategy != "custom" and self.filters is not None:
            raise ValueError("Filters only allowed with custom strategy")
        return self
```

5. Same changes to `SearchQueueUpdate` filters field and add a similar validator (but allow both None since update is partial — only reject filters with non-custom strategy if strategy is explicitly set).

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/test_custom_filter_schema.py -v --no-cov`
Expected: All PASS.

**Step 5: Commit**

```bash
git add src/splintarr/schemas/search.py tests/unit/test_custom_filter_schema.py
git commit -m "feat: add CustomFilterConfig schema with validation"
```

---

### Task 2: Filter Application Logic — Tests

**Files:**
- Create: `tests/unit/test_custom_filter_logic.py`

**Step 1: Write failing tests**

```python
"""Tests for custom filter application logic."""

import pytest

from splintarr.services.custom_filters import apply_custom_filters


class TestApplyCustomFilters:
    """Test filter matching against library items."""

    def _make_record(self, series_id: int, episode_id: int = 1) -> dict:
        return {"seriesId": series_id, "id": episode_id}

    def _make_library_item(self, year=2023, status="continuing", quality_profile="HD-1080p"):
        """Create a mock library item."""
        class MockItem:
            pass
        item = MockItem()
        item.year = year
        item.status = status
        item.quality_profile = quality_profile
        return item

    def test_no_filters_passes_all(self):
        records = [self._make_record(1), self._make_record(2)]
        lib_items = {1: self._make_library_item(), 2: self._make_library_item()}
        filters = {"sources": ["missing"]}
        result = apply_custom_filters(records, lib_items, filters)
        assert len(result) == 2

    def test_year_min_filter(self):
        records = [self._make_record(1), self._make_record(2)]
        lib_items = {
            1: self._make_library_item(year=2018),
            2: self._make_library_item(year=2023),
        }
        filters = {"sources": ["missing"], "year_min": 2020}
        result = apply_custom_filters(records, lib_items, filters)
        assert len(result) == 1

    def test_year_max_filter(self):
        records = [self._make_record(1), self._make_record(2)]
        lib_items = {
            1: self._make_library_item(year=2018),
            2: self._make_library_item(year=2023),
        }
        filters = {"sources": ["missing"], "year_max": 2020}
        result = apply_custom_filters(records, lib_items, filters)
        assert len(result) == 1

    def test_quality_profile_filter(self):
        records = [self._make_record(1), self._make_record(2)]
        lib_items = {
            1: self._make_library_item(quality_profile="HD-1080p"),
            2: self._make_library_item(quality_profile="Ultra-HD"),
        }
        filters = {"sources": ["missing"], "quality_profiles": ["Ultra-HD"]}
        result = apply_custom_filters(records, lib_items, filters)
        assert len(result) == 1

    def test_status_filter(self):
        records = [self._make_record(1), self._make_record(2)]
        lib_items = {
            1: self._make_library_item(status="continuing"),
            2: self._make_library_item(status="ended"),
        }
        filters = {"sources": ["missing"], "statuses": ["continuing"]}
        result = apply_custom_filters(records, lib_items, filters)
        assert len(result) == 1

    def test_combined_filters(self):
        records = [self._make_record(1), self._make_record(2), self._make_record(3)]
        lib_items = {
            1: self._make_library_item(year=2023, status="continuing", quality_profile="Ultra-HD"),
            2: self._make_library_item(year=2018, status="continuing", quality_profile="Ultra-HD"),
            3: self._make_library_item(year=2023, status="ended", quality_profile="SD"),
        }
        filters = {
            "sources": ["missing"],
            "year_min": 2020,
            "statuses": ["continuing"],
            "quality_profiles": ["Ultra-HD"],
        }
        result = apply_custom_filters(records, lib_items, filters)
        assert len(result) == 1  # Only record 1 matches all

    def test_record_without_library_item_excluded(self):
        records = [self._make_record(1)]
        lib_items = {}  # No library data
        filters = {"sources": ["missing"], "year_min": 2020}
        result = apply_custom_filters(records, lib_items, filters)
        assert len(result) == 0

    def test_record_without_library_item_passes_when_no_filters(self):
        records = [self._make_record(1)]
        lib_items = {}
        filters = {"sources": ["missing"]}
        result = apply_custom_filters(records, lib_items, filters)
        assert len(result) == 1
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_custom_filter_logic.py -v --no-cov`
Expected: ImportError — `custom_filters` module does not exist.

**Step 3: Commit**

```bash
git add tests/unit/test_custom_filter_logic.py
git commit -m "test: add custom filter application logic tests (red)"
```

---

### Task 3: Filter Application Logic — Implementation

**Files:**
- Create: `src/splintarr/services/custom_filters.py`

**Step 1: Implement the filter module**

```python
"""
Custom filter application for the Custom search strategy.

Filters wanted records against LibraryItem data (year, status, quality profile)
before they enter the scoring/cooldown/exclusion pipeline.
"""

from typing import Any

import structlog

logger = structlog.get_logger()


def _has_active_filters(filters: dict[str, Any]) -> bool:
    """Check if any filters beyond sources are set."""
    return bool(
        filters.get("year_min")
        or filters.get("year_max")
        or filters.get("quality_profiles")
        or filters.get("statuses")
    )


def _matches_filters(
    library_item: Any, filters: dict[str, Any]
) -> bool:
    """Check if a library item matches all active filters."""
    year_min = filters.get("year_min")
    if year_min and (library_item.year is None or library_item.year < year_min):
        return False

    year_max = filters.get("year_max")
    if year_max and (library_item.year is None or library_item.year > year_max):
        return False

    quality_profiles = filters.get("quality_profiles", [])
    if quality_profiles and library_item.quality_profile not in quality_profiles:
        return False

    statuses = filters.get("statuses", [])
    if statuses and library_item.status not in statuses:
        return False

    return True


def apply_custom_filters(
    records: list[dict[str, Any]],
    library_items: dict[int, Any],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Filter wanted records using custom filter configuration.

    Args:
        records: List of wanted records from Sonarr API
        library_items: Dict of external_id -> LibraryItem
        filters: Parsed filter config dict

    Returns:
        Filtered list of records that match all active filters
    """
    if not _has_active_filters(filters):
        return records

    filtered = []
    for record in records:
        ext_id = record.get("seriesId") or record.get("series", {}).get("id")
        library_item = library_items.get(ext_id) if ext_id else None

        if library_item is None:
            logger.debug("custom_filter_no_library_item", external_id=ext_id)
            continue

        if _matches_filters(library_item, filters):
            filtered.append(record)
        else:
            logger.debug(
                "custom_filter_excluded",
                external_id=ext_id,
                year=library_item.year,
                status=library_item.status,
                quality_profile=library_item.quality_profile,
            )

    logger.info(
        "custom_filters_applied",
        total=len(records),
        passed=len(filtered),
        excluded=len(records) - len(filtered),
    )
    return filtered
```

**Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/test_custom_filter_logic.py -v --no-cov`
Expected: All PASS.

**Step 3: Commit**

```bash
git add src/splintarr/services/custom_filters.py
git commit -m "feat: add custom filter application logic"
```

---

### Task 4: Custom Strategy Execution — Tests

**Files:**
- Create: `tests/unit/test_custom_strategy.py`

**Step 1: Write tests for the custom strategy execution**

Tests should verify:
- Custom strategy with `sources: ["missing"]` only fetches missing records
- Custom strategy with `sources: ["cutoff_unmet"]` only fetches cutoff records
- Custom strategy with `sources: ["missing", "cutoff_unmet"]` fetches both and deduplicates
- Filters are applied before scoring (filtered items don't appear in results)

These tests will mock the Sonarr client and DB session. Follow the same pattern as existing search_queue tests.

**Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_custom_strategy.py -v --no-cov`

**Step 3: Commit**

```bash
git add tests/unit/test_custom_strategy.py
git commit -m "test: add custom strategy execution tests (red)"
```

---

### Task 5: Custom Strategy Execution — Implementation

**Files:**
- Modify: `src/splintarr/services/search_queue.py:979-1020` (replace stub)

**Step 1: Replace the custom strategy stub**

Replace `_execute_custom_strategy` (lines 979-1020) with implementation that:

1. Parses `queue.filters` JSON
2. Fetches from all configured sources (missing and/or cutoff_unmet)
3. Deduplicates by `(series_id, episode_id)` — missing record wins on conflict
4. Loads LibraryItem records for filtering
5. Applies custom filters via `apply_custom_filters()`
6. Feeds filtered records into existing pipeline via `_search_paginated_records()`

**Key change:** Add a `prefetched_records` parameter to `_search_paginated_records`. When provided, skip the API fetch step and use the provided records directly. This avoids duplicating the scoring/cooldown/exclusion pipeline.

In `_search_paginated_records`, add parameter:
```python
    prefetched_records: list[dict[str, Any]] | None = None,
```

And conditionally skip the fetch block:
```python
    if prefetched_records is not None:
        all_records = prefetched_records
    else:
        # Existing fetch logic...
```

**Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/test_custom_strategy.py tests/unit/test_custom_filter_logic.py -v --no-cov`
Expected: All PASS.

**Step 3: Commit**

```bash
git add src/splintarr/services/search_queue.py
git commit -m "feat: implement custom strategy with multi-source fetch and filters"
```

---

### Task 6: Quality Profiles API Endpoint

**Files:**
- Modify: `src/splintarr/api/instances.py` (add endpoint)
- Create: `tests/unit/test_quality_profiles_api.py`

**Step 1: Write failing tests**

Tests for `GET /api/instances/{id}/quality-profiles`:
- Returns distinct profiles for instance
- Returns empty list when no library items
- Auth required
- Instance not found returns 404

**Step 2: Implement endpoint**

In `src/splintarr/api/instances.py`, add:

```python
@router.get("/{instance_id}/quality-profiles", include_in_schema=False)
@limiter.limit("30/minute")
async def get_quality_profiles(
    request: Request,
    instance_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Return distinct quality profile names for an instance's library items."""
    instance = (
        db.query(Instance)
        .filter(Instance.id == instance_id, Instance.user_id == current_user.id)
        .first()
    )
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    from splintarr.models.library import LibraryItem

    profiles = (
        db.query(LibraryItem.quality_profile)
        .filter(
            LibraryItem.instance_id == instance_id,
            LibraryItem.quality_profile.isnot(None),
        )
        .distinct()
        .order_by(LibraryItem.quality_profile)
        .all()
    )
    return JSONResponse(content={"profiles": [p[0] for p in profiles]})
```

**Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/test_quality_profiles_api.py -v --no-cov`

**Step 4: Commit**

```bash
git add src/splintarr/api/instances.py tests/unit/test_quality_profiles_api.py
git commit -m "feat: add quality profiles endpoint for custom filter UI"
```

---

### Task 7: Queue Creation UI — Custom Filter Section

**Files:**
- Modify: `src/splintarr/templates/dashboard/search_queues.html`

**Step 1: Add "Custom" to strategy dropdown**

In the strategy `<select>` (around line 158), add:
```html
<option value="custom">Custom - Advanced filters</option>
```

**Step 2: Add filter section HTML**

After the strategy dropdown and before the queue name field, add a conditional filter section with fieldset containing: source checkboxes, year range inputs, status checkboxes, and a quality profile container div.

**Step 3: Add JavaScript for show/hide and quality profile loading**

- Show/hide custom filter section based on strategy dropdown value
- On instance change, fetch `/api/instances/{id}/quality-profiles` and build checkboxes using DOM construction (createElement, NOT innerHTML — use `document.createElement('label')` and `document.createElement('input')` for XSS safety)
- Update `getFormData()` to serialize filter checkboxes/inputs into the `filters` JSON field when strategy is "custom", or set `filters: null` otherwise
- Add validation: at least one source must be checked when strategy is custom

**Step 4: Commit**

```bash
git add src/splintarr/templates/dashboard/search_queues.html
git commit -m "feat: add custom filter UI to queue creation modal"
```

---

### Task 8: Preview Integration

**Files:**
- Modify: `src/splintarr/services/search_queue.py` (preview_queue method, around line 1072)

**Step 1: Update preview to apply custom filters**

The preview method already validates custom filters JSON (lines 1072-1077). Add filter application after fetching records and loading library items:

```python
    # Apply custom filters (for custom strategy)
    if queue.strategy == "custom" and filters:
        from splintarr.services.custom_filters import apply_custom_filters
        all_records = apply_custom_filters(all_records, library_items, filters)
```

Also update preview to fetch from both sources when custom strategy has both sources configured (fetch missing + cutoff, combine, deduplicate — same logic as the execution path).

**Step 2: Add tests**

Create `tests/unit/test_custom_preview.py` with mock tests verifying preview respects custom filters.

**Step 3: Commit**

```bash
git add src/splintarr/services/search_queue.py tests/unit/test_custom_preview.py
git commit -m "feat: integrate custom filters with preview/dry-run"
```

---

### Task 9: Queue Edit UI for Custom Filters

**Files:**
- Modify: `src/splintarr/templates/dashboard/search_queues.html` (edit modal)

**Step 1: Pre-populate filters when editing a custom queue**

When the edit modal opens for a custom queue:
1. Detect if strategy is "custom" and show filter section
2. Parse `queue.filters` JSON
3. Set source checkboxes, year inputs, status checkboxes
4. Fetch and populate quality profile checkboxes, pre-checking the saved ones

**Step 2: Commit**

```bash
git add src/splintarr/templates/dashboard/search_queues.html
git commit -m "feat: pre-populate custom filters in queue edit modal"
```

---

### Task 10: Integration Tests

**Files:**
- Create: `tests/integration/test_custom_strategy_integration.py`

**Step 1: Write integration tests**

- Queue creation with custom strategy saves filters JSON correctly
- Queue edit preserves and updates filters
- Non-custom strategy rejects filters
- Custom strategy without filters rejected
- Quality profiles endpoint returns correct data

**Step 2: Run all tests**

Run: `.venv/bin/python -m pytest tests/ --no-cov -q`
Expected: No new failures.

**Step 3: Commit**

```bash
git add tests/integration/test_custom_strategy_integration.py
git commit -m "test: add integration tests for custom strategy filters"
```

---

### Task 11: Lint, Type Check & Final Verification

**Step 1: Run linting**

Run: `.venv/bin/ruff check src/splintarr/services/custom_filters.py src/splintarr/schemas/search.py src/splintarr/api/instances.py`

**Step 2: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ --no-cov -q`

**Step 3: Fix any issues and commit**

```bash
git add -u
git commit -m "chore: lint and type fixes for custom strategy filters"
```

---

### Summary

| Task | What | Files |
|------|------|-------|
| 1 | CustomFilterConfig schema + validation | `schemas/search.py`, tests |
| 2 | Filter logic tests (red) | `tests/unit/test_custom_filter_logic.py` |
| 3 | Filter logic implementation (green) | `services/custom_filters.py` |
| 4 | Custom strategy execution tests (red) | `tests/unit/test_custom_strategy.py` |
| 5 | Custom strategy execution (green) | `services/search_queue.py` |
| 6 | Quality profiles API endpoint | `api/instances.py`, tests |
| 7 | Queue creation UI — filter section | `templates/dashboard/search_queues.html` |
| 8 | Preview integration | `services/search_queue.py`, tests |
| 9 | Queue edit UI | `templates/dashboard/search_queues.html` |
| 10 | Integration tests | `tests/integration/` |
| 11 | Lint, types, final check | Various |
