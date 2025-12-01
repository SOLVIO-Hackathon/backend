# Zerobin Backend API

FastAPI backend for the Zerobin waste management platform with gamified cleanup quests and e-waste marketplace.

## Features

### 1. CleanQuests - Gamified Waste Cleanup
- Citizens report waste with photos and location
- AI-powered waste classification
- Collectors accept missions and earn bounty points
- EXIF metadata verification (GPS, timestamp, device)
- Google Gemini Vision API for before/after photo verification
- Real-time geohashing for duplicate detection

### 2. FlashTrade - E-Waste Marketplace
- Users list e-waste devices with photos
- AI estimates device value based on condition
- Kabadiwalas bid on listings
- In-app secure chat (locked until deal confirmed)
- Weight verification system
- Instant payment integration (bKash/Nagad)

### 3. God View Dashboard
- Real-time heatmap of waste reports
- Collector leaderboards
- Ward-level statistics
- Impact metrics and analytics

## Tech Stack

- **Framework**: FastAPI 0.115+
- **Database**: PostgreSQL 16.5 with PostGIS
- **ORM**: SQLAlchemy 2.0 (async)
- **Authentication**: JWT with role-based access control
- **Migrations**: Alembic
- **AI**: Google Gemini Vision API, LangChain, LangGraph

## Quick Start

### 1. Start Database
```bash
docker-compose up -d
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Edit `.env` file with your settings (database, API keys)

### 4. Run Migrations
```bash
alembic upgrade head
```

### 5. Start Server
```bash
python main.py
```

Server: http://localhost:8000
Docs: http://localhost:8000/docs

## API Structure

- `POST /api/v1/auth/register` - Register user
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/quests` - List CleanQuests
- `POST /api/v1/quests` - Create quest
- `GET /api/v1/listings` - List e-waste
- `POST /api/v1/bids` - Create bid
- `GET /api/v1/dashboard/analytics` - Admin dashboard

## Development

All models, schemas, and routers are ready. Implement:
- Image upload service
- AI verification workflows
- Payment integration
- Real-time features

See full documentation in Swagger UI.
