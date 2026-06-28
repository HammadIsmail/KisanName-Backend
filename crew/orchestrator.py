"""
KisanNama CrewAI Orchestrator

Flow:
  1. Parse district/crop from query (gpt-4o)
  2. Run Data Agent → get crop area
  3. Run Risk Agent → compute risk level
  4. Run Market Agent → get price trend
  5. Run Strategy Agent → suggest alternatives
  6. Stream final recommendation via SSE in BOTH Urdu and English simultaneously
"""
import json
import os
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session

from crew.tools import make_tools

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_openai_client = OpenAI(api_key=OPENAI_API_KEY)


# ─── SSE helpers ──────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _agent_event(agent: str, status: str, msg_ur: str, msg_en: str) -> str:
    """Emit a single agent_update event that contains both language strings."""
    return _sse({
        "type": "agent_update",
        "agent": agent,
        "status": status,
        "message_ur": msg_ur,
        "message_en": msg_en,
    })


# ─── Query parser ─────────────────────────────────────────────────────────────

def parse_query(text: str) -> dict:
    """Extract district, crop, land_acres from any-language farming query using gpt-4o."""
    system = (
        "You extract structured information from farming queries (Urdu or English). "
        "Return ONLY valid JSON with keys: district (string|null), crop (string|null — one of Potato/Onion/Wheat), land_acres (number|null). "
        "If you cannot determine a value, use null."
    )
    response = _openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


# ─── Risk calculation ─────────────────────────────────────────────────────────

def compute_risk(area: int, prev: int) -> tuple[str, float]:
    if prev == 0:
        return "low", 0.0
    change = ((area - prev) / prev) * 100
    if change > 25:
        level = "high"
    elif change > 10:
        level = "medium"
    else:
        level = "low"
    return level, round(change, 1)


# ─── Main orchestrator ────────────────────────────────────────────────────────

