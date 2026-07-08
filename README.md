<div align="center">

# 🗑️ ZeroBin

### Bangladesh's First AI-Driven Waste Management Platform

Gamified cleanup quests, an AI-verified e-waste marketplace, and a real-time city-wide waste intelligence dashboard — built as a FastAPI backend for citizens, waste collectors, kabadiwalas, and municipal administrators.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.5-4169E1?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-enabled-4169E1?style=flat)](https://postgis.net/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0_async-D71F00?style=flat)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat)](LICENSE)

[Live Demo](https://frontend-solvio.vercel.app/) · [Report Bug](../../issues) · [Request Feature](../../issues)

</div>

---

## 📖 Overview

Urban waste collection in Bangladesh runs almost entirely on manual reporting and blind scheduling — an estimated **55% of reported waste goes uncollected**, public complaints go unanswered, and only **0.45% of e-waste is formally recycled**, despite the country producing 367,000+ tonnes of e-waste every year.

**ZeroBin** replaces that blind process with a closed-loop, AI-verified system: citizens report waste and get rewarded for it, licensed collectors complete verified cleanup "quests," informal e-waste collectors (*kabadiwalas*) bid on valuable e-waste through a transparent marketplace, and city administrators get a live, predictive dashboard of waste hotspots and bin conditions across their wards.

This repository contains the **backend API** powering all four user roles: **Citizen, Collector, Kabadiwala, and Admin.**

---

## ✨ Core Services

| # | Service | What it does |
|---|---------|---------------|
| 1 | **CleanQuests** | Citizens report waste with photo + GPS → AI classifies it → collectors accept the "quest" and get paid in bounty points for verified before/after cleanup |
| 2 | **FlashTrade** | Citizens list e-waste devices → AI estimates resale value from photos → kabadiwalas bid → in-app chat unlocks only after a deal is confirmed |
| 3 | **God View Dashboard** | Real-time waste hotspot heatmap, collector leaderboards, ward-level statistics, and bin fill-level forecasting for city administrators |

---

## 🧠 The Role of AI

ZeroBin isn't just a reporting form — every step of the pipeline is AI-assisted and human-verified:

| Component | Model / Technique | Purpose |
|---|---|---|
| **Waste Classification** | Gemini 2.5 Flash + LangChain | Detects waste type and severity from citizen-uploaded photos |
| **Fraud Detection** | Sightengine + SerpAPI (Reverse Image Search) | Flags AI-generated images and photos re-used from the internet, preventing fraudulent reports |
| **Cleanup Verification** | Gemini Vision + metadata analysis | Cross-checks collector before/after photos; low-confidence cases are escalated to human admin review |
| **Bangla Sentiment Analysis** | Fine-tuned on Onubhuti-Bangla-Sentiment | Scores complaint urgency (94.5% accuracy) to prioritize critical issues |
| **Waste Hotspot Prediction** | LightGBM | Forecasts waste report volume by location for the next 3 days |
| **Bin Fill-Level Prediction** | LSTM (time-series) | Predicts bin overflow from the last 48 hours of sensor/report data, factoring in weekends, holidays, and weather |
| **EcoAssistant** | Agentic bot (LangGraph) | Bangla-speaking assistant with guarded, read-only database access and web search for waste-related queries |

All fine-tuned models and the training dataset are published publicly on Hugging Face (see [ML Models](#-ml-models) below).

---

## 🖼️ Screenshots

<details open>
<summary><strong>Citizen</strong></summary>

| Landing Page | Waste Report | Fraud Detection |
|---|---|---|
| <img src="https://github.com/user-attachments/assets/9e81064a-441a-4d94-ba6b-55cfa2098f94" width="280"/> | <img src="https://github.com/user-attachments/assets/1199ff67-289d-41d3-ad65-648f69e1d1cd" width="280"/> | <img src="https://github.com/user-attachments/assets/7e8454a3-dc78-458e-adf0-71b99f94893b" width="280"/> |

| All Reports | E-waste Selling | E-waste Listing |
|---|---|---|
| <img src="https://github.com/user-attachments/assets/cf54b317-8a82-413a-b6ea-e9e71c45a77c" width="280"/> | <img src="https://github.com/user-attachments/assets/69583e54-1544-4920-af6e-c99d96daeb05" width="280"/> | <img src="https://github.com/user-attachments/assets/31bd39a0-8dcc-4341-8435-38382e17a4cd" width="280"/> |

| Accept Bid | Submit Complaint | Agentic Bot |
|---|---|---|
| <img src="https://github.com/user-attachments/assets/20d64a85-6ee0-42d5-91fe-562960e1b0ee" width="280"/> | <img src="https://github.com/user-attachments/assets/816c8b40-c803-4f80-9b06-1a70d32da817" width="280"/> | <img src="https://github.com/user-attachments/assets/e415119b-9be3-4539-9694-db0dd82ec635" width="200"/> |

</details>

<details>
<summary><strong>Kabadiwala</strong></summary>

| E-waste Listings | Offer Pickup Service |
|---|---|
| <img src="https://github.com/user-attachments/assets/6aefdc26-6a09-4d8d-916c-972ea6d46aaf" width="400"/> | <img src="https://github.com/user-attachments/assets/85168d40-d186-423b-9064-e37690076ea3" width="330"/> |

</details>

<details>
<summary><strong>Admin</strong></summary>

| Dashboard | Reports listed by Citizen |
|---|---|
| <img src="https://github.com/user-attachments/assets/f6b684fa-91de-47c7-bf09-a0e5fa49154e" width="400"/> | <img src="https://github.com/user-attachments/assets/3b1caa7e-d061-4a3b-aea1-84ec0f0b6166" width="400"/> |

| Manual Review | Flagged Review |
|---|---|
| <img src="https://github.com/user-attachments/assets/63b9de24-4544-4f2b-ade2-9ad79672bdb4" width="400"/> | <img src="https://github.com/user-attachments/assets/7e68db86-6dfa-42ea-8a46-e7f7c3cc0ff1" width="400"/> |

| Bin Level Monitoring | Bin Prediction Result |
|---|---|
| <img src="https://github.com/user-attachments/assets/99154911-226c-4f7b-ae70-c3d54ddd94f9" width="400"/> | <img src="https://github.com/user-attachments/assets/70f79662-5cc8-4e3e-9367-489f46d33f82" width="330"/> |

</details>

<details>
<summary><strong>Collector</strong></summary>

<img src="https://github.com/user-attachments/assets/29c8e1eb-1918-479f-b412-29fdb3b35791" width="600"/>

</details>

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| **API Framework** | FastAPI 0.115+ |
| **Database** | PostgreSQL 16.5 with PostGIS (geospatial queries) |
| **ORM** | SQLAlchemy 2.0 (fully async) |
| **Migrations** | Alembic |
| **Auth** | JWT with role-based access control (Citizen / Collector / Kabadiwala / Admin) |
| **AI / ML** | Google Gemini Vision API, LangChain, LangGraph, LightGBM, LSTM |
| **Payments** | Stripe |
| **Fraud Detection** | Sightengine (AI-image detection), SerpAPI (reverse image search) |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16.5 with PostGIS

### 1. Start the database
```bash
docker-compose up -d
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
Copy `.env.example` to `.env` and fill in your database credentials and API keys (Gemini, Sightengine, SerpAPI, Stripe).

### 4. Run migrations
```bash
alembic upgrade head
```

### 5. Start the server
```bash
python main.py
```

The API will be available at:
- **Server:** http://localhost:8000
- **Interactive Docs (Swagger UI):** http://localhost:8000/docs

---

## 📡 API Structure

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new user |
| `POST` | `/api/v1/auth/login` | Authenticate and receive a JWT |
| `GET` | `/api/v1/quests` | List CleanQuests |
| `POST` | `/api/v1/quests` | Create a new waste report / quest |
| `GET` | `/api/v1/listings` | Browse e-waste listings |
| `POST` | `/api/v1/bids` | Submit a bid on an e-waste listing |
| `GET` | `/api/v1/dashboard/analytics` | Admin analytics and hotspot data |

Full request/response schemas are available in the Swagger UI once the server is running.

---

## 🤖 ML Models

All fine-tuned models and datasets are open-sourced on Hugging Face:

| Model | Purpose |
|---|---|
| Waste Hotspot Prediction (LightGBM) | Forecasts waste-report volume by geography |
| Bin Fill-Level Prediction (LSTM) | Predicts bin overflow from historical sensor data |
| Bangla Sentiment Model | Complaint urgency scoring in Bangla (94.5% accuracy) |

---

## 🗺️ Roadmap

- [x] Core FastAPI backend — models, schemas, routers
- [x] JWT-based RBAC for 4 user roles
- [x] Gemini-based waste classification & cleanup verification
- [x] Fraud detection pipeline (Sightengine + reverse image search)
- [x] Bangla sentiment model for complaint triage
- [x] LightGBM hotspot prediction & LSTM bin-fill forecasting
- [x] Agentic Bangla-speaking assistant (EcoAssistant)
- [ ] Image upload service hardening
- [ ] Stripe payment integration for FlashTrade
- [ ] Real-time WebSocket notifications
- [ ] SmartBin IoT sensor integration (MobileNetV2)

---

## 👥 Team — DU_Caffeine

| Name | Role |
|---|---|
| **Abrar** (DU) | Team Lead & ML Engineer |
| **Jamal** (DU) | Tech Lead & Backend |
| **Ashik** (DU) | Frontend Developer |
| **Laila** (BRAC) | Strategic Analyst |

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 📬 Contact

For questions, partnerships, or contributions, reach out at **abrar2020015622@cs.du.ac.bd**.
