"""
RFC 7807 Problem Details Error Handlers for Clearance Check Canary API.
Guarantees consistent error formatting across all exceptions with zero stack traces leaked.
"""
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from canary.application.identity.permissions import PermissionDeniedError
from canary.application.identity.four_eyes import FourEyesViolationError

logger = logging.getLogger(__name__)


def create_problem_response(
    status_code: int,
    title: str,
    detail: str,
    instance: str,
    code: str,
    error_type: str = "about:blank",
) -> JSONResponse:
    """Format and return standard RFC 7807 problem details JSON."""
    payload = {
        "type": error_type,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "code": code,
    }
    return JSONResponse(
        status_code=status_code,
        content=payload,
        media_type="application/problem+json",
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request input validation errors without leaking tracebacks."""
    errors = exc.errors()
    first_msg = errors[0]["msg"] if errors else "Request body failed schema validation."
    loc = " -> ".join(str(l) for l in errors[0].get("loc", [])) if errors else "body"
    detail = f"Validation failed at '{loc}': {first_msg}"

    return create_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Unprocessable Entity",
        detail=detail,
        instance=request.url.path,
        code="VALIDATION_ERROR",
        error_type="https://clearancecheck.canary/errors/validation-error",
    )


async def permission_denied_handler(request: Request, exc: PermissionDeniedError) -> JSONResponse:
    """Handle role permission authorization errors."""
    return create_problem_response(
        status_code=status.HTTP_403_FORBIDDEN,
        title="Forbidden",
        detail=str(exc),
        instance=request.url.path,
        code="PERMISSION_DENIED",
        error_type="https://clearancecheck.canary/errors/permission-denied",
    )


async def four_eyes_violation_handler(request: Request, exc: FourEyesViolationError) -> JSONResponse:
    """Handle four-eyes principle maker-checker violations."""
    return create_problem_response(
        status_code=status.HTTP_403_FORBIDDEN,
        title="Four-Eyes Violation",
        detail=str(exc),
        instance=request.url.path,
        code="FOUR_EYES_VIOLATION",
        error_type="https://clearancecheck.canary/errors/four-eyes-violation",
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle business logic value validation errors."""
    return create_problem_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        title="Bad Request",
        detail=str(exc),
        instance=request.url.path,
        code="INVALID_ARGUMENT",
        error_type="https://clearancecheck.canary/errors/invalid-argument",
    )


async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    """Handle resource not found errors."""
    msg = str(exc).strip("'")
    return create_problem_response(
        status_code=status.HTTP_404_NOT_FOUND,
        title="Not Found",
        detail=msg,
        instance=request.url.path,
        code="RESOURCE_NOT_FOUND",
        error_type="https://clearancecheck.canary/errors/not-found",
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all unhandled exception handler that hides stack traces."""
    logger.error(f"Internal server error on {request.url.path}: {exc}", exc_info=True)
    return create_problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="An internal server error occurred while processing the request. Contact IT support.",
        instance=request.url.path,
        code="INTERNAL_SERVER_ERROR",
        error_type="https://clearancecheck.canary/errors/internal-error",
    )
