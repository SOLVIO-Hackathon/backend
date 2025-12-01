from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "message": "Welcome to Zerobin API! Visit /docs for API documentation.",
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
