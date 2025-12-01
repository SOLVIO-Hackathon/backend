from typing import List
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator

# Get the backend directory path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Application settings and configuration - loads from .env file"""

    # Application
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool
    API_V1_PREFIX: str

    # Database
    DATABASE_URL: str
    ASYNC_DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # CORS
    BACKEND_CORS_ORIGINS: List[str]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    # Google Gemini API
    GOOGLE_API_KEY: str

    # File Upload
    MAX_UPLOAD_SIZE: int
    ALLOWED_EXTENSIONS: List[str]

    # Firebase Storage (Optional)
    FIREBASE_CREDENTIALS_PATH: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""

    # Payment Gateway (Mock for Hackathon)
    BKASH_API_KEY: str = "mock-api-key"
    NAGAD_API_KEY: str = "mock-api-key"

    # Stripe Payment Gateway
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_CONNECT_REFRESH_URL: str = "https://your-app.com/connect/refresh"
    STRIPE_CONNECT_RETURN_URL: str = "https://your-app.com/connect/return"

    # Verification Thresholds
    EXIF_GPS_TOLERANCE_METERS: int
    EXIF_TIME_TOLERANCE_MINUTES: int
    AI_VERIFICATION_CONFIDENCE_THRESHOLD: float

    # Rewards
    DEFAULT_QUEST_BOUNTY_ORGANIC: int
    DEFAULT_QUEST_BOUNTY_RECYCLABLE: int
    DEFAULT_QUEST_BOUNTY_GENERAL: int
    COMMISSION_RATE_PERCENT: float

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )


settings = Settings()

# Debug: Print loaded config on import
if settings.DEBUG:
    print(f"✅ Loaded .env from: {ENV_FILE}")
    print(f"   DATABASE_URL: {settings.DATABASE_URL}")
    print(f"   SECRET_KEY: {settings.SECRET_KEY[:20]}...")
    print(f"   CORS_ORIGINS: {settings.BACKEND_CORS_ORIGINS}")
