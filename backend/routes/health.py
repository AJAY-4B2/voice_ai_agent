"""Health check router."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "running", "service": "2Care.ai Voice AI Agent", "version": "1.0.0"}
