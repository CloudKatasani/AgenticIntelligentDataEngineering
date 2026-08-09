"""Domain exceptions and their HTTP mapping.

Keeping the exception taxonomy in the domain means services can refuse work for
domain reasons (an unmet hard dependency, a tier violation) without knowing they
are being called over HTTP.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ADEError(Exception):
    """Base class for every error the application raises deliberately."""

    status_code = 400
    code = "ade_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFound(ADEError):
    status_code = 404
    code = "not_found"


class ValidationFailed(ADEError):
    status_code = 422
    code = "validation_failed"


class DriverUnavailable(ADEError):
    """A source system is supported but its Python driver is not installed."""

    status_code = 503
    code = "driver_unavailable"


class ConnectionFailed(ADEError):
    status_code = 502
    code = "connection_failed"


class DependencyGateBlocked(ADEError):
    """Design rule 2: hard dependencies block execution."""

    status_code = 409
    code = "dependency_gate_blocked"


class AutonomyGateBlocked(ADEError):
    """Design rule 3: an agent may never act above its tier."""

    status_code = 409
    code = "autonomy_gate_blocked"


class CostCapExceeded(ADEError):
    status_code = 402
    code = "cost_cap_exceeded"


class ReadOnlyViolation(ADEError):
    """A generated statement would mutate a source system."""

    status_code = 403
    code = "read_only_violation"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ADEError)
    async def _handle_ade_error(_: Request, exc: ADEError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )
