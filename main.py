from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.routers import auth, quests, listings, bids, dashboard, health, payments


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler"""
    # Startup
    print("🚀 Starting Zerobin API...")
    # Uncomment to auto-create tables (use Alembic in production)
    # await init_db()
    print("✅ Database connected")
    yield
    # Shutdown
    print("👋 Shutting down Zerobin API...")


# Main FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Zerobin - Gamified Waste Management & E-Waste Marketplace Platform for Hackathon",
    lifespan=lifespan,
    docs_url=None,  # Disable main app docs
    redoc_url=None,
    openapi_url=None,
)

# CORS middleware - Allow everything for hackathon
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


# No health endpoints on main app - everything is in api_v1


# API v1 routes with Swagger at /docs
api_v1 = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Zerobin API - Hackathon Version | All endpoints available for testing",
    docs_url="/docs",  # Swagger UI at root /docs
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "Authentication", "description": "User registration and login"},
        {"name": "CleanQuests", "description": "Gamified waste cleanup missions"},
        {"name": "FlashTrade", "description": "E-waste marketplace listings"},
        {"name": "FlashTrade - Bids", "description": "Bidding system for e-waste"},
        {"name": "Payments", "description": "Stripe payment integration"},
        {"name": "Dashboard", "description": "Admin dashboard and analytics"},
    ],
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
)


# Custom OpenAPI schema with Bearer token support
def custom_openapi():
    if api_v1.openapi_schema:
        return api_v1.openapi_schema

    openapi_schema = get_openapi(
        title=f"{settings.APP_NAME} v1",
        version="1.0.0",
        description="Zerobin API - Hackathon Version",
        routes=api_v1.routes,
    )

    # Add Bearer token security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT token from /auth/login (without 'Bearer' prefix, just the token)"
        }
    }

    # Mark protected endpoints (all except login/register)
    for path, path_item in openapi_schema["paths"].items():
        if "/auth/login" not in path and "/auth/register" not in path:
            for method in path_item.values():
                if isinstance(method, dict):
                    method["security"] = [{"BearerAuth": []}]

    api_v1.openapi_schema = openapi_schema
    return api_v1.openapi_schema


api_v1.openapi = custom_openapi

# Include routers in v1
api_v1.include_router(health.router)
api_v1.include_router(auth.router)
api_v1.include_router(quests.router)
api_v1.include_router(listings.router)
api_v1.include_router(bids.router)
api_v1.include_router(payments.router)
api_v1.include_router(dashboard.router)

# Mount v1 API at root level (so /docs works directly)
app.mount("", api_v1)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
