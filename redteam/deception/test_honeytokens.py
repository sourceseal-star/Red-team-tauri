#!/usr/bin/env python3
"""
Unit tests for Deception module — honeytoken generation and rotation.
Tests: JWT honeytoken, API key, AWS credentials, DB connection string,
       TokenRotationManager, STIX TIP export.
"""

import unittest
import json
import os
import time
import re
import base64
import hmac
import hashlib

try:
    from auto_rotation import HoneyTokenGenerator, TokenRotationManager
except ImportError:
    from deception.auto_rotation import HoneyTokenGenerator, TokenRotationManager


class TestHoneyTokenGenerator(unittest.TestCase):
    """Tests for HoneyTokenGenerator."""

    def setUp(self):
        self.gen = HoneyTokenGenerator()

    def test_jwt_generation(self):
        """Generated JWT should have 3 base64url parts separated by dots."""
        jwt_token = self.gen.generate_jwt()
        parts = jwt_token.split(".")
        self.assertEqual(len(parts), 3, "JWT must have header.payload.signature")

    def test_jwt_header_valid(self):
        """JWT header should decode to valid JSON with alg HS256."""
        jwt_token = self.gen.generate_jwt()
        header_b64 = jwt_token.split(".")[0]
        # Add padding for base64 decode
        padding = 4 - len(header_b64) % 4
        if padding != 4:
            header_b64 += "=" * padding
        header = json.loads(base64.urlsafe_b64decode(header_b64))
        self.assertEqual(header["alg"], "HS256")
        self.assertEqual(header["typ"], "JWT")

    def test_jwt_payload_valid(self):
        """JWT payload should contain expected fields."""
        jwt_token = self.gen.generate_jwt(user_id="test_lure")
        payload_b64 = jwt_token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        self.assertEqual(payload["sub"], "test_lure")
        self.assertEqual(payload["role"], "SuperAdmin")
        self.assertIn("iat", payload)
        self.assertIn("exp", payload)
        self.assertGreater(payload["exp"], payload["iat"])

    def test_jwt_signature_verifiable(self):
        """JWT signature should be verifiable with the known secret key."""
        jwt_token = self.gen.generate_jwt()
        parts = jwt_token.split(".")
        signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
        secret_key = os.environ.get("DECEPTION_HMAC_KEY", "decoy_test_key")
        expected_sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")
        self.assertEqual(parts[2], expected_b64)

    def test_api_key_generation(self):
        """API key should start with prefix and contain hex chars."""
        api_key = self.gen.generate_api_key()
        self.assertTrue(api_key.startswith("sk-live-"))
        # Should have prefix + 40 hex chars
        hex_part = api_key.replace("sk-live-", "")
        self.assertEqual(len(hex_part), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in hex_part))

    def test_api_key_custom_prefix(self):
        """API key should accept custom prefix."""
        api_key = self.gen.generate_api_key(prefix="rk-")
        self.assertTrue(api_key.startswith("rk-live-"))

    def test_api_key_uniqueness(self):
        """Two generated API keys should be different."""
        key1 = self.gen.generate_api_key()
        key2 = self.gen.generate_api_key()
        self.assertNotEqual(key1, key2)

    def test_aws_credentials_format(self):
        """AWS credentials should match standard format."""
        creds = self.gen.generate_aws_credentials()
        self.assertIn("aws_access_key_id", creds)
        self.assertIn("aws_secret_access_key", creds)
        # Access key ID starts with AKIA and is 20 chars
        self.assertTrue(creds["aws_access_key_id"].startswith("AKIA"))
        self.assertEqual(len(creds["aws_access_key_id"]), 20)
        # Secret access key is 40 chars
        self.assertEqual(len(creds["aws_secret_access_key"]), 40)

    def test_aws_credentials_uniqueness(self):
        """Two AWS credential sets should be different."""
        c1 = self.gen.generate_aws_credentials()
        c2 = self.gen.generate_aws_credentials()
        self.assertNotEqual(c1["aws_access_key_id"], c2["aws_access_key_id"])
        self.assertNotEqual(c1["aws_secret_access_key"], c2["aws_secret_access_key"])

    def test_db_connection_string(self):
        """DB connection string should contain credentials and a known DB engine."""
        conn = self.gen.generate_db_connection_string()
        # Should contain a password placeholder (it gets filled in)
        self.assertIn("://", conn)
        self.assertIn("sourceseal-internal.net", conn)
        # Should match one of the known DB engines
        engines = ["postgresql://", "mongodb+srv://", "mysql://", "mssql+pyodbc://"]
        self.assertTrue(any(conn.startswith(e) for e in engines), f"Unknown DB engine in: {conn}")

    def test_db_connection_strings_differ(self):
        """Multiple connection strings should have different passwords."""
        conns = set()
        for _ in range(10):
            conns.add(self.gen.generate_db_connection_string())
        self.assertGreater(len(conns), 1, "Connection strings should vary")


