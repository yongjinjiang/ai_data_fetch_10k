"""Shared SSL helpers for consistent HTTPS behavior across the project."""

from __future__ import annotations

import os
import ssl
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_ca_bundle_path() -> str | None:
    """Return a CA bundle path, preferring env override, then certifi."""
    env_path = os.getenv("SSL_CERT_FILE")
    if env_path and Path(env_path).exists():
        return env_path

    try:
        import certifi

        return certifi.where()
    except Exception:
        return None


def create_ssl_context() -> ssl.SSLContext:
    """Create an SSL context using the project's CA bundle strategy."""
    ca_bundle = get_ca_bundle_path()
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()


def get_requests_verify_value() -> str | bool:
    """Value suitable for requests(..., verify=...)."""
    ca_bundle = get_ca_bundle_path()
    return ca_bundle if ca_bundle else True
