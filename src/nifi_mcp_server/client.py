from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class NiFiError(Exception):
	"""Base exception for NiFi API errors with detailed error information."""
	def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
		self.status_code = status_code
		self.response_body = response_body
		super().__init__(message)

	def __str__(self):
		msg = super().__str__()
		if self.status_code:
			msg = f"[{self.status_code}] {msg}"
		if self.response_body:
			msg = f"{msg}\n\nNiFi API Response:\n{self.response_body}"
		return msg


class NiFiClient:
	def __init__(
		self,
		base_url: str,
		session: requests.Session,
		timeout_seconds: int = 30,
		proxy_context_path: Optional[str] = None,
		client_cert: Optional[Tuple[str, str]] = None,
	):
		self.base_url = base_url.rstrip("/")
		self.session = session
		self.timeout = timeout_seconds
		self._version_info: Optional[Tuple[int, int, int]] = None
		self.proxy_context_path = proxy_context_path
		self.client_cert = client_cert

		# Add CDP proxy headers if configured
		if self.proxy_context_path:
			self.session.headers.update({'X-ProxyContextPath': self.proxy_context_path})

	def _url(self, path: str) -> str:
		return f"{self.base_url}/{path.lstrip('/')}"

	@retry(
		retry=retry_if_exception_type((NiFiError, requests.HTTPError, requests.ConnectionError, requests.Timeout)),
		wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
		stop=stop_after_attempt(3),
		reraise=True,
	)
	def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		resp = self.session.get(self._url(path), params=params, timeout=self.timeout, cert=self.client_cert)
		if not resp.ok:
			error_body = resp.text if resp.text else "(empty response)"
			raise NiFiError(
				f"GET {path} failed: {resp.reason}",
				status_code=resp.status_code,
				response_body=error_body
			)
		return resp.json()

	@retry(
		retry=retry_if_exception_type((NiFiError, requests.HTTPError, requests.ConnectionError, requests.Timeout)),
		wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
		stop=stop_after_attempt(3),
		reraise=True,
	)
	def _put(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
		resp = self.session.put(self._url(path), json=data, timeout=self.timeout, cert=self.client_cert)
		if not resp.ok:
			error_body = resp.text if resp.text else "(empty response)"
			raise NiFiError(
				f"PUT {path} failed: {resp.reason}",
				status_code=resp.status_code,
				response_body=error_body
			)
		return resp.json()

	@retry(
		retry=retry_if_exception_type((NiFiError, requests.HTTPError, requests.ConnectionError, requests.Timeout)),
		wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
		stop=stop_after_attempt(3),
		reraise=True,
	)
	def _post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
		resp = self.session.post(self._url(path), json=data, timeout=self.timeout, cert=self.client_cert)
		if not resp.ok:
			error_body = resp.text if resp.text else "(empty response)"
			raise NiFiError(
				f"POST {path} failed: {resp.reason}",
				status_code=resp.status_code,
				response_body=error_body
			)
		return resp.json()

	@retry(
		retry=retry_if_exception_type((NiFiError, requests.HTTPError, requests.ConnectionError, requests.Timeout)),
		wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
		stop=stop_after_attempt(3),
		reraise=True,
	)
	def _delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		resp = self.session.delete(self._url(path), params=params, timeout=self.timeout, cert=self.client_cert)
		if not resp.ok:
			error_body = resp.text if resp.text else "(empty response)"
			raise NiFiError(
				f"DELETE {path} failed: {resp.reason}",
				status_code=resp.status_code,
				response_body=error_body
			)
		return resp.json() if resp.content else {}

	# --- rest of your existing methods unchanged ---
	# (keep everything from your current file after this point as-is)