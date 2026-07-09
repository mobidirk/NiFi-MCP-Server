from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple

import requests

from .config import ServerConfig


@dataclass
class IncomingAuthResult:
	authenticated: bool
	username: Optional[str] = None
	groups: Set[str] = field(default_factory=set)
	status_code: int = 401
	message: str = "Unauthorized"

	@staticmethod
	def success(username: str, groups: Optional[Set[str]] = None) -> "IncomingAuthResult":
		return IncomingAuthResult(
			authenticated=True,
			username=username,
			groups=groups or set(),
			status_code=200,
			message="OK",
		)

	@staticmethod
	def unauthorized(message: str = "Unauthorized") -> "IncomingAuthResult":
		return IncomingAuthResult(
			authenticated=False,
			status_code=401,
			message=message,
		)

	@staticmethod
	def forbidden(message: str = "Forbidden") -> "IncomingAuthResult":
		return IncomingAuthResult(
			authenticated=False,
			status_code=403,
			message=message,
		)


def parse_basic_auth_header(auth_header: Optional[str]) -> Optional[Tuple[str, str]]:
	if not auth_header or not auth_header.startswith("Basic "):
		return None
	try:
		raw = base64.b64decode(auth_header[len("Basic "):].strip()).decode("utf-8")
		username, password = raw.split(":", 1)
		return username, password
	except Exception:
		return None


class IncomingAuthProvider:
	def authenticate(self, headers: Dict[str, str]) -> IncomingAuthResult:
		raise NotImplementedError


class BasicStaticIncomingAuthProvider(IncomingAuthProvider):
	def __init__(self, username: str, password: str):
		self.username = username
		self.password = password

	def authenticate(self, headers: Dict[str, str]) -> IncomingAuthResult:
		auth_header = headers.get("Authorization") or headers.get("authorization")
		creds = parse_basic_auth_header(auth_header)
		if not creds:
			return IncomingAuthResult.unauthorized("Missing or invalid Basic Authorization header")
		u, p = creds
		if u == self.username and p == self.password:
			return IncomingAuthResult.success(username=u)
		return IncomingAuthResult.unauthorized("Invalid username or password")


class NoneIncomingAuthProvider(IncomingAuthProvider):
	def __init__(self, environment: str):
		self.environment = (environment or "").lower()

	def authenticate(self, headers: Dict[str, str]) -> IncomingAuthResult:
		if self.environment != "local":
			return IncomingAuthResult.forbidden("none auth mode is only allowed in local environment")
		return IncomingAuthResult.success(username="local-dev-user")


class KnoxIncomingAuthProvider(IncomingAuthProvider):
	"""
	Keep Knox incoming auth unchanged if you already have one.
	Current repo has only Knox auth factory for MCP->NiFi.
	For now this provider returns unauthorized unless you wire existing inbound Knox logic.
	"""
	def authenticate(self, headers: Dict[str, str]) -> IncomingAuthResult:
		return IncomingAuthResult.unauthorized("Incoming Knox auth provider is not wired yet")


class LdapIncomingAuthProvider(IncomingAuthProvider):
	def __init__(self, config: ServerConfig):
		self.config = config

	def authenticate(self, headers: Dict[str, str]) -> IncomingAuthResult:
		# TODO: implement ldap3 bind/search; fail closed on errors.
		return IncomingAuthResult.forbidden("LDAP auth provider not implemented yet")


class NiFiIntegratedIncomingAuthProvider(IncomingAuthProvider):
	def __init__(self, config: ServerConfig):
		self.config = config
		self.base_url = (config.mcp_auth_nifi_base_url or "").rstrip("/")
		self.timeout = config.mcp_auth_nifi_timeout_seconds

	def _verify(self):
		if not self.config.mcp_auth_nifi_tls_verify:
			return False
		if self.config.mcp_auth_nifi_tls_ca_file:
			return self.config.mcp_auth_nifi_tls_ca_file
		return True

	def _cert(self):
		if self.config.mcp_auth_nifi_tls_client_cert_file and self.config.mcp_auth_nifi_tls_client_key_file:
			return (self.config.mcp_auth_nifi_tls_client_cert_file, self.config.mcp_auth_nifi_tls_client_key_file)
		return None

	def _extract_nested(self, payload: dict, dotted: str):
		if not dotted:
			return None
		node = payload
		for p in dotted.split("."):
			if not isinstance(node, dict):
				return None
			node = node.get(p)
		return node

	def authenticate(self, headers: Dict[str, str]) -> IncomingAuthResult:
		auth_header = headers.get("Authorization") or headers.get("authorization")
		creds = parse_basic_auth_header(auth_header)
		if not creds:
			return IncomingAuthResult.unauthorized("Missing or invalid Basic Authorization header")
		username, password = creds

		try:
			# 1) token
			token_resp = requests.post(
				f"{self.base_url}{self.config.mcp_auth_nifi_token_endpoint}",
				data={"username": username, "password": password},
				headers={"Content-Type": "application/x-www-form-urlencoded"},
				timeout=self.timeout,
				verify=self._verify(),
				cert=self._cert(),
			)
			if token_resp.status_code in (401, 403):
				return IncomingAuthResult.unauthorized("Invalid username or password")
			token_resp.raise_for_status()
			token = token_resp.text.strip()
			if not token:
				return IncomingAuthResult.unauthorized("NiFi token endpoint returned empty token")

			bearer = {"Authorization": f"Bearer {token}"}

			# 2) current user
			me_resp = requests.get(
				f"{self.base_url}{self.config.mcp_auth_nifi_current_user_endpoint}",
				headers=bearer,
				timeout=self.timeout,
				verify=self._verify(),
				cert=self._cert(),
			)
			if me_resp.status_code == 403:
				return IncomingAuthResult.forbidden("Authenticated but not allowed to resolve current user")
			me_resp.raise_for_status()
			me = me_resp.json()

			resolved_username = me.get(self.config.mcp_auth_nifi_current_user_username_field, username)
			user_id = me.get(self.config.mcp_auth_nifi_current_user_id_field)

			groups: Set[str] = set()

			# 3) tenants/users/{id} -> groups
			if user_id:
				user_ep = self.config.mcp_auth_nifi_user_by_id_endpoint_template.replace("{id}", str(user_id))
				user_resp = requests.get(
					f"{self.base_url}{user_ep}",
					headers=bearer,
					timeout=self.timeout,
					verify=self._verify(),
					cert=self._cert(),
				)
				if user_resp.status_code == 403:
					return IncomingAuthResult.forbidden("Authenticated but not allowed to resolve user groups")
				user_resp.raise_for_status()

				user_payload = user_resp.json()
				raw_groups = user_payload.get(self.config.mcp_auth_nifi_groups_field)
				if raw_groups is None and self.config.mcp_auth_nifi_groups_field_fallback:
					raw_groups = self._extract_nested(user_payload, self.config.mcp_auth_nifi_groups_field_fallback)

				if isinstance(raw_groups, list):
					groups = {str(g) for g in raw_groups if g is not None}
				elif isinstance(raw_groups, str):
					groups = {raw_groups}

			if self.config.mcp_authz_group_check_enabled and self.config.mcp_authz_required_group:
				if not groups and self.config.mcp_auth_nifi_groups_missing_is_denied:
					return IncomingAuthResult.forbidden("Authenticated but groups missing")
				if self.config.mcp_authz_required_group not in groups:
					return IncomingAuthResult.forbidden("Authenticated but not in required group")

			return IncomingAuthResult.success(username=resolved_username, groups=groups)

		except requests.RequestException:
			# fail closed
			return IncomingAuthResult.unauthorized("Authentication backend error")


