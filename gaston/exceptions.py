"""Exceptions raised by the Gaston API client."""

from __future__ import annotations

from typing import Any


class GastonError(Exception):
    """Base class for all errors raised by the client."""


class GastonAPIError(GastonError):
    """Raised when the API returns an error response.

    Attributes:
        message: Human readable error message returned by the API.
        status_code: HTTP status code of the response (if any).
        details: Optional extra payload returned alongside the error.
        payload: The full decoded response body.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: Any | None = None,
        payload: Any | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details
        self.payload = payload
        prefix = f"[{status_code}] " if status_code is not None else ""
        super().__init__(f"{prefix}{message}")


class AuthenticationError(GastonAPIError):
    """Raised when the token is invalid or the user is disabled (HTTP 403)."""


class NotFoundError(GastonAPIError):
    """Raised when a requested resource does not exist (HTTP 404)."""


class RateLimitError(GastonAPIError):
    """Raised when the monthly file/API limit is exhausted (HTTP 429)."""


class BadRequestError(GastonAPIError):
    """Raised for invalid requests (HTTP 400)."""