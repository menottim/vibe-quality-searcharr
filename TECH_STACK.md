# Technology Stack Recommendation
## Vibe-Quality-Searcharr

**Version**: 1.0
**Date**: 2026-02-24
**Status**: Proposed

---

## Executive Summary

This document proposes the technology stack for Vibe-Quality-Searcharr based on the requirements established in the PRD, with emphasis on security, maintainability, and Docker-first deployment.

## Decision Criteria

1. **Security**: Strong cryptography libraries, active security maintenance
2. **Simplicity**: Straightforward implementation, minimal complexity
3. **Docker Support**: Easy containerization, small image sizes
4. **Library Ecosystem**: Mature libraries for password hashing, HTTP clients, scheduling
5. **Developer Experience**: Good tooling, clear documentation
6. **Performance**: Adequate for workload (not performance-critical application)
7. **Maintainability**: Long-term support, active community

---

## Recommended Stack

### Option A: Python (Recommended)

**Runtime**: Python 3.11+ (currently 3.13 is latest stable)

**Why Python:**
- ✅ Excellent cryptography libraries (`argon2-cffi`, `cryptography`)
- ✅ Strong ecosystem for HTTP APIs (`httpx`, `requests`)
- ✅ Mature web frameworks with security built-in
- ✅ Native async support for concurrent API calls
- ✅ Simple scheduler implementations
- ✅ SQLAlchemy ORM with SQLCipher support
- ✅ Easier to maintain for single developer
- ✅ Faster development for CRUD applications
- ✅ Type hints for safety (via `mypy`)

**Core Dependencies**:

```python
# Web Framework
fastapi = "^0.110.0"           # Modern async API framework
uvicorn = "^0.27.0"            # ASGI server
pydantic = "^2.6.0"            # Data validation

# Database
sqlalchemy = "^2.0.25"         # ORM
sqlcipher3 = "^0.5.2"          # SQLite encryption
alembic = "^1.13.0"            # Database migrations

# Authentication & Security
argon2-cffi = "^23.1.0"        # Password hashing (Argon2id)
python-jose = "^3.3.0"         # JWT tokens for sessions
python-multipart = "^0.0.9"    # Form data parsing
cryptography = "^42.0.0"       # AES encryption for API keys
pyotp = "^2.9.0"               # TOTP for 2FA

# HTTP Client
httpx = "^0.26.0"              # Async HTTP client for Sonarr/Radarr APIs

# Scheduling
apscheduler = "^3.10.4"        # Background job scheduling

# Utilities
python-dotenv = "^1.0.0"       # Environment variable loading
pyyaml = "^6.0.1"              # YAML config parsing
tenacity = "^8.2.3"            # Retry logic with backoff

# Testing
pytest = "^8.0.0"              # Testing framework
pytest-asyncio = "^0.23.0"     # Async test support
pytest-cov = "^4.1.0"          # Code coverage
httpx-mock = "^0.30.0"         # Mock HTTP responses
freezegun = "^1.4.0"           # Mock time for scheduler tests

# Security & Quality
bandit = "^1.7.6"              # Security linting
safety = "^3.0.0"              # Dependency vulnerability scanning
mypy = "^1.8.0"                # Type checking
ruff = "^0.1.15"               # Fast linter (replaces flake8, black, isort)

# Production
gunicorn = "^21.2.0"           # Production WSGI server (with uvicorn workers)
```

