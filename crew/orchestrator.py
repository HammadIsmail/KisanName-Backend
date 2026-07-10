"""
KisanNama CrewAI Orchestrator

Flow:
  1. Parse district/crop from query (google/gemma-4-31b-it via self-hosted vLLM)
  2. Run CrewAI Crew (Data, Risk, Market, Strategy) sequentially.
  3. Extract risk_level and recommended_crop from the output.
  4. Stream final recommendation via SSE in BOTH Urdu and English simultaneously
"""
import json
import os
import asyncio
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
from openai import OpenAI        # vLLM exposes an OpenAI-compatible API
from crewai import Agent, Task, Crew, Process, LLM
from sqlalchemy.orm import Session

from crew.tools import make_tools

load_dotenv()

import litellm

# --- FIX FOR CREWAI CACHE_BREAKPOINT BUG ---
original_completion = litellm.completion

def patched_completion(*args, **kwargs):
    if "messages" in kwargs:
        for msg in kwargs["messages"]:
            msg.pop("cache_breakpoint", None)
    return original_completion(*args, **kwargs)

litellm.completion = patched_completion
# -------------------------------------------

# ─── Self-hosted vLLM client (OpenAI-compatible) ──────────────────────────────

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://129.212.184.69:8000/v1")
VLLM_MODEL    = os.getenv("VLLM_MODEL",    "google/gemma-4-31b-it")

# OpenAI SDK pointed at vLLM — used for parse_query, extract_fields, streaming
_vllm_client = OpenAI(
    api_key="not-needed",   # vLLM doesn't require a key
    base_url=VLLM_BASE_URL,
)

# CrewAI LLM object — used by all agents
# Use "openai/" prefix so LiteLLM routes through the OpenAI-compatible path
_crew_llm = LLM(
    model=f"openai/{VLLM_MODEL}",
    api_key="not-needed",
    base_url=VLLM_BASE_URL,
    temperature=0.2,        # low temp for reliable tool-calling
)


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
    """Extract district, crop, land_acres from any-language farming query."""
    system = (
        "You extract structured information from farming queries (Urdu or English). "
        "Return ONLY valid JSON with keys: district (string|null), crop (string|null — one of Potato/Onion/Wheat), land_acres (number|null). "
        "If you cannot determine a value, use null. "
        "Do NOT include any explanation or markdown — output raw JSON only."
    )
    response = _vllm_client.chat.completions.create(
        model=VLLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=256,
    )
    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model wraps output in ```json ... ```
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)

GREETING_KEYWORDS = {
    "السلام", "سلام", "hello", "hi", "hey", "آداب", "جی", "ہیلو",
    "نمستے", "کیا حال", "good morning", "good evening", "assalam",
    "ہائے", "السلام علیکم"
}

