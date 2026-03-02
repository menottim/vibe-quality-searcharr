# Table Header Tooltips Design

**Date:** 2026-03-02
**Status:** Approved

## Overview

Add hover tooltips to non-obvious table headers across the app using Pico CSS's built-in `data-tooltip` attribute. Migrate existing `title` attributes to `data-tooltip` for consistency.

## Approach

- Use `data-tooltip="..."` on `<th>` elements (Pico CSS native, zero JS)
- Only on headers where meaning isn't immediately clear
- Migrate 3 existing `title` attributes to `data-tooltip`

## Tooltip Inventory

### Dashboard - Recent Search Activity (`dashboard/index.html`)

| Header | Tooltip |
|--------|---------|
| Strategy | Search strategy used (missing, cutoff, recent, etc.) |
| Status | Whether the search completed, failed, or was skipped |
| Items | Searched: sent to indexer. Eligible: matched queue filters. |

### Dashboard - Indexer Health (`dashboard/index.html`)

| Header | Tooltip |
|--------|---------|
| Query Limit | Maximum queries allowed per day by the indexer |
| Queries Used | Number of queries consumed today |

### Search History (`dashboard/search_history.html`)

| Header | Tooltip |
|--------|---------|
| Strategy | Search strategy used (missing, cutoff, recent, etc.) |
| Status | Whether the search completed, failed, or was skipped |
| Items | Searched: sent to indexer. Eligible: matched queue filters. |
| Duration | How long the search execution took |

### Search Queue Detail - Execution History (`dashboard/search_queue_detail.html`)

| Header | Tooltip | Notes |
|--------|---------|-------|
| Searched | Items sent to Sonarr/Radarr for search | Migrate from `title` |
| Eligible | Items matching queue filters that were candidates for searching | Migrate from `title` |

### Search Queue Detail - API Details nested table (`dashboard/search_queue_detail.html`)

| Header | Tooltip |
|--------|---------|
| Score | Search priority score based on intelligence settings |
| Command | API command sent to Sonarr/Radarr |

### Exclusions (`dashboard/exclusions.html`)

| Header | Tooltip |
|--------|---------|
| Expires | When this exclusion will automatically be removed |

## Headers Excluded (self-explanatory)

Instance, Queue, Title, Type, Reason, Started, Time, Item, Result, Indexer, empty action column.

## Also Migrate

The `Items` column tooltip text in `dashboard/index.html` uses a `title` attribute on a `<span>` inside the `<td>` (not the `<th>`). This inline tooltip should also be migrated to `data-tooltip` for consistency.
