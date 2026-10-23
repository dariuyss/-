"""Container adapter for `uvicorn main:app` while preserving package imports."""
from backend.main import app

__all__ = ["app"]
