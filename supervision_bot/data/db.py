import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.future import select
import config


class Base(DeclarativeBase):
    pass


class Child(Base):
    __tablename__ = "children"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String, nullable=False)
    age        = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class Session(Base):
    __tablename__ = "sessions"
    id                  = Column(Integer, primary_key=True)
    child_id            = Column(Integer, ForeignKey("children.id"))
    started_at          = Column(DateTime, default=datetime.utcnow)
    ended_at            = Column(DateTime, nullable=True)
    rounds_completed    = Column(Integer, default=0)
    total_focus_seconds = Column(Integer, default=0)
    focus_score_avg     = Column(Float, nullable=True)


class Event(Base):
    __tablename__ = "events"
    id               = Column(Integer, primary_key=True)
    session_id       = Column(Integer, ForeignKey("sessions.id"))
    event_type       = Column(String)
    priority         = Column(String)
    timestamp        = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Integer, nullable=True)


class FocusSnapshot(Base):
    __tablename__ = "focus_snapshots"
    id             = Column(Integer, primary_key=True)
    session_id     = Column(Integer, ForeignKey("sessions.id"))
    minute_mark    = Column(Integer)
    writing_score  = Column(Float)
    face_present   = Column(Boolean)
    phone_detected = Column(Boolean)


class Database:
    def __init__(self, url: str = config.DATABASE_URL):
        self._engine = create_async_engine(url, echo=False)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create_child(self, name: str, age: int) -> int:
        async with self._session_factory() as s:
            child = Child(name=name, age=age)
            s.add(child)
            await s.commit()
            await s.refresh(child)
            return child.id

    async def start_session(self, child_id: int) -> int:
        async with self._session_factory() as s:
            session = Session(child_id=child_id, started_at=datetime.utcnow())
            s.add(session)
            await s.commit()
            await s.refresh(session)
            return session.id

    async def end_session(self, session_id: int, summary: dict) -> None:
        async with self._session_factory() as s:
            result = await s.execute(select(Session).where(Session.id == session_id))
            session = result.scalar_one_or_none()
            if session:
                session.ended_at          = datetime.utcnow()
                session.rounds_completed  = summary.get("rounds_completed", 0)
                session.total_focus_seconds = summary.get("total_focus_seconds", 0)
                session.focus_score_avg   = summary.get("focus_score_avg")
                await s.commit()

    async def log_event(self, session_id: int, event) -> None:
        async with self._session_factory() as s:
            duration = event.context.get("duration_seconds") if hasattr(event, "context") else None
            row = Event(
                session_id=session_id,
                event_type=event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                priority=event.priority.value if hasattr(event.priority, "value") else str(event.priority),
                timestamp=event.timestamp,
                duration_seconds=duration,
            )
            s.add(row)
            await s.commit()

    async def log_snapshot(self, session_id: int, minute: int, fv) -> None:
        async with self._session_factory() as s:
            snap = FocusSnapshot(
                session_id=session_id,
                minute_mark=minute,
                writing_score=fv.writing_score,
                face_present=fv.face_present,
                phone_detected=fv.phone_detected,
            )
            s.add(snap)
            await s.commit()

    async def get_session(self, session_id: int) -> dict:
        async with self._session_factory() as s:
            result = await s.execute(select(Session).where(Session.id == session_id))
            row = result.scalar_one_or_none()
            if not row:
                return {}
            return {
                "id": row.id, "child_id": row.child_id,
                "started_at": row.started_at, "ended_at": row.ended_at,
                "rounds_completed": row.rounds_completed,
                "total_focus_seconds": row.total_focus_seconds,
                "focus_score_avg": row.focus_score_avg,
            }

    async def get_events(self, session_id: int) -> list[dict]:
        async with self._session_factory() as s:
            result = await s.execute(
                select(Event).where(Event.session_id == session_id).order_by(Event.timestamp)
            )
            return [
                {"id": r.id, "event_type": r.event_type, "priority": r.priority,
                 "timestamp": r.timestamp, "duration_seconds": r.duration_seconds}
                for r in result.scalars().all()
            ]

    async def get_history(self, child_id: int, days: int = 7) -> list[dict]:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        async with self._session_factory() as s:
            result = await s.execute(
                select(Session).where(
                    Session.child_id == child_id,
                    Session.started_at >= cutoff
                ).order_by(Session.started_at)
            )
            return [
                {"id": r.id, "started_at": r.started_at, "ended_at": r.ended_at,
                 "rounds_completed": r.rounds_completed,
                 "total_focus_seconds": r.total_focus_seconds,
                 "focus_score_avg": r.focus_score_avg}
                for r in result.scalars().all()
            ]

    async def get_current_session(self, child_id: int) -> dict | None:
        async with self._session_factory() as s:
            result = await s.execute(
                select(Session).where(
                    Session.child_id == child_id,
                    Session.ended_at.is_(None)
                ).order_by(Session.started_at.desc())
            )
            row = result.scalars().first()
            if not row:
                return None
            return {
                "id": row.id, "child_id": row.child_id,
                "started_at": row.started_at, "ended_at": row.ended_at,
                "rounds_completed": row.rounds_completed,
                "total_focus_seconds": row.total_focus_seconds,
            }

    async def get_children(self) -> list[dict]:
        async with self._session_factory() as s:
            result = await s.execute(select(Child))
            return [{"id": r.id, "name": r.name, "age": r.age} for r in result.scalars().all()]

    async def get_snapshots(self, session_id: int) -> list[dict]:
        async with self._session_factory() as s:
            result = await s.execute(
                select(FocusSnapshot)
                .where(FocusSnapshot.session_id == session_id)
                .order_by(FocusSnapshot.minute_mark)
            )
            return [
                {"minute_mark": r.minute_mark, "writing_score": r.writing_score,
                 "face_present": r.face_present, "phone_detected": r.phone_detected}
                for r in result.scalars().all()
            ]
