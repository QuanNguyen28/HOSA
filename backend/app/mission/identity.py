"""Canonical scientific-input identities shared by all backend services."""
import hashlib
import json

def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


