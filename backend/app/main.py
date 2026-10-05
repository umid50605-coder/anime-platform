from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import get_settings
from app.core.logging import RequestContextMiddleware, get_logger, setup_logging
from app.core.logging.context import get_request_id
from app.core.logging.middleware import REQUEST_ID_HEADER
from app.schemas.common import HealthStatus

settings = get_settings()

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("%s starting up (environment=%s)", settings.app_name, settings.environment)
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added AFTER CORSMiddleware above: Starlette applies middleware in reverse
# registration order, so this one ends up outermost - request correlation
# and request-lifecycle logging wrap everything else, including CORS
# handling and FastAPI's own exception handling below.
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Basic error-handling structure: never leak a raw traceback to the client,
    always log it server-side. Route-level, expected errors (validation, 404,
    401, 409, ...) are raised as HTTPException in the routers and are NOT
    caught here - FastAPI handles those with their own status codes.

    request_id is not passed explicitly - it's stamped onto every log record
    automatically (see app/core/logging/context.py) via the contextvar that
    RequestContextMiddleware sets for the duration of this request.
    """
    logger.exception(
        "unhandled exception method=%s path=%s exception_type=%s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
    # This handler is invoked by Starlette's ServerErrorMiddleware, which sits
    # OUTSIDE RequestContextMiddleware - so the normal header-attaching path
    # in middleware.py never runs for this response. Set it explicitly here
    # instead, or a truly unhandled exception would be the one response that
    # never carries X-Request-ID.
    response.headers[REQUEST_ID_HEADER] = get_request_id()
    return response


@app.get("/health", response_model=HealthStatus, tags=["health"])
def health_check() -> HealthStatus:
    return HealthStatus(status="ok", environment=settings.environment)


app.include_router(api_router, prefix="/api")