**Project Structure**:
```
vibe-quality-searcharr/
├── src/
│   ├── vibe_quality_searcharr/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── config.py               # Configuration management
│   │   ├── database.py             # Database session management
│   │   ├── models/                 # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── instance.py
│   │   │   ├── search_queue.py
│   │   │   └── search_history.py
│   │   ├── schemas/                # Pydantic schemas (API contracts)
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   └── instance.py
│   │   ├── api/                    # API routes
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── instances.py
│   │   │   ├── search.py
│   │   │   └── dashboard.py
│   │   ├── core/                   # Core business logic
│   │   │   ├── __init__.py
│   │   │   ├── security.py         # Password hashing, encryption
│   │   │   ├── auth.py             # Authentication logic
│   │   │   ├── scheduler.py        # Search scheduling
│   │   │   └── strategies.py       # Search strategies
│   │   ├── services/               # External service integrations
│   │   │   ├── __init__.py
│   │   │   ├── sonarr.py           # Sonarr API client
│   │   │   └── radarr.py           # Radarr API client (future)
│   │   ├── templates/              # Jinja2 HTML templates
│   │   │   ├── base.html
│   │   │   ├── dashboard.html
│   │   │   └── setup_wizard.html
│   │   └── static/                 # CSS, JS (minimal)
│   │       ├── css/
│   │       └── js/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── security/
├── alembic/                        # Database migrations
│   ├── versions/
│   └── env.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
├── pyproject.toml                  # Poetry dependency management
├── README.md
└── .env.example
```

---

### Option B: Node.js/TypeScript (Alternative)

**Runtime**: Node.js 20 LTS + TypeScript 5.x

**Why Node.js:**
- ✅ Strong async/await support (native to platform)
- ✅ Good TypeScript support for type safety
- ✅ Mature web frameworks (Express, Fastify)
- ✅ Excellent npm ecosystem

**Why NOT Node.js for this project:**
- ⚠️ SQLCipher integration more complex
- ⚠️ Argon2 binding requires native compilation
- ⚠️ More boilerplate for similar functionality
- ⚠️ Larger Docker images typically

**Core Dependencies** (if choosing Node.js):
```json
{
  "dependencies": {
    "fastify": "^4.26.0",
    "typeorm": "^0.3.20",
    "@fastify/cors": "^9.0.1",
    "@fastify/helmet": "^11.1.1",
    "argon2": "^0.31.2",
    "jsonwebtoken": "^9.0.2",
    "node-cron": "^3.0.3",
    "axios": "^1.6.7",
    "zod": "^3.22.4"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "@types/node": "^20.11.5",
    "vitest": "^1.2.1",
    "eslint": "^8.56.0",
    "@typescript-eslint/eslint-plugin": "^6.19.1"
  }
}
```

---

## Selected Stack: Python

**Recommendation: Use Python for Vibe-Quality-Searcharr MVP**

### Rationale:

1. **Security Libraries**: Python has best-in-class cryptography support
   - `argon2-cffi` is official Argon2 binding
   - `cryptography` is audited and actively maintained
   - `sqlcipher3` provides seamless SQLite encryption

2. **Development Speed**: Faster to implement CRUD operations and business logic
   - FastAPI auto-generates OpenAPI docs
   - Pydantic provides automatic validation
   - SQLAlchemy ORM reduces boilerplate

3. **Testing**: Mature testing ecosystem
   - pytest is industry standard
   - Easy to mock external APIs
   - Security testing tools (bandit, safety)

4. **Docker**: Official Python slim images are compact
   - `python:3.13-slim` base: ~140MB
   - Final image ~200-250MB with dependencies

5. **Personal Use**: Single developer, maintainability matters more than performance

---

## Web Framework: FastAPI

**Choice**: FastAPI over Flask/Django

**Why FastAPI:**
- ✅ Built-in async support (important for concurrent Sonarr/Radarr API calls)
- ✅ Automatic OpenAPI/Swagger documentation
- ✅ Pydantic integration for request/response validation (prevents injection)
- ✅ Modern Python type hints throughout
- ✅ Built-in dependency injection for auth
- ✅ Excellent performance (Starlette + Uvicorn)
- ✅ Security best practices by default
- ✅ Easy to add Jinja2 templates for web UI

**Why NOT Flask:**
- No async support without extensions
- Manual validation required
- No automatic API docs

**Why NOT Django:**
- Overkill for this application
- Heavier, more opinionated
- Admin interface not needed (custom dashboard)

---

## Database

**Primary**: SQLite 3.x with SQLCipher encryption
**ORM**: SQLAlchemy 2.0
**Migrations**: Alembic

