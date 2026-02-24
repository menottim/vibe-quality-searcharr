# Phase 5: Search Scheduling - Implementation Documentation

## Overview

Phase 5 implements the core automation functionality for Vibe-Quality-Searcharr - the search scheduler that orchestrates systematic backlog searching across Sonarr/Radarr instances.

## Components Implemented

### 1. Search Scheduler Service (`services/scheduler.py`)

**Purpose:** Background job management using APScheduler for automated search execution.

**Key Features:**
- AsyncIOScheduler with SQLAlchemy job store for persistence
- Graceful lifecycle management (start/stop/pause/resume)
- Automatic loading of existing queues on startup
- Job scheduling for recurring and one-time searches
- Event listeners for job execution tracking
- Misfire grace time and job coalescing

**Key Methods:**
- `start()` - Initialize and start the scheduler
- `stop(wait=True)` - Gracefully shutdown the scheduler
- `pause()` / `resume()` - Pause/resume job execution
- `schedule_queue(queue_id, reschedule=False)` - Schedule a search queue
- `unschedule_queue(queue_id)` - Remove a queue from scheduler
- `get_status()` - Get scheduler status and job list

**Configuration:**
```python
jobstores = {
    "default": SQLAlchemyJobStore(url=database_url, tablename="apscheduler_jobs")
}

job_defaults = {
    "coalesce": True,              # Combine missed runs
    "max_instances": 1,            # One instance per job
    "misfire_grace_time": 300,     # 5 minutes grace
}
```

### 2. Search Queue Manager (`services/search_queue.py`)

**Purpose:** Executes search strategies and manages search queue operations.

**Search Strategies:**

1. **Missing Strategy** - Searches for all missing episodes/movies
2. **Cutoff Unmet Strategy** - Searches for items not meeting quality cutoff
3. **Recent Strategy** - Prioritizes recently added/aired content
4. **Custom Strategy** - User-defined filters (extensible)

**Key Features:**
- Rate limiting using token bucket algorithm
- Search cooldown tracking (default 24 hours per item)
- Batch processing with pagination
- Error handling and partial success tracking
- Integration with Sonarr/Radarr clients
- Search history recording

**Rate Limiting:**
```python
# Token bucket algorithm
- tokens_per_second: configurable per instance (default: 5.0)
- Tokens replenish over time
- Each search consumes 1 token
- Requests blocked when no tokens available
```

**Cooldown Tracking:**
```python
# Prevents duplicate searches
- Default: 24 hours per item
- Tracked in memory: {item_key: last_search_time}
- Format: "sonarr_{instance_id}_episode_{episode_id}"
```

### 3. Search History Service (`services/search_history.py`)

**Purpose:** Track and analyze search execution history.

**Key Features:**
- History retrieval with filtering (instance, queue, strategy, status, dates)
- Statistical analysis (success rates, trends)
- Performance metrics per queue
- Recent failures for troubleshooting
- History cleanup (configurable retention period)

**Statistics Provided:**
- Total searches / successful / failed
- Success rate percentage
- Items searched / found
- Average duration
- Searches by strategy breakdown
- Daily trend data

### 4. Search Queue API (`api/search_queue.py`)

**Endpoints:**

```
POST   /api/search-queues              - Create search queue
GET    /api/search-queues              - List all queues
GET    /api/search-queues/{id}         - Get queue details
PUT    /api/search-queues/{id}         - Update queue
DELETE /api/search-queues/{id}         - Delete queue
POST   /api/search-queues/{id}/start   - Manually trigger search
POST   /api/search-queues/{id}/pause   - Pause queue
POST   /api/search-queues/{id}/resume  - Resume queue
GET    /api/search-queues/{id}/status  - Get queue status
```

**Authentication:** All endpoints require JWT authentication

**Authorization:** Users can only access queues for their own instances

**Request Example:**
```json
{
  "instance_id": 1,
  "name": "Daily Missing Episodes",
  "strategy": "missing",
  "recurring": true,
  "interval_hours": 24
}
```

