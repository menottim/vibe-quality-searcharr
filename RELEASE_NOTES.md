# Splintarr v1.0.0-alpha Release Notes

**Release Date:** 2026-03-02
**Status:** Alpha -- Ready for Testing

## What is Splintarr?

Splintarr automates intelligent backlog searching for Sonarr. It runs as a Docker container on your home network, intelligently scheduling searches for missing and quality-upgradeable content while respecting indexer rate limits.

## Alpha Scope

This alpha supports **Sonarr only**. Radarr support is planned for a future release. All backend code for Radarr exists but is disabled in the UI.

### Tested Platform

This release has been hand-tested on **Docker Desktop for Windows**. It is expected to work on Linux and macOS Docker environments but has not been independently verified.

## Features

### Core Search Engine
- Automated backlog searching with configurable strategies (missing, cutoff unmet, recent)
- Per-episode search tracking prevents repeated searches of the same content
- Season pack detection with automatic individual episode fallback
- Search result feedback loop -- tracks whether searches resulted in grabs
- Adaptive search prioritization with customizable cooldowns
- Cooldown override option for manual "Run Now" operations

### Instance Management
- Connect multiple Sonarr instances
- Encrypted API key storage (Fernet)
- Instance health monitoring with auto-recovery
- Docker networking tips with click-to-copy URLs

### Library
- Visual poster grid with episode-level completion tracking
- Missing content and cutoff unmet filtered views
- Series detail pages with per-season episode breakdown
- Quality profile display from Sonarr
- Content exclusion lists

### Search Queues
- Create, edit, clone, and delete search queues
- Pause/resume with automatic scheduling
- Configurable search intervals and batch sizes
- Queue presets for common configurations
- Detailed execution history with per-item results

### Integrations
- **Prowlarr** -- Indexer-aware rate limiting
- **Discord** -- Notifications for search activity, instance health, and errors

### Setup & Configuration
- Guided setup wizard (6 steps)
- Config export (import coming in a future release)
- Discord and Prowlarr configuration in settings
- Contextual dashboard with Getting Started guide

### Security
- SQLCipher encrypted database (AES-256)
- Argon2id password hashing with pepper
- JWT authentication with httpOnly cookies
- Optional TOTP two-factor authentication
- SSRF protection on instance URLs
- CSP nonce-based script security
- Rate limiting on sensitive endpoints

### Operations
- Structured JSON logging with truncation and deduplication
- Log rotation (5MB per file, 3 backups)
- Health check endpoint for Docker
- Database integrity checking

## Known Limitations

- **Sonarr only** -- Radarr support is disabled in the alpha (backend code exists, UI is gated)
- **Single-worker only** -- Rate limiting is in-memory, doesn't share state across workers
- **No CSRF tokens** on setup wizard form submissions (mitigated by SameSite=strict cookies)
- **No config import** -- Export only in this release
- **Series-level cooldown** -- Cooldown applies at the series level in Sonarr, not per-episode (by design)
- **Tested on Windows Docker only** -- Linux/macOS should work but is unverified

## Setup

### Windows
```powershell
git clone https://github.com/menottim/splintarr.git
cd splintarr
.\scripts\setup-windows.ps1 -AutoStart
```

### Linux / macOS
```bash
git clone https://github.com/menottim/splintarr.git
cd splintarr
./scripts/setup.sh --auto-start
```

Then open **http://localhost:7337** to complete the setup wizard.

## Security Audit Summary

A pre-alpha security audit found **0 Critical** and **2 High** findings:
- **HIGH-01 (Fixed):** Sync status endpoint limited to minimal response for unauthenticated users
- **HIGH-02 (Known):** No CSRF tokens on form-POST setup endpoints (mitigated by SameSite=strict cookies)

## Feedback

Please report bugs and feedback at: https://github.com/menottim/splintarr/issues
