"""Tests for global exception handlers in main.py."""

import logging

import pytest


class TestRequestValidationErrorHandler:
    """Tests for 422 validation error logging."""

    def test_validation_error_returns_422(self, client):
        """Validation errors still return 422 with error details."""
        response = client.post(
            "/api/auth/login",
            json={"username": 123},
        )
        assert response.status_code == 422

    def test_validation_error_logs_warning(self, client, caplog):
        """Validation errors are logged at WARNING level."""
        with caplog.at_level(logging.WARNING):
            client.post(
                "/api/auth/login",
                json={"username": 123},
            )

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "http_validation_error" in getattr(r, "msg", str(r.getMessage()))
            for r in warning_records
        ), "Expected a WARNING log containing 'http_validation_error'"

    def test_validation_error_response_contains_details(self, client):
        """Validation error response includes field-level error details."""
        response = client.post(
            "/api/auth/login",
            json={"username": 123},
        )
        data = response.json()
        assert "detail" in data


class TestHTTPExceptionHandler:
    """Tests for HTTPException logging (4xx and 5xx)."""

    def test_404_returns_json(self, client):
        """404 errors return JSON response."""
        response = client.get("/api/nonexistent-endpoint-that-does-not-exist")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_404_logs_warning(self, client, caplog):
        """404 errors are logged at WARNING level."""
        with caplog.at_level(logging.WARNING):
            client.get("/api/nonexistent-endpoint-that-does-not-exist")

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) > 0, "Expected a WARNING log for 404 error"


class TestUnhandledExceptionHandler:
    """Tests for catch-all unhandled exception logging."""

    def test_unhandled_exception_returns_500(self, client):
        """Unhandled exceptions return 500 with generic message."""
        from vibe_quality_searcharr.main import app
        from fastapi import Request

        @app.get("/test-crash")
        async def crash_endpoint(request: Request):
            raise RuntimeError("test unhandled crash")

        try:
            response = client.get("/test-crash")
            assert response.status_code == 500
            data = response.json()
            assert data["detail"] == "Internal server error"
        finally:
            # Clean up the test route
            app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != "/test-crash"]

    def test_unhandled_exception_logs_error(self, client, caplog):
        """Unhandled exceptions are logged at ERROR level."""
        import logging
        from vibe_quality_searcharr.main import app
        from fastapi import Request

        @app.get("/test-crash-log")
        async def crash_log_endpoint(request: Request):
            raise RuntimeError("test logging crash")

        try:
            with caplog.at_level(logging.ERROR):
                client.get("/test-crash-log")

            error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
            assert any(
                "unhandled" in getattr(r, "msg", str(r.getMessage())).lower()
                for r in error_records
            ), "Expected an ERROR log containing 'unhandled'"
        finally:
            app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != "/test-crash-log"]