**Why SQLite + SQLCipher:**
- ✅ Zero administration (serverless)
- ✅ Perfect for single-server deployment
- ✅ File-based storage (easy backups)
- ✅ SQLCipher provides transparent AES-256 encryption
- ✅ Adequate performance for workload (thousands of records, not millions)
- ✅ ACID compliant
- ✅ No network attack surface

**Why SQLAlchemy:**
- ✅ Prevents SQL injection via parameterized queries
- ✅ Automatic migrations via Alembic
- ✅ Type-safe queries
- ✅ Easy to switch to PostgreSQL later if needed

**Database File Security**:
```python
# SQLCipher connection string
SQLALCHEMY_DATABASE_URL = f"sqlite+pysqlcipher://:{encryption_key}@/data/vibe-quality-searcharr.db?cipher=aes-256-cfb&kdf_iter=256000"
```

**Future Option**: PostgreSQL 15+ (if multi-server deployment needed)

---

## Frontend

**Choice**: Server-Side Rendered HTML with minimal JavaScript

**Stack**:
- **Templates**: Jinja2 (built into FastAPI)
- **CSS**: Plain CSS or lightweight framework (Pico.css, Water.css)
- **JavaScript**: Vanilla JS for interactivity (no React/Vue for MVP)
- **Icons**: Heroicons or Feather Icons (SVG)

**Why SSR over SPA:**
- ✅ Simpler security model (no CORS complexity)
- ✅ Faster initial load
- ✅ Less JavaScript attack surface
- ✅ No build pipeline needed
- ✅ Works without JavaScript enabled
- ✅ Matches "technical interface" design goal

**Progressive Enhancement**:
- Core functionality works without JS
- HTMX or Alpine.js for dynamic updates (optional)
- WebSocket for live search queue updates (optional)

**Example Tech:**
```html
<!-- Lightweight CSS framework for technical UI -->
<link rel="stylesheet" href="https://unpkg.com/@picocss/pico@1/css/pico.min.css">

<!-- Optional: HTMX for dynamic updates without heavy JS -->
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
```

---

## Authentication & Security

### Password Hashing
**Library**: `argon2-cffi` (official Python binding)

```python
from argon2 import PasswordHasher
from argon2.low_level import Type

ph = PasswordHasher(
    time_cost=3,           # 3 iterations
    memory_cost=131072,    # 128 MiB
    parallelism=1,
    hash_len=32,
    salt_len=32,
    type=Type.ID           # Argon2id
)

# Hash password
hash = ph.hash(password)

# Verify password (constant time)
try:
    ph.verify(hash, password)
    # Password correct
except argon2.exceptions.VerifyMismatchError:
    # Password incorrect
```

### Session Management
**Library**: `python-jose` for JWT tokens

```python
from jose import jwt
from datetime import datetime, timedelta

# Generate session token
token = jwt.encode(
    {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
    },
    secret_key,
    algorithm="HS256"
)
```

### API Key Encryption (for Sonarr/Radarr)
**Library**: `cryptography` (Fernet - AES-128-CBC)

```python
from cryptography.fernet import Fernet

# Derive key from master password or use system-generated
cipher = Fernet(encryption_key)

# Encrypt API key before storing
encrypted_api_key = cipher.encrypt(api_key.encode())

# Decrypt when needed
decrypted_api_key = cipher.decrypt(encrypted_api_key).decode()
```

### 2FA (TOTP)
**Library**: `pyotp`

```python
import pyotp

# Generate secret
secret = pyotp.random_base32()

# Generate QR code URI
totp = pyotp.TOTP(secret)
uri = totp.provisioning_uri(
    name=username,
    issuer_name="Vibe-Quality-Searcharr"
)

# Verify code
is_valid = totp.verify(user_code, valid_window=1)
```

---

## HTTP Client for Sonarr/Radarr APIs

**Library**: `httpx` (async HTTP client)

**Why httpx over requests:**
- ✅ Native async/await support
- ✅ HTTP/2 support
- ✅ Same API as `requests` (familiar)
- ✅ Built-in retry logic
- ✅ Connection pooling
- ✅ Timeout controls

