from __future__ import annotations

from typing import Callable, Dict

from auth.factory import build_auth_provider


class AuthMiddleware:
    """
    Framework-agnostic middleware helper.
    Wire into Flask/FastAPI/etc by adapting request/response objects.
    """

    def __init__(self, config: Dict[str, str], knox_delegate=None):
        self.provider = build_auth_provider(config, knox_delegate=knox_delegate)

    def authenticate_or_reject(self, headers: Dict[str, str]):
        result = self.provider.authenticate(headers)
        if not result.authenticated:
            return {
                "allowed": False,
                "status_code": result.status_code,
                "body": {"error": result.message},
            }
        return {
            "allowed": True,
            "status_code": 200,
            "principal": {
                "username": result.username,
                "groups": sorted(result.groups),
            },
        }