def is_greeting(text: str) -> bool:
    """Return True if the query is a greeting or completely off-topic with no farming intent."""
    lowered = text.lower().strip()
    words = lowered.split()
    if len(words) <= 8 and any(kw in lowered for kw in GREETING_KEYWORDS):
        return True
    return False

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
    ALL events contain BOTH Urdu and English content.
    """
    get_crop_area_summary, assess_risk, get_market_trend_summary = make_tools(db)

    # ── Step 0: Check for greeting — stream via LLM for a natural, human feel ─
    if is_greeting(query_text) and not district and not crop:
        greeting_ur_prompt = (
            "تم KisanNama کے AI زرعی مشیر ہو — ایک دوستانہ اور ہمدرد پاکستانی ماہر۔\n"
            f"ایک کسان نے یہ کہا: \"{query_text}\"\n\n"
            "ان کا پُرجوش، گرمجوشی سے اردو میں استقبال کرو۔ اپنا تعارف KisanNama کے مشیر کے طور پر کراؤ۔ "
            "انہیں بتاؤ کہ تم آلو، پیاز اور گندم کی کاشت کے بارے میں ضلع کی سطح پر مشورہ دے سکتے ہو۔ "
            "ان سے پوچھو کہ وہ کس ضلع میں کون سی فصل اگانا چاہتے ہیں۔ "
            "صرف اردو میں لکھو، 60-80 الفاظ میں رکھو، قدرتی اور انسانی لہجہ استعمال کرو۔"
        )
        greeting_en_prompt = (
            "You are the KisanNama AI Agricultural Advisor — a friendly, knowledgeable expert for Pakistani farmers.\n"
            f"A farmer just said: \"{query_text}\"\n\n"
            "Warmly welcome them, introduce yourself as KisanNama's advisor. "
            "Let them know you can advise on potato, onion, and wheat cultivation at the district level. "
            "Ask them which district they are in and which crop they are planning to grow. "
            "Reply ONLY in English. Keep it to 60-80 words. Use a warm, natural, conversational tone."
        )

        def _stream_greeting_ur():
            return _vllm_client.chat.completions.create(
                model=VLLM_MODEL,
                messages=[{"role": "user", "content": greeting_ur_prompt}],
                stream=True,
                temperature=0.8,
                max_tokens=256,
            )

        def _stream_greeting_en():
            return _vllm_client.chat.completions.create(
                model=VLLM_MODEL,
                messages=[{"role": "user", "content": greeting_en_prompt}],
                stream=True,
                temperature=0.8,
                max_tokens=256,
            )

        ur_greeting_stream = await asyncio.to_thread(_stream_greeting_ur)
        for chunk in ur_greeting_stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield _sse({"type": "token", "lang": "ur", "content": delta.content})

        en_greeting_stream = await asyncio.to_thread(_stream_greeting_en)
        for chunk in en_greeting_stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield _sse({"type": "token", "lang": "en", "content": delta.content})

        yield _sse({"type": "done", "risk_level": "low", "recommended_crop": None, "district": None})
        return

    # ── Step 1: Parse query if fields missing ───────────────────────────────
    if not district or not crop:
        yield _agent_event(
            "data_agent", "running",
            "سوال سے ضلع اور فصل نکالی جا رہی ہے...",
            "Extracting district and crop from query...",
        )
        try:
            parsed = await asyncio.to_thread(parse_query, query_text)
            district = district or parsed.get("district")
            crop = crop or parsed.get("crop")
            land_acres = land_acres or parsed.get("land_acres")
        except Exception as e:
            yield _sse({"type": "error", "message_ur": "سوال پارس کرنے میں خرابی ہوئی۔", "message_en": f"Query parsing failed: {e}"})
            return

    if not district or not crop:
        if not district and not crop:
            msg_ur = "معاف کیجئے گا، براہ کرم اپنے ضلع اور فصل کا نام بتائیں۔"
            msg_en = "Please let me know your district and which crop you are planning to grow."
        elif not district:
            msg_ur = f"آپ {crop} کس ضلع میں کاشت کرنا چاہتے ہیں؟"
            msg_en = f"Which district are you planning to plant {crop} in?"
        else:
            msg_ur = f"آپ {district} میں کون سی فصل کاشت کرنا چاہتے ہیں؟"
            msg_en = f"Which crop are you planning to plant in {district}?"
            
        yield _sse({"type": "token", "lang": "ur", "content": msg_ur})
        yield _sse({"type": "token", "lang": "en", "content": msg_en})
        yield _sse({"type": "done", "risk_level": "low", "recommended_crop": None, "district": district})
        return

    # ── Step 2: Run CrewAI Agents ───────────────────────────────────────────
    yield _agent_event("data_agent", "running", "ایجنٹس کام کر رہے ہیں...", "Agents are working...")

    data_agent = Agent(
        role="Data Agent",
        goal="Fetch crop area statistics from the database",
        backstory="Expert in agricultural data.",
        tools=[get_crop_area_summary],
        llm=_crew_llm,
        verbose=True,
    )

    risk_agent = Agent(
        role="Risk Agent",
        goal="Assess risk level based on area changes",
        backstory="Expert in agricultural risk assessment.",
        tools=[assess_risk],
        llm=_crew_llm,
        verbose=True,
    )

    market_agent = Agent(
        role="Market Agent",
        goal="Fetch market price trends",
        backstory="Expert in market price analysis.",
        tools=[get_market_trend_summary],
        llm=_crew_llm,
        verbose=True,
    )

    strategy_agent = Agent(
        role="Strategy Agent",
        goal="Suggest alternative crops based on data, risk, and market trends",
        backstory="Expert agricultural strategist.",
        llm=_crew_llm,
        verbose=True,
    )

    data_task = Task(
        description=f"Fetch crop area summary for {crop} in {district}.",
        expected_output="A text summary of the crop area, including percentage change vs 3-year average.",
        agent=data_agent,
        async_execution=True,
    )

    risk_task = Task(
        description="Based on the percentage change from the Data Agent, assess the risk level.",
        expected_output="Risk level assessment (HIGH/MEDIUM/LOW).",
        agent=risk_agent,
        context=[data_task],
    )

    market_task = Task(
        description=f"Fetch market trend summary for {crop} in {district}.",
        expected_output="A text summary of market trends including the trend direction.",
        agent=market_agent,
        async_execution=True,
    )

    strategy_task = Task(
        description=(
            f"Based on the Data, Risk, and Market summaries, suggest 2-3 alternative crops "
            f"for {crop} in {district}. Provide reasons."
        ),
        expected_output="A comprehensive report including the data, risk, market trends, and 2-3 alternative crops.",
        agent=strategy_agent,
        context=[data_task, risk_task, market_task],
    )

    crew = Crew(
        agents=[data_agent, risk_agent, market_agent, strategy_agent],
        tasks=[data_task, risk_task, market_task, strategy_task],
        process=Process.sequential,
        verbose=True,
    )

    yield _agent_event("data_agent", "running", "ڈیٹا حاصل کیا جا رہا ہے...", "Fetching data...")
    yield _agent_event("risk_agent", "running", "خطرے کا تجزیہ ہو رہا ہے...", "Analyzing risk...")
    yield _agent_event("market_agent", "running", "مارکیٹ دیکھی جا رہی ہے...", "Checking market...")
    yield _agent_event("strategy_agent", "running", "متبادل فصلیں سوچی جا رہی ہیں...", "Formulating strategy...")

    loop = asyncio.get_running_loop()
    q = asyncio.Queue()

    def make_cb(agent, msg_ur, msg_en):
        def cb(output):
            loop.call_soon_threadsafe(q.put_nowait, _agent_event(agent, "done", msg_ur, msg_en))
        return cb

    data_task.callback = make_cb("data_agent", "ڈیٹا حاصل کر لیا گیا", "Data fetched")
    risk_task.callback = make_cb("risk_agent", "خطرے کا تجزیہ ہو گیا", "Risk analyzed")
    market_task.callback = make_cb("market_agent", "مارکیٹ کا تجزیہ ہو گیا", "Market analyzed")
    strategy_task.callback = make_cb("strategy_agent", "متبادل فصلیں تیار ہیں", "Strategy ready")

    kickoff_task = asyncio.create_task(asyncio.to_thread(crew.kickoff))

    while not kickoff_task.done():
        try:
            event = await asyncio.wait_for(q.get(), timeout=0.5)
            yield event
        except asyncio.TimeoutError:
            continue

    while not q.empty():
        yield q.get_nowait()

    crew_result = await kickoff_task
    merged_outputs = str(crew_result)

    # ── Step 3: Extract final fields for UI ──────────────────────────────────
    extract_sys = (
        "You are reading an agricultural advisory report.\n"
        "'recommended_crop' must be an ALTERNATIVE crop that is being suggested INSTEAD OF the crop being analyzed.\n"
        "Do NOT return the crop under analysis as recommended_crop.\n"
        "Extract: risk_level (low/medium/high) and recommended_crop (the suggested alternative, not the crop being studied).\n"
        "Return ONLY raw JSON — no markdown, no explanation."
    )

    def extract_fields():
        try:
            res = _vllm_client.chat.completions.create(
                model=VLLM_MODEL,
                messages=[
                    {"role": "system", "content": extract_sys},
                    {"role": "user", "content": merged_outputs},
                ],
                temperature=0,
                max_tokens=128,
            )
            raw = res.choices[0].message.content.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            return json.loads(raw)
        except Exception as e:
            print(f"Warning: Failed to extract fields: {e}")
            CROP_ALTERNATIVES = {
                "potato": "Onion",
                "onion": "Wheat",
                "wheat": "Onion",
            }
            fallback_alt = CROP_ALTERNATIVES.get(str(crop).lower(), "Wheat") if crop else "Wheat"
            return {"risk_level": "low", "recommended_crop": fallback_alt}

    extracted = await asyncio.to_thread(extract_fields)
    risk_level = extracted.get("risk_level", "low").lower()
    recommended_crop = extracted.get("recommended_crop", crop)

    # ── Step 4: Final recommendation — streamed in BOTH languages ───────────
    ur_prompt = f"""تم KisanNama کے AI زرعی مشیر ہو۔ ایک پاکستانی کسان نے یہ سوال پوچھا ہے:

