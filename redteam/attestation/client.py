#!/usr/bin/env python3
import json
import time
import base64
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any

@dataclass
class Finding:
    severity: str  # "CRITICAL", "HIGH", "MEDIUM"
    type: str
    detail: str
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))

@dataclass
class AttestationReport:
    device_id: str
    platform: str  # "android" or "ios"
    attestation_token: str
    findings: List[Finding]

def generate_mock_jwt(device_id: str, nonce: str) -> str:
    """
    Generates a valid-format mock JWT token (header.payload.signature)
    using base64url encoding, avoiding third-party library dependencies.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "device_id": device_id,
        "timestamp": int(time.time()),
        "nonce": nonce,
        "integrity_token": f"play_integrity_verified_for_{device_id}"
    }
    
    def b64_encode(data: Dict[str, Any]) -> str:
        json_str = json.dumps(data)
        b64_bytes = base64.urlsafe_b64encode(json_str.encode('utf-8'))
        return b64_bytes.decode('utf-8').rstrip('=')
        
    encoded_header = b64_encode(header)
    encoded_payload = b64_encode(payload)
    mock_signature = "mock_signature_bytes_here"
    
    # Return mock token prefix to inform the server to bypass cryptography checks
    return f"mock_play_integrity_jwt_token_for_{encoded_header}.{encoded_payload}.{mock_signature}"

def send_post_request(url: str, data: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(url)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    jsondata = json.dumps(data)
    jsondataasbytes = jsondata.encode('utf-8')
    req.add_header('Content-Length', str(len(jsondataasbytes)))
    
    try:
        with urllib.request.urlopen(req, jsondataasbytes, timeout=5) as response:
            res_body = response.read().decode('utf-8')
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"[-] HTTP Error {e.code}: {error_body}")
        try:
            return json.loads(error_body)
        except Exception:
            return {"error": error_body}
    except urllib.error.URLError as e:
        print(f"[-] Connection Error: {e.reason}")
        return {"error": str(e.reason)}

def send_get_request(url: str) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            res_body = response.read().decode('utf-8')
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"[-] HTTP Error {e.code}: {error_body}")
        try:
            return json.loads(error_body)
        except Exception:
            return {"error": error_body}
    except urllib.error.URLError as e:
        print(f"[-] Connection Error: {e.reason}")
        return {"error": str(e.reason)}

def run_simulation(server_url: str):
    print("==================================================")
    print("      RASP Device Attestation Simulator Client     ")
    print("==================================================")
    print(f"Target Server: {server_url}\n")
    
    # Scenario 1: Clean/Safe Device
    print("[+] Scenario 1: Sending Clean Android Device Report...")
    clean_device_id = "device_pixel_9_clean"
    token_clean = generate_mock_jwt(clean_device_id, "nonce_123456")
    report_clean = AttestationReport(
        device_id=clean_device_id,
        platform="android",
        attestation_token=token_clean,
        findings=[]  # Safe device has no findings
    )
    res_clean = send_post_request(f"{server_url}/api/attestation/report", asdict(report_clean))
    print(f"[*] Server response: {res_clean}")
    
    # Query status of clean device
    time.sleep(0.5)
    print(f"[*] Querying status of '{clean_device_id}'...")
    status_clean = send_get_request(f"{server_url}/api/attestation/status/{clean_device_id}")
    print(f"[*] Device Status: {status_clean.get('status')} | Findings count: {len(status_clean.get('findings', []))}\n")

    # Scenario 2: Compromised/Rooted Android Device
    print("[+] Scenario 2: Sending Compromised Android Device Report...")
    compromised_device_id = "device_nexus_6_rooted"
    token_comp = generate_mock_jwt(compromised_device_id, "nonce_789012")
    report_comp = AttestationReport(
        device_id=compromised_device_id,
        platform="android",
        attestation_token=token_comp,
        findings=[
            Finding(severity="CRITICAL", type="ROOT_DETECTED", detail="Device is rooted (su binary or Magisk artifacts detected)."),
            Finding(severity="CRITICAL", type="FRIDA_DETECTED", detail="Frida instrumentation framework was found active on the device.")
        ]
    )
    res_comp = send_post_request(f"{server_url}/api/attestation/report", asdict(report_comp))
    print(f"[*] Server response: {res_comp}")
    
    # Query status of compromised device
    time.sleep(0.5)
    print(f"[*] Querying status of '{compromised_device_id}'...")
    status_comp = send_get_request(f"{server_url}/api/attestation/status/{compromised_device_id}")
    print(f"[*] Device Status: {status_comp.get('status')} | Findings: {status_comp.get('findings')}\n")

    # Scenario 3: Suspicious iOS Emulator Device
    print("[+] Scenario 3: Sending Suspicious iOS Simulator Report...")
    ios_device_id = "device_iphone_15_sim"
    token_ios = "mock_apple_device_check_token_for_" + ios_device_id
    report_ios = AttestationReport(
        device_id=ios_device_id,
        platform="ios",
        attestation_token=token_ios,
        findings=[
            Finding(severity="HIGH", type="emulator_detected", detail="The application is running inside a virtual simulator/emulator environment.")
        ]
    )
    res_ios = send_post_request(f"{server_url}/api/attestation/report", asdict(report_ios))
    print(f"[*] Server response: {res_ios}")
    
    # Query status of suspicious device
    time.sleep(0.5)
    print(f"[*] Querying status of '{ios_device_id}'...")
    status_ios = send_get_request(f"{server_url}/api/attestation/status/{ios_device_id}")
    print(f"[*] Device Status: {status_ios.get('status')} | Findings: {status_ios.get('findings')}\n")

    # Scenario 4: Rate Limiting Test (Same Device Sent Instantly Again)
    print("[+] Scenario 4: Testing Rate Limiter (Sending Clean Android Report again immediately)...")
    res_ratelimit = send_post_request(f"{server_url}/api/attestation/report", asdict(report_clean))
    print(f"[*] Server response: {res_ratelimit}")

if __name__ == "__main__":
    server = "http://127.0.0.1:8000"
    if len(sys.argv) > 1:
        server = sys.argv[1]
    run_simulation(server)


class AttestationClient:
    """Cliente que simula envío de atestación desde un dispositivo móvil."""

    def __init__(self, server_url: str = "http://localhost:9090", device_id: str = "test-device-001"):
        self.server_url = server_url.rstrip("/")
        self.device_id = device_id
        try:
            import requests as _requests
            self._requests = _requests
        except ImportError:
            self._requests = None

    def _generate_play_integrity_token(self) -> str:
        """Genera un mock Play Integrity JWT token."""
        import base64, json, hashlib
        header = base64.b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).decode().rstrip("=")
        payload_data = {
            "device_id": self.device_id,
            "timestamp": datetime.utcnow().isoformat(),
            "nonce": hashlib.sha256(str(time.time()).encode()).hexdigest()[:16],
            "apk_package": "com.sourceseal.app",
            "integrity_verdict": "MEETS_DEVICE_INTEGRITY",
        }
        payload = base64.b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
        signature = hashlib.sha256((header + "." + payload + "sourceseal-secret").encode()).hexdigest()
        return f"{header}.{payload}.{signature}"

    def _generate_devicecheck_token(self) -> str:
        """Genera un mock Apple DeviceCheck token."""
        import base64, hashlib
        return base64.b64encode(hashlib.sha256(
            f"devicecheck:{self.device_id}:{time.time()}".encode()
        ).digest()).decode().rstrip("=")

    def send_report(self, findings: list, platform: str = "android") -> dict:
        """Envía findings al servidor de atestación."""
        token = (self._generate_play_integrity_token() if platform == "android"
                 else self._generate_devicecheck_token())
        report = {
            "device_id": self.device_id,
            "platform": platform,
            "integrity_token": token,
            "findings": findings,
        }
        if self._requests:
            try:
                resp = self._requests.post(
                    f"{self.server_url}/api/attestation/report",
                    json=report, timeout=10, verify=False,
                )
                return resp.json()
            except Exception as e:
                return {"status": "error", "error": str(e)}
        else:
            return {"status": "no_requests_lib", "report": report}

    def get_status(self) -> dict:
        """Obtiene el estado de atestación de este dispositivo."""
        if self._requests:
            try:
                resp = self._requests.get(
                    f"{self.server_url}/api/attestation/status/{self.device_id}",
                    timeout=10, verify=False,
                )
                return resp.json()
            except Exception as e:
                return {"status": "error", "error": str(e)}
        return {"status": "offline"}
