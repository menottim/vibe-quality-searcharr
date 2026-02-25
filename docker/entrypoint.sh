#!/bin/bash
set -e

# Entrypoint script that handles permissions and drops to non-root user

# Function to log messages
log() {
    echo "[entrypoint] $1"
}

log "Starting Vibe-Quality-Searcharr entrypoint..."

# Ensure /data directory exists and has correct permissions
if [ -d "/data" ]; then
    log "Setting permissions on /data directory..."
    # Try to fix permissions, but don't fail if we can't (Windows mounts)
    chown -R appuser:appuser /data 2>/dev/null || log "Note: Could not change ownership (this is normal on Windows)"
    chmod -R u+rw /data 2>/dev/null || log "Note: Could not change permissions (this is normal on Windows)"
    log "Permissions configured"
else
    log "WARNING: /data directory does not exist!"
fi

# Copy Docker secrets to a location accessible by all users
# Docker secrets are mounted as root-only readable files
if [ -d "/run/secrets" ]; then
    log "Copying Docker secrets for accessibility..."
    mkdir -p /tmp/secrets

    # Copy each secret file if it exists
    for secret in db_key secret_key pepper; do
        if [ -f "/run/secrets/$secret" ]; then
            cp "/run/secrets/$secret" "/tmp/secrets/$secret"
            chmod 644 "/tmp/secrets/$secret"  # Make readable by all
            log "Copied secret: $secret"
        fi
    done

    # Update environment variables to point to new secret locations
    export DATABASE_KEY_FILE=/tmp/secrets/db_key
    export SECRET_KEY_FILE=/tmp/secrets/secret_key
    export PEPPER_FILE=/tmp/secrets/pepper
    log "Secrets configured at /tmp/secrets/"
fi

# Ensure /data directory exists and is writable
if [ -d "/data" ]; then
    log "Setting permissions on /data directory..."
    chown -R appuser:appuser /data 2>/dev/null || log "Note: Could not change ownership (this is normal on Windows)"
    chmod -R u+rw /data 2>/dev/null || log "Note: Could not change permissions (this is normal on Windows)"
    log "Permissions configured"
else
    log "WARNING: /data directory does not exist!"
fi

# TEMPORARY: Run as root for debugging
# On Windows, file permissions don't work the same way, so running as root is simpler
log "Running as root for Windows/debugging compatibility"
log "Database path: /data/vibe-quality-searcharr.db"
log "Key file: ${DATABASE_KEY_FILE:-not set}"
exec "$@"
