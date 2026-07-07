# KisanNama — Project Architecture

> AMD Agentic AI Hackathon — AI-powered crop advisory system for Pakistani farmers

---

## Overview

KisanNama is a multi-agent AI system that helps Pakistani farmers make data-driven planting decisions. Farmers ask questions in Urdu (via text or voice), and five specialized CrewAI agents analyze district-level crop data, price history, weather, and market demand to deliver localized Urdu recommendations. A separate government dashboard allows PBS and agriculture department employees to enter and manage district crop data.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js 16.2.9(latest) (App Router) | Farmer chat UI + Govt dashboard |
| Backend | FastAPI (Python 3.11+) | API server, SSE streaming |
| Agent framework | CrewAI | Multi-agent orchestration |
| LLM | Fireworks AI (deepseek-v4-pro) | Agent reasoning, Urdu generation, synthesis |
| Database | PostgreSQL | Structured crop + user data |
| Weather | ~~Open-Meteo API~~ | ~~Removed~~ |
| STT | Web Speech API (browser) | Urdu voice input (ur-PK) |
| TTS | edge-tts (Microsoft Neural Voices) | Urdu audio output (ur-PK-UzmaNeural) |
| Auth | JWT (python-jose) | Farmer + govt employee sessions |
| Hosting | Railway (backend) + Vercel (frontend) | Deployment |

---

## Crops Supported

| Crop | Risk profile | Seasons |
|---|---|---|
| Potato | High volatility | Rabi |
| Onion | Medium volatility | Rabi + Kharif |
| Wheat | Low volatility (baseline) | Rabi |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Next.js)                     │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ VoiceInput   │  │ ChatInterface│  │  AgentLog    │  │
│  │ Web Speech   │  │ Urdu RTL UI  │  │  SSE stream  │  │
│  │ API (ur-PK)  │  │              │  │  display     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────▲───────┘  │
│         └─────────────────┘                  │          │
│                    │                          │          │
│            POST /query                   SSE chunks     │
│            POST /tts                         │          │
└────────────────────┼──────────────────────────┼─────────┘
                     │                          │
