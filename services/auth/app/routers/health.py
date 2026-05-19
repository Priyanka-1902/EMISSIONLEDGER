from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..database import get_session_factory

router = APIRouter()


@router.get("/")
async def health():
    return {"status": "ok", "service": "auth"}


@router.get("/ready")
async def readiness():
    """Kubernetes readiness probe — checks DB connectivity."""
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"DB unavailable: {e}")
