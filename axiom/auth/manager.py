import hashlib
import hmac
import base64
import json
import time
from typing import Dict, Any, Optional

SECRET_KEY = "AXIOM_SECURE_PLATFORM_KEY"  # In production, load from secure local config

def hash_password(password: str) -> str:
    """PBKDF2 password hashing (no external bcrypt dependencies required)."""
    salt = b"axiom_salt_vector"
    iterations = 100000
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return base64.b64encode(key).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    """Verifies a password against the PBKDF2 hash."""
    return hash_password(password) == hashed

def _base64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").replace("=", "")

def _base64_url_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))

def create_jwt_token(payload: Dict[str, Any], expires_in: int = 3600) -> str:
    """
    Generates a secure cryptographically signed JWT token 
    without external dependencies using HMAC-SHA256.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    
    # Add expiration time to payload
    payload_copy = payload.copy()
    payload_copy["exp"] = int(time.time()) + expires_in
    
    header_encoded = _base64_url_encode(json.dumps(header).encode("utf-8"))
    payload_encoded = _base64_url_encode(json.dumps(payload_copy).encode("utf-8"))
    
    signing_input = f"{header_encoded}.{payload_encoded}".encode("utf-8")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_encoded = _base64_url_encode(signature)
    
    return f"{header_encoded}.{payload_encoded}.{signature_encoded}"

def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and cryptographically validates a JWT token.
    Returns the payload if valid, otherwise None.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        
        header_encoded, payload_encoded, signature_encoded = parts
        signing_input = f"{header_encoded}.{payload_encoded}".encode("utf-8")
        
        # Verify signature
        expected_signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        expected_signature_encoded = _base64_url_encode(expected_signature)
        
        if not hmac.compare_digest(signature_encoded.encode("utf-8"), expected_signature_encoded.encode("utf-8")):
            return None
            
        payload = json.loads(_base64_url_decode(payload_encoded).decode("utf-8"))
        
        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception:
        return None