┌────────────────────▼──────────────────────────┼─────────┐
│                FastAPI (main.py)               │         │
│                                               │         │
│  POST /query ──────────────────────────► SSE stream     │
│  POST /tts ────────────────────────────► MP3 bytes      │
│  POST /auth/signup                                      │
│  POST /auth/login                                       │
│  GET  /admin/* ────────────────────────► Govt dashboard │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              CrewAI Orchestrator                         │
│         (crew/orchestrator.py)                          │
│                                                         │
│  Parses Urdu query → fans out → merges results          │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │  Data    │ │  Risk    │ │  Market  │ │  Strategy │  │
│  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent    │  │
│  │          │ │          │ │          │ │           │  │
│  │PBS data  │ │Oversupply│ │Price     │ │Crop       │  │
│  │+ weather │ │detection │ │outlook   │ │alternatives│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
└───────┼────────────┼────────────┼──────────────┼────────┘
        └────────────┴────────────┴──────────────┘
                              │
                              ▼
                   Fireworks AI — deepseek-v4-pro (synthesis)
                   Urdu recommendation
                   streamed back via SSE
```

---

## Folder Structure

```
kisannama/
├── backend/
│   ├── agents/
│   │   ├── data_agent.py         # Fetches PBS crop area data
│   │   ├── risk_agent.py         # Oversupply scoring (area vs 3-year avg)
│   │   ├── market_agent.py       # Price history + export demand signals
│   │   ├── strategy_agent.py     # Crop alternative recommendations
│   │   └── alert_agent.py        # Continuous risk monitoring
│   ├── crew/
│   │   ├── orchestrator.py       # CrewAI Crew + Process.hierarchical
│   │   └── tools.py              # @tool-decorated DB + API functions
│   ├── services/
│   │   ├── speech.py             # edge-tts (Microsoft Neural Voices)
│   │   └── urdu_utils.py         # RTL text helpers
│   ├── routers/
│   │   ├── auth.py               # /auth/signup, /auth/login
│   │   ├── query.py              # /query SSE endpoint
│   │   ├── tts.py                # /tts endpoint
│   │   └── admin.py              # /admin/* govt dashboard endpoints
│   ├── models/
│   │   ├── user.py               # SQLAlchemy User model
│   │   ├── crop.py               # Crop, District models
│   │   └── crop_area.py          # CropArea (govt entries) model
│   ├── schemas/
│   │   ├── auth.py               # Pydantic signup/login schemas
│   │   ├── query.py              # QueryRequest schema
│   │   └── admin.py              # CropEntry schemas
│   ├── main.py                   # FastAPI app, CORS, router registration
│   ├── database.py               # SQLAlchemy engine + session
│   ├── seed_data.py              # PBS district + crop data seeder
│   ├── requirements.txt
│   └── .env
│
└── frontend/
    ├── app/
    │   ├── page.tsx              # Farmer chat UI (home)
    │   ├── layout.tsx            # Root layout
    │   ├── admin/
    │   │   ├── layout.tsx        # Sidebar + auth guard
    │   │   ├── page.tsx          # Crop entries table
    │   │   ├── add/page.tsx      # Add record form
    │   │   └── alerts/page.tsx   # Risk alerts view
    │   └── api/
    │       └── tts/route.ts      # Next.js API route proxying to /tts
    ├── components/
    │   ├── ChatInterface.tsx     # Main chat (Urdu RTL input + messages)
    │   ├── AgentLog.tsx          # SSE stream display (agent status)
    │   ├── VoiceInput.tsx        # Web Speech API (STT, ur-PK)
    │   ├── SpeakButton.tsx       # Google TTS audio playback
    │   ├── RecoCard.tsx          # Styled recommendation output card
    │   └── admin/
    │       ├── EntriesTable.tsx
    │       ├── AddRecordForm.tsx
    │       └── AlertsList.tsx
    ├── lib/
    │   ├── api.ts                # Fetch helpers for backend endpoints
    │   ├── sse.ts                # SSE stream reader utility
    │   └── adminApi.ts           # Admin-specific fetch helpers
    ├── .env.local
    └── package.json
```

---

## Database Schema

```sql
-- Users (farmers + govt employees share this table, role distinguishes them)
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    phone       VARCHAR(20) UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,         -- bcrypt hash
    role        VARCHAR(20) DEFAULT 'farmer',  -- 'farmer' | 'admin'
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Reference data (seeded once)
CREATE TABLE crops (
    id    SERIAL PRIMARY KEY,
    name  VARCHAR(50) NOT NULL  -- 'Potato' | 'Onion' | 'Wheat'
);

CREATE TABLE districts (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(100) NOT NULL,
    province  VARCHAR(50) NOT NULL
);

-- Core table — govt employees fill this via dashboard
CREATE TABLE crop_area (
    id               SERIAL PRIMARY KEY,
    district_id      INT REFERENCES districts(id),
    crop_id          INT REFERENCES crops(id),
    season           VARCHAR(20) NOT NULL,       -- 'Rabi 2025-26'
    area_acres       INT NOT NULL,
    prev_year_acres  INT NOT NULL,
    expected_yield   INT,                        -- maunds/acre
    data_source      VARCHAR(100),
    notes            TEXT,
    entered_by       INT REFERENCES users(id),
    created_at       TIMESTAMP DEFAULT NOW()
);

-- Price history (seeded from commodity exchange data)
CREATE TABLE price_history (
    id          SERIAL PRIMARY KEY,
    crop_id     INT REFERENCES crops(id),
    district_id INT REFERENCES districts(id),
    price_pkr   INT NOT NULL,                   -- PKR per maund
    recorded_at DATE NOT NULL
);

-- Farmer queries log (for analytics)
CREATE TABLE query_log (
    id          SERIAL PRIMARY KEY,
    user_id     INT REFERENCES users(id),
    query_text  TEXT NOT NULL,
    district    VARCHAR(100),
    crop        VARCHAR(50),
    response    TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

---

## Agent Design

### Data Agent
- **Input:** district name, crop name, season
- **Tools:** `get_crop_area()` (PostgreSQL)
- **Output:** JSON with current area, previous year area

### Risk Agent
- **Input:** Data Agent output
- **Logic:** if `(area - prev) / prev > 0.25` → High risk; `> 0.10` → Medium; else Low
- **Output:** risk level, percentage change, reasoning

### Market Agent
- **Input:** crop name, district
- **Tools:** `get_price_history()` (PostgreSQL, last 3 seasons)
- **Output:** price trend (rising/stable/falling), last known mandi price

### Strategy Agent
- **Input:** Risk Agent + Market Agent outputs
- **Tools:** Fireworks API call (deepseek-v4-pro) with structured context
- **Output:** 2–3 alternative crop suggestions with reasoning

### Orchestrator
- Runs Data, Risk, Market, Strategy agents in parallel via `Process.hierarchical`
- All agents use `deepseek-v4-pro` as their LLM via CrewAI's `LLM` wrapper
- Merges results into a single context object
- Makes final Fireworks streaming call (deepseek-v4-pro) to generate Urdu recommendation
- Streams response chunks via SSE

---

## Authentication Flow

- Farmer signup: phone + name + password (no OTP for hackathon)
- JWT issued on signup and login, expires in 7 days
- Farmer routes: require valid JWT
- Admin routes: require JWT with `role = admin`
- Admin accounts created manually (seeded in DB, not self-serve)

---

## Speech Flow

### STT (voice input)
```
Farmer taps mic → VoiceInput.tsx starts SpeechRecognition (ur-PK)
→ Transcript appears in input field → Farmer confirms → POST /query
```

### TTS (voice output)
```
Recommendation arrives → SpeakButton appears → Farmer taps
→ POST /tts with Urdu text → edge-tts (Microsoft Neural Voices) returns MP3
→ Browser Audio API plays it → Fallback: browser SpeechSynthesis
```

---

## SSE Streaming Format

Each event from `POST /query` is a JSON line:

```
data: {"type": "agent_update", "agent": "data_agent", "status": "running", "message": "Fetching Sahiwal district data..."}

data: {"type": "agent_update", "agent": "risk_agent", "status": "done", "message": "High risk detected — +37% above last year"}

data: {"type": "token", "content": "آپ کے "}

data: {"type": "token", "content": "ضلع ساہیوال میں"}

data: {"type": "done"}
```

---

## Environment Variables

### Backend (.env)
```
FIREWORKS_API_KEY=fw_...
DATABASE_URL=postgresql://user:pass@host:5432/kisannama
SECRET_KEY=your-jwt-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_DAYS=7
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:3000
```

---

## Deployment

| Service | Platform | Notes |
|---|---|---|
| Backend | Railway | Free tier, auto-deploy from GitHub |
| Frontend | Vercel | Free tier, Next.js native |
| Database | Railway PostgreSQL | Provisioned alongside backend |
| TTS | edge-tts | Free Microsoft Neural Voices |

---

## Hackathon Build Order

1. `POST /auth/signup` + `POST /auth/login` — auth working
2. `POST /query` returning hardcoded Urdu string — proves connection
3. Strategy Agent calling Fireworks AI deepseek-v4-pro — proves AI works
4. Add Data, Risk, Market agents in parallel
5. Seed DB with PBS potato/onion/wheat district data
6. Wire SSE streaming to AgentLog.tsx in frontend
7. Build govt dashboard (entries table + add form)
8. Add voice input (VoiceInput.tsx — Web Speech API)
9. Add TTS (SpeakButton.tsx — edge-tts)
10. Polish RecoCard UI and Urdu RTL styling
