from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Set, Tuple

import requests

from auth.models import AuthResult

log = logging.getLogger(__name__)


class AuthProvider(ABC):
    @abstractmethod
    def authenticate(self, headers: Dict[str, str]) -> AuthResult:
        raise NotImplementedError


def _parse_basic_auth(headers: Dict[str, str]) -> Optional[Tuple[str, str]]:
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header:
        return None
    if not auth_header.startswith("Basic "):
        return None

    encoded = auth_header[len("Basic "):].strip()
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None


class BasicStaticAuthProvider(AuthProvider):
    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password

    def authenticate(self, headers: Dict[str, str]) -> AuthResult:
        creds = _parse_basic_auth(headers)
        if not creds:
            return AuthResult.unauthorized("Missing or invalid Basic Authorization header")
        username, password = creds
        if username == self._username and password == self._password:
            return AuthResult.success(username=username)
        return AuthResult.unauthorized("Invalid username or password")


class NoAuthProvider(AuthProvider):
    def __init__(self, environment: str):
        self._environment = (environment or "").lower()

    def authenticate(self, headers: Dict[str, str]) -> AuthResult:
        if self._environment != "local":
            return AuthResult.forbidden("none auth mode is only permitted in local environment")
        return AuthResult.success(username="local-dev-user")


class KnoxAuthProvider(AuthProvider):
    """
    Adapter wrapper for existing Knox auth logic.
    Keep existing Knox implementation unchanged and call it from here.
    """
    def __init__(self, knox_delegate):
        self._delegate = knox_delegate

    def authenticate(self, headers: Dict[str, str]) -> AuthResult:
        try:
            # Expected existing behavior:
            # result = self._delegate.authenticate(headers)
            # Return mapped AuthResult below.
            result = self._delegate.authenticate(headers)
            if result.get("authenticated"):
                return AuthResult.success(
                    username=result.get("username", "unknown"),
                    groups=set(result.get("groups", [])),
                )
            return AuthResult.unauthorized(result.get("message", "Unauthorized"))
        except Exception:
            log.exception("Knox auth backend error")
            return AuthResult.unauthorized("Authentication backend error")


class LdapAuthProvider(AuthProvider):
    """
    Placeholder LDAP provider.
    Implement with your LDAP client library (ldap3 recommended).
    """
    def __init__(self, config: Dict[str, str]):
        self.config = config

    def authenticate(self, headers: Dict[str, str]) -> AuthResult:
        creds = _parse_basic_auth(headers)
        if not creds:
            return AuthResult.unauthorized("Missing or invalid Basic Authorization header")
        username, password = creds
        try:
            # TODO: Implement LDAP bind/search logic.
            # Fail-closed on any exception.
            # If success, optionally load groups from LDAP and return AuthResult.success(username, groups)
            raise NotImplementedError("LDAP auth not yet implemented")
        except NotImplementedError:
            return AuthResult.forbidden("LDAP provider not implemented yet")
        except Exception:
            log.exception("LDAP auth backend error")
            return AuthResult.unauthorized("Authentication backend error")