**Response Example:**
```json
{
  "id": 1,
  "instance_id": 1,
  "name": "Daily Missing Episodes",
  "strategy": "missing",
  "recurring": true,
  "interval_hours": 24,
  "is_active": true,
  "status": "pending",
  "next_run": "2024-01-16T10:00:00Z",
  "last_run": null,
  "consecutive_failures": 0,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 5. Search History API (`api/search_history.py`)

**Endpoints:**

```
GET    /api/search-history             - List history with filters
GET    /api/search-history/stats       - Get statistics
DELETE /api/search-history             - Clean up old history
GET    /api/search-history/failures    - Get recent failures
GET    /api/search-history/queue/{id}  - Get queue history
```

**Query Parameters:**
- `instance_id` - Filter by instance
- `queue_id` - Filter by queue
- `strategy` - Filter by strategy
- `status` - Filter by status
- `start_date` / `end_date` - Date range filter
- `limit` / `offset` - Pagination

## Integration with Main App

### Startup Event
```python
@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...

    # Start search scheduler
    await start_scheduler(get_session_factory())
    logger.info("search_scheduler_started")
```

### Shutdown Event
```python
@app.on_event("shutdown")
async def shutdown_event():
    # Stop search scheduler
    await stop_scheduler()
    logger.info("search_scheduler_stopped")

    # ... existing shutdown code ...
```

### Router Registration
```python
# Include routers
app.include_router(auth.router)
app.include_router(instances.router)
app.include_router(search_queue.router)      # NEW
app.include_router(search_history.router)    # NEW
```

## Database Schema

### APScheduler Jobs Table
Created automatically by APScheduler:
```sql
CREATE TABLE apscheduler_jobs (
    id VARCHAR(191) PRIMARY KEY,
    next_run_time REAL,
    job_state BLOB NOT NULL
);
```

### Existing Tables Used
- `search_queue` - Queue configuration and status
- `search_history` - Execution history records
- `instances` - Sonarr/Radarr instance details

## Testing

### Unit Tests

**Scheduler Tests** (`tests/unit/test_scheduler.py`):
- Lifecycle operations (start/stop/pause/resume)
- Job scheduling (recurring and one-time)
- Queue loading on startup
- Status reporting

**Queue Manager Tests** (`tests/unit/test_search_queue_manager.py`):
- Strategy execution (missing, cutoff, recent, custom)
- Rate limiting enforcement
- Cooldown period tracking
- Error handling

**History Service Tests** (`tests/unit/test_search_history_service.py`):
- History retrieval with filtering
- Statistics calculation
- Cleanup operations
- Performance metrics

### Integration Tests

**API Tests** (`tests/integration/test_search_queue_api.py`):
- CRUD operations
- Authentication and authorization
- Input validation
- Queue control operations

### Running Tests

```bash
# Run all Phase 5 tests
pytest tests/unit/test_scheduler.py -v
pytest tests/unit/test_search_queue_manager.py -v
pytest tests/unit/test_search_history_service.py -v
pytest tests/integration/test_search_queue_api.py -v

# Run with coverage
pytest --cov=src/vibe_quality_searcharr/services/scheduler.py
pytest --cov=src/vibe_quality_searcharr/services/search_queue.py
pytest --cov=src/vibe_quality_searcharr/services/search_history.py
pytest --cov=src/vibe_quality_searcharr/api/search_queue.py
pytest --cov=src/vibe_quality_searcharr/api/search_history.py
```

## Configuration

### Environment Variables

```bash
# Search Settings
SEARCH_INTERVAL_HOURS=24           # Default search interval
MAX_CONCURRENT_SEARCHES=5          # Max simultaneous searches

# Rate Limiting
API_REQUEST_TIMEOUT=30             # Timeout for API requests
API_MAX_RETRIES=3                  # Max retry attempts
```

### Search Queue Configuration

**Recurring Search:**
```json
{
  "instance_id": 1,
  "name": "Daily Missing Check",
  "strategy": "missing",
  "recurring": true,
  "interval_hours": 24
}
```

**One-time Search:**
```json
{
  "instance_id": 1,
  "name": "Initial Backlog Scan",
  "strategy": "missing",
  "recurring": false
}
```

**Custom Strategy:**
```json
{
  "instance_id": 1,
  "name": "Quality Upgrades",
  "strategy": "custom",
  "recurring": true,
  "interval_hours": 48,
  "filters": {
    "quality": "Bluray-1080p",
    "minDays": 30
  }
}
```

## Security Considerations

### Authentication
- All API endpoints require JWT authentication
- Token validation on every request

### Authorization
- Users can only access queues for their own instances
- Instance ownership verified on all operations

### Rate Limiting
- Per-instance rate limits enforced
- Prevents overwhelming Sonarr/Radarr servers
- Configurable tokens per second

### API Key Security
- API keys encrypted in database using Fernet
- Decrypted only during search execution
- Never exposed in API responses

### Input Validation
- All inputs validated using Pydantic schemas
- SQL injection prevention via ORM
- XSS protection via FastAPI

## Performance Considerations

### Database Queries
- Indexed columns: `instance_id`, `is_active`, `status`, `next_run`
- Pagination support for large result sets
- Connection pooling for concurrent access

### Memory Management
- Cooldown tracking: in-memory cache with TTL
- Rate limit tokens: per-instance tracking
- Job state: persisted to database

### Concurrency
- AsyncIO for non-blocking I/O
- APScheduler handles job execution
- Thread-safe database operations

## Error Handling

### Queue Execution Errors
```python
try:
    result = await execute_search()