class IncomingAuthFactory:
	@staticmethod
	def build(config: ServerConfig) -> IncomingAuthProvider:
		mode = (config.mcp_auth_mode or "basic_static").lower()

		if mode == "basic_static":
			return BasicStaticIncomingAuthProvider(
				username=config.mcp_auth_basic_username or "",
				password=config.mcp_auth_basic_password or "",
			)
		if mode == "none":
			return NoneIncomingAuthProvider(environment=config.environment)
		if mode == "knox":
			return KnoxIncomingAuthProvider()
		if mode == "ldap":
			return LdapIncomingAuthProvider(config)
		if mode == "nifi_integrated":
			return NiFiIntegratedIncomingAuthProvider(config)

		raise ValueError(f"Unsupported mcp.auth.mode: {mode}")


class KnoxAuthFactory:
	def __init__(
		self,
		gateway_url: str,
		token: Optional[str],
		cookie: Optional[str],
		user: Optional[str],
		password: Optional[str],
		token_endpoint: Optional[str],
		passcode_token: Optional[str],
		verify: bool | str,
	):
		self.gateway_url = gateway_url.rstrip("/") if gateway_url else ""
		self.token = token
		self.cookie = cookie
		self.user = user
		self.password = password
		self.token_endpoint = token_endpoint or (
			f"{self.gateway_url}/knoxtoken/api/v1/token" if self.gateway_url else None
		)
		self.passcode_token = passcode_token
		self.verify = verify

	def build_session(self) -> requests.Session:
		session = requests.Session()
		session.verify = self.verify

		# Priority: Explicit Cookie -> Knox token (as cookie for CDP) -> Passcode token -> Basic creds token exchange
		if self.cookie:
			session.headers["Cookie"] = self.cookie
			return session

		if self.token:
			# For CDP NiFi, Knox JWT tokens must be sent as cookies, not Bearer headers
			session.headers["Cookie"] = f"hadoop-jwt={self.token}"
			return session

		if self.passcode_token:
			# Prefer exchanging passcode for JWT via knoxtoken endpoint when available
			if self.token_endpoint:
				jwt = self._exchange_passcode_for_jwt()
				session.headers["Authorization"] = f"Bearer {jwt}"
				return session
			# Fallback: send passcode as header (may not work on all deployments)
			session.headers["X-Knox-Passcode"] = self.passcode_token
			return session

		if self.user and self.password and self.token_endpoint:
			jwt = self._fetch_knox_token()
			session.headers["Authorization"] = f"Bearer {jwt}"
			return session

		return session

	def _fetch_knox_token(self) -> str:
		resp = requests.get(
			self.token_endpoint,
			auth=(self.user, self.password),
			verify=self.verify,
			timeout=15,
		)
		resp.raise_for_status()
		try:
			data = resp.json()
			return data.get("access_token") or data.get("token") or data.get("accessToken")
		except ValueError:
			text = resp.text.strip()
			try:
				decoded = base64.b64decode(text).decode("utf-8")
				if decoded.count(".") == 2:
					return decoded
			except Exception:
				pass
			return text

	def _exchange_passcode_for_jwt(self) -> str:
		if not (self.passcode_token and self.token_endpoint):
			raise RuntimeError("Passcode token exchange requires token_endpoint and passcode token")
		header = {
			"Authorization": "Basic " + base64.b64encode(f"passcode:{self.passcode_token}".encode()).decode(),
			"X-Requested-By": "nifi-mcp-server",
		}
		resp = requests.get(self.token_endpoint, headers=header, verify=self.verify, timeout=15)
		resp.raise_for_status()
		try:
			data = resp.json()
			return data.get("access_token") or data.get("token") or data.get("accessToken")
		except ValueError:
			return resp.text.strip()