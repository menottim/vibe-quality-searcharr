# Product Requirements Document: Vibe-Quality-Searcharr

## Document Information
- **Version**: 1.0
- **Last Updated**: 2026-02-24
- **Status**: Draft

## Executive Summary

Vibe-Quality-Searcharr is a local server application that automates intelligent backlog searching for missing and upgradeable media releases in Sonarr and Radarr instances. It addresses the limitation where Servarr applications only monitor newly posted releases, not historical content, by implementing long-term systematic searching that respects API rate limits while maximizing coverage.

## 1. Product Overview

### 1.1 Problem Statement

Sonarr and Radarr do not actively search for missing episodes or quality upgrades from historical releases. They only react to newly posted content on RSS feeds. Users with large libraries containing thousands of missing or low-quality items have no automated way to systematically search their backlog without:
- Manually triggering searches (time-consuming)
- Hitting indexer API rate limits
- Repeatedly searching the same items
- Consuming excessive bandwidth and resources

### 1.2 Solution

Vibe-Quality-Searcharr runs as a local service that intelligently orchestrates backlog searches across Sonarr and Radarr instances by:
- Identifying media items that are missing or below quality cutoff
- Prioritizing searches based on configurable criteria
- Distributing searches over time to respect API limits
- Tracking search history to avoid redundant queries
- Operating within user-defined resource constraints

### 1.3 Success Criteria

- Successfully search 1000+ items per day per indexer without rate limiting
- Reduce manual search interventions by 90%
- Achieve 95%+ uptime for the service
- Zero security incidents related to credential exposure or unauthorized access
- Complete initial backlog search within user-configured timeframe (e.g., 30-90 days)

## 2. Core Functionality

### 2.1 Primary Features

#### 2.1.1 Intelligent Backlog Discovery
- Query Sonarr/Radarr APIs to retrieve lists of:
  - Missing episodes/movies
  - Items below quality cutoff (upgradeable)
  - Items with custom format scores below target
- Support filtering by series, quality profile, tags, and date ranges
- Refresh discovery lists on configurable schedule (default: daily)

#### 2.1.2 Search Orchestration
- Distribute searches evenly across time windows to respect indexer limits
- Implement configurable search strategies:
  - **Round-robin**: Cycle through all items systematically
  - **Priority-based**: Search high-priority items first (recently aired, popular, user favorites)
  - **Aging-based**: Prioritize items not searched recently
  - **Random**: Distribute searches randomly to avoid patterns
- Support per-indexer rate limit configuration
- Batch searches when API supports bulk operations
- Track last search timestamp per item to avoid redundant searches

#### 2.1.3 Search History & State Management
- Maintain persistent database of:
  - All searched items with timestamps
  - Search results and outcomes
  - API quota consumption per indexer
  - Success/failure rates
- Provide query interface for search history
- Support manual exclusions (items to never search)
- Allow search reset for specific items or date ranges

#### 2.1.4 Scheduling & Resource Management
- Configurable search windows (e.g., search only during off-peak hours)
- Per-instance search rate limits (searches per hour/day)
- Per-indexer API quota tracking and enforcement
- Pause/resume functionality
- Dry-run mode for testing configurations

#### 2.1.5 Multi-Instance Support
- Connect to multiple Sonarr instances
- Connect to multiple Radarr instances
- Independent configuration per instance
- Aggregate status dashboard across all instances

#### 2.1.6 Configuration Drift Detection
- Periodically poll Sonarr/Radarr instances for configuration changes
- Detect changes in:
  - Quality profiles (renamed, deleted, added)
  - Tags (renamed, deleted, added)
  - Custom formats (for quality scoring)
- Alert user via dashboard when drift detected
- Show detailed comparison of current vs. expected configuration
- Provide guided migration UI:
  - Show items affected by config change
  - Suggest mappings (e.g., old profile → new profile)
  - Allow user to review and confirm migration
  - Apply changes atomically
- Log all configuration changes and migrations for audit trail
- Allow manual refresh/sync of configuration

### 2.2 User Interface

#### 2.2.1 Setup Wizard (First-Run Experience)
On first launch, guide user through:
1. **Welcome & Overview**: Brief explanation of what Vibe-Quality-Searcharr does
2. **Admin Account Creation**: Create initial admin username and password
3. **Add First Instance**:
   - Instance type (Sonarr/Radarr)
   - URL (with validation)
   - API key (with connection test)
   - Instance name/label
4. **Basic Configuration**:
   - Default search strategy (recommend round-robin)
   - Search rate limit (searches per hour, default based on indexer count)
   - Search window (24/7 or specific hours)
5. **Complete Setup**: Show summary and link to dashboard

