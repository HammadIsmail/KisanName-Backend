"""
KisanNama CrewAI Orchestrator

Flow:
  1. Parse district/crop from query (gpt-4o)
  2. Run CrewAI Crew (Data, Risk, Market, Strategy) hierarchically.
  3. Extract risk_level and recommended_crop from the output.
  4. Stream final recommendation via SSE in BOTH Urdu and English simultaneously
"""
import json
import os
import asyncio
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session
from crewai import Agent, Task, Crew, Process

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

    # ── Step 2: Run CrewAI Agents ───────────────────────────────────────────
    yield _agent_event("data_agent", "running", "ایجنٹس کام کر رہے ہیں...", "Agents are working...")
    
    # Define Agents
    llm = "gpt-4o"
    
    data_agent = Agent(
        role="Data Agent",
        goal="Fetch crop area statistics from the database",
        backstory="Expert in agricultural data.",
        tools=[get_crop_area_summary],
        llm=llm,
        verbose=True
    )

    risk_agent = Agent(
        role="Risk Agent",
        goal="Assess risk level based on area changes",
        backstory="Expert in agricultural risk assessment.",
        tools=[assess_risk],
        llm=llm,
        verbose=True
    )

    market_agent = Agent(
        role="Market Agent",
        goal="Fetch market price trends",
        backstory="Expert in market price analysis.",
        tools=[get_market_trend_summary],
        llm=llm,
        verbose=True
    )

    strategy_agent = Agent(
        role="Strategy Agent",
        goal="Suggest alternative crops based on data, risk, and market trends",
        backstory="Expert agricultural strategist.",
        llm=llm,
        verbose=True
    )

    # Define Tasks
    data_task = Task(
        description=f"Fetch crop area summary for {crop} in {district}.",
        expected_output="A text summary of the crop area, including percentage change vs 3-year average.",
        agent=data_agent
    )

    risk_task = Task(
        description="Based on the percentage change from the Data Agent, assess the risk level.",
        expected_output="Risk level assessment (HIGH/MEDIUM/LOW).",
        agent=risk_agent,
        context=[data_task],
        async_execution=True
    )

    market_task = Task(
        description=f"Fetch market trend summary for {crop} in {district}.",
        expected_output="A text summary of market trends including the trend direction.",
        agent=market_agent,
        async_execution=True
    )

    strategy_task = Task(
        description=f"Based on the Data, Risk, and Market summaries, suggest 2-3 alternative crops for {crop} in {district}. Provide reasons.",
        expected_output="A comprehensive report including the data, risk, market trends, and 2-3 alternative crops.",
        agent=strategy_agent,
        context=[data_task, risk_task, market_task]
    )

    crew = Crew(
        agents=[data_agent, risk_agent, market_agent, strategy_agent],
        tasks=[data_task, risk_task, market_task, strategy_task],
        process=Process.hierarchical,
        manager_llm=llm,
        verbose=True
    )

    # Run Crew in background thread to not block async generator
    def run_crew():
        return crew.kickoff()
        
    crew_result = await asyncio.to_thread(run_crew)
    merged_outputs = str(crew_result)

    # Yield done states for UI checkmarks
    yield _agent_event("data_agent", "done", "ڈیٹا حاصل کر لیا گیا", "Data fetched")
    yield _agent_event("risk_agent", "done", "خطرے کا تجزیہ ہو گیا", "Risk analyzed")
    yield _agent_event("market_agent", "done", "مارکیٹ کا تجزیہ ہو گیا", "Market analyzed")
    yield _agent_event("strategy_agent", "done", "متبادل فصلیں تیار ہیں", "Strategy ready")

    # ── Step 3: Extract final fields for UI ──────────────────────────────────
    extract_sys = "Extract risk_level (low/medium/high) and recommended_crop (string) from the report."
    def extract_fields():
        res = _openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": extract_sys},
                {"role": "user", "content": merged_outputs}
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(res.choices[0].message.content)
        
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

    # Stream Urdu tokens first
    def stream_ur():
        return _openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": ur_prompt}],
            stream=True,
            temperature=0.5,
            max_tokens=600,
        )
    ur_stream = await asyncio.to_thread(stream_ur)
    for chunk in ur_stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield _sse({"type": "token", "lang": "ur", "content": delta.content})

    # Stream English tokens
    def stream_en():
        return _openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": en_prompt}],
            stream=True,
            temperature=0.5,
            max_tokens=600,
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
