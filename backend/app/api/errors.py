"""How request validation failures are reported."""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def validation_error_response(request: Request, exc: Exception) -> JSONResponse:
    """Say what was wrong without repeating what was sent.

    FastAPI's default includes the rejected input. For a registration or sign-in request that is the
    password, or the whole body when a field is missing, which could then end up in logs.
    """
    assert isinstance(exc, RequestValidationError)
    problems = [{key: error[key] for key in ("type", "loc", "msg")} for error in exc.errors()]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": problems})
