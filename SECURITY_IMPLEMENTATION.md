# Security Implementation Guide
## Vibe-Quality-Searcharr - Python/FastAPI Stack

**Version**: 1.0
**Date**: 2026-02-24
**Based on**: OWASP Top 10 2025, NIST Guidelines, Industry Best Practices

---

## Document Purpose

This guide provides specific implementation details for security requirements defined in the PRD, tailored to our chosen technology stack (Python 3.13+ / FastAPI / SQLite+SQLCipher).

---

## 1. FastAPI Security Implementation

### 1.1 Authentication & Authorization

**JWT Token Configuration** (Short-lived access tokens)

```python
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")  # 256-bit random key
ALGORITHM = "HS256"  # Symmetric for access tokens
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived
REFRESH_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer()

def create_access_token(data: dict) -> str:
    """Create short-lived JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str, jti: str) -> str:
    """Create long-lived refresh token with unique identifier"""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
        "jti": jti  # Unique token ID for revocation tracking
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Validate JWT and return current user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Validate token type
        if payload.get("type") != "access":
            raise credentials_exception

        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user
```

**Refresh Token Revocation Tracking**

```python
# models/refresh_token.py
from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.sql import func

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    jti = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_info = Column(String(255))
    ip_address = Column(String(45))
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    def is_valid(self) -> bool:
        """Check if token is still valid"""
        return not self.revoked and datetime.utcnow() < self.expires_at
```

### 1.2 Input Validation with Pydantic

**Strict validation schemas prevent injection attacks**

```python
from pydantic import BaseModel, Field, validator, constr
from typing import Optional
import re

class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=32) = Field(
        ...,
        description="Username (alphanumeric and underscore only)"
    )
    password: constr(min_length=12, max_length=128) = Field(
        ...,
        description="Password (12-128 characters)"
    )

    @validator("username")
    def username_alphanumeric(cls, v):
        """Ensure username is alphanumeric"""
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username must be alphanumeric with underscores only")
        return v

    @validator("password")
    def password_not_common(cls, v):
        """Check against common passwords (implement via have i been pwned API)"""
        # TODO: Implement HIBP API check
        return v

class InstanceCreate(BaseModel):
    name: constr(min_length=1, max_length=100)
    url: constr(regex=r"^https?://[^\s]+$")  # Must be valid URL
    api_key: constr(min_length=20, max_length=256)
    instance_type: Literal["sonarr", "radarr"]

    @validator("url")
    def validate_url(cls, v):
        """Additional URL validation"""
        parsed = urlparse(v)
        # Prevent SSRF - no localhost/internal IPs unless explicitly allowed
        if parsed.hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
            if not os.getenv("ALLOW_LOCAL_INSTANCES", "false").lower() == "true":
                raise ValueError("Local instance URLs not allowed")
        return v
```

### 1.3 Security Headers

**Implement comprehensive security headers**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # Allow inline for HTMX
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# CORS - Restrictive by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7337"],  # Only same-origin in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Trusted Host
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", os.getenv("ALLOWED_HOST", "")]
)
```

### 1.4 Rate Limiting

**Implement per-IP and per-user rate limiting**

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to authentication endpoints
@app.post("/api/auth/login")
@limiter.limit("5/minute")  # 5 attempts per minute per IP
async def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    # Also implement account-level rate limiting
    user = db.query(User).filter(User.username == credentials.username).first()

    if user and user.failed_login_attempts >= 10:
        # Check if lockout period expired
        if user.account_locked_until and datetime.utcnow() < user.account_locked_until:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked. Try again after {user.account_locked_until}"
            )

    # Login logic...
```

---

## 2. Python Security Best Practices

### 2.1 SQL Injection Prevention

**Always use SQLAlchemy parameterized queries**

```python
# ✅ CORRECT - Parameterized query
user = db.query(User).filter(User.username == username).first()

# ✅ CORRECT - Parameterized with SQLAlchemy Core
stmt = select(User).where(User.username == username)
result = db.execute(stmt).scalar_one_or_none()

# ❌ NEVER DO THIS - String concatenation
# query = f"SELECT * FROM users WHERE username = '{username}'"  # VULNERABLE!
```

### 2.2 Secure Random Generation

**Use secrets module for cryptographic operations**

