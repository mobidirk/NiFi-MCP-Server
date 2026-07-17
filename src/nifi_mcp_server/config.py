from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


def _parse_properties_file(path: str) -> Dict[str, str]:
	"""
	Simple .properties parser (key=value, ignores comments/# and empty lines).
	"""
	props: Dict[str, str] = {}
	p = Path(path)
	if not p.exists():
		return props

	for raw_line in p.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#"):
			continue
		if "=" not in line:
			continue
		k, v = line.split("=", 1)
		props[k.strip()] = v.strip()
	return props


def _pick(props: Dict[str, str], env_key: str, prop_key: str, default: Optional[str] = None) -> Optional[str]:
	"""
	Priority: ENV var > properties file (dot-style or ENV-style key) > default.
	"""
	val = os.getenv(env_key)
	if val is not None and str(val).strip() != "":
		return val
	if prop_key in props:
		return props[prop_key]
	if env_key in props:
		return props[env_key]
	return default


def _as_bool(value: Optional[str], default: bool = False) -> bool:
	if value is None:
		return default
	return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class ServerConfig:
	# Config source
	config_file: str = "config.properties"

	# Transport
	transport: Optional[str] = None
	host: Optional[str] = None
	port: Optional[int] = None

	# Runtime environment
	environment: str = "local"

	# MCP incoming auth mode (user -> MCP)
	mcp_auth_mode: str = "basic_static"  # basic_static|none|knox|ldap|nifi_integrated
	mcp_auth_fail_open: bool = False
	mcp_authz_group_check_enabled: bool = False
	mcp_authz_required_group: str = ""

	# basic_static
	mcp_auth_basic_username: Optional[str] = None
	mcp_auth_basic_password: Optional[str] = None

	# none
	mcp_auth_none_allow_in_local_only: bool = True

	# Knox + NiFi
	knox_gateway_url: str = ""
	nifi_api_base: Optional[str] = None

	# Knox options
	knox_token: Optional[str] = None
	knox_cookie: Optional[str] = None
	knox_user: Optional[str] = None
	knox_password: Optional[str] = None
	knox_token_endpoint: Optional[str] = None
	knox_passcode_token: Optional[str] = None

	# LDAP (skeleton config)
	mcp_auth_ldap_url: Optional[str] = None
	mcp_auth_ldap_bind_dn: Optional[str] = None
	mcp_auth_ldap_bind_password: Optional[str] = None
	mcp_auth_ldap_user_base_dn: Optional[str] = None
	mcp_auth_ldap_user_filter: Optional[str] = None
	mcp_auth_ldap_group_base_dn: Optional[str] = None
	mcp_auth_ldap_group_filter: Optional[str] = None
	mcp_auth_ldap_timeout_seconds: int = 5
	mcp_auth_ldap_tls_verify: bool = True
	mcp_auth_ldap_tls_ca_file: Optional[str] = None

	# NiFi integrated auth
	mcp_auth_nifi_base_url: Optional[str] = None
	mcp_auth_nifi_timeout_seconds: int = 8
	mcp_auth_nifi_tls_verify: bool = True
	mcp_auth_nifi_tls_ca_file: Optional[str] = None
	mcp_auth_nifi_tls_client_cert_file: Optional[str] = None
	mcp_auth_nifi_tls_client_key_file: Optional[str] = None

	mcp_auth_nifi_token_endpoint: str = "/nifi-api/access/token"
	mcp_auth_nifi_current_user_endpoint: str = "/nifi-api/access/current-user"
	mcp_auth_nifi_user_by_id_endpoint_template: str = "/nifi-api/tenants/users/{id}"
	mcp_auth_nifi_current_user_username_field: str = "identity"
	mcp_auth_nifi_current_user_id_field: str = "id"
	mcp_auth_nifi_groups_field: str = "userGroups"
	mcp_auth_nifi_groups_field_fallback: str = "component.userGroups"
	mcp_auth_nifi_groups_missing_is_denied: bool = True

	# TLS/HTTP for MCP->NiFi client
	verify_ssl_env: str = "true"
	ca_bundle: Optional[str] = None
	timeout_seconds: int = 30
	max_retries: int = 3
	rate_limit_rps: float = 5.0

	# Optional NiFi client cert for MCP->NiFi calls (mTLS)
	nifi_tls_cert_file: Optional[str] = None
	nifi_tls_key_file: Optional[str] = None

	# Behavior
	readonly: bool = True
	allowed_actions_csv: str = ""

	# CDP-specific proxy headers
	proxy_context_path: Optional[str] = None

	@classmethod
	def from_env_and_properties(cls, config_path: Optional[str] = None) -> "ServerConfig":
		# Resolution order:
		# 1) explicit arg, 2) CONFIG_PROPERTIES_PATH env, 3) ./config.properties,
		# 4) package-local config.properties (works when launched from repo root)
		if config_path:
			if not Path(config_path).exists():
				raise ValueError(f"Config file not found: {config_path}")
			path = config_path
		else:
			env_path = os.getenv("CONFIG_PROPERTIES_PATH")
			if env_path:
				env_path_obj = Path(env_path)
				if env_path_obj.exists():
					path = str(env_path_obj)
				else:
					cwd_path = Path("config.properties")
					if cwd_path.exists():
						path = str(cwd_path)
					else:
						path = str(Path(__file__).with_name("config.properties"))
			else:
				cwd_path = Path("config.properties")
				if cwd_path.exists():
					path = str(cwd_path)
				else:
					path = str(Path(__file__).with_name("config.properties"))

		props = _parse_properties_file(path)

		cfg = cls()
		cfg.config_file = path

		# transport
		cfg.transport = _pick(props, "MCP_TRANSPORT", "mcp.transport", None)
		cfg.host = _pick(props, "MCP_HOST", "mcp.host", None)
		port_value = _pick(props, "MCP_PORT", "mcp.port", None)
		cfg.port = int(port_value) if port_value else None

		# env/runtime
		cfg.environment = _pick(props, "APP_ENVIRONMENT", "app.environment", "local") or "local"

		# auth mode + authz
		cfg.mcp_auth_mode = (_pick(props, "MCP_AUTH_MODE", "mcp.auth.mode", "basic_static") or "basic_static").lower()
		cfg.mcp_auth_fail_open = _as_bool(_pick(props, "MCP_AUTH_FAIL_OPEN", "mcp.auth.fail_open", "false"), default=False)
		cfg.mcp_authz_group_check_enabled = _as_bool(
			_pick(props, "MCP_AUTHZ_GROUP_CHECK_ENABLED", "mcp.authz.group_check.enabled", "false"),
			default=False
		)
		cfg.mcp_authz_required_group = _pick(props, "MCP_AUTHZ_REQUIRED_GROUP", "mcp.authz.required_group", "") or ""

		# basic_static
		cfg.mcp_auth_basic_username = _pick(props, "MCP_AUTH_BASIC_USERNAME", "mcp.auth.basic.username", None)
		cfg.mcp_auth_basic_password = _pick(props, "MCP_AUTH_BASIC_PASSWORD", "mcp.auth.basic.password", None)

		# none
		cfg.mcp_auth_none_allow_in_local_only = _as_bool(
			_pick(props, "MCP_AUTH_NONE_ALLOW_IN_LOCAL_ONLY", "mcp.auth.none.allow_in_local_only", "true"),
			default=True
		)

		# knox + nifi
		cfg.knox_gateway_url = _pick(props, "KNOX_GATEWAY_URL", "knox.gateway.url", "") or ""
		cfg.nifi_api_base = _pick(props, "NIFI_API_BASE", "nifi.api.base", None)

		cfg.knox_token = _pick(props, "KNOX_TOKEN", "knox.token", None)
		cfg.knox_cookie = _pick(props, "KNOX_COOKIE", "knox.cookie", None)
		cfg.knox_user = _pick(props, "KNOX_USER", "knox.user", None)
		cfg.knox_password = _pick(props, "KNOX_PASSWORD", "knox.password", None)
		cfg.knox_token_endpoint = _pick(props, "KNOX_TOKEN_ENDPOINT", "knox.token.endpoint", None)
		cfg.knox_passcode_token = _pick(props, "KNOX_PASSCODE_TOKEN", "knox.passcode.token", None)

		# ldap
		cfg.mcp_auth_ldap_url = _pick(props, "MCP_AUTH_LDAP_URL", "mcp.auth.ldap.url", None)
		cfg.mcp_auth_ldap_bind_dn = _pick(props, "MCP_AUTH_LDAP_BIND_DN", "mcp.auth.ldap.bind_dn", None)
		cfg.mcp_auth_ldap_bind_password = _pick(props, "MCP_AUTH_LDAP_BIND_PASSWORD", "mcp.auth.ldap.bind_password", None)
		cfg.mcp_auth_ldap_user_base_dn = _pick(props, "MCP_AUTH_LDAP_USER_BASE_DN", "mcp.auth.ldap.user_base_dn", None)
		cfg.mcp_auth_ldap_user_filter = _pick(props, "MCP_AUTH_LDAP_USER_FILTER", "mcp.auth.ldap.user_filter", None)
		cfg.mcp_auth_ldap_group_base_dn = _pick(props, "MCP_AUTH_LDAP_GROUP_BASE_DN", "mcp.auth.ldap.group_base_dn", None)
		cfg.mcp_auth_ldap_group_filter = _pick(props, "MCP_AUTH_LDAP_GROUP_FILTER", "mcp.auth.ldap.group_filter", None)
		cfg.mcp_auth_ldap_timeout_seconds = int(_pick(props, "MCP_AUTH_LDAP_TIMEOUT_SECONDS", "mcp.auth.ldap.timeout_seconds", "5") or "5")
		cfg.mcp_auth_ldap_tls_verify = _as_bool(_pick(props, "MCP_AUTH_LDAP_TLS_VERIFY", "mcp.auth.ldap.tls.verify", "true"), default=True)
		cfg.mcp_auth_ldap_tls_ca_file = _pick(props, "MCP_AUTH_LDAP_TLS_CA_FILE", "mcp.auth.ldap.tls.ca_file", None)

		# nifi integrated
		cfg.mcp_auth_nifi_base_url = _pick(props, "MCP_AUTH_NIFI_BASE_URL", "mcp.auth.nifi.base_url", None)
		cfg.mcp_auth_nifi_timeout_seconds = int(_pick(props, "MCP_AUTH_NIFI_TIMEOUT_SECONDS", "mcp.auth.nifi.timeout_seconds", "8") or "8")
		cfg.mcp_auth_nifi_tls_verify = _as_bool(_pick(props, "MCP_AUTH_NIFI_TLS_VERIFY", "mcp.auth.nifi.tls.verify", "true"), default=True)
		cfg.mcp_auth_nifi_tls_ca_file = _pick(props, "MCP_AUTH_NIFI_TLS_CA_FILE", "mcp.auth.nifi.tls.ca_file", None)
		cfg.mcp_auth_nifi_tls_client_cert_file = _pick(props, "MCP_AUTH_NIFI_TLS_CLIENT_CERT_FILE", "mcp.auth.nifi.tls.client_cert_file", None)
		cfg.mcp_auth_nifi_tls_client_key_file = _pick(props, "MCP_AUTH_NIFI_TLS_CLIENT_KEY_FILE", "mcp.auth.nifi.tls.client_key_file", None)

		cfg.mcp_auth_nifi_token_endpoint = _pick(props, "MCP_AUTH_NIFI_TOKEN_ENDPOINT", "mcp.auth.nifi.token_endpoint", "/nifi-api/access/token") or "/nifi-api/access/token"
		cfg.mcp_auth_nifi_current_user_endpoint = _pick(props, "MCP_AUTH_NIFI_CURRENT_USER_ENDPOINT", "mcp.auth.nifi.current_user_endpoint", "/nifi-api/access/current-user") or "/nifi-api/access/current-user"
		cfg.mcp_auth_nifi_user_by_id_endpoint_template = _pick(
			props,
			"MCP_AUTH_NIFI_USER_BY_ID_ENDPOINT_TEMPLATE",
			"mcp.auth.nifi.user_by_id_endpoint_template",
			"/nifi-api/tenants/users/{id}"
		) or "/nifi-api/tenants/users/{id}"
		cfg.mcp_auth_nifi_current_user_username_field = _pick(
			props,
			"MCP_AUTH_NIFI_CURRENT_USER_USERNAME_FIELD",
			"mcp.auth.nifi.current_user_username_field",
			"identity"
		) or "identity"
		cfg.mcp_auth_nifi_current_user_id_field = _pick(
			props,
			"MCP_AUTH_NIFI_CURRENT_USER_ID_FIELD",
			"mcp.auth.nifi.current_user_id_field",
			"id"
		) or "id"
		cfg.mcp_auth_nifi_groups_field = _pick(props, "MCP_AUTH_NIFI_GROUPS_FIELD", "mcp.auth.nifi.groups_field", "userGroups") or "userGroups"
		cfg.mcp_auth_nifi_groups_field_fallback = _pick(
			props,
			"MCP_AUTH_NIFI_GROUPS_FIELD_FALLBACK",
			"mcp.auth.nifi.groups_field_fallback",
			"component.userGroups"
		) or "component.userGroups"
		cfg.mcp_auth_nifi_groups_missing_is_denied = _as_bool(
			_pick(props, "MCP_AUTH_NIFI_GROUPS_MISSING_IS_DENIED", "mcp.auth.nifi.groups_missing_is_denied", "true"),
			default=True
		)

		# HTTP/TLS for NiFi client
		cfg.verify_ssl_env = (_pick(props, "KNOX_VERIFY_SSL", "knox.verify.ssl", "true") or "true").lower()
		cfg.ca_bundle = _pick(props, "KNOX_CA_BUNDLE", "knox.ca.bundle", None)
		cfg.timeout_seconds = int(_pick(props, "HTTP_TIMEOUT_SECONDS", "http.timeout.seconds", "30") or "30")
		cfg.max_retries = int(_pick(props, "HTTP_MAX_RETRIES", "http.max.retries", "3") or "3")
		cfg.rate_limit_rps = float(_pick(props, "HTTP_RATE_LIMIT_RPS", "http.rate_limit.rps", "5") or "5")

		cfg.nifi_tls_cert_file = _pick(props, "NIFI_TLS_CERT_FILE", "nifi.tls.cert_file", None)
		cfg.nifi_tls_key_file = _pick(props, "NIFI_TLS_KEY_FILE", "nifi.tls.key_file", None)

		# behavior
		cfg.readonly = _as_bool(_pick(props, "NIFI_READONLY", "nifi.readonly", "true"), default=True)
		cfg.allowed_actions_csv = _pick(props, "NIFI_ALLOWED_ACTIONS", "nifi.allowed_actions", "") or ""
		cfg.proxy_context_path = _pick(props, "NIFI_PROXY_CONTEXT_PATH", "nifi.proxy.context.path", None)

		cfg.validate()
		return cfg

	def validate(self) -> None:
		if not self.transport:
			raise ValueError("mcp.transport must be set")

		transport = self.transport.lower()
		if transport != "stdio":
			if not self.host:
				raise ValueError("mcp.host must be set when mcp.transport is not stdio")
			if self.port is None:
				raise ValueError("mcp.port must be set when mcp.transport is not stdio")
			if self.port < 1 or self.port > 65535:
				raise ValueError("mcp.port must be between 1 and 65535")

		if self.mcp_auth_fail_open:
			raise ValueError("mcp.auth.fail_open=true is not allowed; fail-closed is required")

		if self.mcp_auth_mode == "none" and self.mcp_auth_none_allow_in_local_only and self.environment.lower() != "local":
			raise ValueError("mcp.auth.mode=none is only allowed when app.environment=local")

		if self.mcp_auth_mode == "basic_static":
			if not self.mcp_auth_basic_username or not self.mcp_auth_basic_password:
				raise ValueError(
					"basic_static mode requires mcp.auth.basic.username and mcp.auth.basic.password "
					f"(loaded from: {self.config_file})."
				)

		if self.mcp_auth_mode == "ldap":
			required = [
				self.mcp_auth_ldap_url,
				self.mcp_auth_ldap_bind_dn,
				self.mcp_auth_ldap_bind_password,
				self.mcp_auth_ldap_user_base_dn,
				self.mcp_auth_ldap_user_filter,
			]
			if not all(required):
				raise ValueError("ldap mode missing required ldap settings")

		if self.mcp_auth_mode == "nifi_integrated":
			if not self.mcp_auth_nifi_base_url:
				raise ValueError("nifi_integrated mode requires mcp.auth.nifi.base_url")

	def build_verify(self) -> bool | str:
		if self.ca_bundle:
			return self.ca_bundle
		return self.verify_ssl_env not in {"0", "false", "no"}

	def build_nifi_base(self) -> str:
		if self.nifi_api_base:
			return self.nifi_api_base.rstrip("/")
		if not self.knox_gateway_url:
			raise ValueError("NIFI_API_BASE or KNOX_GATEWAY_URL must be set")
		return f"{self.knox_gateway_url.rstrip('/')}/nifi-api"