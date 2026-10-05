from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    environment: str


class ErrorResponse(BaseModel):
    """Consistent error shape returned by the global exception handler."""

    detail: str
