# Vibe-Quality-Searcharr User Guide

## Welcome

Vibe-Quality-Searcharr is an intelligent backlog search automation tool for Sonarr and Radarr. This guide will help you get started and make the most of the application.

## Table of Contents

1. [Installation](#installation)
2. [First-Time Setup](#first-time-setup)
3. [Adding Instances](#adding-instances)
4. [Creating Search Queues](#creating-search-queues)
5. [Understanding Search Strategies](#understanding-search-strategies)
6. [Monitoring Progress](#monitoring-progress)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Installation

### Using Docker (Recommended)

```bash
docker run -d \
  --name vibe-quality-searcharr \
  -p 7337:7337 \
  -v /path/to/data:/data \
  -v /path/to/secrets:/run/secrets:ro \
  -e SECRET_KEY_FILE=/run/secrets/secret_key \
  -e PEPPER_FILE=/run/secrets/pepper \
  -e DATABASE_KEY_FILE=/run/secrets/db_key \
  vibe-quality-searcharr:latest
```

### Using Docker Compose

```yaml
version: '3.8'
services:
  vibe-quality-searcharr:
    image: vibe-quality-searcharr:latest
    container_name: vibe-quality-searcharr
    ports:
      - "7337:7337"
    volumes:
      - ./data:/data
      - ./secrets:/run/secrets:ro
    environment:
      - ENVIRONMENT=production
      - SECRET_KEY_FILE=/run/secrets/secret_key
      - PEPPER_FILE=/run/secrets/pepper
      - DATABASE_KEY_FILE=/run/secrets/db_key
    restart: unless-stopped
```

### Manual Installation

```bash
# Clone repository
git clone https://github.com/yourusername/vibe-quality-searcharr.git
cd vibe-quality-searcharr

# Install with Poetry
poetry install

# Generate secrets
python -c "import secrets; print(secrets.token_urlsafe(64))" > secrets/secret_key
python -c "import secrets; print(secrets.token_urlsafe(32))" > secrets/pepper
python -c "import secrets; print(secrets.token_urlsafe(32))" > secrets/db_key

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run application
poetry run uvicorn vibe_quality_searcharr.main:app --host 0.0.0.0 --port 7337
```

---

## First-Time Setup

### 1. Access Setup Wizard

Navigate to `http://localhost:7337` in your browser. You'll be automatically redirected to the setup wizard.

### 2. Create Admin Account

![Setup Wizard](images/setup-wizard.png)

Fill in the required fields:
- **Username:** Choose a memorable username (e.g., "admin")
- **Email:** Your email address for account recovery
- **Password:** Strong password (min 8 chars, uppercase, lowercase, number, special char)
- **Confirm Password:** Re-enter your password

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

Click "Create Account" to proceed.

### 3. Log In

After account creation, you'll be redirected to the login page. Enter your credentials to access the dashboard.

---

## Adding Instances

### Sonarr Instance

1. Navigate to **Instances** → **Add Instance**
2. Fill in the instance details:
   - **Name:** Friendly name (e.g., "Main Sonarr")
   - **Type:** Select "Sonarr"
   - **Base URL:** Your Sonarr URL (e.g., `http://localhost:8989`)
   - **API Key:** Find in Sonarr Settings → General → API Key
3. Click "Test Connection" to verify
4. Click "Save Instance"

### Radarr Instance

Same steps as Sonarr, but select "Radarr" as the type and use your Radarr URL and API key.

**Finding Your API Key:**
- Sonarr: Settings → General → Security → API Key
- Radarr: Settings → General → Security → API Key

**Local Instances:**
- Development: `ALLOW_LOCAL_INSTANCES=true` permits localhost URLs
- Production: Set `ALLOW_LOCAL_INSTANCES=false` for security

---

## Creating Search Queues

Search queues automate the process of searching for missing or wanted content.

### 1. Navigate to Search Queues

Click "Search Queues" in the navigation menu, then "Create Queue".

### 2. Configure Queue

**Basic Settings:**
- **Name:** Descriptive name (e.g., "Missing Episodes - Weekly")
- **Instance:** Select the Sonarr/Radarr instance
- **Strategy:** Choose search strategy (see below)
- **Max Items per Run:** Number of items to search (e.g., 10-50)

**Advanced Settings:**
- **Is Active:** Enable/disable the queue
- **Recurring:** Enable for automated execution
- **Schedule:** Cron expression for recurring queues (e.g., "0 2 * * *" = daily at 2 AM)

### 3. Example Configurations

**Missing Episodes (Sonarr):**
```
Name: Missing Episodes - Daily
Strategy: missing
Max Items: 20
Schedule: 0 2 * * * (Daily at 2 AM)
```

**Cutoff Unmet (Radarr):**
```
Name: Quality Upgrades - Weekly
Strategy: cutoff
Max Items: 50
Schedule: 0 3 * * 0 (Weekly on Sunday at 3 AM)
```

**Recent Additions:**
```
Name: New Shows - 4x Daily
Strategy: recent
Max Items: 10
Schedule: 0 */6 * * * (Every 6 hours)
```

---

## Understanding Search Strategies

### Missing Strategy
**Purpose:** Search for completely missing episodes/movies

**Best For:**
- New library additions
- Filling in gaps in existing series
- After adding new shows/movies to Sonarr/Radarr

**How It Works:**
1. Queries Sonarr/Radarr for all missing items
2. Sorts by priority (monitored, download date, etc.)
3. Triggers search for top N items (Max Items per Run)

**Recommended Settings:**
- Max Items: 10-30 (to avoid overwhelming indexers)
- Schedule: Daily or on-demand

### Cutoff Strategy
**Purpose:** Search for quality upgrades (better releases)

**Best For:**
- Improving library quality over time
- Upgrading from 720p to 1080p/4K
- Finding better audio/video codecs

**How It Works:**
1. Queries for items below quality cutoff
2. Prioritizes by popularity, release date
3. Triggers search for upgrade candidates

**Recommended Settings:**
- Max Items: 20-50 (upgrades are less urgent)
- Schedule: Weekly or bi-weekly

### Recent Strategy
**Purpose:** Focus on recently added or aired content

**Best For:**
- New seasons of existing shows
- Recently released movies
- Keeping up with current airings

**How It Works:**
1. Queries for items added/aired in last 30 days
2. Prioritizes by air date (newest first)
3. Triggers search for recent items

**Recommended Settings:**
- Max Items: 5-15 (targeted searches)
- Schedule: Multiple times daily (every 4-6 hours)

### Custom Strategy (Advanced)
**Purpose:** Fine-tuned control with custom filters

**Configuration:**
```json
{
  "monitored_only": true,
  "min_year": 2020,
  "max_year": 2024,
  "tags": ["favorite", "must-have"],
  "sort_by": "popularity",
  "sort_order": "desc"
}
```

---

## Monitoring Progress

### Dashboard

The dashboard provides an overview of your automation:

**Statistics:**
- Total instances configured
- Active search queues
- Searches completed today/week/month
- Success rate percentage

**Recent Activity:**
- Last 10 searches executed
- Status (success/failed/partial)
- Items found/downloaded
- Error messages (if any)

### Search History

Navigate to **Search History** to view detailed logs:

**Filters:**
- Date range
- Instance
- Queue
- Status (success/failed/all)

**Details:**
- Execution time
- Items processed
- Results found
- Downloads triggered
- Error details

### Queue Status

On the **Search Queues** page, each queue shows:
- **Status:** idle / running / error
- **Last Run:** Timestamp of last execution
- **Next Run:** Scheduled next execution
- **Success Rate:** Historical success percentage

**Actions:**
- **Start Now:** Execute immediately (on-demand)
- **Pause:** Temporarily disable
- **Edit:** Modify configuration
- **Delete:** Remove queue

---

## Troubleshooting

### Queue Not Running

**Symptoms:** Queue status stuck on "idle", no executions

**Solutions:**
1. Check if queue is active (Edit → Is Active toggle)
2. Verify instance is online (test connection)
3. Check schedule configuration (cron expression valid)
4. Review logs for error messages

### Connection Errors

**Symptoms:** "Connection failed" when testing instance

**Solutions:**
1. Verify URL is correct (include protocol: http:// or https://)
2. Check Sonarr/Radarr is running and accessible
3. Verify API key is correct (copy from Sonarr/Radarr settings)
4. Check firewall/network settings
5. For local instances, ensure `ALLOW_LOCAL_INSTANCES=true` in development

### No Results Found

**Symptoms:** Searches complete but find nothing

**Solutions:**
1. Check indexers are configured in Sonarr/Radarr
2. Verify indexers are responding (check Sonarr/Radarr logs)
3. Review content availability (might not be released yet)
4. Check quality profile settings
5. Verify items are monitored in Sonarr/Radarr

### Rate Limiting

**Symptoms:** API returns "429 Too Many Requests"

**Solutions:**
1. Reduce `max_items_per_run` in queue configuration
2. Increase time between queue executions
3. Stagger multiple queue schedules
4. Adjust Sonarr/Radarr rate limiting settings

### Authentication Issues

**Symptoms:** Cannot log in, sessions expire quickly

**Solutions:**
1. Check username/password are correct
2. Verify cookies are enabled in browser
3. Clear browser cache and cookies
4. Check `SECRET_KEY` environment variable is set
5. Verify `ACCESS_TOKEN_EXPIRE_MINUTES` setting

---

## FAQ

### General Questions

**Q: How often should I run search queues?**
A: Depends on strategy:
- Missing: Daily or on-demand
- Cutoff: Weekly
- Recent: Multiple times daily (every 4-6 hours)

**Q: What's a good "Max Items per Run" value?**
A: Start with 10-20. Adjust based on:
- Indexer limits
- Download client capacity
- Network bandwidth
- Disk space

**Q: Can I run multiple queues simultaneously?**
A: Yes, but be mindful of:
- API rate limits (both app and Sonarr/Radarr)
- Indexer rate limits
- System resources

**Q: Does this download content automatically?**
A: No, it only triggers searches in Sonarr/Radarr. Your existing download client handles downloads.

### Technical Questions

**Q: Where is data stored?**
A: SQLite database in `/data/vibe-quality-searcharr.db` (encrypted with SQLCipher)

**Q: Are API keys stored securely?**
A: Yes, encrypted using Fernet (AES-128-CBC + HMAC) before storage

**Q: Can I backup my configuration?**
A: Yes, backup `/data/vibe-quality-searcharr.db`. Keep `DATABASE_KEY` safe for restore.

**Q: Does this work with other Servarr apps?**
A: Currently supports Sonarr and Radarr. Other apps may be added in future releases.

**Q: Can I use this with Sonarr v3 and v4?**
A: Yes, compatible with Sonarr v3 and v4 (API is backward compatible)

### Troubleshooting Questions

**Q: Why are searches slow?**
A: Searches are performed sequentially to respect rate limits. Adjust `max_items_per_run` if too slow.

**Q: Can I see what the app is searching for?**
A: Yes, check Search History for detailed logs of each execution

**Q: How do I reset my password?**
A: Currently requires database access. Password reset feature coming in future release.

**Q: Why can't I add localhost instances in production?**
A: Security feature. Set `ALLOW_LOCAL_INSTANCES=true` only in trusted environments.

---

## Advanced Usage

### Webhook Integration

Configure webhooks to receive notifications:

```bash
# Coming in future release
POST /api/webhooks/register
{
  "url": "https://your-webhook-url.com/notify",
  "events": ["search.completed", "search.failed"],
  "secret": "your-webhook-secret"
}
```

### API Access

Access the API programmatically:

```bash
# Get auth token
curl -X POST http://localhost:7337/api/auth/login \
  -d "username=admin&password=yourpassword"

# Use token for API calls
curl -X GET http://localhost:7337/api/search-queues/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**API Documentation:** Available at `http://localhost:7337/docs` (Swagger UI)

### Custom Strategies (Coming Soon)

Define advanced search logic:

```python
# Example custom strategy
{
  "name": "High Priority Missing",
  "filters": {
    "monitored": true,
    "missing": true,
    "tags": ["priority"],
    "year_range": [2020, 2024]
  },
  "sort": {
    "field": "popularity",
    "order": "desc"
  },
  "limit": 20
}
```

---

## Getting Help

**Documentation:**
- User Guide: This document
- API Docs: http://localhost:7337/docs
- Security Guide: SECURITY_GUIDE.md
- Deployment Guide: DEPLOYMENT_GUIDE.md

**Support:**
- GitHub Issues: https://github.com/yourusername/vibe-quality-searcharr/issues
- Discussions: https://github.com/yourusername/vibe-quality-searcharr/discussions
- Discord: [Coming soon]

**Contributing:**
See CONTRIBUTING.md for contribution guidelines.

---

**Version:** 0.1.0
**Last Updated:** 2026-02-24