except Exception as e:
    queue.mark_failed(str(e))
    history.mark_failed(str(e))
    # Deactivate after 5 consecutive failures
```

### Scheduler Errors
```python
try:
    await scheduler.start()
except Exception as e:
    logger.error("scheduler_start_failed", error=str(e))
    # App continues in read-only mode
```

### API Errors
- 401 Unauthorized - Authentication required
- 403 Forbidden - Access denied
- 404 Not Found - Resource not found
- 422 Unprocessable Entity - Validation error
- 500 Internal Server Error - Server error

## Monitoring and Logging

### Structured Logging
```python
logger.info("search_queue_executed",
    queue_id=queue_id,
    status=result["status"],
    items_searched=result["items_searched"],
    items_found=result["items_found"]
)
```

### Metrics Tracked
- Searches per hour
- Success rate
- Items found rate
- Average duration
- Error rate by type

### Health Checks
```python
GET /health
{
  "status": "healthy",
  "scheduler": {
    "running": true,
    "jobs_count": 5
  }
}
```

## Future Enhancements

### Priority-Based Strategy
- Use quality profile cutoff scores
- Factor in aging (older + high priority)
- Configurable priority weights

### Aging-Based Strategy
- Oldest missing items first
- Use air date or added date
- Help catch long-missing content

### Advanced Custom Filters
- Quality profile filtering
- Tag-based filtering
- Series/movie filtering
- Season/year range filtering

### Webhook Notifications
- Success/failure notifications
- Configurable webhook endpoints
- Custom payload templates

### Search Analytics Dashboard
- Visual trends and charts
- Success rate over time
- Items found per strategy
- Instance performance comparison

## Troubleshooting

### Scheduler Not Starting
1. Check database connection
2. Verify APScheduler dependencies
3. Check log for error messages
4. Ensure database migrations applied

### Searches Not Executing
1. Verify queue is active
2. Check next_run time
3. Verify instance credentials
4. Check rate limit settings

### High Failure Rate
1. Check recent failures endpoint
2. Verify API key validity
3. Check instance connectivity
4. Review error messages in history

### Performance Issues
1. Reduce concurrent searches
2. Increase rate limit interval
3. Add cooldown period
4. Limit batch size

## Code Statistics

### Lines of Code
- `scheduler.py`: ~500 lines
- `search_queue.py`: ~650 lines
- `search_history.py`: ~350 lines
- `search_queue.py` (API): ~550 lines
- `search_history.py` (API): ~300 lines
- **Total Production Code**: ~2,350 lines

### Test Coverage
- Unit tests: ~600 lines
- Integration tests: ~400 lines
- **Total Test Code**: ~1,000 lines
- **Target Coverage**: 80%+

## Dependencies

### Required Packages
```toml
apscheduler = "^3.11.0"      # Job scheduling
httpx = "^0.27.0"            # Async HTTP client
tenacity = "^9.0.0"          # Retry logic
structlog = "^24.4.0"        # Structured logging
```

### Development Packages
```toml
pytest = "^8.3.0"
pytest-asyncio = "^0.25.0"
pytest-mock = "^3.14.0"
```

## Conclusion

Phase 5 successfully implements the core automation functionality for Vibe-Quality-Searcharr. The search scheduler provides reliable, configurable, and efficient automated searching across Sonarr/Radarr instances with comprehensive error handling, monitoring, and security features.

The implementation follows best practices:
- Clean architecture with separation of concerns
- Comprehensive error handling
- Security-first design
- Extensive testing
- Detailed logging and monitoring
- Performance optimization

The system is production-ready and provides a solid foundation for future enhancements.