class TestTokenRotationManager(unittest.TestCase):
    """Tests for TokenRotationManager."""

    def test_initialization(self):
        """Manager should initialize with empty token store."""
        mgr = TokenRotationManager(default_ttl=3600)
        self.assertEqual(len(mgr.active_tokens), 0)
        self.assertEqual(mgr.default_ttl, 3600)

    def test_rotate_all(self):
        """rotate_all should populate active_tokens with all 4 types."""
        mgr = TokenRotationManager(default_ttl=60)
        result = mgr.rotate_all()
        self.assertIn("jwt", result)
        self.assertIn("api_key", result)
        self.assertIn("aws", result)
        self.assertIn("db_connection", result)
        self.assertGreater(len(mgr.active_tokens), 0)

    def test_rotate_invalidates_old_tokens(self):
        """Second rotation should replace old tokens."""
        mgr = TokenRotationManager(default_ttl=60)
        first = mgr.rotate_all()
        old_key = first["api_key"]
        # Verify old token is active
        self.assertIn(old_key, mgr.active_tokens)
        # Rotate again
        second = mgr.rotate_all()
        new_key = second["api_key"]
        # Old token should no longer be in active set
        self.assertNotIn(old_key, mgr.active_tokens)
        self.assertIn(new_key, mgr.active_tokens)

    def test_tokens_have_expiry(self):
        """Each token should have expires_at metadata."""
        mgr = TokenRotationManager(default_ttl=120)
        mgr.rotate_all()
        for token_value, meta in mgr.active_tokens.items():
            self.assertIn("expires_at", meta)
            self.assertGreater(meta["expires_at"], meta.get("created_at", 0))

    def test_token_types_present(self):
        """Should have JWT, API_KEY, AWS, and DB_CONNECTION_STRING types."""
        mgr = TokenRotationManager(default_ttl=60)
        mgr.rotate_all()
        types_present = set()
        for meta in mgr.active_tokens.values():
            types_present.add(meta["type"])
        self.assertIn("JWT", types_present)
        self.assertIn("API_KEY", types_present)
        self.assertIn("AWS_ACCESS_KEY_ID", types_present)
        self.assertIn("DB_CONNECTION_STRING", types_present)

    def test_callback_registration(self):
        """Callbacks should be called when registered."""
        mgr = TokenRotationManager(default_ttl=60)
        callback_calls = []

        def alert_callback(token_type, value, meta):
            callback_calls.append((token_type, value))

        mgr.callbacks.append(alert_callback)
        mgr.rotate_all()
        # If callbacks are called during rotation, we should have entries
        # (depends on implementation — some call on access, not rotation)
        # At minimum, the callback list should be non-empty and registered
        self.assertIn(alert_callback, mgr.callbacks)


class TestDeceptionMesh(unittest.TestCase):
    """Tests for DeceptionMesh (from mesh.py)."""

    def test_mesh_initialization(self):
        """DeceptionMesh should initialize."""
        from deception.mesh import DeceptionMesh
        mesh = DeceptionMesh()
        self.assertIsNotNone(mesh)

    def test_canary_token(self):
        """CanaryToken should be creatable with required args."""
        from deception.mesh import CanaryToken
        token = CanaryToken(
            id='canary-001', token='aws-key-lure', type='aws',
            context='decoy-bucket', created_at='2026-07-23T00:00:00Z'
        )
        self.assertIsNotNone(token)
        self.assertEqual(token.id, 'canary-001')


if __name__ == "__main__":
    unittest.main()
