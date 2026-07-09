# KisanNama — API Reference

> Base URL (local): `http://localhost:8000`
> Base URL (production): `https://kisannama-api.up.railway.app`
> All requests/responses use `Content-Type: application/json` unless noted.
> Protected routes require: `Authorization: Bearer <token>`

---

## Auth

### POST /auth/signup

Register a new farmer account. No OTP required.

**Request**
```json
{
  "name": "Ali Hassan",
  "phone": "03001234567",
  "password": "mypassword123",
  "role": "farmer"
}
```

**Response 201**
```json
{
  "id": 1,
  "name": "Ali Hassan",
  "phone": "03001234567",
  "role": "farmer",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response 409** — phone already registered
```json
{
  "detail": "Phone number already registered."
}
```

**Response 422** — validation error
```json
{
  "detail": [
    {
      "loc": ["body", "phone"],
      "msg": "Phone number must be 11 digits starting with 03",
      "type": "value_error"
    }
  ]
}
```

---

### POST /auth/login

**Request**
```json
{
  "phone": "03001234567",
  "password": "mypassword123"
}
```

**Response 200**
```json
{
  "id": 1,
  "name": "Ali Hassan",
  "role": "farmer",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response 401**
```json
{
  "detail": "Incorrect phone number or password."
}
```

---

### GET /auth/me

Returns current user from JWT. Protected.

**Headers**
```
Authorization: Bearer <token>
```

**Response 200**
```json
{
  "id": 1,
  "name": "Ali Hassan",
  "phone": "03001234567",
  "role": "farmer",
  "created_at": "2025-06-27T10:00:00Z"
}
```

**Response 401**
```json
{
  "detail": "Token expired or invalid."
}
```

---

## Farmer Query (Core Feature)

### POST /query

Accepts a farmer's Urdu question, runs all CrewAI agents (powered by `google/gemma-4-31b-it` via self-hosted vLLM on AMD GPU), and streams back agent updates followed by the bilingual Urdu + English recommendation as Server-Sent Events.

**Headers**
```
Authorization: Bearer <token>
Content-Type: application/json
Accept: text/event-stream
```

**Request**
```json
{
  "text": "میں ساہیوال میں 15 ایکڑ زمین پر اگلے ماہ آلو لگانا چاہتا ہوں",
  "district": "Sahiwal",
  "crop": "Potato",
  "land_acres": 15
}
```

> `district`, `crop`, and `land_acres` are extracted automatically by `google/gemma-4-31b-it` if not provided. Sending them explicitly speeds up processing.

**Response** — `Content-Type: text/event-stream`

Each line is a JSON object prefixed with `data: `.

```
data: {"type": "agent_update", "agent": "data_agent", "status": "running", "message": "Sahiwal district data لوڈ ہو رہا ہے..."}

data: {"type": "agent_update", "agent": "data_agent", "status": "done", "message": "ڈیٹا مل گیا — رقبہ 5,200 ایکڑ، گزشتہ سال 3,800 ایکڑ"}

data: {"type": "agent_update", "agent": "risk_agent", "status": "running", "message": "خطرے کا تجزیہ ہو رہا ہے..."}

data: {"type": "agent_update", "agent": "risk_agent", "status": "done", "message": "زیادہ خطرہ — گزشتہ سال سے 37% زیادہ رقبہ"}

data: {"type": "agent_update", "agent": "market_agent", "status": "running", "message": "مارکیٹ کا تجزیہ ہو رہا ہے..."}

data: {"type": "agent_update", "agent": "market_agent", "status": "done", "message": "قیمتیں گرنے کا رجحان — گزشتہ 3 ماہ میں 22% کمی"}

data: {"type": "agent_update", "agent": "strategy_agent", "status": "running", "message": "بہترین فصلوں کا انتخاب ہو رہا ہے..."}

data: {"type": "agent_update", "agent": "strategy_agent", "status": "done", "message": "متبادل فصلیں تیار ہیں"}

data: {"type": "token", "content": "السلام علیکم! آپ کے سوال کا جواب یہ ہے:\n\n"}

data: {"type": "token", "content": "ضلع ساہیوال میں اس وقت آلو کا رقبہ گزشتہ سال سے **37% زیادہ** ہے۔"}

data: {"type": "token", "content": " اگر آپ نے آلو لگائے تو قیمت گرنے کا بہت زیادہ خطرہ ہے۔"}

data: {"type": "done", "risk_level": "high", "recommended_crop": "Onion", "district": "Sahiwal"}
```

**SSE event types**

| type | description |
|---|---|
| `agent_update` | One agent reporting its progress. Has `agent`, `status` (`running`/`done`/`error`), `message` |
| `token` | One chunk of the Urdu recommendation text |
| `done` | Stream complete. Includes summary metadata |
| `error` | Something failed. Has `message` field |

**Response 401** — missing or invalid token
```
data: {"type": "error", "message": "Authentication required."}
```

**Response 422** — empty query
```json
{
  "detail": "Query text cannot be empty."
}
```

---

## Text to Speech

### POST /tts

Converts Urdu text to MP3 audio using edge-tts (Microsoft Neural Voices).

**Headers**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request**
```json
{
  "text": "ضلع ساہیوال میں اس وقت آلو کا رقبہ گزشتہ سال سے زیادہ ہے۔",
  "voice": "ur-PK-UzmaNeural",
  "model": "tts-1"
}
```

> `voice` is optional. Defaults to `ur-PK-UzmaNeural` (female). Another option is `ur-PK-AsadNeural` (male).
> `model` is optional. Kept for API backwards compatibility, but ignored by the edge-tts backend.

**Response 200**
```
Content-Type: audio/mpeg

<binary MP3 bytes>
```

Frontend plays this directly:
```typescript
const blob = await res.blob();
const url = URL.createObjectURL(blob);
new Audio(url).play();
```

**Response 400**
```json
{
  "detail": "Text too long. Maximum 1000 characters per request."
}
```

**Response 503**
```json
{
  "detail": "TTS service temporarily unavailable. Use browser fallback."
}
```

---

## Admin — Crop Data Management

> All `/admin` routes require JWT with `role = admin`.

### GET /admin/entries

Returns all crop area records with optional filters.

**Query params**

| param | type | description |
|---|---|---|
| `crop` | string | Filter by crop name: `Potato`, `Onion`, `Wheat` |
| `district` | string | Filter by district name |
| `season` | string | e.g. `Rabi 2025-26` |
| `page` | int | Default 1 |
| `limit` | int | Default 20, max 100 |

**Request**
```
GET /admin/entries?crop=Potato&season=Rabi+2025-26&page=1&limit=20
Authorization: Bearer <admin-token>
```

**Response 200**
```json
{
  "total": 8,
  "page": 1,
  "limit": 20,
  "entries": [
    {
      "id": 1,
      "district": "Sahiwal",
      "crop": "Potato",
      "season": "Rabi 2025-26",
      "area_acres": 5200,
      "prev_year_acres": 3800,
      "change_pct": 36.8,
      "risk_level": "high",
      "expected_yield": 180,
      "data_source": "PBS field survey",
      "notes": "",
      "entered_by": "Ahmad Raza",
      "created_at": "2025-06-27T09:30:00Z"
    },
    {
      "id": 2,
      "district": "Okara",
      "crop": "Potato",
      "season": "Rabi 2025-26",
      "area_acres": 4800,
      "prev_year_acres": 4200,
      "change_pct": 14.3,
      "risk_level": "medium",
      "expected_yield": 175,
      "data_source": "Patwari report",
      "notes": "",
      "entered_by": "Ahmad Raza",
      "created_at": "2025-06-27T09:35:00Z"
    }
  ]
}
```

---

### POST /admin/entries

Add a new crop area record.

**Request**
```json
{
  "district_id": 1,
  "crop_id": 1,
  "season": "Rabi 2025-26",
  "area_acres": 5200,
  "prev_year_acres": 3800,
  "expected_yield": 180,
  "data_source": "PBS field survey",
  "notes": "Verified from 3 tehsils"
}
```

**Response 201**
```json
{
  "id": 9,
  "district": "Sahiwal",
  "crop": "Potato",
  "season": "Rabi 2025-26",
  "area_acres": 5200,
  "prev_year_acres": 3800,
  "change_pct": 36.8,
  "risk_level": "high",
  "expected_yield": 180,
  "data_source": "PBS field survey",
  "notes": "Verified from 3 tehsils",
  "entered_by": "Ahmad Raza",
  "created_at": "2025-06-27T10:00:00Z"
}
```

**Response 409** — record already exists for same district + crop + season
```json
{
  "detail": "Entry already exists for Sahiwal / Potato / Rabi 2025-26. Use PUT to update."
}
```

**Response 422**
```json
{
  "detail": [
    {
      "loc": ["body", "area_acres"],
      "msg": "area_acres must be greater than 0",
      "type": "value_error"
    }
  ]
}
```

---

### PUT /admin/entries/{id}

Update an existing record.

**Request**
```json
{
  "area_acres": 5400,
  "notes": "Updated after re-survey of Chichawatni tehsil"
}
```

> Only send fields you want to update. All fields are optional.

**Response 200**
```json
{
  "id": 9,
  "district": "Sahiwal",
  "crop": "Potato",
  "season": "Rabi 2025-26",
  "area_acres": 5400,
  "prev_year_acres": 3800,
  "change_pct": 42.1,
  "risk_level": "high",
  "expected_yield": 180,
  "data_source": "PBS field survey",
  "notes": "Updated after re-survey of Chichawatni tehsil",
  "entered_by": "Ahmad Raza",
  "created_at": "2025-06-27T10:00:00Z",
  "updated_at": "2025-06-27T14:22:00Z"
}
```

**Response 404**
```json
{
  "detail": "Entry with id 9 not found."
}
```

---

### DELETE /admin/entries/{id}

**Response 200**
```json
{
  "detail": "Entry deleted successfully."
}
```

---

### GET /admin/alerts

Returns all entries with risk level `high` or `medium`, sorted by severity.

**Response 200**
```json
{
  "total": 4,
  "alerts": [
    {
      "id": 1,
      "district": "Sahiwal",
      "crop": "Potato",
      "risk_level": "high",
      "change_pct": 36.8,
      "area_acres": 5200,
      "prev_year_acres": 3800,
      "season": "Rabi 2025-26",
      "message": "Planted area is 37% above last year. Price crash risk is significant."
    },
    {
      "id": 3,
      "district": "Faisalabad",
      "crop": "Onion",
      "risk_level": "medium",
      "change_pct": 13.1,
      "area_acres": 3100,
      "prev_year_acres": 2740,
      "season": "Rabi 2025-26",
      "message": "Planted area is 13% above last year. Monitor over next 4 weeks."
    }
  ]
}
```

---

## Reference Data

### GET /admin/districts

Returns all districts (for dropdown population in the add record form).

**Response 200**
```json
{
  "districts": [
    {"id": 1, "name": "Sahiwal", "province": "Punjab"},
    {"id": 2, "name": "Okara", "province": "Punjab"},
    {"id": 3, "name": "Faisalabad", "province": "Punjab"},
    {"id": 4, "name": "Multan", "province": "Punjab"},
    {"id": 5, "name": "Lahore", "province": "Punjab"},
    {"id": 6, "name": "Gujranwala", "province": "Punjab"},
    {"id": 7, "name": "Sheikhupura", "province": "Punjab"},
    {"id": 8, "name": "Rahim Yar Khan", "province": "Punjab"}
  ]
}
```

---

### GET /admin/crops

**Response 200**
```json
{
  "crops": [
    {"id": 1, "name": "Potato"},
    {"id": 2, "name": "Onion"},
    {"id": 3, "name": "Wheat"}
  ]
}
```

---

## Health Check

### GET /health

No auth required. Used by Railway for uptime monitoring.

**Response 200**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "connected"
}
```

---

## Error Codes Reference

| HTTP code | When it happens |
|---|---|
| 200 | Success |
| 201 | Record created |
| 400 | Bad request (e.g. text too long for TTS) |
| 401 | Missing, expired, or invalid JWT |
| 403 | Valid JWT but insufficient role (farmer hitting /admin route) |
| 404 | Record not found |
| 409 | Conflict (duplicate entry, phone already registered) |
| 422 | Validation error (missing required field, wrong type) |
| 500 | Internal server error |
| 503 | Upstream service unavailable (vLLM server unreachable, Microsoft TTS) |

---

## JWT Structure

Payload decoded from the token:
```json
{
  "sub": "1",
  "name": "Ali Hassan",
  "role": "farmer",
  "exp": 1751234567
}
```

Token expires in **7 days**. Frontend should redirect to `/login` on 401.

---

## Notes for Frontend Integration

- The `/query` endpoint returns `text/event-stream`. Use `EventSource` or a manual `fetch` + `ReadableStream` reader — do not use regular `fetch().then(res => res.json())`.
- TTS response is binary MP3. Use `res.blob()` then `URL.createObjectURL()`.
- All Urdu text in responses is right-to-left. Set `dir="rtl"` on any element rendering it.
- Admin token is the same JWT structure, just with `role: admin`. Store in `localStorage` with key `kisannama_token`.
- The `done` event from `/query` includes `risk_level`, `recommended_crop`, and `district` for rendering the `RecoCard` badge/header without parsing the Urdu text.
