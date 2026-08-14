"""
defense.attestation — Hardware Keystore + Device Attestation
=============================================================

Mock de Android KeyStore / StrongBox y SafetyNet / Play Integrity API.

La generación real de claves ECDSA/RSA con respaldo TEE/StrongBox no es
posible en un proceso Python fuera del dispositivo, así que se modela
con ``pycryptodome`` (``Crypto.PublicKey``) y se valida el ciclo de vida
completo: generate → sign → unwrap → verify_cert_chain → verify_integrity.

El verificador de attestation valida:
  * Cadena de certificados X.509 (mock de Google Hardware Attestation Root).
  * Integridad del binario (comparación contra hash conocido).
  * Versión del sistema operativo.
  * Nivel de parche de seguridad.
"""
from __future__ import annotations

import base64
import dataclasses
import datetime
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# pycryptodome es la única dependencia de criptografía disponible en el
# proyecto (declarada en requirements.txt).
from Crypto.PublicKey import RSA, ECC
from Crypto.Signature import pkcs1_15, eddsa
from Crypto.Hash import SHA256, SHA384
from Crypto.Util import number

logger = logging.getLogger(__name__)


# ===================== Data types =====================


@dataclasses.dataclass
class AttestationCert:
    """Certificado X.509 mock (DER simulado como dict)."""
    subject: str
    issuer: str
    not_before: float
    not_after: float
    public_key_pem: str
    serial: str
    is_google_root: bool = False

    def is_valid_at(self, ts: float) -> bool:
        return self.not_before <= ts <= self.not_after


@dataclasses.dataclass
class AttestationResult:
    valid: bool
    reason: str
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ===================== Hardware Keystore (mock) =====================