```python
import secrets
import string

def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure random token"""
    return secrets.token_urlsafe(length)

def generate_api_key() -> str:
    """Generate secure API key"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(64))

def generate_pepper() -> bytes:
    """Generate pepper for password hashing"""
    return secrets.token_bytes(32)
```

### 2.3 Secure File Operations

**Validate file paths to prevent directory traversal**

```python
from pathlib import Path

DATA_DIR = Path("/data")

def safe_file_path(filename: str) -> Path:
    """Ensure file path is within data directory"""
    filepath = (DATA_DIR / filename).resolve()

    # Prevent directory traversal
    if not filepath.is_relative_to(DATA_DIR):
        raise ValueError("Invalid file path")

    return filepath

# Usage
config_file = safe_file_path(user_provided_filename)
```

### 2.4 Security Linting with Bandit

**.bandit configuration**

```yaml
# .bandit
tests:
  - B201  # Flask debug mode
  - B501  # SSL/TLS certificate validation
  - B502  # SSL with bad version
  - B503  # SSL with bad defaults
  - B504  # SSL with no version
  - B505  # Weak cryptographic key
  - B506  # YAML load
  - B507  # SSH with no host key verification
  - B601  # Paramiko calls
  - B602  # Subprocess with shell=True
  - B603  # Subprocess without shell
  - B604  # Function call with shell=True
  - B605  # Process with shell
  - B606  # Process without shell
  - B607  # Partial path
  - B608  # SQL injection
  - B609  # Wildcard injection

skips:
  - B101  # assert_used (okay in tests)

exclude_dirs:
  - /tests
  - /venv
```

---

## 3. SQLite/SQLCipher Security

### 3.1 Database Connection with Encryption

**Secure SQLCipher connection**

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

def get_database_key() -> str:
    """Retrieve database encryption key from secure storage"""
    # Option 1: Docker secret
    secret_file = os.getenv("DATABASE_KEY_FILE")
    if secret_file and os.path.exists(secret_file):
        with open(secret_file, 'r') as f:
            return f.read().strip()

    # Option 2: Environment variable
    key = os.getenv("DATABASE_KEY")
    if key:
        return key

    # Option 3: System keyring (macOS Keychain, Windows Credential Manager)
    try:
        import keyring
        key = keyring.get_password("vibe-quality-searcharr", "database_key")
        if key:
            return key
    except ImportError:
        pass

    raise RuntimeError("Database encryption key not configured")

# SQLCipher connection
database_key = get_database_key()
DATABASE_URL = f"sqlite+pysqlcipher://:{database_key}@/data/vibe-quality-searcharr.db?cipher=aes-256-cfb&kdf_iter=256000"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # For FastAPI
        "timeout": 30,  # Connection timeout
    },
    pool_pre_ping=True,  # Test connections before use
    pool_recycle=3600,  # Recycle connections every hour
)

# Set SQLite PRAGMA settings for security
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    # Security PRAGMAs
    cursor.execute("PRAGMA foreign_keys = ON")  # Referential integrity
    cursor.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
    cursor.execute("PRAGMA synchronous = FULL")  # Crash safety
    cursor.execute("PRAGMA temp_store = MEMORY")  # Reduce disk writes
    cursor.execute("PRAGMA secure_delete = ON")  # Overwrite deleted data
    cursor.execute("PRAGMA auto_vacuum = FULL")  # Reclaim space
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### 3.2 Database File Permissions

**Set restrictive file permissions on startup**

```python
import os
import stat

def secure_database_file():
    """Set database file permissions to owner-only"""
    db_path = "/data/vibe-quality-searcharr.db"

    if os.path.exists(db_path):
        # Set to 0600 (rw-------)
        os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)

        # Also secure WAL and SHM files
        for suffix in ["-wal", "-shm"]:
            wal_path = db_path + suffix
            if os.path.exists(wal_path):
                os.chmod(wal_path, stat.S_IRUSR | stat.S_IWUSR)

# Call on application startup
@app.on_event("startup")
async def startup_event():
    secure_database_file()
```

### 3.3 Backup Encryption

**Encrypt database backups**