Wizard should:
- Validate all inputs before proceeding
- Show clear error messages if connection fails
- Allow skipping and returning later
- Be accessible for additional instances after initial setup

#### 2.2.2 Web Dashboard (Technical Interface)
- Real-time status of all connected instances
- Current search queue and progress
- Search history with filtering and sorting
- Configuration management (YAML/JSON viewer with form editor)
- API quota usage visualization
- Manual search triggering for specific items
- Configuration drift alerts with migration UI
- Logs viewer with filtering

Dashboard design principles:
- Function over form (technical, not polished)
- Information density (show details)
- Direct access to technical info (API responses, queue internals)
- Minimal JavaScript (server-rendered where possible)

#### 2.2.3 API Endpoints
- RESTful API for all dashboard operations
- Webhook support for external triggers
- Health check endpoint
- OpenAPI/Swagger documentation

### 2.3 Configuration Management

#### 2.3.1 Instance Configuration
- Sonarr/Radarr connection details (URL, API key)
- Instance-specific search strategies
- Quality profile filtering
- Tag-based filtering
- Priority rules

#### 2.3.2 Global Configuration
- Search scheduling parameters
- Resource limits
- Logging levels
- Database retention policies
- Security settings

## 3. Technical Architecture

### 3.1 System Components

```
┌─────────────────────────────────────────────────────┐
│                 Vibe-Quality-Searcharr                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │   Web UI     │  │   REST API   │  │  Webhooks│ │
│  └──────┬───────┘  └──────┬───────┘  └────┬─────┘ │
│         │                 │                │        │
│  ┌──────┴─────────────────┴────────────────┴─────┐ │
│  │         Application Core & Scheduler          │ │
│  └──────┬─────────────────┬────────────────┬─────┘ │
│         │                 │                │        │
│  ┌──────┴───────┐  ┌──────┴──────┐  ┌─────┴──────┐│
│  │ Sonarr Client│  │Radarr Client│  │ DB Manager ││
│  └──────────────┘  └─────────────┘  └────────────┘│
└─────────────────────────────────────────────────────┘
         │                  │                 │
         ▼                  ▼                 ▼
    [Sonarr API]      [Radarr API]    [SQLite/PostgreSQL]
```

### 3.2 Technology Considerations

#### Recommended Stack
- **Runtime**: Node.js (TypeScript) or Python 3.11+
- **Database**: SQLite (default) with PostgreSQL option for scale
- **Web Framework**: Express/Fastify (Node) or FastAPI (Python)
- **UI Framework**: React/Vue.js or server-rendered templates
- **Scheduler**: Node-cron or APScheduler
- **HTTP Client**: Axios or httpx with retry logic

### 3.3 Data Storage

#### Database Schema (Conceptual)
- `instances`: Sonarr/Radarr instance configurations (encrypted API keys)
- `search_queue`: Pending searches with priority and scheduling
- `search_history`: Historical searches with outcomes
- `exclusions`: User-defined items to skip
- `api_quotas`: Per-indexer quota tracking
- `audit_log`: Security and access audit trail

### 3.4 API Integration Requirements

#### Sonarr/Radarr API Usage
- Use official Servarr API endpoints (v3+)
- Required endpoints:
  - `GET /api/v3/wanted/missing`: Retrieve missing items
  - `GET /api/v3/wanted/cutoff`: Retrieve upgradeable items
  - `POST /api/v3/command`: Trigger searches
  - `GET /api/v3/qualityprofile`: Retrieve quality profiles
  - `GET /api/v3/series` or `/api/v3/movie`: Retrieve media metadata
- Implement exponential backoff for failed requests
- Cache responses where appropriate (quality profiles, series metadata)
- Respect Sonarr/Radarr rate limits (documented or detected)

## 4. Security Requirements

This section addresses OWASP Top 10 2025 and lessons from Huntarr security failures.

**📘 Implementation Details**: See `SECURITY_IMPLEMENTATION.md` for complete code examples, configuration, and implementation guidance specific to the Python/FastAPI stack.

### 4.1 A01:2025 - Broken Access Control

#### Requirements
- **All API endpoints MUST require authentication** - no unauthenticated access to any functionality
- Implement role-based access control (RBAC):
  - **Admin**: Full configuration and operational control
  - **Operator**: Can trigger searches, view status, cannot modify configuration
  - **Viewer**: Read-only access to status and history
- Enforce principle of least privilege for all operations
- Validate authorization on every request (not just route-level)
- Implement CORS restrictions to prevent unauthorized cross-origin requests
- Session tokens must be validated on server-side for every protected resource
- Deny access by default; require explicit grants

