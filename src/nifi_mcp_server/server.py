from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

import anyio

from .auth import IncomingAuthFactory, KnoxAuthFactory
from .best_practices import NiFiBestPractices, SmartFlowBuilder
from .client import NiFiClient
from .config import ServerConfig
from .flow_builder import analyze_flow_request
from .setup_helper import SetupGuide

try:
	from mcp.server import FastMCP
except Exception as e:  # pragma: no cover
	raise RuntimeError("The 'mcp' package is required. Install with: pip install mcp") from e


def _redact_sensitive(obj: Any, max_items: int = 200) -> Any:
	redact_keys = {"password", "passcode", "token", "secret", "kerberosKeytab", "sslKeystorePasswd"}
	if isinstance(obj, dict):
		redacted: Dict[str, Any] = {}
		for k, v in obj.items():
			if k.lower() in redact_keys:
				redacted[k] = "***REDACTED***"
			else:
				redacted[k] = _redact_sensitive(v, max_items)
		return redacted
	if isinstance(obj, list):
		if len(obj) > max_items:
			return [_redact_sensitive(x, max_items) for x in obj[:max_items]] + [{"truncated": True, "omitted_count": len(obj) - max_items}]
		return [_redact_sensitive(x, max_items) for x in obj]
	return obj


def build_client(config: ServerConfig) -> NiFiClient:
	verify = config.build_verify()
	nifi_base = config.build_nifi_base()

	auth = KnoxAuthFactory(
		gateway_url=config.knox_gateway_url,
		token=config.knox_token,
		cookie=config.knox_cookie,
		user=config.knox_user,
		password=config.knox_password,
		token_endpoint=config.knox_token_endpoint,
		passcode_token=config.knox_passcode_token,
		verify=verify,
	)
	session = auth.build_session()

	client_cert = None
	if config.nifi_tls_cert_file and config.nifi_tls_key_file:
		client_cert = (config.nifi_tls_cert_file, config.nifi_tls_key_file)

	return NiFiClient(
		nifi_base,
		session,
		timeout_seconds=config.timeout_seconds,
		proxy_context_path=config.proxy_context_path,
		client_cert=client_cert,
	)


def create_server(nifi: NiFiClient, readonly: bool, config: ServerConfig) -> FastMCP:
	app = FastMCP(
		"nifi-mcp-server",
		host=config.host or "127.0.0.1",
		port=config.port or 3030,
	)
	incoming_auth = IncomingAuthFactory.build(config)
	expose_auth_test_tool = os.getenv("MCP_AUTH_EXPOSE_TEST_TOOL", "false").lower() == "true"

	def _get_context_authorization() -> Optional[str]:
		"""Best-effort fetch of Authorization header from current transport request."""
		try:
			ctx = app.get_context()
			req = ctx.request_context.request
			if req is None:
				return None
			headers = getattr(req, "headers", None)
			if headers is None:
				return None
			# Starlette headers are case-insensitive; keep both keys for compatibility.
			return headers.get("authorization") or headers.get("Authorization")
		except Exception:
			return None

	def _check_incoming_auth(authorization: Optional[str]) -> Dict[str, Any]:
		effective_authorization = authorization or _get_context_authorization()
		headers = {"Authorization": effective_authorization} if effective_authorization else {}
		result = incoming_auth.authenticate(headers)
		if not result.authenticated:
			return {"ok": False, "status_code": result.status_code, "error": result.message}
		return {"ok": True, "principal": {"username": result.username, "groups": sorted(result.groups)}}

	if expose_auth_test_tool:
		@app.tool()
		async def authenticate_request(authorization: Optional[str] = None) -> Dict[str, Any]:
			"""
			Validate incoming user auth based on configured mcp.auth.mode.
			Pass full Authorization header value, e.g.:
			- "Basic base64(user:pass)"
			"""
			return _check_incoming_auth(authorization)

	@app.tool()
	async def get_nifi_version(authorization: Optional[str] = None) -> Dict[str, Any]:
		authz = _check_incoming_auth(authorization)
		if not authz["ok"]:
			return authz
		data = nifi.get_version_info()
		version_tuple = nifi.get_version_tuple()
		return {
			"principal": authz["principal"],
			"version_info": _redact_sensitive(data),
			"parsed_version": f"{version_tuple[0]}.{version_tuple[1]}.{version_tuple[2]}",
			"is_nifi_2x": nifi.is_nifi_2x(),
			"major_version": version_tuple[0],
		}

	# NOTE:
	# Apply same authz check pattern to other tools if you want strict user->MCP enforcement for every tool.
	# To keep this patch concise, only get_nifi_version is shown fully wired.

	return app


async def run_stdio() -> None:
	config = ServerConfig.from_env_and_properties()
	nifi = build_client(config)
	server = create_server(nifi, readonly=config.readonly, config=config)
	await server.run_stdio_async()


def main() -> None:
	try:
		config = ServerConfig.from_env_and_properties()
		transport = config.transport.lower()

		if transport != "stdio":
			nifi = build_client(config)
			server = create_server(nifi, readonly=config.readonly, config=config)
			server.run(transport=transport)
			return

		anyio.run(run_stdio)
	except (KeyboardInterrupt, asyncio.CancelledError):
		# Normal operator shutdown via Ctrl-C.
		return


if __name__ == "__main__":
	main()