```python
from cryptography.fernet import Fernet
import shutil

def backup_database(backup_key: bytes):
    """Create encrypted database backup"""
    db_path = "/data/vibe-quality-searcharr.db"
    backup_path = f"/backups/backup-{datetime.utcnow().isoformat()}.db"
    encrypted_path = backup_path + ".enc"

    # Copy database
    shutil.copy2(db_path, backup_path)

    # Encrypt backup
    cipher = Fernet(backup_key)
    with open(backup_path, 'rb') as f:
        data = f.read()

    encrypted_data = cipher.encrypt(data)

    with open(encrypted_path, 'wb') as f:
        f.write(encrypted_data)

    # Remove unencrypted copy
    os.remove(backup_path)

    # Set permissions
    os.chmod(encrypted_path, stat.S_IRUSR | stat.S_IWUSR)

    return encrypted_path
```

---

## 4. HTTP Client Security (httpx)

### 4.1 Rate Limiting for External APIs

**Implement rate limiting for Sonarr/Radarr API calls**

```python
import httpx
from asyncio import Semaphore
import time
from collections import deque

class RateLimitedClient:
    """HTTP client with rate limiting"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        requests_per_second: int = 5,
        max_concurrent: int = 10
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.requests_per_second = requests_per_second
        self.max_concurrent = max_concurrent

        # Concurrent request limiter
        self.semaphore = Semaphore(max_concurrent)

        # Time-based rate limiter
        self.request_times = deque(maxlen=requests_per_second)

        # HTTP client
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Api-Key": api_key},
            timeout=30.0,
            limits=httpx.Limits(
                max_connections=max_concurrent,
                max_keepalive_connections=5
            ),
            verify=True  # Always verify SSL certificates
        )

    async def _wait_for_rate_limit(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()

        # Remove timestamps older than 1 second
        while self.request_times and self.request_times[0] < now - 1:
            self.request_times.popleft()

        # If at limit, wait
        if len(self.request_times) >= self.requests_per_second:
            wait_time = 1 - (now - self.request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.request_times.append(time.time())

    async def request(self, method: str, endpoint: str, **kwargs):
        """Make rate-limited request"""
        async with self.semaphore:  # Limit concurrent requests
            await self._wait_for_rate_limit()  # Respect rate limit

            response = await self.client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response

    async def close(self):
        await self.client.aclose()
```

### 4.2 Certificate Validation

**Always validate SSL certificates, with optional bypass**

```python
class SonarrClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        verify_ssl: bool = True,
        ca_cert_path: Optional[str] = None
    ):
        # Certificate validation configuration
        if not verify_ssl:
            logger.warning(
                "SSL certificate verification disabled for %s - "
                "This is insecure and should only be used in development",
                base_url
            )
            verify = False
        elif ca_cert_path:
            verify = ca_cert_path  # Use custom CA bundle
        else:
            verify = True  # Use system CA bundle

        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Api-Key": api_key},
            verify=verify
        )
```

### 4.3 Retry Logic with Exponential Backoff

**Implement secure retry logic**

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import httpx

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def fetch_with_retry(client: httpx.AsyncClient, endpoint: str):
    """Fetch with automatic retry on transient failures"""
    response = await client.get(endpoint)
    response.raise_for_status()
    return response.json()
```

---

## 5. Docker Security

### 5.1 Secure Dockerfile

**Production-ready Dockerfile with security hardening**

```dockerfile
# syntax=docker/dockerfile:1.4

# Build stage
FROM python:3.13-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry==1.7.1 && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi --no-root

# Runtime stage
FROM python:3.13-slim-bookworm

# Security: Create non-root user with specific UID/GID
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -s /sbin/nologin -c "Application user" appuser

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code with correct ownership
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser alembic.ini ./

# Create data directory with correct permissions
RUN mkdir -p /data && chown appuser:appuser /data

# Security: Run as non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:7337/health')" || exit 1

# Expose port
EXPOSE 7337

# Run application
CMD ["uvicorn", "src.vibe_quality_searcharr.main:app", "--host", "0.0.0.0", "--port", "7337", "--workers", "1"]
```

### 5.2 Docker Compose with Secrets

**Secure docker-compose.yml**

```yaml
version: '3.9'

services:
  vibe-quality-searcharr:
    build: .
    image: vibe-quality-searcharr:latest
    container_name: vibe-quality-searcharr

    # Security: Run as non-root
    user: "1000:1000"

    # Security: Read-only root filesystem
    read_only: true

    # Security: Drop all capabilities
    cap_drop:
      - ALL

    # Security: No new privileges
    security_opt:
      - no-new-privileges:true

    environment:
      - DATABASE_KEY_FILE=/run/secrets/db_key
      - SECRET_KEY_FILE=/run/secrets/secret_key
      - PEPPER_FILE=/run/secrets/pepper
      - LOG_LEVEL=INFO
      - ENVIRONMENT=production

    secrets:
      - db_key
      - secret_key
      - pepper

    volumes:
      # Data directory (read-write)
      - ./data:/data:rw
      # Temp directory (for read-only filesystem)
      - /tmp

    ports:
      - "127.0.0.1:7337:7337"  # Bind to localhost only

    restart: unless-stopped

    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M

