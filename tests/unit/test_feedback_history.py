"""Tests for feedback check using Sonarr history API."""
from unittest.mock import AsyncMock

import pytest

from splintarr.services.feedback import FeedbackCheckService


class TestCheckSonarrEpisodeViaHistory:
    """Test _check_sonarr_episode uses history API instead of hasFile."""

    @pytest.mark.asyncio
    async def test_confirms_grab_when_history_has_grabbed_event_after_command(self):
        """A grabbed event AFTER command_issued_at = confirmed grab."""
        service = FeedbackCheckService(db=None)
        mock_client = AsyncMock()
        mock_client.get_history = AsyncMock(return_value=[
            {
                "episodeId": 42,
                "eventType": "grabbed",
                "date": "2026-03-14T10:35:00Z",
                "sourceTitle": "Show.S01E01.1080p",
            },
        ])

        entry = {
            "item_id": 42,
            "series_id": 100,
            "command_issued_at": "2026-03-14T10:30:00Z",
        }

        result = await service._check_sonarr_episode(mock_client, entry)
        assert result is True
        assert entry.get("source_title") == "Show.S01E01.1080p"

    @pytest.mark.asyncio
    async def test_rejects_grab_when_history_event_before_command(self):
        """A grabbed event BEFORE command_issued_at = not our grab."""
        service = FeedbackCheckService(db=None)
        mock_client = AsyncMock()
        mock_client.get_history = AsyncMock(return_value=[
            {
                "episodeId": 42,
                "eventType": "grabbed",
                "date": "2026-03-14T10:25:00Z",
                "sourceTitle": "Show.S01E01.720p",
            },
        ])

        entry = {
            "item_id": 42,
            "series_id": 100,
            "command_issued_at": "2026-03-14T10:30:00Z",
        }

        result = await service._check_sonarr_episode(mock_client, entry)
        assert result is False
        assert "source_title" not in entry

    @pytest.mark.asyncio
    async def test_rejects_grab_when_no_history(self):
        """No grabbed events = no grab."""
        service = FeedbackCheckService(db=None)
        mock_client = AsyncMock()
        mock_client.get_history = AsyncMock(return_value=[])

        entry = {
            "item_id": 42,
            "series_id": 100,
            "command_issued_at": "2026-03-14T10:30:00Z",
        }

        result = await service._check_sonarr_episode(mock_client, entry)
        assert result is False

    @pytest.mark.asyncio
    async def test_fallback_to_hasfile_when_no_timestamp(self):
        """If command_issued_at is missing (old data), fall back to hasFile check."""
        service = FeedbackCheckService(db=None)
        mock_client = AsyncMock()
        mock_client.get_episodes = AsyncMock(return_value=[
            {"id": 42, "hasFile": True},
        ])

        entry = {
            "item_id": 42,
            "series_id": 100,
        }

        result = await service._check_sonarr_episode(mock_client, entry)
        assert result is True
