from __future__ import annotations
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sse_starlette.sse import EventSourceResponse
import config
from api.schemas import (
    SessionStatus, EventOut, SnapshotOut, SessionOut,
    SessionSummary, ChildOut, ChildCreate, SessionStartRequest,
    ChatRequest, ChatResponse,
)

app = FastAPI(title="AI Homework Supervision Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve dashboard static files
_DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), '..', 'dashboard')
if os.path.isdir(_DASHBOARD_DIR):
    app.mount("/dashboard", StaticFiles(directory=_DASHBOARD_DIR, html=True), name="dashboard")

# Injected by main.py
_session_manager = None


def set_session_manager(sm) -> None:
    global _session_manager
    _session_manager = sm


def _get_sm():
    if _session_manager is None:
        raise HTTPException(status_code=503, detail="Session manager not initialized")
    return _session_manager


# ── Session endpoints ────────────────────────────────────────────────────────

@app.post("/session/language")
async def set_language(body: dict):
    sm = _get_sm()
    lang = body.get("lang", "en")
    sm.set_language(lang)
    return {"lang": lang, "voice": config.TTS_VOICE}


@app.get("/session/current", response_model=SessionStatus)
async def get_current_session():
    sm = _get_sm()
    fv = sm.aggregator.get_latest()
    last_events = sm.rules.get_session_events()
    last_event  = last_events[-1].event_type.value if last_events else None
    return SessionStatus(
        session_id=sm._session_id,
        pomodoro_state=sm.pomodoro.current_state,
        elapsed_seconds=sm.pomodoro.elapsed_seconds,
        round_number=sm.pomodoro.round_number,
        child_name=sm._child_name,
        is_focused=(fv is not None and not fv.is_distracted and fv.face_present),
        last_event=last_event,
        focus_score_current=sm._compute_focus_score() if fv else 0.0,
        person_count=fv.person_count if fv else 0,
        stranger_present=fv.stranger_present if fv else False,
    )


@app.post("/session/start")
async def start_session(req: SessionStartRequest):
    sm = _get_sm()
    child_id = await sm.db.create_child(req.child_name, req.child_age)
    sm._child_id = child_id
    session_id = await sm.db.start_session(child_id)
    sm._session_id = session_id
    sm.start_session(req.child_name)
    return {"session_id": session_id, "child_name": req.child_name}


@app.post("/session/stop", response_model=SessionSummary)
async def stop_session():
    sm = _get_sm()
    if sm._session_id is None:
        raise HTTPException(status_code=400, detail="No active session")
    session_id = sm._session_id
    summary = sm.end_session()
    await sm.db.end_session(session_id, summary)
    event_counts = summary.get("event_counts", {})
    ai_summary = _generate_summary(summary)
    return SessionSummary(
        session_id=session_id,
        total_focus_seconds=summary.get("total_focus_seconds", 0),
        rounds_completed=summary.get("rounds_completed", 0),
        focus_score_avg=summary.get("focus_score_avg", 0.0),
        event_counts=event_counts,
        ai_summary=ai_summary,
    )


@app.get("/session/{session_id}/events", response_model=list[EventOut])
async def get_events(session_id: int):
    sm = _get_sm()
    rows = await sm.db.get_events(session_id)
    return [EventOut(**r) for r in rows]


@app.get("/session/{session_id}/snapshots", response_model=list[SnapshotOut])
async def get_snapshots(session_id: int):
    sm = _get_sm()
    rows = await sm.db.get_snapshots(session_id)
    return [SnapshotOut(**r) for r in rows]


@app.get("/history/{child_id}", response_model=list[SessionOut])
async def get_history(child_id: int, days: int = 7):
    sm = _get_sm()
    rows = await sm.db.get_history(child_id, days)
    return [SessionOut(**r) for r in rows]


@app.get("/children", response_model=list[ChildOut])
async def list_children():
    sm = _get_sm()
    rows = await sm.db.get_children()
    return [ChildOut(**r) for r in rows]


@app.post("/children", response_model=ChildOut)
async def create_child(body: ChildCreate):
    sm = _get_sm()
    child_id = await sm.db.create_child(body.name, body.age)
    return ChildOut(id=child_id, name=body.name, age=body.age)


# ── SSE live feature stream ───────────────────────────────────────────────────