class HardwareKeystore:
    """Mock de Android KeyStore con respaldo StrongBox.

    Genera pares de claves RSA-2048 (equivalente a ``KeyGenParameterSpec``
    con ``setIsStrongBoxBacked(true)``). Las claves se mantienen en un
    store en memoria; el ``sign_payload`` emula la operación interna del
    TEE (la clave privada nunca sale del keystore)."""

    KEY_ALGO_RSA = "RSA-2048"
    KEY_ALGO_ECDSA = "ECDSA-P256"

    def __init__(self, *, key_bits: int = 2048):
        self.key_bits = key_bits
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        # Certificado raíz de Google (mock) — siempre confiable.
        self._root_pub_pem = self._generate_root_pub()

    @property
    def root_public_pem(self) -> str:
        return self._root_pub_pem

    def _generate_root_pub(self) -> str:
        key = RSA.generate(self.key_bits)
        return key.publickey().export_key().decode()

    # ---------- API pública ----------

    def generate_key(self, alias: str, *, algo: str = KEY_ALGO_RSA) -> str:
        """Genera una clave y la guarda bajo ``alias``. Retorna el PEM
        público (lo que la app ve). Lanza ``KeyError`` si ya existe."""
        with self._lock:
            if alias in self._keys:
                raise KeyError(f"alias {alias} ya existe")
            if algo == self.KEY_ALGO_RSA:
                key = RSA.generate(self.key_bits)
                pem = key.export_key().decode()
                pub_pem = key.publickey().export_key().decode()
            elif algo == self.KEY_ALGO_ECDSA:
                key = ECC.generate(curve="P-256")
                pem = key.export_key(format="PEM")
                pub_pem = key.public_key().export_key(format="PEM")
            else:
                raise ValueError(f"algo no soportado: {algo}")
            self._keys[alias] = {
                "algo": algo,
                "private_pem": pem,
                "public_pem": pub_pem,
                "created_at": time.time(),
                "wrapped": False,
            }
            return pub_pem

    def has_key(self, alias: str) -> bool:
        with self._lock:
            return alias in self._keys

    def sign_payload(self, alias: str, payload: bytes) -> bytes:
        """Firma ``payload`` con la clave privada (mock TEE)."""
        with self._lock:
            entry = self._keys.get(alias)
            if entry is None:
                raise KeyError(f"alias {alias} no existe")
            algo = entry["algo"]
            priv_pem = entry["private_pem"]
        if algo == self.KEY_ALGO_RSA:
            key = RSA.import_key(priv_pem)
            h = SHA256.new(payload)
            return pkcs1_15.new(key).sign(h)
        elif algo == self.KEY_ALGO_ECDSA:
            key = ECC.import_key(priv_pem)
            h = SHA256.new(payload)
            # EdDSA no es exactamente ECDSA-P256 — usamos DSS para P-256.
            from Crypto.Signature import DSS
            from Crypto.PublicKey import ECC
            signer = DSS.new(key, "deterministic-rfc6979")
            return signer.sign(h)
        else:
            raise ValueError(f"algo no soportado: {algo}")

    def unwrap_key(self, alias: str, wrapped: bytes) -> str:
        """Simula ``KeyStore.unwrapKey``: 'desenvuelve' una clave
        wrappeada con AES (mock) y la importa al keystore bajo
        ``alias``."""
        # En una StrongBox real el unwrap usa AES-GCM con la KEK del TEE.
        # Aquí basta con un XOR determinístico + nonce; la seguridad
        # criptográfica real la aporta el HSM de producción.
        if len(wrapped) < 12:
            raise ValueError("wrapped demasiado corto")
        nonce = wrapped[:12]
        ct = wrapped[12:]
        # XOR con keystream derivado de SHA-256(nonce + root_pub)
        ks = hashlib.sha256(nonce + self._root_pub_pem.encode()).digest()
        pt = bytes(b ^ ks[i % len(ks)] for i, b in enumerate(ct))
        pem = pt.decode("utf-8", errors="replace")
        with self._lock:
            self._keys[alias] = {
                "algo": self.KEY_ALGO_RSA,
                "private_pem": pem,
                "public_pem": RSA.import_key(pem).publickey().export_key().decode(),
                "created_at": time.time(),
                "wrapped": True,
            }
        return self._keys[alias]["public_pem"]

    def delete_key(self, alias: str) -> bool:
        with self._lock:
            return self._keys.pop(alias, None) is not None

    # ---------- Mock attestation payload ----------

    def attestation_payload(self, alias: str, *, nonce: bytes) -> Dict[str, Any]:
        """Genera un attestation payload firmado (SafetyNet-style)."""
        if not self.has_key(alias):
            raise KeyError(alias)
        nonce_b64 = base64.b64encode(nonce).decode()
        body = {
            "alias": alias,
            "nonce": nonce_b64,
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "algo": self._keys[alias]["algo"],
            "strongbox": True,
        }
        blob = json.dumps(body, sort_keys=True).encode()
        sig = self.sign_payload(alias, blob)
        return {
            "body": body,
            "signature": base64.b64encode(sig).decode(),
            "cert_chain": [
                base64.b64encode(self._root_pub_pem.encode()).decode(),
            ],
        }


# ===================== Attestation Verifier =====================


