from __future__ import annotations

from typing import Dict

from auth.providers import (
    AuthProvider,
    BasicStaticAuthProvider,
    KnoxAuthProvider,
    LdapAuthProvider,
    NiFiIntegratedAuthProvider,
    NoAuthProvider,
)


def _require(config: Dict[str, str], key: str):
    value = config.get(key, "").strip()
    if not value:
        raise ValueError(f"Missing required config key: {key}")
    return value


def build_auth_provider(config: Dict[str, str], knox_delegate=None) -> AuthProvider:
    mode = config.get("mcp.auth.mode", "basic_static").strip().lower()

    if config.get("mcp.auth.fail_open", "false").lower() != "false":
        raise ValueError("mcp.auth.fail_open must be false (fail-closed required)")

    if mode == "basic_static":
        username = _require(config, "mcp.auth.basic.username")
        password = _require(config, "mcp.auth.basic.password")
        return BasicStaticAuthProvider(username=username, password=password)

    if mode == "none":
        env = _require(config, "app.environment").lower()
        allow_local_only = config.get("mcp.auth.none.allow_in_local_only", "true").lower() == "true"
        if allow_local_only and env != "local":
            raise ValueError("none auth mode is only allowed when app.environment=local")
        return NoAuthProvider(environment=env)

    if mode == "knox":
        if knox_delegate is None:
            raise ValueError("Knox mode selected but knox_delegate is not provided")
        return KnoxAuthProvider(knox_delegate=knox_delegate)

    if mode == "ldap":
        _require(config, "mcp.auth.ldap.url")
        _require(config, "mcp.auth.ldap.bind_dn")
        _require(config, "mcp.auth.ldap.bind_password")
        _require(config, "mcp.auth.ldap.user_base_dn")
        _require(config, "mcp.auth.ldap.user_filter")
        return LdapAuthProvider(config=config)

    if mode == "nifi_integrated":
        _require(config, "mcp.auth.nifi.base_url")
        return NiFiIntegratedAuthProvider(config=config)

    raise ValueError(f"Unsupported mcp.auth.mode: {mode}")