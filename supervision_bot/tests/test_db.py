import sys, os, asyncio, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pytest_asyncio


@pytest.fixture
def tmp_db_url(tmp_path):
    db_file = tmp_path / "test.db"
    return f"sqlite+aiosqlite:///{db_file}"


@pytest.mark.asyncio
async def test_init_creates_all_tables(tmp_db_url):
    from data.db import Database
    db = Database(url=tmp_db_url)
    await db.init()
    # Check tables exist by running queries
    async with db._session_factory() as s:
        from sqlalchemy import text
        result = await s.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {row[0] for row in result.fetchall()}
    assert "children"       in tables
    assert "sessions"       in tables
    assert "events"         in tables
    assert "focus_snapshots" in tables


@pytest.mark.asyncio
async def test_start_session_returns_integer(tmp_db_url):
    from data.db import Database
    db = Database(url=tmp_db_url)
    await db.init()
    child_id   = await db.create_child("TestChild", 10)
    session_id = await db.start_session(child_id)
    assert isinstance(session_id, int)
    assert session_id > 0


@pytest.mark.asyncio
async def test_log_event_retrievable(tmp_db_url):
    from data.db import Database
    from logic.rules_engine import EventType, Priority, Event
    from datetime import datetime
    db = Database(url=tmp_db_url)
    await db.init()
    child_id   = await db.create_child("TestChild", 10)
    session_id = await db.start_session(child_id)

    ev = Event(
        event_type=EventType.PHONE_DETECTED,
        priority=Priority.HIGH,
        message_intent="phone_detected_high",
        context={"duration_seconds": 7},
        timestamp=datetime.utcnow(),
    )
    await db.log_event(session_id, ev)

    rows = await db.get_events(session_id)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "phone_detected"
    assert rows[0]["priority"]   == "3"


@pytest.mark.asyncio
async def test_end_session_sets_ended_at(tmp_db_url):
    from data.db import Database
    db = Database(url=tmp_db_url)
    await db.init()
    child_id   = await db.create_child("TestChild", 10)
    session_id = await db.start_session(child_id)
    await db.end_session(session_id, {"rounds_completed": 2, "total_focus_seconds": 3000, "focus_score_avg": 80.0})
    row = await db.get_session(session_id)
    assert row["ended_at"] is not None
    assert row["rounds_completed"] == 2


@pytest.mark.asyncio
async def test_create_child_returns_id(tmp_db_url):
    from data.db import Database
    db = Database(url=tmp_db_url)
    await db.init()
    child_id = await db.create_child("Alice", 9)
    assert isinstance(child_id, int)
    assert child_id > 0