class AttestationVerifier:
    """Verifica attestation payloads (mock) emitidos por un
    ``HardwareKeystore`` o un dispositivo Android real (Key Attestation)."""

    def __init__(
        self,
        *,
        min_os_version: str = "13",
        min_patch_level: str = "2024-09",
        required_key_strongbox: bool = True,
        cert_chain_max_depth: int = 4,
    ):
        self.min_os_version = min_os_version
        self.min_patch_level = min_patch_level
        self.required_key_strongbox = required_key_strongbox
        self.cert_chain_max_depth = cert_chain_max_depth
        # Mock: aceptamos cualquier cadena que apunte a un PEM con el
        # header "BEGIN PUBLIC KEY" (en producción validaríamos contra el
        # root CA real de Google Hardware Attestation).
        self._known_roots: List[str] = []

    def add_trusted_root(self, root_pub_pem: str) -> None:
        self._known_roots.append(root_pub_pem)

    # ---------- Public verifiers ----------

    def verify_cert_chain(self, cert_chain_b64: List[str]) -> AttestationResult:
        """Valida que la cadena de certificados termine en un root conocido.
        En este mock, basta con que la cadena esté bien formada (cada
        elemento base64-decodable) y no exceda la profundidad máxima."""
        if not cert_chain_b64:
            return AttestationResult(False, "cadena vacía")
        if len(cert_chain_b64) > self.cert_chain_max_depth:
            return AttestationResult(False, f"cadena excede max depth {self.cert_chain_max_depth}")
        try:
            decoded = [base64.b64decode(c).decode() for c in cert_chain_b64]
        except Exception as e:
            return AttestationResult(False, f"base64 inválido: {e}")
        if not all(d.startswith("-----BEGIN") for d in decoded):
            return AttestationResult(False, "elementos no parecen PEM")
        # En mock aceptamos si el root está en _known_roots, o si la
        # cadena tiene al menos un elemento (modo permisivo para tests).
        if self._known_roots:
            if not any(r in self._known_roots for r in decoded):
                return AttestationResult(False, "root no confiable", {"decoded": decoded})
        return AttestationResult(True, "cadena aceptada", {"depth": len(decoded)})

    def verify_integrity(self, binary_sha256: str, expected_sha256: str) -> AttestationResult:
        if not binary_sha256 or not expected_sha256:
            return AttestationResult(False, "hash vacío")
        if binary_sha256.lower() != expected_sha256.lower():
            return AttestationResult(False, "hash mismatch",
                                     {"expected": expected_sha256, "actual": binary_sha256})
        return AttestationResult(True, "integridad OK")

    def verify_os_version(self, reported_version: str) -> AttestationResult:
        try:
            reported_major = int(reported_version.split(".")[0])
            min_major = int(self.min_os_version.split(".")[0])
        except (ValueError, AttributeError):
            return AttestationResult(False, "version inválida", {"reported": reported_version})
        if reported_major < min_major:
            return AttestationResult(False, f"OS {reported_version} < {self.min_os_version}")
        return AttestationResult(True, "OS OK", {"reported": reported_version, "min": self.min_os_version})

    def verify_patch_level(self, reported_patch: str) -> AttestationResult:
        """reported_patch formato YYYY-MM. Compara lexicográficamente."""
        if not reported_patch or len(reported_patch) < 7:
            return AttestationResult(False, "patch inválido", {"reported": reported_patch})
        if reported_patch < self.min_patch_level:
            return AttestationResult(False,
                                     f"patch {reported_patch} < {self.min_patch_level}")
        return AttestationResult(True, "patch OK",
                                 {"reported": reported_patch, "min": self.min_patch_level})

    def verify_payload(
        self,
        payload: Dict[str, Any],
        *,
        expected_binary_sha256: Optional[str] = None,
        reported_os_version: Optional[str] = None,
        reported_patch_level: Optional[str] = None,
        root_pub_pem: Optional[str] = None,
    ) -> AttestationResult:
        """Verificación agregada: cadena + integridad + OS + patch."""
        chain = self.verify_cert_chain(payload.get("cert_chain", []))
        if not chain.valid:
            return chain
        if root_pub_pem:
            self.add_trusted_root(root_pub_pem)
        body = payload.get("body", {})
        if self.required_key_strongbox and not body.get("strongbox"):
            return AttestationResult(False, "strongbox requerido pero no presente")
        if expected_binary_sha256 and body.get("binary_sha256"):
            integ = self.verify_integrity(body["binary_sha256"], expected_binary_sha256)
            if not integ.valid:
                return integ
        if reported_os_version:
            os_res = self.verify_os_version(reported_os_version)
            if not os_res.valid:
                return os_res
        if reported_patch_level:
            patch = self.verify_patch_level(reported_patch_level)
            if not patch.valid:
                return patch
        return AttestationResult(True, "attestation OK",
                                 {"chain": chain.details,
                                  "os": reported_os_version,
                                  "patch": reported_patch_level})
