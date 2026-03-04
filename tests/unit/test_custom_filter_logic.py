"""Tests for apply_custom_filters() — custom search strategy filter application."""

from splintarr.services.custom_filters import apply_custom_filters


class _FakeLibraryItem:
    """Minimal stand-in for models.library.LibraryItem with filter-relevant attrs."""

    def __init__(
        self,
        year: int | None = None,
        status: str | None = None,
        quality_profile: str | None = None,
    ):
        self.year = year
        self.status = status
        self.quality_profile = quality_profile


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _record(series_id: int, episode_id: int = 1) -> dict:
    """Build a minimal Sonarr wanted-API record."""
    return {"seriesId": series_id, "id": episode_id}


def _library(
    year: int | None = 2020,
    status: str = "continuing",
    quality_profile: str = "HD-1080p",
) -> _FakeLibraryItem:
    return _FakeLibraryItem(year=year, status=status, quality_profile=quality_profile)


# ---------------------------------------------------------------------------
# No active filters — passthrough
# ---------------------------------------------------------------------------


class TestNoActiveFilters:
    """When only sources are set (no year/status/profile), all records pass."""

    def test_all_records_pass_through(self):
        records = [_record(1), _record(2), _record(3)]
        library_items = {
            1: _library(year=2000),
            2: _library(year=2010),
            3: _library(year=2020),
        }
        filters = {"sources": ["missing"]}

        result = apply_custom_filters(records, library_items, filters)
        assert result == records

    def test_records_without_library_item_pass_when_no_filters(self):
        """Records with no matching library item should pass when no filters active."""
        records = [_record(1), _record(99)]
        library_items = {1: _library()}
        filters = {"sources": ["missing"]}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Year filters
# ---------------------------------------------------------------------------


class TestYearMinFilter:
    """year_min excludes records whose library item year is below the threshold."""

    def test_excludes_below_year_min(self):
        records = [_record(1), _record(2)]
        library_items = {
            1: _library(year=1999),
            2: _library(year=2000),
        }
        filters = {"sources": ["missing"], "year_min": 2000}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 1
        assert result[0]["seriesId"] == 2

    def test_year_min_boundary_included(self):
        records = [_record(1)]
        library_items = {1: _library(year=2000)}
        filters = {"sources": ["missing"], "year_min": 2000}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 1

    def test_year_min_with_null_year_excluded(self):
        """Library item with year=None should be excluded when year_min is set."""
        records = [_record(1)]
        library_items = {1: _library(year=None)}
        filters = {"sources": ["missing"], "year_min": 2000}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 0


class TestYearMaxFilter:
    """year_max excludes records whose library item year is above the threshold."""

    def test_excludes_above_year_max(self):
        records = [_record(1), _record(2)]
        library_items = {
            1: _library(year=2025),
            2: _library(year=2026),
        }
        filters = {"sources": ["missing"], "year_max": 2025}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 1
        assert result[0]["seriesId"] == 1

    def test_year_max_boundary_included(self):
        records = [_record(1)]
        library_items = {1: _library(year=2025)}
        filters = {"sources": ["missing"], "year_max": 2025}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 1

    def test_year_max_with_null_year_excluded(self):
        """Library item with year=None should be excluded when year_max is set."""
        records = [_record(1)]
        library_items = {1: _library(year=None)}
        filters = {"sources": ["missing"], "year_max": 2025}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Quality profile filter
# ---------------------------------------------------------------------------


class TestQualityProfileFilter:
    """quality_profiles filter only includes records with matching profiles."""

    def test_includes_matching_profiles(self):
        records = [_record(1), _record(2), _record(3)]
        library_items = {
            1: _library(quality_profile="HD-1080p"),
            2: _library(quality_profile="SD"),
            3: _library(quality_profile="Ultra-HD"),
        }
        filters = {
            "sources": ["missing"],
            "quality_profiles": ["HD-1080p", "Ultra-HD"],
        }

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 2
        assert {r["seriesId"] for r in result} == {1, 3}

    def test_excludes_non_matching_profile(self):
        records = [_record(1)]
        library_items = {1: _library(quality_profile="SD")}
        filters = {"sources": ["missing"], "quality_profiles": ["HD-1080p"]}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Status filter
# ---------------------------------------------------------------------------