@app.get("/stream/features")
async def stream_features(request: Request):
    sm = _get_sm()

    async def generator():
        while True:
            if await request.is_disconnected():
                break
            fv = sm.aggregator.get_latest()
            if fv is not None:
                data = {
                    "timestamp":       fv.timestamp.isoformat(),
                    "face_present":    fv.face_present,
                    "phone_detected":  fv.phone_detected,
                    "is_distracted":   fv.is_distracted,
                    "is_fatigued":     fv.is_fatigued,
                    "writing_score":   round(fv.writing_score, 2),
                    "work_confidence": round(fv.work_confidence, 1),
                    "hand_writing":    fv.hand_writing,
                    "identity_known":  fv.identity_known,
                    "face_mismatch":   fv.face_mismatch,
                    "identity_distance": round(fv.identity_distance, 3),
                    "is_live":         fv.is_live,
                    "is_talking":      fv.is_talking,
                    "ear_avg":         round(fv.ear_avg, 3),
                    "perclos":         round(fv.perclos, 3),
                    "pomodoro_state":  sm.pomodoro.current_state,
                    "elapsed_seconds": sm.pomodoro.elapsed_seconds,
                    "round_number":    sm.pomodoro.round_number,
                }
                import json
                yield {"data": json.dumps(data)}
            await asyncio.sleep(1)

    return EventSourceResponse(generator())


# ── LLM Coach chat ───────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat_with_coach(req: ChatRequest):
    """Student sends a message — LLM replies and speaks via TTS."""
    sm = _get_sm()
    fv = sm.aggregator.get_latest()
    reply = await sm.llm_coach.chat(
        user_message=req.message,
        fv=fv,
        pomodoro_state=sm.pomodoro.current_state,
        elapsed_sec=sm.pomodoro.elapsed_seconds,
    )
    # Speak the reply through TTS
    sm._tts_queue.put_nowait(reply)
    return ChatResponse(reply=reply, spoken=True)


@app.post("/coach/greet")
async def coach_greet():
    """Student presses 'Start studying' — LLM gives a personalised opening greeting."""
    sm = _get_sm()
    fv = sm.aggregator.get_latest()
    greeting = await sm.llm_coach.alert(
        event_type="session_start",
        fv=fv,
        pomodoro_state=sm.pomodoro.current_state,
        elapsed_sec=sm.pomodoro.elapsed_seconds,
    )
    if greeting is None:
        greeting = sm.scripts.get("session_start",
                                  focus_min=config.FOCUS_DURATION // 60)
    sm._tts_queue.put_nowait(greeting)
    return {"greeting": greeting}


# ── Camera frame ─────────────────────────────────────────────────────────────

@app.get("/camera/frame")
async def camera_frame():
    """Returns the latest camera frame as a JPEG image."""
    sm = _get_sm()
    try:
        import cv2
        # Prefer the annotated frame (face boxes + labels) over the raw frame
        frame = getattr(sm, 'latest_annotated_frame', None)
        if frame is None:
            frame = sm.capture.get_frame() if sm.capture else None
        if frame is None:
            raise HTTPException(status_code=204, detail="No frame available")
        # Resize to 480×270 for fast delivery (~15–20 KB per frame)
        small = cv2.resize(frame, (480, 270), interpolation=cv2.INTER_LINEAR)
        _, buf = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 45])
        return Response(content=buf.tobytes(), media_type='image/jpeg',
                        headers={"Cache-Control": "no-store"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── TTS status ───────────────────────────────────────────────────────────────

@app.get("/tts/status")
async def tts_status():
    """Returns whether the TTS engine is currently speaking. Used by voice mode."""
    sm = _get_sm()
    return {"speaking": sm.tts.is_speaking()}


@app.get("/tts/latest")
async def tts_latest():
    """Serves the most recently generated TTS audio file."""
    sm = _get_sm()
    path = getattr(sm.tts, 'latest_path', None)
    if path is None or not Path(str(path)).exists():
        raise HTTPException(status_code=404, detail="No audio available")
    return FileResponse(str(path), media_type='audio/mpeg',
                        headers={"Cache-Control": "no-store"})


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    sm = _get_sm()
    cam_running = sm.capture.is_running() if sm.capture else False
    cam_error = getattr(sm.capture, '_camera_error', None) if sm.capture else None
    session_active = sm._session_id is not None
    return {
        "status": "ok",
        "api_version": "1.0",
        "camera_running": cam_running,
        "camera_error": cam_error,
        "session_active": session_active,
        "pomodoro_state": sm.pomodoro.current_state,
        "cv_loop_running": sm._running,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _generate_summary(summary: dict) -> str:
    rounds = summary.get("rounds_completed", 0)
    minutes = summary.get("total_focus_seconds", 0) // 60
    counts = summary.get("event_counts", {})
    phone  = counts.get("phone_detected", 0)
    distracted = counts.get("distracted_gaze", 0)
    parts = [f"Completed {rounds} Pomodoro round(s) with {minutes} total focus minutes."]
    if phone:
        parts.append(f"⚠️ Phone detected {phone} time(s) — try to keep it away next time!")
    if distracted:
        parts.append(f"Distraction alerts: {distracted}.")
    focus_score = summary.get("focus_score_avg", 0.0)
    if phone == 0 and distracted == 0 and focus_score >= 80:
        parts.append("Excellent focus session! 🌟")
    elif focus_score >= 60:
        parts.append("Good effort — keep improving!")
    else:
        parts.append("Room to improve — try to put your phone away and stay focused.")
    return " ".join(parts)
