# Tiered Error Logging via Global Exception Handlers

**Date**: 2026-02-26
**Status**: Approved

## Problem

HTTP error responses (422 validation errors, 404s, rate limit errors) are not logged anywhere. Pydantic validation happens before endpoint code runs, so the try-except blocks in endpoints never fire. The existing 404 handler doesn't log. Only 500 errors are explicitly logged.

## Solution

Add three global FastAPI exception handlers in `main.py` with tiered log levels:

| Error Type | Log Level | Destination |
|---|---|---|
| `RequestValidationError` (422) | WARNING | all.log |
| `HTTPException` 4xx | WARNING | all.log |
| `HTTPException` 5xx | ERROR | all.log + error.log |
| Unhandled `Exception` | ERROR | all.log + error.log |

## Handlers

### 1. RequestValidationError handler
- Logs field-level validation details at WARNING
- Returns same 422 JSON response FastAPI normally returns
- Structured log: event, path, method, error details

### 2. HTTPException handler
- Replaces default + consolidates existing 404/500 handlers
- 4xx → WARNING, 5xx → ERROR
- Returns same JSON format
- Structured log: event, path, method, status_code, detail

### 3. Catch-all Exception handler
- Logs at ERROR with full traceback
- Returns generic 500 response
- Safety net for unexpected errors

## Log format

```json
{"event": "http_validation_error", "path": "/api/search-queues", "method": "POST", "errors": [...], "level": "warning"}
{"event": "http_client_error", "path": "/api/foo", "status_code": 404, "level": "warning"}
{"event": "http_server_error", "path": "/api/bar", "status_code": 500, "error": "...", "level": "error"}
{"event": "unhandled_exception", "path": "/api/baz", "error": "...", "level": "error"}
```

## Files changed

- `main.py` — Add 3 exception handlers, remove existing 404/500 handlers (consolidated)

## Files NOT changed

- `logging_config.py` — Handler levels already correct
- Endpoint error logging — Business-logic `logger.error()` calls remain
- Response formats — Clients see same JSON responses
