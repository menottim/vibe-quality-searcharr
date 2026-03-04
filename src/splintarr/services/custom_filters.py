"""Custom filter application for the Custom search strategy."""

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


def _matches_filters(library_item: Any, filters: dict[str, Any]) -> bool:
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
    """Filter wanted records using custom filter configuration.

    Args:
        records: Sonarr/Radarr wanted API records (each has seriesId or series.id).
        library_items: Map of external_id -> LibraryItem for the instance.
        filters: Custom filter config dict with optional keys: sources, year_min,
                 year_max, quality_profiles, statuses.

    Returns:
        Filtered list of records that match all active filter criteria.
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
