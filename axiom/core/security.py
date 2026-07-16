"""
OCIF Security Module — Cryptography, Authentication & RBAC.

Enforces role-based access controls (RBAC) per the security matrix in Document 14,
provides cryptographically secure JWT token parsing/signing, password hashing,
and SHA-256 hash chaining functions for Layer 7 audit integrity.

Traces to:
  - Document 14 (Security Design) Section 3: Identity & Access Management
  - Document 14 (Security Design) Section 3.1: RBAC Matrix
  - Document 9 (Database Design) Section 4.5: SHA-256 audit log chain
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, Any, Optional, List
from core.config import settings
from core.exceptions import AuthenticationError, AuthorizationError
from core.models.base import UserRole


# ===========================================================================
# Password Hashing Utilities (PBKDF2-SHA256 with a per-user random salt)
# ===========================================================================

_PBKDF2_ITERATIONS = 100_000
_SALT_BYTES = 16


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Computes a PBKDF2-SHA256 password hash with a per-user random salt.

    Returns a self-describing ``salt$hash`` string (both base64) so each
    stored credential carries its own salt. Passing no salt generates a fresh
    random one — the previous implementation used a single hardcoded global
    salt for every user, which defeats the purpose of salting (identical
    passwords produced identical hashes and a single rainbow table covered the
    whole platform).
    """
    if salt is None:
        salt = secrets.token_bytes(_SALT_BYTES)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{base64.b64encode(salt).decode('utf-8')}${base64.b64encode(key).decode('utf-8')}"


def verify_password(password: str, stored: str) -> bool:
    """Verifies a password against a stored ``salt$hash`` credential.

    Uses a constant-time comparison to avoid leaking match progress via timing.
    """
    if not stored or "$" not in stored:
        return False
    salt_b64, _, hash_b64 = stored.partition("$")
    try:
        salt = base64.b64decode(salt_b64.encode("utf-8"))
    except Exception:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    try:
        expected = base64.b64decode(hash_b64.encode("utf-8"))
    except Exception:
        return False
    return hmac.compare_digest(candidate, expected)


# ===========================================================================
# Symmetric Secret Encryption (per-user provider API keys, at rest)
# ===========================================================================

def _fernet():
    """Builds a Fernet cipher for encrypting user-supplied provider API keys.

    Uses OCIF_SECRET_ENCRYPTION_KEY when set (must be a valid urlsafe-base64
    32-byte Fernet key); otherwise derives a stable key from the JWT secret so
    local development works without extra configuration. In production, set an
    explicit key so rotating the JWT secret does not orphan stored ciphertext.
    """
    from cryptography.fernet import Fernet

    configured = settings.entitlement.secret_encryption_key
    if configured:
        key = configured.encode("utf-8")
    else:
        digest = hashlib.sha256(
            f"axiom-key-encryption::{settings.auth.jwt_secret_key}".encode("utf-8")
        ).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypts a secret (e.g. a provider API key) for storage at rest."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypts a secret previously produced by :func:`encrypt_secret`."""
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def last4(secret: str) -> str:
    """Returns the last 4 characters of a secret for safe display."""
    return secret[-4:] if len(secret) >= 4 else "****"


# ===========================================================================
# Cryptographically Signed JWT Token Utilities
# ===========================================================================

def _base64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").replace("=", "")