async def run_query_stream(
    query_text: str,
    db: Session,
    district: Optional[str] = None,
    crop: Optional[str] = None,
    land_acres: Optional[float] = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE strings.
    ALL events contain BOTH Urdu and English content. The frontend picks
    which language to display based on the user's toggle.
    """
    get_crop_area, get_price_history = make_tools(db)

    # ── Step 1: Parse query if fields missing ───────────────────────────────
    if not district or not crop:
        yield _agent_event(
            "data_agent", "running",
            "سوال سے ضلع اور فصل نکالی جا رہی ہے...",
            "Extracting district and crop from query...",
        )
        try:
            parsed = parse_query(query_text)
            district = district or parsed.get("district")
            crop = crop or parsed.get("crop")
            land_acres = land_acres or parsed.get("land_acres")
        except Exception:
            yield _sse({"type": "error", "message_ur": "سوال پارس کرنے میں خرابی ہوئی۔", "message_en": "Query parsing failed."})
            return

    if not district or not crop:
        yield _sse({
            "type": "error",
            "message_ur": "براہ کرم اپنے سوال میں ضلع اور فصل کا نام بتائیں۔",
            "message_en": "Please specify the district and crop name in your query.",
        })
        return

    # ── Step 2: Data Agent ──────────────────────────────────────────────────
    yield _agent_event(
        "data_agent", "running",
        f"{district} ضلع کا ڈیٹا لوڈ ہو رہا ہے...",
        f"Loading data for {district} district...",
    )
    crop_data = get_crop_area.run(district=district, crop=crop)
    if isinstance(crop_data, str):
        crop_data = json.loads(crop_data)

    if not crop_data.get("found"):
        yield _agent_event(
            "data_agent", "done",
            f"{district} کے لیے ڈیٹا دستیاب نہیں ہے",
            f"No data available for {district}",
        )
        area_acres = 0
        prev_year_acres = 0
    else:
        area_acres = crop_data["area_acres"]
        prev_year_acres = crop_data["prev_year_acres"]
        yield _agent_event(
            "data_agent", "done",
            f"ڈیٹا مل گیا — رقبہ {area_acres:,} ایکڑ، گزشتہ سال {prev_year_acres:,} ایکڑ",
            f"Data found — Area: {area_acres:,} acres, Prev year: {prev_year_acres:,} acres",
        )

    # ── Step 3: Risk Agent ──────────────────────────────────────────────────
    yield _agent_event("risk_agent", "running", "خطرے کا تجزیہ ہو رہا ہے...", "Analyzing risk...")
    risk_level, change_pct = compute_risk(area_acres, prev_year_acres)

    risk_urdu = {"high": "زیادہ", "medium": "درمیانہ", "low": "کم"}[risk_level]
    risk_en = {"high": "High", "medium": "Medium", "low": "Low"}[risk_level]

    risk_label_ur = "زیادہ خطرہ" if risk_level == "high" else "درمیانہ خطرہ" if risk_level == "medium" else "کم خطرہ"
    dir_ur = "زیادہ" if change_pct > 0 else "کم"
    dir_en = "more" if change_pct > 0 else "less"

    yield _agent_event(
        "risk_agent", "done",
        f"{risk_label_ur} — گزشتہ سال سے {abs(change_pct):.0f}% {dir_ur} رقبہ",
        f"{risk_en} Risk — {abs(change_pct):.0f}% {dir_en} area than last year",
    )

    # ── Step 4: Market Agent ─────────────────────────────────────────────────
    yield _agent_event("market_agent", "running", "مارکیٹ کا تجزیہ ہو رہا ہے...", "Analyzing market...")
    price_data = get_price_history.run(crop=crop, district=district)
    if isinstance(price_data, str):
        price_data = json.loads(price_data)

    trend = price_data.get("trend", "stable")
    last_price = price_data.get("last_price_pkr", "N/A")
    price_change = price_data.get("change_pct", 0)

    trend_urdu = {"rising": "بڑھ رہی ہیں", "falling": "گر رہی ہیں", "stable": "مستحکم ہیں"}[trend]
    trend_en = {"rising": "Rising", "falling": "Falling", "stable": "Stable"}[trend]

    if price_data.get("found"):
        dir_price_ur = "اضافہ" if price_change > 0 else "کمی"
        dir_price_en = "increase" if price_change > 0 else "decrease"
        yield _agent_event(
            "market_agent", "done",
            f"قیمتیں {trend_urdu} — آخری قیمت {last_price} روپے فی من، {abs(price_change):.0f}% {dir_price_ur}",
            f"Prices are {trend_en.lower()} — Last price: {last_price} PKR/maund, {abs(price_change):.0f}% {dir_price_en}",
        )
    else:
        yield _agent_event("market_agent", "done", "قیمتوں کا ڈیٹا دستیاب نہیں", "Price data not available")

    # ── Step 5: Strategy Agent ───────────────────────────────────────────────
    yield _agent_event("strategy_agent", "running", "بہترین فصلوں کا انتخاب ہو رہا ہے...", "Selecting optimal crops...")

    # Generate alternatives in both languages in one call
    alternatives_prompt = f"""You are an agricultural expert. A farmer plans to plant {crop} in {district}.

Data:
- Area: {area_acres:,} acres (prev {prev_year_acres:,} acres)
- Change: {change_pct:+.1f}%
- Risk: {risk_en}
- Price trend: {trend_en}

Return a JSON object with two keys:
  "ur": 2-3 alternative crops with one-sentence Urdu reason each
  "en": 2-3 alternative crops with one-sentence English reason each
Return ONLY valid JSON, no markdown."""

    alt_response = _openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": alternatives_prompt}],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=300,
    )
    alt_data = json.loads(alt_response.choices[0].message.content)
    alternatives_ur = alt_data.get("ur", "")
    alternatives_en = alt_data.get("en", "")

    yield _agent_event("strategy_agent", "done", "متبادل فصلیں تیار ہیں", "Alternative crops ready")

    # ── Step 6: Final recommendation — streamed in BOTH languages ───────────
    recommended_crop = crop
    if risk_level == "high" and crop == "Potato":
        recommended_crop = "Onion"
    elif risk_level == "high" and crop == "Onion":
        recommended_crop = "Wheat"

    # --- Urdu stream ---
    ur_prompt = f"""تم KisanNama کے AI زرعی مشیر ہو۔ ایک پاکستانی کسان نے یہ سوال پوچھا ہے:

سوال: {query_text}

ڈیٹا تجزیہ:
- ضلع: {district}
- فصل: {crop}
- رقبہ: {area_acres:,} ایکڑ (گزشتہ سال {prev_year_acres:,} ایکڑ)
- تبدیلی: {change_pct:+.1f}%
- خطرہ: {risk_urdu}
- قیمت کا رجحان: {trend_urdu}
- آخری قیمت: {last_price} روپے فی من
- متبادل فصلیں: {alternatives_ur}

STRICT INSTRUCTION: آپ کو صرف اردو میں جواب دینا ہے۔ انگریزی کا ایک لفظ بھی نہ لکھیں۔
- السلام علیکم سے شروع کریں
- ڈیٹا سے سمجھائیں کہ کیوں خطرہ ہے یا نہیں
- واضح سفارش دیں
- 150-200 الفاظ میں رکھیں""".strip()

    # --- English stream ---
    en_prompt = f"""You are the KisanNama AI Agricultural Advisor. A farmer asked:

Question: {query_text}

Data Analysis:
- District: {district}
- Crop: {crop}
- Area: {area_acres:,} acres (prev {prev_year_acres:,} acres)
- Change: {change_pct:+.1f}%
- Risk: {risk_en}
- Price Trend: {trend_en}
- Last Price: {last_price} PKR/maund
- Alternatives: {alternatives_en}

STRICT INSTRUCTION: Reply ONLY in English. Do not use any Urdu words.
- Start with a friendly greeting
- Explain the data analysis clearly
- Give a clear recommendation
- Keep within 150-200 words""".strip()

    # Stream Urdu tokens first (tagged with lang="ur")
    ur_stream = _openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": ur_prompt}],
        stream=True,
        temperature=0.5,
        max_tokens=600,
    )
    for chunk in ur_stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield _sse({"type": "token", "lang": "ur", "content": delta.content})

    # Stream English tokens (tagged with lang="en")
    en_stream = _openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": en_prompt}],
        stream=True,
        temperature=0.5,
        max_tokens=600,
    )
    for chunk in en_stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield _sse({"type": "token", "lang": "en", "content": delta.content})

    yield _sse({
        "type": "done",
        "risk_level": risk_level,
        "recommended_crop": recommended_crop,
        "district": district,
    })
