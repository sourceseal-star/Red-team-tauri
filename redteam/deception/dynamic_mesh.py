#!/usr/bin/env python3
"""
Dynamic Deception Mesh
=======================
Enhances static mesh with dynamic decoys (with TTL and rotation) and Honey Tokens.
"""
import time
import json
import uuid
import re
import secrets
import hashlib
import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict

try:
    from deception.mesh import DeceptionMesh, CanaryToken, DecoyEndpoint, SyntheticSession
except ImportError:
    from .mesh import DeceptionMesh, CanaryToken, DecoyEndpoint, SyntheticSession


@dataclass
class DynamicDecoy:
    path: str
    template_path: str
    token: str
    created_at: float
    expires_at: float
    ttl_hours: float
    hit_count: int = 0
    last_hit: str = ""
    last_hit_ip: str = ""
    last_hit_ua: str = ""


class HoneyTokenGenerator:
    """Generates fake honey credentials and files with embedded unique canary patterns."""

    @staticmethod
    def generate_canary() -> str:
        return f"SSCANARY-{uuid.uuid4()}"

    def generate_aws_key_pair(self) -> Dict[str, str]:
        # AKIA + 16 random uppercase characters / digits
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        akia = "AKIA" + "".join(secrets.choice(alphabet) for _ in range(16))
        canary = self.generate_canary()
        # Embed canary inside Secret Access Key
        secret = secrets.token_urlsafe(12) + canary + secrets.token_urlsafe(12)
        return {
            "aws_access_key_id": akia,
            "aws_secret_access_key": secret,
            "canary": canary
        }

    def generate_api_token(self, prefix: str = "sk_live_") -> Dict[str, str]:
        canary = self.generate_canary()
        token = f"{prefix}{secrets.token_hex(8)}{canary}{secrets.token_hex(8)}"
        return {
            "token": token,
            "canary": canary
        }

    def generate_jwt_token(self) -> Dict[str, str]:
        import base64
        canary = self.generate_canary()
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": "1234567890",
            "name": "Canary Administrator",
            "admin": True,
            "canary": canary,
            "iat": 1516239022
        }).encode()).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        jwt = f"{header}.{payload}.{signature}_canary_{canary}"
        return {
            "token": jwt,
            "canary": canary
        }

    def generate_env_decoy(self) -> Dict[str, str]:
        """Generates .env file decoy with fake variables all containing canaries."""
        aws = self.generate_aws_key_pair()
        db_canary = self.generate_canary()
        redis_canary = self.generate_canary()

        db_url = f"postgresql://postgres:{db_canary}@db.sourceseal.local:5432/production"
        redis_url = f"redis://:{redis_canary}@redis.sourceseal.local:6379/0"

        env_content = f"""# Production Environment Configurations
DEBUG=false
NODE_ENV=production
PORT=8080

# Database configurations
DATABASE_URL=\"{db_url}\"

# Cache configurations
REDIS_URL=\"{redis_url}\"

# AWS Credentials
AWS_ACCESS_KEY_ID=\"{aws['aws_access_key_id']}\"
AWS_SECRET_ACCESS_KEY=\"{aws['aws_secret_access_key']}\"

# API Keys
JWT_SECRET=\"{secrets.token_urlsafe(32)}\"
"""
        return {
            "env_content": env_content,
            "aws_access_key_id": aws["aws_access_key_id"],
            "aws_secret_access_key": aws["aws_secret_access_key"],
            "aws_canary": aws["canary"],
            "database_url": db_url,
            "db_canary": db_canary,
            "redis_url": redis_url,
            "redis_canary": redis_canary
        }


