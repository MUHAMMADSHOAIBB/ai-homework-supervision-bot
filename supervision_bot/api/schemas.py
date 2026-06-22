from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class SessionStatus(BaseModel):
    session_id: int | None
    pomodoro_state: str
    elapsed_seconds: int
    round_number: int
    child_name: str
    is_focused: bool
    last_event: str | None
    focus_score_current: float


class EventOut(BaseModel):
    event_type: str
    priority: str
    timestamp: datetime
    duration_seconds: int | None


class SnapshotOut(BaseModel):
    minute_mark: int
    writing_score: float
    face_present: bool
    phone_detected: bool


class SessionOut(BaseModel):
    id: int
    started_at: datetime
    ended_at: datetime | None
    rounds_completed: int
    total_focus_seconds: int
    focus_score_avg: float | None


class SessionSummary(BaseModel):
    session_id: int
    total_focus_seconds: int
    rounds_completed: int
    focus_score_avg: float
    event_counts: dict[str, int]
    ai_summary: str


class ChildOut(BaseModel):
    id: int
    name: str
    age: int


class ChildCreate(BaseModel):
    name: str
    age: int


class SessionStartRequest(BaseModel):
    child_name: str = "小明"
    child_age: int  = 10


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    spoken: bool   # True if also sent to TTS
