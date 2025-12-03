from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.routers import auth, quests, listings, bids, dashboard, health, payments
from app.routers import chat, admin_review, disposal, upload, payouts, ai_category, price_prediction, badges, ratings, collectors, notifications, sentiment, bin_prediction, agent, complaints


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler"""
    # Startup
    print("Starting Zerobin API...")
    # Auto-create tables for dev (use Alembic in production)
    try:
        await init_db()
        print("Database tables ensured (init_db)")
    except Exception as e:
        print(f"Warning: Failed to init_db: {e}")
    print("Database connected")

    # Load E-Waste price prediction models
    try:
        from app.services.price_prediction_service import get_predictor
        print("Loading E-Waste price prediction models...")
        get_predictor()
        print("Price prediction models loaded")
    except Exception as e:
        print(f"Warning: Failed to load price prediction models: {e}")

    # Load Bangla sentiment analysis model
    try:
        from app.services.sentiment_service import get_sentiment_analyzer
        print("Loading Bangla sentiment analysis model...")
        get_sentiment_analyzer()
        print("Sentiment analysis model loaded")
    except Exception as e:
        print(f"Warning: Failed to load sentiment analysis model: {e}")

    # Load Bin fill prediction model
    try:
        from app.services.bin_prediction_service import get_bin_prediction_service
        print("Loading Bin fill prediction model...")
        get_bin_prediction_service()
        print("Bin prediction model loaded")
    except Exception as e:
        print(f"Warning: Failed to load bin prediction model: {e}")

    yield
    # Shutdown
    print("Shutting down Zerobin API...")


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
        {"name": "ReAct Agent", "description": "Conversational AI agent for quest creation and data queries"},
        {"name": "CleanQuests", "description": "Gamified waste cleanup missions"},
        {"name": "Collectors", "description": "Collector availability and workload management"},
        {"name": "Notifications", "description": "In-app notification system"},
        {"name": "FlashTrade", "description": "E-waste marketplace listings"},
        {"name": "FlashTrade - Bids", "description": "Bidding system for e-waste"},
        {"name": "Reputation & Badges", "description": "Badge award system and achievements"},
        {"name": "Reputation & Ratings", "description": "Kabadiwala rating and review system"},
        {"name": "Payments", "description": "Stripe payment integration"},
        {"name": "Payouts", "description": "Payout workflow for completed transactions"},
        {"name": "In-App Chat", "description": "Messaging system with deal confirmation lock"},
        {"name": "Upload & QR", "description": "Image upload and QR code generation/validation"},
        {"name": "Waste Disposal Routing", "description": "OpenStreetMap routing to disposal points"},
        {"name": "Admin Review", "description": "Human-in-the-loop review for flagged quests"},
        {"name": "Dashboard", "description": "Admin dashboard and analytics"},
        {"name": "AI Category", "description": "AI-powered e-waste image classification"},
        {"name": "E-Waste Price Prediction", "description": "ML-powered e-waste price estimation"},
        {"name": "Sentiment Analysis", "description": "Bangla sentiment analysis for text"},
        {"name": "Bin Fill Prediction", "description": "Time series forecasting for predicting bin fill-up time"},
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
api_v1.include_router(agent.router)
api_v1.include_router(quests.router)
api_v1.include_router(collectors.router)
api_v1.include_router(notifications.router)
api_v1.include_router(listings.router)
api_v1.include_router(bids.router)
api_v1.include_router(badges.router)
api_v1.include_router(ratings.router)
api_v1.include_router(payments.router)
api_v1.include_router(payouts.router)
api_v1.include_router(chat.router)
api_v1.include_router(upload.router)
api_v1.include_router(disposal.router)
api_v1.include_router(admin_review.router)
api_v1.include_router(dashboard.router)
api_v1.include_router(ai_category.router)
api_v1.include_router(price_prediction.router)
api_v1.include_router(sentiment.router)
api_v1.include_router(bin_prediction.router)
api_v1.include_router(complaints.router)

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
