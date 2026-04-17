"""Usage API router — returns LLM provider usage statistics."""

from fastapi import APIRouter

from app.services.usage_tracker import usage_tracker

router = APIRouter(prefix="/api/usage")


@router.get("/")
async def get_usage() -> dict:
    """Return usage stats for all LLM providers.

    Includes requests/tokens used today, daily limits, and reset time.
    """
    return usage_tracker.get_all()
