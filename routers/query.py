import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth import get_current_user
from crew.orchestrator import run_query_stream
from database import get_db
from models.user import User
from models.chat_session import ChatSession
from models.query_log import QueryLog
from schemas.query import QueryRequest

router = APIRouter(tags=["Query"])


# ─── POST /query ──────────────────────────────────────────────────────────────

@router.post("/query")
async def query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    SSE endpoint — runs agents and streams bilingual recommendation.
    Each event contains BOTH Urdu and English content.
    Tokens are tagged with lang='ur' or lang='en'.
    """
    # Resolve or create session
    if payload.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == payload.session_id,
            ChatSession.user_id == current_user.id,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
    else:
        # Auto-create a new session whose title is the first 60 chars of the query
        title = payload.text[:60].strip()
        session = ChatSession(user_id=current_user.id, title=title)
        db.add(session)
        db.commit()
        db.refresh(session)

    collected_ur: list[str] = []
    collected_en: list[str] = []

    async def event_stream():
        # First emit the session_id so the frontend can store it
        import json
        yield f"data: {json.dumps({'type': 'session', 'session_id': session.id, 'title': session.title}, ensure_ascii=False)}\n\n"

        async for chunk in run_query_stream(
            query_text=payload.text,
            db=db,
            district=payload.district,
            crop=payload.crop,
            land_acres=payload.land_acres,
        ):
            # Collect tokens by language for logging
            import json as _json
            try:
                if chunk.startswith("data: "):
                    event = _json.loads(chunk[6:])
                    if event.get("type") == "token":
                        if event.get("lang") == "ur":
                            collected_ur.append(event.get("content", ""))
                        elif event.get("lang") == "en":
                            collected_en.append(event.get("content", ""))
            except Exception:
                pass
            yield chunk

        # After streaming ends, log the message to DB
        risk_level = None
        recommended_crop = None
        district = None
        try:
            # Parse done event from last collected chunks — peek at last yield
            pass
        except Exception:
            pass

        log = QueryLog(
            user_id=current_user.id,
            session_id=session.id,
            query_text=payload.text,
            district=payload.district,
            crop=payload.crop,
            response_ur="".join(collected_ur),
            response_en="".join(collected_en),
        )
        db.add(log)
        # Update session's updated_at
        session.updated_at = datetime.utcnow()
        db.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── GET /sessions ────────────────────────────────────────────────────────────

@router.get("/sessions")
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all chat sessions for the current user, newest first."""
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in sessions
    ]


# ─── GET /sessions/{session_id}/messages ─────────────────────────────────────

@router.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch all messages (query + response) for a given session."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    logs = (
        db.query(QueryLog)
        .filter(QueryLog.session_id == session_id)
        .order_by(QueryLog.created_at.asc())
        .all()
    )
    return {
        "session": {"id": session.id, "title": session.title},
        "messages": [
            {
                "id": log.id,
                "query_text": log.query_text,
                "district": log.district,
                "crop": log.crop,
                "response_ur": log.response_ur,
                "response_en": log.response_en,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }


# ─── DELETE /sessions/all ─────────────────────────────────────────────────────

@router.delete("/sessions/all")
def delete_all_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete all chat sessions and messages for the current user."""
    # Delete logs first (FK constraint)
    session_ids = [
        s.id for s in db.query(ChatSession.id)
        .filter(ChatSession.user_id == current_user.id)
        .all()
    ]
    if session_ids:
        db.query(QueryLog).filter(QueryLog.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(ChatSession).filter(ChatSession.user_id == current_user.id).delete(synchronize_session=False)
    db.commit()
    return {"deleted": True}


# ─── DELETE /sessions/{session_id} ───────────────────────────────────────────

@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a single chat session and its messages."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    db.query(QueryLog).filter(QueryLog.session_id == session_id).delete(synchronize_session=False)
    db.delete(session)
    db.commit()
    return {"deleted": True}


# ─── GET /history (legacy, kept for compatibility) ───────────────────────────

@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Legacy: returns all logs flat. Use /sessions instead."""
    logs = (
        db.query(QueryLog)
        .filter(QueryLog.user_id == current_user.id)
        .order_by(QueryLog.created_at.asc())
        .all()
    )
    return [
        {
            "id": log.id,
            "session_id": log.session_id,
            "query_text": log.query_text,
            "response_ur": log.response_ur,
            "response_en": log.response_en,
            "created_at": log.created_at,
        }
        for log in logs
    ]
