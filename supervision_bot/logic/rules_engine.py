import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config
from vision.feature_aggregator import FeatureVector, CalibrationProfile


class EventType(Enum):
    PHONE_DETECTED     = "phone_detected"
    OUT_OF_SEAT        = "out_of_seat"
    UNKNOWN_PERSON     = "unknown_person"
    SPOOF_SUSPECTED    = "spoof_suspected"
    TALKING            = "talking"
    DISTRACTED_GAZE    = "distracted_gaze"
    WRITING_IDLE       = "writing_idle"
    FATIGUE_DROWSY     = "fatigue_drowsy"
    BAD_POSTURE_CLOSE  = "bad_posture_close"
    BAD_POSTURE_SLOUCH = "bad_posture_slouch"
    BREAK_STUDYING     = "break_studying"
    BREAK_SEDENTARY    = "break_sedentary"
    GOOD_FOCUS         = "good_focus"


class Priority(Enum):
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3


@dataclass
class Event:
    event_type: EventType
    priority: Priority
    message_intent: str
    context: dict
    timestamp: datetime


class RulesEngine:
    def __init__(self):
        self._session_events: list[Event] = []
        self._last_fired: dict[EventType, float] = {}

        # Duration trackers
        self._phone_since:        float | None = None
        self._no_seat_since:      float | None = None
        self._identity_bad_since: float | None = None
        self._spoof_since:        float | None = None
        self._talking_since:      float | None = None
        self._gaze_off_since:     float | None = None
        self._writing_idle_since: float | None = None
        self._ear_low_since:      float | None = None
        self._good_focus_since:   float | None = None
        self._good_focus_minutes: int          = 0

        # Calibration-derived values (set via set_calibration; defaults from config)
        self._neutral_yaw: float = 0.0
        self._yaw_range:   float = float(config.YAW_DISTRACTED_DEG)

    def set_calibration(self, profile: CalibrationProfile) -> None:
        self._neutral_yaw = profile.neutral_yaw
        self._yaw_range   = profile.yaw_distract_range
        print(f"[Rules] Calibration: neutral_yaw={profile.neutral_yaw:.1f}°, "
              f"yaw_range=±{profile.yaw_distract_range:.1f}°", flush=True)

    def evaluate(self, fv: FeatureVector, pomodoro_state: str) -> list[Event]:
        events: list[Event] = []
        total = len(self._session_events)

        if pomodoro_state == "FOCUS":
            checks = [
                self._check_phone(fv),
                self._check_identity(fv),
                self._check_spoof(fv),
                self._check_talking(fv),
                self._check_out_of_seat(fv),
                self._check_distraction(fv),
                self._check_writing_idle(fv),
                self._check_fatigue(fv),
                self._check_posture(fv),
                self._check_good_focus(fv),
            ]
        elif pomodoro_state == "BREAK":
            checks = self._check_break_rules(fv)
        elif pomodoro_state in ("PREPARE", "RESUME_CHECK"):
            checks = [self._check_phone(fv)]
        else:
            checks = []

        for ev in checks:
            if ev is None:
                continue
            if not self._cooldown_ok(ev.event_type):
                continue
            if total >= config.MAX_ALERTS_PER_SESSION and ev.priority != Priority.HIGH:
                continue
            self._last_fired[ev.event_type] = time.monotonic()
            self._session_events.append(ev)
            events.append(ev)
            total += 1

        return events

    def reset_session(self) -> None:
        self._session_events.clear()
        self._last_fired.clear()
        self._phone_since        = None
        self._no_seat_since      = None
        self._identity_bad_since = None
        self._spoof_since        = None
        self._talking_since      = None
        self._gaze_off_since     = None
        self._writing_idle_since = None
        self._ear_low_since      = None
        self._good_focus_since   = None
        self._good_focus_minutes = 0

    def get_session_events(self) -> list[Event]:
        return list(self._session_events)

    # ── Rule methods ─────────────────────────────────────────────────────────

    def _check_phone(self, fv: FeatureVector) -> Event | None:
        now = time.monotonic()
        if fv.phone_detected:
            if self._phone_since is None:
                self._phone_since = now
            dur = now - self._phone_since
            if dur >= config.PHONE_ALERT_SECONDS:
                return Event(
                    event_type=EventType.PHONE_DETECTED,
                    priority=Priority.HIGH,
                    message_intent="phone_detected_high",
                    context={"duration_seconds": int(dur)},
                    timestamp=datetime.utcnow(),
                )
        else:
            self._phone_since = None
        return None

    def _check_out_of_seat(self, fv: FeatureVector) -> Event | None:
        now = time.monotonic()
        # Grace: if actively working, child may lean forward losing shoulder visibility
        if config.SEAT_WRITING_GRACE and fv.work_confidence >= config.WORK_CONFIDENCE_THRESHOLD:
            self._no_seat_since = None
            return None
        absent = not fv.face_present and not fv.seat_present
        if absent:
            if self._no_seat_since is None:
                self._no_seat_since = now
            dur = now - self._no_seat_since
            if dur >= config.OUT_OF_SEAT_SECONDS:
                return Event(
                    event_type=EventType.OUT_OF_SEAT,
                    priority=Priority.HIGH,
                    message_intent="out_of_seat_high",
                    context={"duration_seconds": int(dur)},
                    timestamp=datetime.utcnow(),
                )
        else:
            self._no_seat_since = None
        return None

    def _check_identity(self, fv: FeatureVector) -> Event | None:
        """Alert if the face on camera is NOT the child who started the session."""
        now = time.monotonic()
        if not config.IDENTITY_VERIFY and not fv.stranger_present:
            self._identity_bad_since = None
            return None

        # ArcFace path: stranger_present fires faster (3s)
        triggered = fv.stranger_present or (
            fv.identity_known and fv.face_present
            and fv.identity_distance > 0.0 and fv.face_mismatch
        )
        if triggered:
            if self._identity_bad_since is None:
                self._identity_bad_since = now
            dur = now - self._identity_bad_since
            # ArcFace uses faster threshold; geometric uses IDENTITY_ALERT_SECONDS
            threshold = config.FACE_STRANGER_ALERT_SEC if fv.stranger_present \
                        else config.IDENTITY_ALERT_SECONDS
            if dur >= threshold:
                return Event(
                    event_type=EventType.UNKNOWN_PERSON,
                    priority=Priority.HIGH,
                    message_intent="unknown_person_high",
                    context={"distance": round(fv.identity_distance, 3),
                             "person_count": fv.person_count},
                    timestamp=datetime.utcnow(),
                )
        else:
            self._identity_bad_since = None
        return None

    def _check_spoof(self, fv: FeatureVector) -> Event | None:
        """Anti-spoof: a face that never moves/blinks is likely a photo held to camera."""
        now = time.monotonic()
        if not config.LIVENESS_CHECK or not fv.face_present:
            self._spoof_since = None
            return None
        if fv.face_static:
            if self._spoof_since is None:
                self._spoof_since = now
            if now - self._spoof_since >= config.SPOOF_ALERT_SECONDS:
                return Event(
                    event_type=EventType.SPOOF_SUSPECTED,
                    priority=Priority.HIGH,
                    message_intent="spoof_suspected_high",
                    context={},
                    timestamp=datetime.utcnow(),
                )
        else:
            self._spoof_since = None
        return None

    def _check_talking(self, fv: FeatureVector) -> Event | None:
        """Optional: alert if the child is talking (mouth moving) instead of studying."""
        now = time.monotonic()
        if not config.TALKING_ALERT:
            return None
        # Talking while writing is fine (reading aloud) — only flag when NOT working
        if fv.is_talking and fv.work_confidence < config.WORK_CONFIDENCE_THRESHOLD:
            if self._talking_since is None:
                self._talking_since = now
            if now - self._talking_since >= config.TALKING_ALERT_SEC:
                return Event(
                    event_type=EventType.TALKING,
                    priority=Priority.MEDIUM,
                    message_intent="talking_medium",
                    context={},
                    timestamp=datetime.utcnow(),
                )
        else:
            self._talking_since = None
        return None

    def _check_distraction(self, fv: FeatureVector) -> Event | None:
        now = time.monotonic()

        # Skip if low-confidence face detection (avoids noisy landmark artifacts)
        if fv.face_confidence < config.MIN_FACE_CONF_FOR_ALERTS:
            self._gaze_off_since = None
            return None

        # Skip if actively working — looking down at paper is expected behavior
        if fv.work_confidence >= config.WORK_CONFIDENCE_THRESHOLD:
            self._gaze_off_since = None
            return None

        # Combined check: BOTH head yaw AND iris gaze must exceed thresholds
        yaw_off  = abs(fv.head_yaw - self._neutral_yaw) > self._yaw_range
        gaze_off = abs(fv.gaze_x) > config.GAZE_X_DISTRACTED
        distracted = yaw_off and gaze_off

        if distracted:
            if self._gaze_off_since is None:
                self._gaze_off_since = now
            dur = now - self._gaze_off_since
            if dur >= config.GAZE_DISTRACTED_SEC:
                return Event(
                    event_type=EventType.DISTRACTED_GAZE,
                    priority=Priority.MEDIUM,
                    message_intent="distracted_gaze_medium",
                    context={"duration_seconds": int(dur)},
                    timestamp=datetime.utcnow(),
                )
        else:
            self._gaze_off_since = None
        return None

    def _check_writing_idle(self, fv: FeatureVector) -> Event | None:
        now = time.monotonic()
        idle = fv.work_confidence < config.WORK_CONFIDENCE_THRESHOLD
        if idle:
            if self._writing_idle_since is None:
                self._writing_idle_since = now
            dur = now - self._writing_idle_since
            if dur >= config.FLOW_IDLE_SECONDS:
                return Event(
                    event_type=EventType.WRITING_IDLE,
                    priority=Priority.MEDIUM,
                    message_intent="writing_idle_medium",
                    context={"duration_seconds": int(dur)},
                    timestamp=datetime.utcnow(),
                )
        else:
            self._writing_idle_since = None
        return None

    def _check_fatigue(self, fv: FeatureVector) -> Event | None:
        now = time.monotonic()

        # Skip if low-confidence face (noisy EAR readings)
        if fv.face_confidence < config.MIN_FACE_CONF_FOR_ALERTS:
            self._ear_low_since = None
            return None

        # Skip if actively working — EAR drops naturally when looking down at paper
        if fv.work_confidence >= config.WORK_CONFIDENCE_THRESHOLD:
            self._ear_low_since = None
            return None

        # PERCLOS-based fatigue (more accurate than raw EAR duration)
        if fv.is_fatigued:
            if self._ear_low_since is None:
                self._ear_low_since = now
            dur = now - self._ear_low_since
            # Require 10s of sustained PERCLOS-fatigued state before alerting
            if dur >= config.EAR_FATIGUE_SECONDS:
                return Event(
                    event_type=EventType.FATIGUE_DROWSY,
                    priority=Priority.MEDIUM,
                    message_intent="fatigue_drowsy_medium",
                    context={"duration_seconds": int(dur), "perclos": round(fv.perclos, 2)},
                    timestamp=datetime.utcnow(),
                )
        else:
            self._ear_low_since = None
        return None

    def _check_posture(self, fv: FeatureVector) -> Event | None:
        if fv.face_confidence < config.MIN_FACE_CONF_FOR_ALERTS:
            return None
        if fv.distance_estimate < 25.0 and fv.face_present:
            return Event(
                event_type=EventType.BAD_POSTURE_CLOSE,
                priority=Priority.LOW,
                message_intent="bad_posture_close_low",
                context={},
                timestamp=datetime.utcnow(),
            )
        if fv.slouch_score > 0.7 and fv.seat_present:
            return Event(
                event_type=EventType.BAD_POSTURE_SLOUCH,
                priority=Priority.LOW,
                message_intent="bad_posture_slouch_low",
                context={},
                timestamp=datetime.utcnow(),
            )
        return None

    def _check_good_focus(self, fv: FeatureVector) -> Event | None:
        now = time.monotonic()
        focused = fv.face_present and not fv.is_distracted and not fv.phone_detected
        if focused:
            if self._good_focus_since is None:
                self._good_focus_since = now
            minutes = int((now - self._good_focus_since) / 60)
            if minutes > self._good_focus_minutes and minutes >= 5:
                self._good_focus_minutes = minutes
                return Event(
                    event_type=EventType.GOOD_FOCUS,
                    priority=Priority.MEDIUM,
                    message_intent="good_focus_positive",
                    context={"minutes": minutes},
                    timestamp=datetime.utcnow(),
                )
        else:
            self._good_focus_since   = None
            self._good_focus_minutes = 0
        return None

    def _check_break_rules(self, fv: FeatureVector) -> list[Event]:
        events = []
        if fv.writing_score > 20.0 and fv.face_present:
            ev = Event(
                event_type=EventType.BREAK_STUDYING,
                priority=Priority.MEDIUM,
                message_intent="break_studying",
                context={},
                timestamp=datetime.utcnow(),
            )
            if self._cooldown_ok(EventType.BREAK_STUDYING):
                events.append(ev)
        if not fv.seat_present and not fv.face_present:
            ev = Event(
                event_type=EventType.BREAK_SEDENTARY,
                priority=Priority.LOW,
                message_intent="break_sedentary",
                context={},
                timestamp=datetime.utcnow(),
            )
            if self._cooldown_ok(EventType.BREAK_SEDENTARY):
                events.append(ev)
        return events

    def _cooldown_ok(self, event_type: EventType) -> bool:
        last = self._last_fired.get(event_type)
        if last is None:
            return True
        return (time.monotonic() - last) >= config.ALERT_COOLDOWN_SEC
