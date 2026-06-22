import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import config
from logic.rules_engine import RulesEngine, EventType, Priority
from vision.feature_aggregator import FeatureVector
from datetime import datetime


def _fv(**kwargs):
    defaults = dict(
        timestamp=datetime.utcnow(), face_present=True, face_confidence=0.9,
        head_pitch=0.0, head_yaw=0.0, ear_avg=0.3, gaze_x=0.0,
        seat_present=True, slouch_score=0.0, distance_estimate=50.0,
        phone_detected=False, phone_confidence=0.0,
        writing_score=50.0, is_distracted=False, is_fatigued=False,
    )
    defaults.update(kwargs)
    return FeatureVector(**defaults)


def test_phone_fires_after_threshold(monkeypatch):
    """Phone detected for PHONE_ALERT_SECONDS → HIGH event fires."""
    engine = RulesEngine()
    # Simulate phone present for longer than threshold
    monkeypatch.setattr(config, 'PHONE_ALERT_SECONDS', 0)  # fire immediately
    fv = _fv(phone_detected=True, phone_confidence=0.9)
    events = engine.evaluate(fv, "FOCUS")
    phone_events = [e for e in events if e.event_type == EventType.PHONE_DETECTED]
    assert phone_events, "Expected PHONE_DETECTED event"
    assert phone_events[0].priority == Priority.HIGH


def test_phone_does_not_fire_before_threshold():
    """Phone detected for < PHONE_ALERT_SECONDS → no event."""
    engine = RulesEngine()
    # With default PHONE_ALERT_SECONDS=5, a single evaluation at t=0 should not fire
    fv = _fv(phone_detected=True)
    events = engine.evaluate(fv, "FOCUS")
    phone_events = [e for e in events if e.event_type == EventType.PHONE_DETECTED]
    assert not phone_events, "Should not fire before threshold"


def test_cooldown_blocks_repeat(monkeypatch):
    """Same event type cannot fire again within ALERT_COOLDOWN_SEC."""
    engine = RulesEngine()
    monkeypatch.setattr(config, 'PHONE_ALERT_SECONDS', 0)
    monkeypatch.setattr(config, 'ALERT_COOLDOWN_SEC', 9999)
    fv = _fv(phone_detected=True, phone_confidence=0.9)
    first = engine.evaluate(fv, "FOCUS")
    assert any(e.event_type == EventType.PHONE_DETECTED for e in first)
    second = engine.evaluate(fv, "FOCUS")
    assert not any(e.event_type == EventType.PHONE_DETECTED for e in second), \
        "Cooldown should block second fire"


def test_max_alerts_cap_blocks_medium(monkeypatch):
    """When session alert count >= MAX_ALERTS_PER_SESSION, only HIGH priority passes."""
    engine = RulesEngine()
    monkeypatch.setattr(config, 'MAX_ALERTS_PER_SESSION', 0)
    monkeypatch.setattr(config, 'ALERT_COOLDOWN_SEC', 0)
    monkeypatch.setattr(config, 'GAZE_DISTRACTED_SEC', 0)
    fv = _fv(head_yaw=40.0)  # triggers DISTRACTED_GAZE (MEDIUM)
    events = engine.evaluate(fv, "FOCUS")
    medium_events = [e for e in events if e.priority == Priority.MEDIUM]
    assert not medium_events, "MEDIUM events should be blocked when cap reached"


def test_out_of_seat_fires_after_threshold(monkeypatch):
    """No face + no seat for OUT_OF_SEAT_SECONDS → HIGH event."""
    engine = RulesEngine()
    monkeypatch.setattr(config, 'OUT_OF_SEAT_SECONDS', 0)
    fv = _fv(face_present=False, seat_present=False)
    events = engine.evaluate(fv, "FOCUS")
    seat_events = [e for e in events if e.event_type == EventType.OUT_OF_SEAT]
    assert seat_events, "Expected OUT_OF_SEAT event"
    assert seat_events[0].priority == Priority.HIGH


def test_distraction_fires_after_yaw_threshold(monkeypatch):
    """Head yaw > YAW_DISTRACTED_DEG for GAZE_DISTRACTED_SEC → MEDIUM event."""
    engine = RulesEngine()
    monkeypatch.setattr(config, 'GAZE_DISTRACTED_SEC', 0)
    fv = _fv(head_yaw=40.0)
    events = engine.evaluate(fv, "FOCUS")
    dist_events = [e for e in events if e.event_type == EventType.DISTRACTED_GAZE]
    assert dist_events


def test_reset_session_clears_counts():
    engine = RulesEngine()
    engine._session_events.append(object())  # fake event
    engine.reset_session()
    assert len(engine.get_session_events()) == 0


def test_no_events_in_idle_state():
    """Rules engine returns nothing when pomodoro state is IDLE."""
    engine = RulesEngine()
    fv = _fv(phone_detected=True)
    events = engine.evaluate(fv, "IDLE")
    assert events == []