secrets:
  db_key:
    file: ./secrets/db_key.txt
  secret_key:
    file: ./secrets/secret_key.txt
  pepper:
    file: ./secrets/pepper.txt

networks:
  default:
    driver: bridge
    internal: false  # Set to true if no internet access needed
```

### 5.3 Secret Generation Script

**Generate secure secrets**

```bash
#!/bin/bash
# generate-secrets.sh

set -e

SECRETS_DIR="./secrets"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Generate database encryption key (32 bytes base64)
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > "$SECRETS_DIR/db_key.txt"

# Generate JWT secret key (64 bytes base64)
python3 -c "import secrets; print(secrets.token_urlsafe(64))" > "$SECRETS_DIR/secret_key.txt"

# Generate pepper (32 bytes base64)
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > "$SECRETS_DIR/pepper.txt"

# Set restrictive permissions
chmod 600 "$SECRETS_DIR"/*.txt

echo "Secrets generated successfully in $SECRETS_DIR"
echo "⚠️  Keep these files secure and NEVER commit them to version control"
```

---

## 6. JWT Session Management

### 6.1 Secure Token Storage (HTTP-Only Cookies)

**Use HTTP-only cookies instead of localStorage**

```python
from fastapi.responses import JSONResponse

@app.post("/api/auth/login")
async def login(response: Response, credentials: UserLogin, db: Session = Depends(get_db)):
    # Authenticate user...
    user = authenticate_user(credentials.username, credentials.password, db)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create tokens
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token_jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(str(user.id), refresh_token_jti)

    # Store refresh token in database
    db_refresh_token = RefreshToken(
        jti=refresh_token_jti,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=30),
        device_info=request.headers.get("User-Agent"),
        ip_address=request.client.host
    )
    db.add(db_refresh_token)
    db.commit()

    # Set HTTP-only cookies
    response = JSONResponse(content={"message": "Login successful"})

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Not accessible to JavaScript
        secure=True,  # HTTPS only
        samesite="strict",  # CSRF protection
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth/refresh"  # Only sent to refresh endpoint
    )

    return response
```

### 6.2 Token Rotation

**Implement refresh token rotation**

```python
@app.post("/api/auth/refresh")
async def refresh_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Rotate refresh token and issue new access token"""

    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        # Decode and validate
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        jti = payload.get("jti")
        user_id = payload.get("sub")

        # Check if token is revoked
        db_token = db.query(RefreshToken).filter(RefreshToken.jti == jti).first()

        if not db_token or not db_token.is_valid():
            raise HTTPException(status_code=401, detail="Token revoked or expired")

        # Revoke old refresh token
        db_token.revoked = True

        # Create new tokens
        new_access_token = create_access_token({"sub": user_id})
        new_refresh_jti = str(uuid.uuid4())
        new_refresh_token = create_refresh_token(user_id, new_refresh_jti)

        # Store new refresh token
        new_db_token = RefreshToken(
            jti=new_refresh_jti,
            user_id=int(user_id),
            expires_at=datetime.utcnow() + timedelta(days=30),
            device_info=request.headers.get("User-Agent"),
            ip_address=request.client.host
        )
        db.add(new_db_token)
        db.commit()

        # Set new cookies
        response = JSONResponse(content={"message": "Token refreshed"})
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/api/auth/refresh"
        )

        return response

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

## 7. Logging Security

### 7.1 Structured Logging with Sensitive Data Filtering

**Configure secure logging**

```python
import structlog
import logging
from typing import Any

def filter_sensitive_data(logger, method_name, event_dict):
    """Remove sensitive data from logs"""
    sensitive_keys = {
        'password', 'api_key', 'token', 'secret', 'authorization',
        'x-api-key', 'pepper', 'salt', 'hash'
    }

    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            event_dict[key] = "***REDACTED***"

    return event_dict

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        filter_sensitive_data,  # Remove sensitive data
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info("user_login_success", username=username, ip=request.client.host)
logger.warning("failed_login_attempt", username=username, ip=request.client.host)
logger.error("api_error", service="sonarr", status_code=500, error=str(e))
```

---

## 8. Testing Security

### 8.1 Security Test Suite

**pytest security tests**

```python
# tests/security/test_authentication.py
import pytest
from fastapi.testclient import TestClient

def test_no_authentication_bypass(client: TestClient):
    """Ensure protected endpoints require authentication"""
    protected_endpoints = [
        "/api/instances",
        "/api/search/queue",
        "/api/settings",
    ]

    for endpoint in protected_endpoints:
        response = client.get(endpoint)
        assert response.status_code == 401

def test_password_not_in_response(client: TestClient):
    """Ensure passwords never appear in API responses"""
    # Create user
    response = client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "secure_password_12345"
    })

    # Check response doesn't contain password
    assert "secure_password_12345" not in response.text
    assert "password" not in response.json()

def test_rate_limiting(client: TestClient):
    """Ensure rate limiting is enforced"""
    # Try to login 10 times rapidly
    for _ in range(10):
        client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "wrong"
        })

    # 11th attempt should be rate limited
    response = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "wrong"
    })
    assert response.status_code == 429

def test_sql_injection_prevention(client: TestClient, db: Session):
    """Ensure SQL injection is prevented"""
    # Attempt SQL injection
    malicious_username = "admin' OR '1'='1"

    response = client.post("/api/auth/login", json={
        "username": malicious_username,
        "password": "anything"
    })

    # Should fail authentication, not succeed via injection
    assert response.status_code == 401
```

---

## 9. Security Checklist

### Pre-Deployment Checklist

- [ ] All secrets stored securely (Docker secrets, environment variables, keyring)
- [ ] Database encryption enabled (SQLCipher)
- [ ] Database file permissions set to 0600
- [ ] Argon2id configured with secure parameters (128 MiB, 3-5 iterations)
- [ ] Pepper stored separately from database
- [ ] JWT tokens short-lived (15 minutes for access, 30 days for refresh)
- [ ] HTTP-only, secure, samesite cookies enabled
- [ ] Refresh token rotation implemented
- [ ] Rate limiting enabled on all authentication endpoints
- [ ] Security headers configured (CSP, X-Frame-Options, etc.)
- [ ] CORS restricted to allowed origins
- [ ] Input validation on all endpoints (Pydantic schemas)
- [ ] SQL injection prevented (parameterized queries only)
- [ ] SSL certificate validation enabled for external APIs
- [ ] Sensitive data filtered from logs
- [ ] Container runs as non-root user (UID 1000)
- [ ] Container has read-only root filesystem
- [ ] Container capabilities dropped (cap_drop: ALL)
- [ ] Security testing passed (SAST, DAST, penetration tests)
- [ ] Dependency vulnerabilities scanned (Safety, Bandit)
- [ ] Container image scanned (Trivy)

---

## 10. References

### Official Documentation
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [SQLCipher Documentation](https://www.zetetic.net/sqlcipher/documentation/)
- [python-jose JWT Documentation](https://python-jose.readthedocs.io/)
- [argon2-cffi Documentation](https://argon2-cffi.readthedocs.io/)

### Security Best Practices
- [How to Secure FastAPI Applications Against OWASP Top 10](https://oneuptime.com/blog/post/2025-01-06-fastapi-owasp-security/view)
- [FastAPI Security Best Practices](https://medium.com/@yogeshkrishnanseeniraj/fastapi-security-best-practices-defending-against-common-threats-58fbd6a15fd2)
- [Python and OWASP Top 10 Guide](https://qwiet.ai/appsec-resources/python-and-owasp-top-10-a-developers-guide/)
- [JWT Security Best Practices 2025](https://oneuptime.com/blog/post/2025-01-06-python-jwt-authentication/view)
- [Docker Security Best Practices 2025](https://oneuptime.com/blog/post/2026-02-02-docker-security-best-practices/view)
- [SQLite Security Hardening](https://blackhawk.sh/en/blog/best-practices-for-securing-sqlite/)

### OWASP Resources
- [OWASP Top 10 2025](https://owasp.org/Top10/2025/)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

---

**Document maintained by**: Vibe-Quality-Searcharr Development Team
**Last security review**: 2026-02-24
**Next review due**: 2026-05-24 (Quarterly)
