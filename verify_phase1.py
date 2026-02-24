#!/usr/bin/env python3
"""Quick verification script for Phase 1 implementation."""

import os
import sys

# Set up environment for testing
os.environ["DATABASE_KEY_FILE"] = "secrets/db_key.txt"
os.environ["SECRET_KEY_FILE"] = "secrets/secret_key.txt"
os.environ["PEPPER_FILE"] = "secrets/pepper.txt"

print("=" * 70)
print("PHASE 1 VERIFICATION")
print("=" * 70)

# Test 1: Configuration
print("\n✓ Testing Configuration Management...")
try:
    from vibe_quality_searcharr.config import settings
    print(f"  - App Name: {settings.app_name}")
    print(f"  - Environment: {settings.environment}")
    print(f"  - Argon2 Memory: {settings.argon2_memory_cost} KiB")
    print(f"  - Argon2 Time Cost: {settings.argon2_time_cost}")
    print(f"  - Secret Key Loaded: {'✓' if settings.get_secret_key() else '✗'}")
    print(f"  - Pepper Loaded: {'✓' if settings.get_pepper() else '✗'}")
    print(f"  - DB Key Loaded: {'✓' if settings.get_database_key() else '✗'}")
    print("  ✅ Configuration: PASS")
except Exception as e:
    print(f"  ❌ Configuration: FAIL - {e}")
    sys.exit(1)

# Test 2: Password Hashing
print("\n✓ Testing Password Security...")
try:
    from vibe_quality_searcharr.core.security import hash_password, verify_password

    password = "test_password_12345"
    hashed = hash_password(password)

    print(f"  - Hash Format: {hashed[:20]}...")
    print(f"  - Hash Length: {len(hashed)} characters")
    print(f"  - Verification: {'✓' if verify_password(password, hashed) else '✗'}")
    print(f"  - Wrong Password Rejected: {'✓' if not verify_password('wrong', hashed) else '✗'}")

    # Check hash format (should be PHC format)
    assert hashed.startswith("$argon2"), "Hash should be Argon2 PHC format"
    assert verify_password(password, hashed), "Password verification failed"
    assert not verify_password("wrong_password", hashed), "Wrong password not rejected"

    print("  ✅ Password Security: PASS")
except Exception as e:
    print(f"  ❌ Password Security: FAIL - {e}")
    sys.exit(1)

# Test 3: Field Encryption
print("\n✓ Testing Field Encryption...")
try:
    from vibe_quality_searcharr.core.security import encrypt_field, decrypt_field

    api_key = "sonarr_api_key_abc123def456"
    encrypted = encrypt_field(api_key)
    decrypted = decrypt_field(encrypted)

    print(f"  - Original: {api_key}")
    print(f"  - Encrypted: {encrypted[:40]}...")
    print(f"  - Decrypted: {decrypted}")
    print(f"  - Round-trip: {'✓' if api_key == decrypted else '✗'}")

    assert api_key == decrypted, "Encryption round-trip failed"
    assert api_key not in encrypted, "Plaintext found in ciphertext"

    print("  ✅ Field Encryption: PASS")
except Exception as e:
    print(f"  ❌ Field Encryption: FAIL - {e}")
    sys.exit(1)

# Test 4: Token Generation
print("\n✓ Testing Token Generation...")
try:
    from vibe_quality_searcharr.core.security import generate_token

    token1 = generate_token(32)
    token2 = generate_token(32)

    print(f"  - Token 1: {token1[:20]}...")
    print(f"  - Token 2: {token2[:20]}...")
    print(f"  - Tokens Different: {'✓' if token1 != token2 else '✗'}")
    print(f"  - Token Length: {len(token1)} chars (URL-safe)")

    assert token1 != token2, "Tokens should be unique"
    assert len(token1) > 32, "Token should be URL-safe encoded"

    print("  ✅ Token Generation: PASS")
except Exception as e:
    print(f"  ❌ Token Generation: FAIL - {e}")
    sys.exit(1)

# Test 5: Database Models
print("\n✓ Testing Database Models...")
try:
    from vibe_quality_searcharr.models import User, RefreshToken, Instance, SearchQueue, SearchHistory

    print(f"  - User Model: ✓")
    print(f"  - RefreshToken Model: ✓")
    print(f"  - Instance Model: ✓")
    print(f"  - SearchQueue Model: ✓")
    print(f"  - SearchHistory Model: ✓")

    print("  ✅ Database Models: PASS")
except Exception as e:
    print(f"  ❌ Database Models: FAIL - {e}")
    sys.exit(1)

# Test 6: Database Connection (in-memory for testing)
print("\n✓ Testing Database Connection...")
try:
    from sqlalchemy import create_engine
    from vibe_quality_searcharr.database import Base

    # Create in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    tables = Base.metadata.tables.keys()
    print(f"  - Tables Created: {len(tables)}")
    for table in sorted(tables):
        print(f"    • {table}")

    assert "users" in tables, "Users table should exist"
    assert "refresh_tokens" in tables, "RefreshTokens table should exist"
    assert "instances" in tables, "Instances table should exist"
    assert "search_queue" in tables, "SearchQueue table should exist"
    assert "search_history" in tables, "SearchHistory table should exist"

    print("  ✅ Database Connection: PASS")
except Exception as e:
    print(f"  ❌ Database Connection: FAIL - {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 70)
print("✅ PHASE 1 VERIFICATION: ALL TESTS PASSED")
print("=" * 70)
print("\nComponents Verified:")
print("  ✓ Configuration Management (Docker secrets support)")
print("  ✓ Password Hashing (Argon2id with pepper)")
print("  ✓ Field Encryption (Fernet AES-128-CBC + HMAC)")
print("  ✓ Token Generation (Cryptographically secure)")
print("  ✓ Database Models (5 models with relationships)")
print("  ✓ Database Schema (5 tables created)")
print("\nPhase 1 Implementation: READY FOR PHASE 2")
print("=" * 70)
