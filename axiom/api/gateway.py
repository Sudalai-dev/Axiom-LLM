"""
OCIF Gateway Service Application — Layer 2.

Establishes the core API gateway using FastAPI. Sets up global exception handlers
to map all platform errors to RFC 7807 Problem Details formats, configures
request context middlewares (correlation ID, logging contexts), and sets rate-limiting.

Traces to:
  - Document 5 (HLD) Section 4: External interfaces and gateway
  - Document 10 (API Specification) Section 8: Error Format (RFC 7807)
  - Document 10 (API Specification) Section 9: Rate Limiting
"""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.exceptions import OCIFError, ProblemDetail
from core.observability import setup_logger

logger = setup_logger("AxiomGateway", level=settings.observability.log_level)

# Resolve frontend directory relative to this file
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# ---------------------------------------------------------------------------
# Middlewares
# ---------------------------------------------------------------------------

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has a X-Correlation-ID trace identifier
    propagated in headers and attached to the request state.
    """
    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = corr_id
        
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Guarantees clean entry/exit of the thread-local request logging context manager,
    preventing any leak of contextvars between concurrent requests.
    """
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        finally:
            # Clean up task-local logging contextvars if resolved in auth dependency
            if hasattr(request.state, "logging_manager"):
                try:
                    request.state.logging_manager.__exit__(None, None, None)
                except Exception as ex:
                    logger.error(f"Error resetting request context manager: {ex}")


# ---------------------------------------------------------------------------
# Global Exception Handlers (RFC 7807)
# ---------------------------------------------------------------------------

def handle_ocif_error(request: Request, exc: OCIFError) -> JSONResponse:
    """Formats standard OCIF platform errors into RFC 7807 response objects."""
    problem = exc.to_problem_detail()
    logger.error(
        f"API Error [{problem.status}]: {problem.detail} (Correlation ID: {problem.correlation_id})",
        extra={"extra_fields": problem.to_dict()}
    )
    return JSONResponse(
        status_code=problem.status,
        content=problem.to_dict(),
        headers={"Content-Type": "application/problem+json"}
    )


def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catches unhandled errors and wraps them into RFC 7807 envelopes."""
    corr_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    problem = ProblemDetail(
        type="https://ocif-platform.dev/errors/internal",
        title="Internal Server Error",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
        correlation_id=corr_id
    )
    logger.critical(
        f"Unhandled System Exception: {str(exc)} (Correlation ID: {corr_id})",
        exc_info=True,
        extra={"extra_fields": problem.to_dict()}
    )
    return JSONResponse(
        status_code=problem.status,
        content=problem.to_dict(),
        headers={"Content-Type": "application/problem+json"}
    )


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    from api.routes.seed import ensure_seed_data
    await ensure_seed_data()
    yield


def create_gateway_app() -> FastAPI:
    """
    Creates and configures the API Gateway FastAPI application instance.
    """
    app = FastAPI(
        title="OCIF API Gateway",
        description="Enterprise AI Platform API Gateway - Layer 2 Boundary",
        version=settings.api_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )

    # Configure CORS per settings — allow all origins in development mode
    cors_origins = ["*"] if settings.is_development else settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=not settings.is_development,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"]
    )

    # Core middlewares
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestContextMiddleware)

    # Register Exception Handlers to enforce RFC 7807 response schema globally
    app.add_exception_handler(OCIFError, handle_ocif_error)
    app.add_exception_handler(Exception, handle_generic_exception)

    # --- API Routes ---
    from api.routes import router as api_router
    app.include_router(api_router)

    # --- Static Frontend ---
    if _FRONTEND_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="static")

    # Simple health check endpoint (bypasses auth checks)
    @app.get("/health", tags=["System"])
    async def get_health():
        return {
            "status": "healthy",
            "environment": settings.environment,
            "version": settings.api_version
        }

    # Redirect root to the mounted frontend for convenience
    @app.get("/", include_in_schema=False)
    async def _root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/static/")

    return app