**Example**:
```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class SonarrClient:
    def __init__(self, base_url: str, api_key: str):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Api-Key": api_key},
            timeout=30.0,
            limits=httpx.Limits(max_connections=10)
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def get_wanted_missing(self, page: int = 1):
        response = await self.client.get(
            "/api/v3/wanted/missing",
            params={"page": page}
        )
        response.raise_for_status()
        return response.json()
```

---

## Scheduler

**Library**: APScheduler 3.x

**Why APScheduler:**
- ✅ Cron-like scheduling
- ✅ Interval-based jobs
- ✅ Persistent job store (SQLite)
- ✅ Job coalescing (prevents duplicate runs)
- ✅ Timezone support
- ✅ Integrates with async functions

**Example**:
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.db')
}

scheduler = AsyncIOScheduler(jobstores=jobstores)

# Add job: search every hour
scheduler.add_job(
    process_search_queue,
    'interval',
    hours=1,
    id='search_queue_processor',
    replace_existing=True
)

scheduler.start()
```

---

## Docker Configuration

### Base Image
**Choice**: `python:3.13-slim-bookworm`

**Why slim over alpine:**
- ✅ Easier to compile native extensions (argon2, cryptography)
- ✅ Better compatibility
- ✅ Slightly larger but more reliable
- ⚠️ Alpine has musl libc issues with some Python packages

### Multi-Stage Build
```dockerfile
# Build stage
FROM python:3.13-slim-bookworm AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Runtime stage
FROM python:3.13-slim-bookworm

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy only runtime dependencies
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

RUN mkdir -p /data && chown appuser:appuser /data

USER appuser

EXPOSE 7337

CMD ["uvicorn", "vibe_quality_searcharr.main:app", "--host", "0.0.0.0", "--port", "7337"]
```

**Image Size Target**: ~200-250 MB

---

## Development Tools

### Package Management
**Tool**: Poetry 1.7+

**Why Poetry:**
- ✅ Dependency resolution (better than pip)
- ✅ Lock file for reproducible builds
- ✅ Virtual environment management
- ✅ Build and publish (for future)

### Code Quality
- **Linter**: Ruff (fast, replaces flake8 + black + isort)
- **Type Checker**: mypy with strict mode
- **Security**: Bandit (SAST), Safety (dependency scanning)
- **Pre-commit hooks**: Run linting + security checks before commit

### Testing
- **Framework**: pytest
- **Coverage**: pytest-cov (target: 80%+)
- **Mocking**: pytest-mock, httpx-mock, freezegun
- **Async tests**: pytest-asyncio

### CI/CD
- **Platform**: GitHub Actions (assumed)
- **Workflow**:
  1. Lint (ruff, mypy)
  2. Security scan (bandit, safety)
  3. Unit tests
  4. Integration tests
  5. Build Docker image
  6. Scan image (Trivy)
  7. Push to registry

---

## Configuration Management

**Approach**: Environment variables + YAML config file

```python
# config.py
from pydantic_settings import BaseSettings
from pydantic import SecretStr

class Settings(BaseSettings):
    # Application
    app_name: str = "Vibe-Quality-Searcharr"
    debug: bool = False

    # Database
    database_url: str = "sqlite+pysqlcipher:///:memory:@/data/app.db"
    database_encryption_key: SecretStr

    # Security
    secret_key: SecretStr  # For JWT signing
    pepper: SecretStr  # For password hashing
    session_expire_hours: int = 24

    # API
    api_rate_limit: str = "100/minute"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()
```

**Docker Secrets Support**:
```yaml
# docker-compose.yml
services:
  vibe-quality-searcharr:
    image: vibe-quality-searcharr:latest
    environment:
      DATABASE_ENCRYPTION_KEY_FILE: /run/secrets/db_key
      SECRET_KEY_FILE: /run/secrets/secret_key
      PEPPER_FILE: /run/secrets/pepper
    secrets:
      - db_key
      - secret_key
      - pepper
    volumes:
      - ./data:/data

