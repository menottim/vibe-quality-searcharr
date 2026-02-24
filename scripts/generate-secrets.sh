#!/bin/bash
# Generate secure secrets for Vibe-Quality-Searcharr

set -e

SECRETS_DIR="./secrets"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

echo "Generating secure secrets..."

# Generate database encryption key (32 bytes base64)
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > "$SECRETS_DIR/db_key.txt"
echo "✓ Database key generated"

# Generate JWT secret key (64 bytes base64)
python3 -c "import secrets; print(secrets.token_urlsafe(64))" > "$SECRETS_DIR/secret_key.txt"
echo "✓ Secret key generated"

# Generate pepper (32 bytes base64)
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > "$SECRETS_DIR/pepper.txt"
echo "✓ Pepper generated"

# Set restrictive permissions
chmod 600 "$SECRETS_DIR"/*.txt

echo ""
echo "✅ Secrets generated successfully in $SECRETS_DIR"
echo "⚠️  IMPORTANT: Keep these files secure and NEVER commit them to version control"
echo "⚠️  Add $SECRETS_DIR to your .gitignore (already done)"
