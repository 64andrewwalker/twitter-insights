"""API key authentication middleware."""

import hmac
import os


def get_api_keys() -> list[str]:
    keys = []
    primary = os.environ.get("TI_API_KEY", "")
    if primary:
        keys.append(primary)
    old = os.environ.get("TI_API_KEY_OLD", "")
    if old:
        keys.append(old)
    return keys


def verify_api_key(provided: str) -> bool:
    if not provided:
        return False
    for valid_key in get_api_keys():
        if hmac.compare_digest(provided.encode(), valid_key.encode()):
            return True
    return False