def _base64_url_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def create_access_token(payload: Dict[str, Any], expires_in: int = None) -> str:
    """
    Creates a secure cryptographically signed JWT token 
    without external dependencies using HMAC-SHA256.
    """
    if expires_in is None:
        expires_in = settings.auth.jwt_expiration_seconds

    header = {"alg": "HS256", "typ": "JWT"}
    
    payload_copy = payload.copy()
    payload_copy["exp"] = int(time.time()) + expires_in
    payload_copy["iat"] = int(time.time())
    payload_copy["iss"] = settings.auth.oauth2_issuer or "ocif-platform"
    payload_copy["aud"] = settings.auth.oauth2_audience

    header_encoded = _base64_url_encode(json.dumps(header).encode("utf-8"))
    payload_encoded = _base64_url_encode(json.dumps(payload_copy).encode("utf-8"))
    
    signing_input = f"{header_encoded}.{payload_encoded}".encode("utf-8")
    
    signature = hmac.new(
        settings.auth.jwt_secret_key.encode("utf-8"), 
        signing_input, 
        hashlib.sha256
    ).digest()
    signature_encoded = _base64_url_encode(signature)
    
    return f"{header_encoded}.{payload_encoded}.{signature_encoded}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and cryptographically validates a JWT token signature and expiry.
    Raises AuthenticationError if invalid or expired.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthenticationError("Invalid token format")
        
        header_encoded, payload_encoded, signature_encoded = parts
        signing_input = f"{header_encoded}.{payload_encoded}".encode("utf-8")
        
        # Verify signature
        expected_signature = hmac.new(
            settings.auth.jwt_secret_key.encode("utf-8"), 
            signing_input, 
            hashlib.sha256
        ).digest()
        expected_signature_encoded = _base64_url_encode(expected_signature)
        
        if not hmac.compare_digest(signature_encoded.encode("utf-8"), expected_signature_encoded.encode("utf-8")):
            raise AuthenticationError("Signature verification failed")
            
        payload = json.loads(_base64_url_decode(payload_encoded).decode("utf-8"))
        
        # Verify expiration
        if payload.get("exp", 0) < time.time():
            raise AuthenticationError("Token has expired")
            
        return payload
    except AuthenticationError:
        raise
    except Exception as e:
        raise AuthenticationError(f"Token decoding failed: {str(e)}")


# ===========================================================================
# RBAC Validation Matrix per Document 14 Section 3.1
# ===========================================================================

# Action to Roles lookup matrix mapping Doc 14 Section 3.1
RBAC_MATRIX: Dict[str, List[UserRole]] = {
    "chat_query": [
        UserRole.END_USER, UserRole.PROCESS_OWNER, UserRole.COMPLIANCE_OFFICER, 
        UserRole.TENANT_ADMIN, UserRole.PLATFORM_ADMIN
    ],
    "view_own_audit": [
        UserRole.END_USER, UserRole.PROCESS_OWNER, UserRole.COMPLIANCE_OFFICER, 
        UserRole.TENANT_ADMIN, UserRole.PLATFORM_ADMIN
    ],
    "view_tenant_audit": [
        UserRole.COMPLIANCE_OFFICER, UserRole.TENANT_ADMIN, UserRole.PLATFORM_ADMIN
    ],
    "approve_hitl": [
        UserRole.PROCESS_OWNER, UserRole.COMPLIANCE_OFFICER, UserRole.TENANT_ADMIN, 
        UserRole.PLATFORM_ADMIN
    ],
    "configure_policies": [
        UserRole.COMPLIANCE_OFFICER, UserRole.TENANT_ADMIN, UserRole.PLATFORM_ADMIN
    ],
    "register_tools": [
        UserRole.TENANT_ADMIN, UserRole.PLATFORM_ADMIN
    ],
    "manage_tenants": [
        UserRole.PLATFORM_ADMIN
    ]
}


def verify_rbac(user_role: UserRole, action: str) -> None:
    """
    Checks if a role is authorized to execute an action based on the RBAC Matrix.
    Raises AuthorizationError if not permitted.
    """
    allowed_roles = RBAC_MATRIX.get(action)
    if not allowed_roles:
        # Default deny posture: block unknown actions
        raise AuthorizationError(f"Action '{action}' is not registered in the security governance schema")
        
    if user_role not in allowed_roles:
        raise AuthorizationError(
            detail=f"User role '{user_role}' is not authorized to perform action '{action}'",
            required_role=", ".join(allowed_roles)
        )


# ===========================================================================
# Cryptographic Audit Hash Chaining (Layer 7)
# ===========================================================================

def calculate_event_hash(prev_hash: Optional[str], event_payload: Dict[str, Any]) -> str:
    """
    Calculates the SHA-256 cryptographic chain hash for a given audit event.
    Per Doc 9 Section 4.5, creates an immutable audit trace by chaining event payloads.
    """
    # Create deterministic representation of payload using sorted keys
    serialized_payload = json.dumps(event_payload, sort_keys=True)
    
    hash_input = f"{prev_hash or ''}:{serialized_payload}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