class DynamicDeceptionMesh(DeceptionMesh):
    """Dynamic deception mesh with expiring auto-rotated decoy URLs and Honey Token support."""

    def __init__(self, rotation_hours: float = 24.0):
        super().__init__()
        self.rotation_hours = rotation_hours
        self.last_rotation_time = 0.0
        self.dynamic_decoys: List[DynamicDecoy] = []
        self.expired_dynamic_decoys: List[DynamicDecoy] = []
        self.rotate_decoys()

    def rotate_decoys(self):
        """Regenerates all tokens and URLs (old ones become invalid/expired)."""
        now = time.time()
        ttl_seconds = self.rotation_hours * 3600
        expires_at = now + ttl_seconds

        new_decoys = []
        templates = [
            "/api/v1/keys/{token}",
            "/api/v2/tokens/{token}",
            "/admin/backup/{token}",
            "/.env.{token}"
        ]

        for template in templates:
            token = str(uuid.uuid4())
            path = template.format(token=token)
            new_decoys.append(DynamicDecoy(
                path=path,
                template_path=template,
                token=token,
                created_at=now,
                expires_at=expires_at,
                ttl_hours=self.rotation_hours
            ))

        # Rotate: archive current ones to expired/invalid list
        self.expired_dynamic_decoys = list(self.dynamic_decoys)
        self.dynamic_decoys = new_decoys
        self.last_rotation_time = now

    def check_rotation(self):
        """Triggers rotation if interval has passed."""
        if time.time() > self.last_rotation_time + (self.rotation_hours * 3600):
            self.rotate_decoys()

    def check_decoy_hit(self, path: str, method: str, ip: str = "", user_agent: str = "") -> Optional[Dict]:
        """Checks if a path hit any active or expired dynamic decoy, or static decoy."""
        self.check_rotation()

        # Check active dynamic decoys
        for d in self.dynamic_decoys:
            if d.path == path:
                d.hit_count += 1
                d.last_hit = datetime.datetime.utcnow().isoformat() + "Z"
                d.last_hit_ip = ip
                d.last_hit_ua = user_agent

                alert = {
                    "type": "decoy_accessed",
                    "severity": "critical",
                    "title": f"CRITICAL - Dynamic Decoy Endpoint Accessed: {method} {path}",
                    "description": f"Dynamic decoy endpoint {path} was accessed by IP {ip or 'unknown'} (User-Agent: {user_agent or 'unknown'}).",
                    "evidence": {
                        "path": d.path,
                        "template_path": d.template_path,
                        "method": method,
                        "token": d.token,
                        "is_expired": False,
                        "hits": d.hit_count,
                        "created_at": datetime.datetime.fromtimestamp(d.created_at, datetime.timezone.utc).isoformat() + "Z",
                        "expires_at": datetime.datetime.fromtimestamp(d.expires_at, datetime.timezone.utc).isoformat() + "Z",
                        "ip": ip,
                        "user_agent": user_agent,
                    },
                    "timestamp": d.last_hit,
                    "mitre": "T1046",
                    "recommended_actions": ["block_ip", "alert_soc", "isolate_endpoint"],
                }
                self.alerts.append(alert)
                return alert

        # Check expired dynamic decoys for a robust security posture
        for d in self.expired_dynamic_decoys:
            if d.path == path:
                d.hit_count += 1
                d.last_hit = datetime.datetime.utcnow().isoformat() + "Z"
                d.last_hit_ip = ip
                d.last_hit_ua = user_agent

                alert = {
                    "type": "decoy_accessed",
                    "severity": "critical",
                    "title": f"CRITICAL - Expired Dynamic Decoy Endpoint Accessed: {method} {path}",
                    "description": (
                        f"Expired/rotated dynamic decoy endpoint {path} was accessed by IP {ip or 'unknown'} "
                        f"(User-Agent: {user_agent or 'unknown'})."
                    ),
                    "evidence": {
                        "path": d.path,
                        "template_path": d.template_path,
                        "method": method,
                        "token": d.token,
                        "is_expired": True,
                        "hits": d.hit_count,
                        "created_at": datetime.datetime.fromtimestamp(d.created_at, datetime.timezone.utc).isoformat() + "Z",
                        "expires_at": datetime.datetime.fromtimestamp(d.expires_at, datetime.timezone.utc).isoformat() + "Z",
                        "ip": ip,
                        "user_agent": user_agent,
                    },
                    "timestamp": d.last_hit,
                    "mitre": "T1046",
                    "recommended_actions": ["block_ip", "alert_soc"],
                }
                self.alerts.append(alert)
                return alert

        # Fallback to parent static decoys check
        return super().check_decoy_hit(path, method, ip)

    def scan_logs_for_canaries(self, log_line: str, ip: str = "", user_agent: str = "") -> Optional[Dict]:
        """Scans network traffic, payloads, or logs for any embedded SSCANARY-{uuid} token."""
        canary_pattern = re.compile(r"SSCANARY-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
        match = canary_pattern.search(log_line)

        if match:
            canary_token = match.group(0)
            now_str = datetime.datetime.utcnow().isoformat() + "Z"

            alert = {
                "type": "canary_token_leaked",
                "severity": "critical",
                "title": "CRITICAL - Canary Token Found in Logs/Traffic",
                "description": f"Canary token '{canary_token}' was detected in network traffic or log line, indicating file compromise or theft!",
                "evidence": {
                    "canary_token": canary_token,
                    "detected_in_log_line": log_line,
                    "ip": ip,
                    "user_agent": user_agent,
                },
                "timestamp": now_str,
                "mitre": "T1550",
                "recommended_actions": ["block_ip", "isolate_compromised_files", "revoke_credentials", "alert_soc"]
            }
            self.alerts.append(alert)
            return alert
        return None

    def generate_fake_database_credentials(self) -> str:
        """Generates a JSON dump with fake users and credentials containing canaries."""
        generator = HoneyTokenGenerator()
        aws = generator.generate_aws_key_pair()
        api_token = generator.generate_api_token()
        jwt_token = generator.generate_jwt_token()

        credentials = [
            {
                "username": "admin_backup",
                "password_hash": hashlib.sha256(secrets.token_bytes(8)).hexdigest(),
                "api_key": api_token["token"],
                "role": "administrator",
                "canary": api_token["canary"]
            },
            {
                "username": "aws_sync_service",
                "aws_access_key_id": aws["aws_access_key_id"],
                "aws_secret_access_key": aws["aws_secret_access_key"],
                "role": "system",
                "canary": aws["canary"]
            },
            {
                "username": "external_api_user",
                "jwt_token": jwt_token["token"],
                "role": "developer",
                "canary": jwt_token["canary"]
            }
        ]
        return json.dumps(credentials, indent=2)

    def export_decoy_list_json(self) -> str:
        """Exports active decoy list as JSON for deployment to WAF/reverse proxy."""
        self.check_rotation()
        decoy_data = []
        for d in self.dynamic_decoys:
            decoy_data.append({
                "path": d.path,
                "method": "GET",
                "token": d.token,
                "expires_at": datetime.datetime.fromtimestamp(d.expires_at, datetime.timezone.utc).isoformat() + "Z",
                "is_expired": time.time() > d.expires_at
            })
        return json.dumps(decoy_data, indent=2)

    def get_summary(self) -> Dict:
        summary = super().get_summary()
        summary.update({
            "active_dynamic_decoys": len(self.dynamic_decoys),
            "expired_dynamic_decoys": len(self.expired_dynamic_decoys),
            "total_dynamic_hits": sum(d.hit_count for d in self.dynamic_decoys) + sum(d.hit_count for d in self.expired_dynamic_decoys),
        })
        return summary
