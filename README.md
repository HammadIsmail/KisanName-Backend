# KisanNama — Backend API 🌾

> The FastAPI backend for KisanNama — a bilingual AI-powered crop advisory platform for Pakistani farmers.

![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![vLLM](https://img.shields.io/badge/vLLM-Gemma_4_31B-blueviolet?logo=google)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-blue?logo=postgresql)


---

## ✨ Features

- 🤖 **4-agent AI pipeline** — Specialized CrewAI agents analyze crop area, compute planting risk, assess market price trends, and suggest alternative crops before generating the final advice.
- 🌐 **Bilingual responses (Urdu + English)** — Every query generates a full response in **both** languages simultaneously using two parallel Gemma streams via self-hosted vLLM. Both are stored in the database; the frontend switches between them with zero re-fetching.
- ⚡ **Real-time SSE streaming** — Responses are streamed token-by-token via Server-Sent Events. All events (`agent_update`, `token`, `done`) carry bilingual content.
- 💬 **Session-based chat history** — Conversations are grouped into `ChatSession` records. Each session holds multiple `QueryLog` messages. Fully queryable via REST.
- 🔊 **Text-to-Speech (TTS)** — `edge-tts` (Microsoft Neural Voices) converts Urdu/English text to high-quality MP3 audio (up to 4,096 characters). Completely free and natively supports Urdu.
- 🔐 **JWT authentication** — Phone number + password login with configurable token expiry.
- 📊 **Admin dashboard API** — CRUD endpoints for managing districts, crops, area estimates, price histories, and user accounts.

---

## 🏗️ Project Structure

```
backend/
├── main.py                   # FastAPI app entry point, CORS, router registration
├── database.py               # SQLAlchemy engine, session, Base, init_db()
├── auth.py                   # JWT token creation + current_user dependency
├── seed_data.py              # Populates DB with districts, crops, price history, admin user
├── migrate.py                # Drops & recreates query tables (run once when schema changes)
├── requirements.txt
│
├── models/
│   ├── user.py               # User accounts
│   ├── crop.py               # Crop + District lookup tables
│   ├── crop_area.py          # CropArea (acres) + PriceHistory per district
│   ├── chat_session.py       # Chat session (groups messages, has a title + timestamps)
│   └── query_log.py          # Individual messages (query_text, response_ur, response_en)
│
├── schemas/
│   ├── query.py              # QueryRequest (text, district, crop, session_id)
│   └── auth.py               # LoginRequest, TokenResponse
│
├── routers/
│   ├── query.py              # /query (SSE), /sessions, /sessions/:id/messages, /history
│   ├── auth.py               # /login, /register
│   ├── tts.py                # /tts (edge-tts speech synthesis → MP3)
│   ├── admin.py              # Admin CRUD for crop/district/user data
│   └── health.py             # /health
│
├── crew/
│   ├── orchestrator.py       # Main agent pipeline — yields bilingual SSE events
│   └── tools.py              # DB-backed tools: get_crop_area, get_price_history
│
└── services/
    └── speech.py             # edge-tts wrapper (synthesize_urdu_async function)
```

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.9+
- **PostgreSQL** database (local or hosted on [Neon](https://neon.tech/))
- **vLLM server** running `google/gemma-4-31b-it` — accessible at `http://129.212.184.69:8000` (no API key required)

---

### 1. Clone & Install

```bash
git clone https://github.com/your-username/kisannama-backend.git
cd kisannama-backend

python -m venv env
source env/bin/activate       # Windows: env\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

> **Note:** We have hosted the Gemma model on an AMD developer account (AMD GPU on cloud). For anyone to clone this repo, you have to run Gemma on your own cloud and provide your URL and model name here in these environment variables.

```env
# Self-hosted vLLM endpoint (no API key required)
VLLM_BASE_URL=http://129.212.184.69:8000/v1
VLLM_MODEL=google/gemma-4-31b-it

DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
SECRET_KEY=any-long-random-string-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_DAYS=7
```

| Variable | Description |
|---|---|
| `VLLM_BASE_URL` | Base URL of the self-hosted vLLM server (e.g. `http://129.212.184.69:8000/v1`) |
| `VLLM_MODEL` | Model name to use — `google/gemma-4-31b-it` |
| `DATABASE_URL` | Full PostgreSQL connection string |
| `SECRET_KEY` | Random secret for signing JWT tokens |
| `ALGORITHM` | JWT algorithm — use `HS256` |
| `ACCESS_TOKEN_EXPIRE_DAYS` | How long login tokens stay valid |

### 3. Seed the Database

This creates all tables and populates them with sample districts, crop area data, price history records, and the default admin user:

```bash
python seed_data.py
```

### 4. Start the Server

```bash
uvicorn main:app --reload
```

- **API** → `http://localhost:8000`
- **Interactive Docs** → `http://localhost:8000/docs`

---

## 🔐 Default Admin Credentials

| Field | Value |
|---|---|
| **Phone** | `03000000001` |
| **Password** | `admin123` |

> ⚠️ Change these before deploying to production.

---

## 🧠 AI Pipeline

When a farmer submits a query, the orchestrator (`crew/orchestrator.py`) runs 4 agents in sequence and then streams the response in both languages:

```
User query (text + optional district/crop/session_id)
        │
        ▼
1. Data Agent      → Fetches crop area & previous year area for the district
2. Risk Agent      → Computes % YoY change → low / medium / high risk label
3. Market Agent    → Retrieves latest price trend & last recorded price
4. Strategy Agent  → Gemma 4 31B suggests 2-3 alternative crops (in both languages)
        │
        ▼
Gemma Stream → Urdu recommendation (tokens tagged lang="ur")
Gemma Stream → English recommendation (tokens tagged lang="en")
        │
        ▼
SSE "done" event → { risk_level, recommended_crop, district }
        │
        ▼
QueryLog saved → { response_ur, response_en } stored in PostgreSQL
```

Every SSE event carries **both** language strings:

```json
{ "type": "agent_update", "agent": "risk_agent", "status": "done",
  "message_ur": "کم خطرہ — گزشتہ سال سے 5% کم رقبہ",
  "message_en": "Low Risk — 5% less area than last year" }

{ "type": "token", "lang": "ur", "content": "السلام" }
{ "type": "token", "lang": "en", "content": "Hello" }
```

---

## 📡 API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/login` | Login with phone + password, returns JWT |
| `POST` | `/register` | Create a new user account |

### Chat & Sessions

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/query` | Submit a query — streams bilingual SSE response |
| `GET` | `/sessions` | List all sessions for the current user |
| `GET` | `/sessions/:id/messages` | Fetch all messages in a session |
| `DELETE` | `/sessions/:id` | Delete a session and its messages |
| `DELETE` | `/sessions/all` | Delete all sessions for the current user |

### Text-to-Speech

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/tts` | Convert text (≤ 4,096 chars) to MP3 audio |

### Admin (requires admin role)

| Method | Endpoint | Description |
|---|---|---|
| `GET/POST/PUT/DELETE` | `/admin/crops/*` | Manage crop types |
| `GET/POST/PUT/DELETE` | `/admin/districts/*` | Manage districts |
| `GET/POST/PUT/DELETE` | `/admin/crop-areas/*` | Manage crop area records |
| `GET/POST/PUT/DELETE` | `/admin/prices/*` | Manage price history |
| `GET` | `/admin/users` | List all users |

---

## 🔄 Schema Migrations

The project uses SQLAlchemy's `create_all` for simple migrations. If you change model schemas (e.g., after pulling updates), run the migration script to drop and recreate the affected tables:

```bash
python migrate.py
```

> ⚠️ This **drops** the `query_log` and `chat_sessions` tables. All existing chat history will be deleted. Crop/user data is preserved.

---

## 🤝 Related Repository

- **Frontend**: [KisanName-Frontend](https://github.com/HammadIsmail/KisanNama-Frontend) — Next.js + TypeScript + Tailwind CSS

---


