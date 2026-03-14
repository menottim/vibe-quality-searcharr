"""Tests for Sonarr history API method."""
from unittest.mock import AsyncMock, patch

import pytest

from splintarr.services.sonarr import SonarrClient


class TestGetHistory:
    """Test get_history method."""

    @pytest.mark.asyncio
    async def test_returns_grabbed_records(self):
        mock_response = {
            "records": [
                {
                    "id": 1,
                    "episodeId": 42,
                    "eventType": "grabbed",
                    "date": "2026-03-14T10:30:00Z",
                    "sourceTitle": "Show.S01E01.1080p.WEB-DL",
                    "downloadId": "abc123",
                },
            ]
        }
        async with SonarrClient(
            url="http://localhost:8989",
            api_key="test-key-that-is-long-enough",
        ) as client:
            with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_response):
                result = await client.get_history(episode_id=42, event_type="grabbed")
                assert len(result) == 1
                assert result[0]["episodeId"] == 42
                assert result[0]["eventType"] == "grabbed"

    @pytest.mark.asyncio
    async def test_passes_correct_params(self):
        mock_response = {"records": []}
        async with SonarrClient(
            url="http://localhost:8989",
            api_key="test-key-that-is-long-enough",
        ) as client:
            with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_response) as mock_req:
                await client.get_history(episode_id=42, event_type="grabbed")
                mock_req.assert_called_once_with(
                    "GET",
                    "/api/v3/history",
                    params={"episodeId": 42, "eventType": "grabbed", "pageSize": 10},
                )

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_records(self):
        mock_response = {"records": []}
        async with SonarrClient(
            url="http://localhost:8989",
            api_key="test-key-that-is-long-enough",
        ) as client:
            with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_response):
                result = await client.get_history(episode_id=99)
                assert result == []