secrets:
  db_key:
    file: ./secrets/db_key.txt
  secret_key:
    file: ./secrets/secret_key.txt
  pepper:
    file: ./secrets/pepper.txt
```

---

## Logging

**Library**: Python standard `logging` + `structlog` for structured logs

```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info("user_login", username=username, ip=request.client.host)
logger.error("api_error", service="sonarr", status_code=500)
```

---

## Summary: Final Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Runtime** | Python | 3.13+ |
| **Web Framework** | FastAPI | 0.110+ |
| **ASGI Server** | Uvicorn | 0.27+ |
| **Database** | SQLite + SQLCipher | 3.x |
| **ORM** | SQLAlchemy | 2.0+ |
| **Migrations** | Alembic | 1.13+ |
| **Password Hashing** | argon2-cffi | 23.1+ |
| **Encryption** | cryptography (Fernet) | 42.0+ |
| **Session** | python-jose (JWT) | 3.3+ |
| **2FA** | pyotp | 2.9+ |
| **HTTP Client** | httpx | 0.26+ |
| **Scheduler** | APScheduler | 3.10+ |
| **Templates** | Jinja2 | 3.1+ |
| **Validation** | Pydantic | 2.6+ |
| **Testing** | pytest | 8.0+ |
| **Linting** | Ruff | 0.1+ |
| **Type Checking** | mypy | 1.8+ |
| **Security Scan** | Bandit + Safety | Latest |
| **Logging** | structlog | Latest |
| **Package Manager** | Poetry | 1.7+ |
| **Container** | Docker | 24+ |
| **Base Image** | python:3.13-slim | Latest |

---

## Next Steps

1. **Initialize Project**:
   ```bash
   poetry new vibe-quality-searcharr
   cd vibe-quality-searcharr
   poetry add fastapi uvicorn sqlalchemy sqlcipher3 argon2-cffi httpx apscheduler
   poetry add --group dev pytest pytest-asyncio pytest-cov mypy ruff bandit safety
   ```

2. **Set Up Project Structure**: Create directory structure as outlined

3. **Configure Docker**: Create Dockerfile and docker-compose.yml

4. **Implement Core Security**: Start with authentication module (password hashing, encryption)

5. **Build Database Models**: Define SQLAlchemy models for users, instances, search queue

6. **Implement Setup Wizard**: First-run experience for initial configuration

7. **Build Sonarr Client**: HTTP client for Sonarr API integration

8. **Implement Search Scheduler**: Background job processing

9. **Create Dashboard**: Web UI for monitoring and control

10. **Testing & Security Audit**: Comprehensive test suite and security review

---

## Alternatives Considered

### Language Alternatives
- ❌ **Go**: Excellent performance, but steeper learning curve, less mature ORM ecosystem
- ❌ **Rust**: Best security/performance, but very steep learning curve, slower development
- ⚠️ **Node.js**: Viable alternative, but weaker cryptography ecosystem for this use case

### Framework Alternatives
- ❌ **Django**: Too heavy, admin interface not needed
- ❌ **Flask**: No async, more boilerplate
- ❌ **Sanic**: Less mature than FastAPI

### Database Alternatives
- ⚠️ **PostgreSQL**: Better for scale, but overkill for single-server personal use
- ❌ **MongoDB**: Not suitable for relational data model

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| SQLCipher complexity | Well-documented, `sqlcipher3` package handles integration |
| SQLite performance at scale | Adequate for 50k+ items, can migrate to PostgreSQL later |
| Python async learning curve | FastAPI docs excellent, modern Python has good async support |
| Native dependency compilation | Use slim base image, not alpine (better compatibility) |
| Single-server limitation | Acceptable for personal use, architecture allows future scaling |

---

## Approval

**Recommended Stack**: Python + FastAPI + SQLite/SQLCipher

This stack provides the best balance of security, development speed, and maintainability for the Vibe-Quality-Searcharr MVP.

**Ready to proceed?** Next step is to create the project structure and begin implementation.