#### Huntarr Lessons Applied
- ❌ **NEVER** expose settings endpoints without authentication
- ❌ **NEVER** return API keys or credentials in API responses
- ❌ **NEVER** allow configuration changes without proper authentication and authorization

### 4.2 A02:2025 - Security Misconfiguration

#### Requirements
- Secure defaults for all configuration options
- Disable unnecessary features and endpoints
- Remove or disable default accounts (force creation of admin on first run)
- Implement security headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security` (if HTTPS enabled)
  - `Content-Security-Policy`
- Provide security hardening guide in documentation
- Regular dependency updates and security patches
- Environment-specific configurations (dev, prod) with clear separation
- Fail securely on configuration errors (don't expose stack traces)
- Configuration validation on startup with clear error messages

#### Deployment Security
- Run as non-root user in containers
- Minimal base images (Alpine, distroless)
- Read-only filesystem where possible
- No package managers in production images
- Network isolation from internet by default (local-only binding)

### 4.3 A03:2025 - Software Supply Chain Failures

#### Requirements
- Pin all dependencies to specific versions
- Implement Software Bill of Materials (SBOM) generation
- Use dependency scanning tools (npm audit, pip-audit, Snyk, Dependabot)
- Verify package integrity (checksums, signatures)
- Regular automated dependency updates with testing
- Use private package registry mirror when possible
- Code signing for releases
- Reproducible builds
- Vulnerability disclosure policy

#### Build Pipeline
- Multi-stage Docker builds to minimize attack surface
- Build artifacts signed with GPG/Cosign
- Automated security scanning in CI/CD
- Immutable build artifacts

### 4.4 A04:2025 - Cryptographic Failures

#### Requirements
- **Credential Storage**:
  - Sonarr/Radarr API keys MUST be encrypted at rest
  - Use industry-standard encryption (AES-256-GCM minimum)
  - Never store credentials in plaintext
  - Use system keyring integration where available (optional)
  - Encryption keys derived from master password or system-generated key
  - Support for external secret management (HashiCorp Vault, environment variables)

- **Data in Transit**:
  - Support HTTPS for web dashboard (with Let's Encrypt integration option)
  - Validate TLS certificates when connecting to Sonarr/Radarr
  - Option to allow self-signed certificates with explicit user consent
  - Minimum TLS 1.2, prefer TLS 1.3

- **Session Management**:
  - Generate cryptographically secure session tokens (32+ bytes entropy)
  - Session tokens stored securely (httpOnly, secure, sameSite cookies)
  - Implement session expiration (default: 24 hours)
  - Session invalidation on logout

- **Password Storage Requirements** (Local Authentication):

  **CRITICAL: Passwords MUST NEVER be stored in plaintext. This section implements OWASP, NIST, and industry best practices for secure password storage.**

  **Hashing Algorithm Selection**:
  - **Primary**: Use Argon2id (winner of the 2015 Password Hashing Competition)
    - Minimum configuration: 19 MiB memory, 2 iterations, 1 degree of parallelism
    - Recommended configuration: 128 MiB memory, 3-5 iterations for maximum security
    - Provides best resistance against GPU/ASIC attacks via memory-hardness
    - Most future-proof option for new systems
  - **Fallback 1**: scrypt (if Argon2id unavailable)
    - Minimum CPU/memory cost: 2^17 (131,072)
    - Block size: 8 (1024 bytes)
    - Parallelization: 1
  - **Fallback 2**: bcrypt (legacy support only)
    - Work factor: 13-14 minimum (produces ~250-500ms computation time)
    - Note: 72-byte password limit
    - Should only be used if Argon2 and scrypt are unavailable
  - **NEVER USE**: MD5, SHA-1, SHA-256 alone, or any non-password-specific hashing algorithms

  **Salt Implementation**:
  - Generate unique salt per password using cryptographically secure random number generator (CSPRNG)
  - Minimum salt length: 128 bits (16 bytes)
  - Recommended length: 256 bits (32 bytes)
  - Store salt in cleartext alongside password hash in database (this is standard practice)
  - Modern libraries (bcrypt, argon2, scrypt) typically handle salt generation automatically
  - Salt prevents rainbow table attacks and ensures identical passwords produce different hashes

  **Pepper Implementation (RECOMMENDED - Defense in Depth)**:
  - Apply server-side secret (pepper) as additional protection layer
  - Implementation: Hash password normally, then apply HMAC-SHA-256 using pepper as key
  - Pepper storage requirements:
    - MUST be stored separately from database (not in same file/server)
    - Recommended: Environment variable, Docker secret, or secrets vault (HashiCorp Vault, AWS Secrets Manager)
    - NEVER commit pepper to version control
    - NEVER store pepper in database or application config files
  - Benefit: Even if database is compromised, passwords cannot be cracked without pepper
  - Rotation strategy: Support multiple peppers with version identifiers for rotation without breaking existing hashes

  **Database Storage Schema**:
  ```
  users table:
    - id (primary key)
    - username (unique, indexed)
    - password_hash (TEXT, stores: algorithm$parameters$salt$hash)
    - password_pepper_version (INTEGER, for pepper rotation)
    - created_at (TIMESTAMP)
    - updated_at (TIMESTAMP)
    - last_password_change (TIMESTAMP)
    - failed_login_attempts (INTEGER)
    - account_locked_until (TIMESTAMP, nullable)
  ```

  **Password Hash Format** (PHC String Format):
  ```
  $argon2id$v=19$m=131072,t=3,p=1$<base64_salt>$<base64_hash>
  ```
  This format encodes algorithm, version, parameters, salt, and hash in a single string

  **SQLite Database Security**:
  - Use SQLCipher for transparent AES-256 encryption of entire database file
  - Database file permissions: 0600 (owner read/write only)
  - Encryption key management:
    - Option 1: Derive from user-provided master password at startup
    - Option 2: System-generated key stored in OS keyring (e.g., macOS Keychain, Windows Credential Manager)
    - Option 3: Environment variable (for Docker deployments)
  - Encrypt database backups with GPG/OpenSSL before storage
  - Regular integrity checks (PRAGMA integrity_check)

  **Password Policy Requirements**:
  - Minimum length: 12 characters (NIST recommendation)
  - Maximum length: 128 characters (prevent DoS via extremely long passwords)
  - No complexity requirements (NIST 2025 guidelines discourage these as they reduce entropy)
  - Check against common password breaches using Have I Been Pwned API (optional, privacy-preserving k-anonymity)
  - Prevent password reuse for last N passwords (optional, requires storing multiple hashes)
  - No forced password rotation (NIST no longer recommends this)
  - Rate limiting on password validation to prevent timing attacks

  **Implementation Libraries**:
  - Python: `argon2-cffi` (official Argon2 binding), `passlib` (multi-algorithm support)
  - Node.js: `argon2` (official Node.js bindings), `bcrypt` (fallback)
  - Ensure libraries are actively maintained and security-patched

  **Migration Path from Existing Hashes**:
  - If upgrading from weaker algorithm, re-hash on next successful login
  - Store algorithm version in password hash for forward compatibility
  - Support multiple algorithms during transition period

#### Huntarr Lessons Applied
- ✅ Encrypt all API keys at rest with strong encryption
- ✅ Never expose decrypted credentials in logs or API responses
- ✅ Use secure random number generation for tokens and keys

### 4.5 A05:2025 - Injection

#### Requirements
- **SQL Injection Prevention**:
  - Use parameterized queries or ORM exclusively
  - Never concatenate user input into SQL statements
  - Validate and sanitize all input
  - Use prepared statements for all database operations

- **Command Injection Prevention**:
  - Avoid system calls with user input
  - If unavoidable, use allowlists and strict validation
  - Never pass unsanitized data to shell commands

- **NoSQL Injection Prevention**:
  - Validate and sanitize all query parameters
  - Use query builders or ODMs

- **API Input Validation**:
  - Validate all input against strict schemas (JSON Schema, Pydantic, Zod)
  - Reject malformed requests
  - Limit input sizes (request body, URL length)
  - Validate data types, formats, and ranges
  - Sanitize data before use in downstream API calls to Sonarr/Radarr

### 4.6 A06:2025 - Insecure Design

#### Requirements
- **Threat Modeling**:
  - Document threat model covering all attack vectors
  - Regular security architecture reviews
  - Principle of least privilege throughout design
  - Defense in depth (multiple security layers)

- **Rate Limiting & DoS Protection**:
  - Rate limit all API endpoints (per IP, per user)
  - Implement request throttling
  - Maximum request sizes enforced
  - Connection limits
  - Timeout configurations

- **Secure State Management**:
  - Search queue cannot be manipulated to execute arbitrary searches
  - All state changes audited
  - Atomic operations for critical state updates
  - Validation of state transitions

- **Privacy by Design**:
  - Minimal data collection
  - No telemetry without explicit opt-in
  - Clear data retention policies
  - User control over data deletion

### 4.7 A07:2025 - Authentication Failures

#### Requirements
- **Authentication Mechanisms**:
  - **Local authentication** with comprehensive password storage security (see A04:2025 Password Storage Requirements for full details)
  - Optional SSO/OAuth2 integration (future version)
  - Optional API key authentication for external integrations (programmatic access)
  - Multi-factor authentication (TOTP) support using time-based one-time passwords

- **Password Verification Security**:
  - Use constant-time comparison to prevent timing attacks
  - Hash comparison must take same time regardless of correctness
  - Apply rate limiting: max 5 attempts per minute per IP address
  - Apply account-level rate limiting: max 10 attempts per hour per account
  - Log all verification attempts (success and failure) with timestamps and source IPs

- **Session Security**:
  - Secure session token generation (CSPRNG)
  - Session fixation prevention
  - Automatic session expiration
  - Concurrent session limits
  - Logout invalidates all sessions (option for single vs. all devices)

- **Brute Force Protection**:
  - Account lockout after N failed attempts (configurable, default: 5)
  - Progressive delays between attempts
  - CAPTCHA option after repeated failures
  - Audit logging of failed authentication

- **Credential Recovery**:
  - Secure password reset mechanism (if applicable)
  - Reset tokens expire quickly (15-30 minutes)
  - One-time use reset tokens
  - Alternative: require database reset for forgotten passwords (acceptable for local tool)

#### Huntarr Lessons Applied
- ✅ No authentication bypass vulnerabilities
- ✅ 2FA cannot be enrolled without proper authentication
- ✅ All auth endpoints properly protected
- ✅ **NEVER** store passwords in plaintext (Huntarr stored passwords in plaintext SQLite)
- ✅ All password hashes use Argon2id with proper parameters
- ✅ Pepper stored separately from database for defense in depth
- ✅ Database encrypted at rest using SQLCipher
- ✅ Constant-time password comparison prevents timing attacks

#### Common Authentication Vulnerabilities to Avoid

**CRITICAL - Do NOT implement:**
1. Storing passwords in plaintext or using weak hashing (MD5, SHA-1)
2. Using same salt for all passwords
3. Storing pepper in database alongside hashes
4. Returning different error messages for "user not found" vs "wrong password" (username enumeration)
5. Allowing unlimited login attempts without rate limiting
6. Comparing passwords using `==` or string comparison (timing attacks)
7. Logging passwords or password hashes
8. Exposing password hashes in API responses
9. Using short iteration counts for password hashing algorithms
10. Implementing custom cryptography instead of using vetted libraries

### 4.8 A08:2025 - Software or Data Integrity Failures

#### Requirements
- **Update Mechanism**:
  - Signed updates with verification before installation
  - Secure update channel (HTTPS)
  - Integrity checks for all downloaded artifacts
  - Rollback capability if update fails

- **Data Integrity**:
  - Database integrity checks (foreign keys, constraints)
  - Backup and restore functionality
  - Transaction isolation for critical operations
  - Checksums for configuration files

- **Code Integrity**:
  - No dynamic code execution from user input
  - No `eval()` or equivalent constructs with untrusted data
  - Strict Content Security Policy
  - Subresource Integrity (SRI) for frontend dependencies

### 4.9 A09:2025 - Security Logging and Alerting Failures

#### Requirements
- **Comprehensive Audit Logging**:
  - Log all authentication attempts (success and failure)
  - Log all configuration changes with user attribution
  - Log all API calls to Sonarr/Radarr instances
  - Log all authorization failures
  - Log all search operations
  - Structured logging format (JSON)

- **Log Security**:
  - Never log credentials, API keys, or sensitive data
  - Sanitize logs to prevent injection attacks
  - Protect log files with appropriate permissions
  - Log rotation and retention policies
  - Tamper-evident logging (optional: append-only)

- **Alerting**:
  - Alert on repeated authentication failures
  - Alert on configuration changes
  - Alert on API connection failures
  - Alert on unusual search patterns
  - Configurable notification channels (email, webhook)

- **Monitoring**:
  - Health check endpoint for external monitoring
  - Metrics export (Prometheus format optional)
  - Performance metrics (API latency, queue depth, search success rate)

### 4.10 A10:2025 - Mishandling of Exceptional Conditions

#### Requirements
- **Error Handling**:
  - Catch all exceptions and handle gracefully
  - Never expose stack traces or internal errors to users
  - Generic error messages to users, detailed errors in logs
  - Fail securely (deny access on error, don't bypass checks)

- **Input Validation Errors**:
  - Reject invalid input with clear error messages
  - Don't process partially valid data
  - Validate early, fail fast

- **Resource Exhaustion**:
  - Handle API rate limit errors gracefully
  - Implement circuit breakers for failing external services
  - Timeout configurations for all external calls
  - Maximum retry limits with exponential backoff

- **Edge Cases**:
  - Handle missing/deleted items in Sonarr/Radarr
  - Handle API version mismatches
  - Handle database connection failures
  - Handle concurrent modifications gracefully

### 4.11 Network Security

#### Requirements
- **Network Isolation**:
  - Bind to localhost (127.0.0.1) by default
  - Require explicit configuration to bind to external interfaces
  - No uPnP or automatic firewall rule creation
  - Clear documentation on network security implications

- **TLS Configuration**:
  - Optional TLS support for dashboard
  - Certificate validation when connecting to Sonarr/Radarr
  - No SSLv3, TLS 1.0, TLS 1.1
  - Strong cipher suites only

### 4.12 Secrets Management

#### Requirements
- **Configuration Security**:
  - Support for environment variables for sensitive data
  - Support for Docker secrets
  - Support for external secret managers (Vault, AWS Secrets Manager)
  - Warn if configuration file has incorrect permissions (not 0600)
  - Encrypt configuration file or use separate encrypted vault

- **Runtime Security**:
  - Clear sensitive data from memory after use
  - No sensitive data in environment variables (if avoidable)
  - No sensitive data in process names or command-line arguments

### 4.13 Security Testing Requirements

#### Requirements
- Static Application Security Testing (SAST) in CI/CD
- Dynamic Application Security Testing (DAST) for API endpoints
- Dependency vulnerability scanning
- Container image scanning
- Penetration testing before major releases
- Security code review checklist

#### Authentication & Password Storage Testing
- **Unit Tests**:
  - Verify Argon2id is used with correct parameters
  - Verify unique salt generated per password
  - Verify pepper is applied correctly
  - Verify password hash format matches PHC string format
  - Verify constant-time comparison is used
  - Test password validation timing (should be constant regardless of correctness)
  - Test password length limits (min 12, max 128)

- **Integration Tests**:
  - Verify passwords never appear in logs
  - Verify passwords never appear in database (only hashes)
  - Verify database encryption is active (SQLCipher)
  - Test successful authentication flow
  - Test failed authentication flow
  - Test account lockout after N failed attempts
  - Test rate limiting on login endpoint
  - Test 2FA enrollment and verification

- **Security Tests**:
  - Attempt timing attacks on password verification
  - Attempt SQL injection on login form
  - Attempt brute force attacks (should be rate limited)
  - Verify error messages don't leak username existence
  - Attempt session fixation attacks
  - Attempt to bypass authentication on protected endpoints
  - Extract and verify database file is encrypted
  - Verify pepper is not accessible from database dump

- **Compliance Validation**:
  - OWASP ASVS (Application Security Verification Standard) Level 2 compliance for authentication
  - Verify NIST SP 800-63B compliance for password storage
  - Document compliance with OWASP Top 10 2025

## 5. Non-Functional Requirements

### 5.1 Performance
- API response time < 200ms for 95th percentile
- Support 10,000+ items in search queue without degradation
- Database queries optimized with indexes
- Efficient pagination for large datasets
- Background search operations don't block UI

### 5.2 Reliability
- 99.5% uptime target
- Automatic restart on crash
- Graceful handling of Sonarr/Radarr downtime
- Database corruption recovery
- State persistence across restarts

### 5.3 Scalability
- Support 10+ Sonarr/Radarr instances
- Handle libraries with 50,000+ items
- Horizontal scalability considerations (future)

### 5.4 Usability
- First-time setup wizard
- Clear documentation for all features
- Sensible defaults requiring minimal configuration
- Progressive disclosure of advanced features
- Helpful error messages with remediation steps

### 5.5 Maintainability
- Comprehensive test coverage (80%+ unit, integration tests)
- Clean code architecture (SOLID principles)
- API documentation (OpenAPI/Swagger)
- Code comments for complex logic
- Contributing guide for open source

### 5.6 Compatibility
- Support Sonarr v3+ and Radarr v3+
- Cross-platform (Linux, macOS, Windows)
- Docker support with official images
- ARM64 support for Raspberry Pi

### 5.7 Monitoring & Observability
- Structured logging (JSON)
- Health check endpoints
- Metrics endpoint (optional Prometheus)
- Detailed status reporting
- Search success/failure analytics

## 6. User Stories

### 6.1 Core User Journeys

**As a media library curator**, I want to automatically search for missing episodes without manual intervention, so that my library gradually becomes more complete.

**As a quality enthusiast**, I want to systematically upgrade my existing media to higher quality releases, so that I can improve my library quality over time.

**As a self-hoster**, I want to respect indexer API limits, so that I don't get banned or rate-limited.

**As a system administrator**, I want comprehensive security controls, so that my API keys and credentials remain protected.

**As a power user**, I want fine-grained control over search priorities, so that I can optimize for content I care about most.

**As a new user**, I want simple setup with minimal configuration, so that I can start benefiting from automatic searches quickly.

### 6.2 Feature-Specific Stories

**Search Management**
- I want to see what items are queued for searching
- I want to manually trigger searches for specific items
- I want to exclude certain items from automatic searching
- I want to pause/resume searching temporarily

**Monitoring**
- I want to see search success rates
- I want to know when API limits are being approached
- I want to be alerted when searches are failing repeatedly
- I want to see historical trends of search activity

**Configuration**
- I want to search only during off-peak hours
- I want to prioritize recently-aired content
- I want to set different search rates for different instances
- I want to configure which quality profiles trigger upgrades

## 7. Release Planning

### 7.1 MVP (v1.0)
- **Setup wizard** for initial configuration (add first instance, create admin account, basic settings)
- Single Sonarr instance support
- All four search strategies: round-robin, priority-based, aging-based, random
- SQLite database
- Technical web dashboard (status, queue, history, configuration)
- Local authentication with password and optional TOTP MFA
- API key encryption at rest (AES-256-GCM)
- **Configuration drift detection** with manual migration UI
- Official Docker image with docker-compose example
- Core security requirements implemented (OWASP Top 10 2025 compliance)
- Comprehensive documentation for technical users

### 7.2 v1.1
- Radarr support
- Multi-instance support (multiple Sonarr/Radarr instances)
- Search exclusions (manual item blacklist)
- Enhanced priority configuration (weighted parameters)
- Configuration import/export
- Advanced filtering by tags and quality profiles

### 7.3 v1.2
- Enhanced dashboard with analytics and charts
- Webhook support for external integrations
- PostgreSQL support as alternative to SQLite
- Role-based access control (admin, operator, viewer)
- Notification system (email, webhooks) for alerts
- Search performance analytics

### 7.4 Future Considerations (v2.0+)
- OAuth2/SSO authentication option
- Native binary distributions (Linux, macOS, Windows)
- Prowlarr integration for indexer management
- Custom format score tracking and optimization
- Plugin system for custom search strategies
- Machine learning-based search prioritization
- Readarr, Lidarr, Whisparr support
- Metrics export (Prometheus format)
- Grafana dashboard templates

## 8. Risks and Mitigations

### 8.1 Security Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| API key exposure | Critical | Medium | Encryption at rest, strict access controls, comprehensive audit logging |
| Authentication bypass | Critical | Low | Defense in depth, security testing, code review |
| Injection attacks | High | Medium | Input validation, parameterized queries, SAST |
| Supply chain compromise | High | Medium | Dependency scanning, pinned versions, SBOM |

### 8.2 Operational Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Indexer rate limiting | Medium | High | Intelligent scheduling, quota tracking, backoff strategies |
| Database corruption | High | Low | Regular backups, integrity checks, recovery procedures |
| Sonarr/Radarr API changes | Medium | Medium | API version detection, graceful degradation, update notifications |

### 8.3 Adoption Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Complex setup | Medium | Medium | Setup wizard, Docker image, comprehensive docs |
| Performance issues | Medium | Low | Load testing, optimization, scalability design |
| Trust concerns | High | Medium | Open source, security audit, transparent security practices |

## 9. Success Metrics

### 9.1 Functional Metrics
- Search completion rate: >95%
- API error rate: <1%
- Search queue processing time: <expected based on rate limits
- Missing item discovery accuracy: 100%

### 9.2 Security Metrics
- Zero critical security vulnerabilities
- Security audit pass rate: 100%
- Authentication failure rate tracked and alerted
- No credential exposure incidents

### 9.3 User Satisfaction
- Setup time <15 minutes for basic configuration
- User-reported issues <10 per release
- Community adoption rate (stars, forks, Docker pulls)

## 10. Documentation Requirements

### 10.1 User Documentation
- Quick start guide
- Installation instructions (Docker, native)
- Configuration reference
- API documentation
- Troubleshooting guide
- FAQ

### 10.2 Security Documentation
- Security architecture document
- Threat model
- Security hardening guide
- Incident response plan
- Vulnerability disclosure policy
- Security audit reports

### 10.3 Developer Documentation
- Architecture overview
- API reference
- Database schema
- Contributing guide
- Code style guide
- Testing guide

## 11. Compliance and Standards

### 11.1 Security Standards
- OWASP Top 10 2025 compliance
- CWE/SANS Top 25 awareness
- Follow principle of least privilege
- Security by design principles

### 11.2 Code Quality
- Linting with strict rules
- Type safety (TypeScript or Python type hints)
- Test coverage >80%
- Code review required for all changes

## 12. Design Decisions

### 12.1 Resolved Decisions

1. **Authentication**: Local authentication for v1.0 with optional TOTP MFA. OAuth2/SSO can be added in future versions if needed. Rationale: Simpler for MVP, matches personal use case, works offline.

2. **Deployment Model**: Docker-first with official images. Native binaries may be added later as secondary option. Rationale: Matches self-hosted ecosystem patterns, easier cross-platform support, simplified dependency management.

3. **Plugin System**: No plugin system for v1.0. Built-in search strategies (round-robin, priority-based, aging-based, random) with configurable parameters. Rationale: Reduces complexity, security concerns with arbitrary code execution, can add later if clear demand emerges.

4. **Distributed Deployment**: Single-server architecture only. No distributed/clustered deployment. Rationale: Personal use case doesn't require scale, single server can handle 10+ instances with 50k+ items, significantly simpler architecture.

5. **Target User Persona**: Technical self-hosters who are already running *arr stack. Includes setup wizard for initial configuration but otherwise assumes technical competency. Rationale: Primary user is technical, allows faster development, can iterate on UX later.

6. **Configuration Migration**: Detect configuration drift in Sonarr/Radarr instances, alert user, require manual migration with guided UI. No automatic migrations. Rationale: Gives user visibility and control, prevents silent failures, appropriate for technical audience.

### 12.2 Future Considerations

- OAuth2/SSO integration for multi-user scenarios
- Native binary distributions for non-Docker deployments
- Plugin system for custom search strategies if community demand exists
- Horizontal scaling if usage patterns require it

## Appendix A: References

### Security Resources - OWASP & Standards
- [OWASP Top 10 2025](https://owasp.org/Top10/2025/)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [NIST SP 800-63B - Digital Identity Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [NIST SP 800-132 - Password-Based Key Derivation](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-132.pdf)

### Password Hashing Resources
- [Password Hashing Guide 2025: Argon2 vs Bcrypt vs Scrypt](https://guptadeepak.com/the-complete-guide-to-password-hashing-argon2-vs-bcrypt-vs-scrypt-vs-pbkdf2-2026/)
- [Argon2 vs bcrypt vs scrypt Comparison](https://stytch.com/blog/argon2-vs-bcrypt-vs-scrypt/)
- [Salting Passwords Properly: 2025 Best Practices](https://www.onlinehashcrack.com/guides/password-recovery/salting-passwords-properly-2025-best-practices.php)
- [Salt and Pepper in Password Security](https://www.baeldung.com/cs/password-salt-pepper)

### Database Security Resources
- [Securing SQLite Databases: Best Practices](https://www.sqliteforum.com/p/securing-your-sqlite-database-best)
- [SQLite Encryption with SQLCipher](https://www.datasunrise.com/knowledge-center/sqlite-encryption/)
- [Basic Security Practices for SQLite](https://dev.to/stephenc222/basic-security-practices-for-sqlite-safeguarding-your-data-23lh)

### Vulnerability Case Studies
- [Huntarr Security Review](https://github.com/rfsbraz/huntarr-security-review)
- [Huntarr Vulnerability Report - Critical Auth Failures](https://piunikaweb.com/2026/02/24/huntarr-security-vulnerability-arr-api-keys-exposed/)
- [Huntarr Security Discussion](https://github.com/community-scripts/ProxmoxVE/discussions/12225)

### Servarr Resources
- [Servarr Wiki](https://wiki.servarr.com/)
- [Sonarr Issue #6309 - Long Term Search Missing](https://github.com/Sonarr/Sonarr/issues/6309)
- [Sonarr API Documentation](https://wiki.servarr.com/sonarr/api)
- [Radarr API Documentation](https://wiki.servarr.com/radarr/api)

### Technical Resources
- [OWASP Broken Access Control](https://owasp.org/Top10/2025/A01_2025-Broken_Access_Control/)
- [OWASP Injection](https://owasp.org/Top10/2025/A05_2025-Injection/)
- [OWASP Cryptographic Failures](https://owasp.org/Top10/2025/A04_2025-Cryptographic_Failures/)

## Appendix B: Glossary

- **Backlog**: Media items that are missing or below quality cutoff
- **Cutoff**: The quality threshold at which Sonarr/Radarr stops searching for upgrades
- **Indexer**: A service that indexes torrent/NZB releases and provides search capabilities
- **Quality Profile**: User-defined preferences for media quality (resolution, codec, etc.)
- **Custom Format**: Advanced scoring system in Sonarr/Radarr for fine-grained quality control
- **Servarr**: Collective name for the *arr application family (Sonarr, Radarr, Lidarr, etc.)
- **API Key**: Authentication token for accessing Sonarr/Radarr APIs
- **Rate Limit**: Maximum number of API requests allowed in a time period

---

**Document Control**
- This PRD should be reviewed quarterly
- All changes require security review
- Major feature additions require threat modeling update
