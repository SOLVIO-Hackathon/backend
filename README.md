# Zerobin Backend API

FastAPI backend for the Zerobin waste management platform with gamified cleanup quests and e-waste marketplace.

Citizen
Landing Page 
<img width="1482" height="964" alt="image" src="https://github.com/user-attachments/assets/9e81064a-441a-4d94-ba6b-55cfa2098f94" />
Waste Report 
<img width="1632" height="802" alt="image" src="https://github.com/user-attachments/assets/1199ff67-289d-41d3-ad65-648f69e1d1cd" />
Fradual Waste Report Detection
<img width="1702" height="972" alt="image" src="https://github.com/user-attachments/assets/7e8454a3-dc78-458e-adf0-71b99f94893b" />
All waste Reports 
<img width="1700" height="816" alt="image" src="https://github.com/user-attachments/assets/cf54b317-8a82-413a-b6ea-e9e71c45a77c" />
E-waste Selling 
<img width="1698" height="808" alt="image" src="https://github.com/user-attachments/assets/69583e54-1544-4920-af6e-c99d96daeb05" />
E-waste list 
<img width="1700" height="822" alt="image" src="https://github.com/user-attachments/assets/31bd39a0-8dcc-4341-8435-38382e17a4cd" />
Accept Bid 
<img width="1714" height="868" alt="image" src="https://github.com/user-attachments/assets/20d64a85-6ee0-42d5-91fe-562960e1b0ee" />
Submit Complain
<img width="1712" height="818" alt="image" src="https://github.com/user-attachments/assets/816c8b40-c803-4f80-9b06-1a70d32da817" />
Agentic Bot 
<img width="916" height="872" alt="image" src="https://github.com/user-attachments/assets/e415119b-9be3-4539-9694-db0dd82ec635" />




Kabadiwala 
E-waste Available listing
<img width="1710" height="812" alt="image" src="https://github.com/user-attachments/assets/6aefdc26-6a09-4d8d-916c-972ea6d46aaf" />
Offer pick up Service 
<img width="1414" height="914" alt="image" src="https://github.com/user-attachments/assets/85168d40-d186-423b-9064-e37690076ea3" />


Admin 
Dashbaord 
<img width="1710" height="816" alt="image" src="https://github.com/user-attachments/assets/f6b684fa-91de-47c7-bf09-a0e5fa49154e" />
Waste Report listed by Citizen 
<img width="1710" height="820" alt="image" src="https://github.com/user-attachments/assets/3b1caa7e-d061-4a3b-aea1-84ec0f0b6166" />
Manual Review 
<img width="1350" height="920" alt="image" src="https://github.com/user-attachments/assets/63b9de24-4544-4f2b-ade2-9ad79672bdb4" />
Flagged Review 
<img width="1726" height="826" alt="image" src="https://github.com/user-attachments/assets/7e68db86-6dfa-42ea-8a46-e7f7c3cc0ff1" />
Waste Bin Level Monitoring 
<img width="1710" height="816" alt="image" src="https://github.com/user-attachments/assets/99154911-226c-4f7b-ae70-c3d54ddd94f9" />
Bin Prediction Result 
<img width="1096" height="836" alt="image" src="https://github.com/user-attachments/assets/70f79662-5cc8-4e3e-9367-489f46d33f82" />


Collector
Dashboard
<img width="1710" height="802" alt="image" src="https://github.com/user-attachments/assets/29c8e1eb-1918-479f-b412-29fdb3b35791" />



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
- Instant payment integration (Stripe)

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
