from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set


@dataclass
class AuthResult:
    authenticated: bool
    username: Optional[str] = None
    groups: Set[str] = field(default_factory=set)
    status_code: int = 401
    message: str = "Unauthorized"

    @staticmethod
    def unauthorized(message: str = "Unauthorized") -> "AuthResult":
        return AuthResult(authenticated=False, status_code=401, message=message)

    @staticmethod
    def forbidden(message: str = "Forbidden") -> "AuthResult":
        return AuthResult(authenticated=False, status_code=403, message=message)

    @staticmethod
    def success(username: str, groups: Optional[Set[str]] = None) -> "AuthResult":
        return AuthResult(
            authenticated=True,
            username=username,
            groups=groups or set(),
            status_code=200,
            message="OK",
        )