class TestStatusFilter:
    """statuses filter only includes records with matching statuses."""

    def test_includes_matching_statuses(self):
        records = [_record(1), _record(2), _record(3)]
        library_items = {
            1: _library(status="continuing"),
            2: _library(status="ended"),
            3: _library(status="upcoming"),
        }
        filters = {
            "sources": ["missing"],
            "statuses": ["continuing", "ended"],
        }

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 2
        assert {r["seriesId"] for r in result} == {1, 2}

    def test_excludes_non_matching_status(self):
        records = [_record(1)]
        library_items = {1: _library(status="deleted")}
        filters = {"sources": ["missing"], "statuses": ["continuing"]}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Combined filters
# ---------------------------------------------------------------------------


class TestCombinedFilters:
    """When multiple filters are active, all must match (AND logic)."""

    def test_all_filters_must_match(self):
        records = [_record(1), _record(2), _record(3), _record(4)]
        library_items = {
            1: _library(year=2020, status="continuing", quality_profile="HD-1080p"),
            2: _library(year=1990, status="continuing", quality_profile="HD-1080p"),
            3: _library(year=2020, status="ended", quality_profile="HD-1080p"),
            4: _library(year=2020, status="continuing", quality_profile="SD"),
        }
        filters = {
            "sources": ["missing"],
            "year_min": 2000,
            "statuses": ["continuing"],
            "quality_profiles": ["HD-1080p"],
        }

        result = apply_custom_filters(records, library_items, filters)
        # Only record 1 matches all three criteria
        assert len(result) == 1
        assert result[0]["seriesId"] == 1

    def test_year_range_with_status(self):
        records = [_record(1), _record(2), _record(3)]
        library_items = {
            1: _library(year=2010, status="continuing"),
            2: _library(year=2020, status="ended"),
            3: _library(year=2025, status="continuing"),
        }
        filters = {
            "sources": ["missing"],
            "year_min": 2010,
            "year_max": 2020,
            "statuses": ["continuing"],
        }

        result = apply_custom_filters(records, library_items, filters)
        # Record 1: year=2010 in range, continuing -> pass
        # Record 2: year=2020 in range, ended -> fail (status)
        # Record 3: year=2025 out of range -> fail (year_max)
        assert len(result) == 1
        assert result[0]["seriesId"] == 1


# ---------------------------------------------------------------------------
# Missing library item with active filters
# ---------------------------------------------------------------------------


class TestMissingLibraryItem:
    """Records without a matching library item are excluded when filters active."""

    def test_excluded_when_filters_active(self):
        records = [_record(1), _record(99)]
        library_items = {1: _library(year=2020)}
        filters = {"sources": ["missing"], "year_min": 2000}

        result = apply_custom_filters(records, library_items, filters)
        # Record 99 has no library item -> excluded
        assert len(result) == 1
        assert result[0]["seriesId"] == 1

    def test_empty_library_items_excludes_all(self):
        records = [_record(1), _record(2)]
        library_items: dict = {}
        filters = {"sources": ["missing"], "statuses": ["continuing"]}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for the filter function."""

    def test_empty_records_returns_empty(self):
        result = apply_custom_filters([], {}, {"sources": ["missing"], "year_min": 2000})
        assert result == []

    def test_empty_filters_dict_passthrough(self):
        """Empty filters dict (no active filters) should pass all records through."""
        records = [_record(1)]
        library_items = {1: _library()}
        result = apply_custom_filters(records, library_items, {})
        assert result == records

    def test_record_with_nested_series_id(self):
        """Some Sonarr endpoints nest the series ID under series.id."""
        records = [{"series": {"id": 1}, "id": 10}]
        library_items = {1: _library(year=2020)}
        filters = {"sources": ["missing"], "year_min": 2000}

        result = apply_custom_filters(records, library_items, filters)
        assert len(result) == 1

    def test_empty_quality_profiles_list_not_active(self):
        """An empty quality_profiles list should not count as an active filter."""
        records = [_record(1)]
        library_items = {1: _library(quality_profile="SD")}
        filters = {"sources": ["missing"], "quality_profiles": []}

        result = apply_custom_filters(records, library_items, filters)
        assert result == records

    def test_empty_statuses_list_not_active(self):
        """An empty statuses list should not count as an active filter."""
        records = [_record(1)]
        library_items = {1: _library(status="deleted")}
        filters = {"sources": ["missing"], "statuses": []}

        result = apply_custom_filters(records, library_items, filters)
        assert result == records