سوال: {query_text}

ایجنٹس کی رپورٹ:
{merged_outputs}

STRICT INSTRUCTION: آپ کو صرف اردو میں جواب دینا ہے۔ انگریزی کا ایک لفظ بھی نہ لکھیں۔
- السلام علیکم سے شروع کریں
- رپورٹ کی بنیاد پر سفارش دیں
- 150-200 الفاظ میں رکھیں"""

    en_prompt = f"""You are the KisanNama AI Agricultural Advisor. A farmer asked:

Question: {query_text}

Agents Report:
{merged_outputs}

STRICT INSTRUCTION: Reply ONLY in English. Do not use any Urdu words.
- Start with a friendly greeting
- Give a recommendation based on the report
- Keep within 150-200 words"""

    # Stream Urdu tokens
    def stream_ur():
        return _vllm_client.chat.completions.create(
            model=VLLM_MODEL,
            messages=[{"role": "user", "content": ur_prompt}],
            stream=True,
            temperature=0.5,
            max_tokens=2048,
        )

    ur_stream = await asyncio.to_thread(stream_ur)
    for chunk in ur_stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield _sse({"type": "token", "lang": "ur", "content": delta.content})

    # Stream English tokens
    def stream_en():
        return _vllm_client.chat.completions.create(
            model=VLLM_MODEL,
            messages=[{"role": "user", "content": en_prompt}],
            stream=True,
            temperature=0.5,
            max_tokens=2048,
        )

    en_stream = await asyncio.to_thread(stream_en)
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