class NiFiIntegratedAuthProvider(AuthProvider):
    def __init__(self, config: Dict[str, str]):
        self.base_url = config["mcp.auth.nifi.base_url"].rstrip("/")
        self.timeout = int(config.get("mcp.auth.nifi.timeout_seconds", "8"))

        self.token_endpoint = config.get("mcp.auth.nifi.token_endpoint", "/nifi-api/access/token")
        self.current_user_endpoint = config.get("mcp.auth.nifi.current_user_endpoint", "/nifi-api/access/current-user")
        self.user_by_id_template = config.get("mcp.auth.nifi.user_by_id_endpoint_template", "/nifi-api/tenants/users/{id}")

        self.username_field = config.get("mcp.auth.nifi.current_user_username_field", "identity")
        self.user_id_field = config.get("mcp.auth.nifi.current_user_id_field", "id")
        self.groups_field = config.get("mcp.auth.nifi.groups_field", "userGroups")
        self.groups_field_fallback = config.get("mcp.auth.nifi.groups_field_fallback", "")

        self.group_check_enabled = config.get("mcp.authz.group_check.enabled", "false").lower() == "true"
        self.required_group = config.get("mcp.authz.required_group", "").strip()
        self.groups_missing_is_denied = config.get("mcp.auth.nifi.groups_missing_is_denied", "true").lower() == "true"

        self.verify_tls = config.get("mcp.auth.nifi.tls.verify", "true").lower() == "true"
        self.ca_file = config.get("mcp.auth.nifi.tls.ca_file", "").strip() or None
        self.client_cert = config.get("mcp.auth.nifi.tls.client_cert_file", "").strip()
        self.client_key = config.get("mcp.auth.nifi.tls.client_key_file", "").strip()

    def _tls_verify_param(self):
        if not self.verify_tls:
            return False
        if self.ca_file:
            return self.ca_file
        return True

    def _client_cert_param(self):
        if self.client_cert and self.client_key:
            return (self.client_cert, self.client_key)
        return None

    def _extract_nested(self, payload: dict, dotted: str):
        if not dotted:
            return None
        node = payload
        for part in dotted.split("."):
            if not isinstance(node, dict):
                return None
            node = node.get(part)
        return node

    def authenticate(self, headers: Dict[str, str]) -> AuthResult:
        creds = _parse_basic_auth(headers)
        if not creds:
            return AuthResult.unauthorized("Missing or invalid Basic Authorization header")
        username, password = creds

        verify = self._tls_verify_param()
        cert = self._client_cert_param()

        try:
            # Step 1: get token
            token_resp = requests.post(
                f"{self.base_url}{self.token_endpoint}",
                data={"username": username, "password": password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
                verify=verify,
                cert=cert,
            )
            if token_resp.status_code in (401, 403):
                return AuthResult.unauthorized("Invalid username or password")
            token_resp.raise_for_status()
            token = token_resp.text.strip()
            if not token:
                return AuthResult.unauthorized("Token not returned by NiFi")

            authz = {"Authorization": f"Bearer {token}"}

            # Step 2: current user
            current_resp = requests.get(
                f"{self.base_url}{self.current_user_endpoint}",
                headers=authz,
                timeout=self.timeout,
                verify=verify,
                cert=cert,
            )
            if current_resp.status_code == 403:
                return AuthResult.forbidden("Not allowed to resolve current user")
            current_resp.raise_for_status()
            current_payload = current_resp.json()

            resolved_username = current_payload.get(self.username_field, username)
            user_id = current_payload.get(self.user_id_field)
            groups: Set[str] = set()

            # Step 3: groups by user id
            if user_id:
                user_ep = self.user_by_id_template.replace("{id}", str(user_id))
                user_resp = requests.get(
                    f"{self.base_url}{user_ep}",
                    headers=authz,
                    timeout=self.timeout,
                    verify=verify,
                    cert=cert,
                )
                if user_resp.status_code == 403:
                    return AuthResult.forbidden("Not allowed to resolve user groups")
                user_resp.raise_for_status()
                user_payload = user_resp.json()

                raw_groups = user_payload.get(self.groups_field)
                if raw_groups is None and self.groups_field_fallback:
                    raw_groups = self._extract_nested(user_payload, self.groups_field_fallback)

                if isinstance(raw_groups, list):
                    groups = {str(g) for g in raw_groups if g is not None}
                elif isinstance(raw_groups, str):
                    groups = {raw_groups}

            if self.group_check_enabled and self.required_group:
                if not groups and self.groups_missing_is_denied:
                    return AuthResult.forbidden("Groups missing; access denied")
                if self.required_group not in groups:
                    return AuthResult.forbidden("Authenticated but not in required group")

            return AuthResult.success(username=resolved_username, groups=groups)

        except requests.HTTPError as e:
            log.warning("NiFi integrated auth HTTP error: %s", str(e))
            return AuthResult.unauthorized("Authentication backend error")
        except requests.RequestException:
            log.exception("NiFi integrated auth connectivity/TLS error")
            return AuthResult.unauthorized("Authentication backend error")
        except Exception:
            log.exception("NiFi integrated auth unexpected error")
            return AuthResult.unauthorized("Authentication backend error")