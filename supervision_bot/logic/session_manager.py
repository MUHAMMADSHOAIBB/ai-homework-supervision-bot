import asyncio
import time
from datetime import datetime
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import config
from vision.capture import CameraCapture
from vision.mediapipe_module import MediaPipeModule
from vision.yolo_module import YoloModule
from vision.optical_flow import OpticalFlowModule
from vision.feature_aggregator import FeatureAggregator, FeatureVector, CalibrationProfile
from logic.state_machine import PomodoroMachine
from logic.rules_engine import RulesEngine, Event, EventType
from output.script_bank import ScriptBank
from output.tts import TTSEngine
from output.expression import ExpressionDisplay
from output.llm_coach import LLMCoach
from data.db import Database


_POMODORO_TO_EXPRESSION = {
    "IDLE":         "IDLE",
    "PREPARE":      "PREPARE",
    "FOCUS":        "FOCUS",
    "BREAK":        "BREAK",
    "RESUME_CHECK": "BREAK",
    "COMPLETE":     "COMPLETE",
}

_EVENT_TO_EXPRESSION = {
    EventType.PHONE_DETECTED:    "PHONE_ALERT",
    EventType.FATIGUE_DROWSY:    "FATIGUE",
    EventType.GOOD_FOCUS:        "GOOD_FOCUS",
    EventType.DISTRACTED_GAZE:   "CONCERNED",
    EventType.OUT_OF_SEAT:       "CONCERNED",
    EventType.UNKNOWN_PERSON:    "CONCERNED",
    EventType.SPOOF_SUSPECTED:   "CONCERNED",
    EventType.TALKING:           "CONCERNED",
    EventType.WRITING_IDLE:      "CONCERNED",
    EventType.BAD_POSTURE_CLOSE: "CONCERNED",
    EventType.BAD_POSTURE_SLOUCH:"CONCERNED",
}


class SessionManager:
    """Owns all modules. Runs the main async loop."""

    def __init__(self, debug: bool = False, api_only: bool = False):
        self._debug    = debug
        self._api_only = api_only
        self.capture    = None
        self.mp_module  = None
        self.yolo_module = None
        self.flow_module = None

        if not api_only:
            self.capture     = CameraCapture()
            self.mp_module   = MediaPipeModule()
            self.yolo_module = YoloModule()
            self.flow_module = OpticalFlowModule()

        self.aggregator = FeatureAggregator()
        self.pomodoro   = PomodoroMachine(on_state_change=self._on_state_change)
        self.rules      = RulesEngine()
        self.tts        = TTSEngine()
        self.scripts    = ScriptBank(language=config.LANGUAGE)
        self.llm_coach  = LLMCoach()
        self.db         = Database()
        self.expression = ExpressionDisplay()

        self._running      = False
        self._session_id: int | None = None
        self._child_id: int | None   = None
        self._child_name   = config.CHILD_NAME
        self._frame_count  = 0
        self._last_tick_time: float  = 0.0
        self._last_snapshot_min: int = -1
        self._tts_queue: asyncio.Queue = asyncio.Queue()

        # Calibration state — collected during PREPARE phase
        self._calib_ear:   list[float] = []
        self._calib_yaw:   list[float] = []
        self._calib_pitch: list[float] = []
        self._calib_sig:   list[tuple] = []   # face signatures for identity
        self._calibration: CalibrationProfile | None = None

    async def run(self) -> None:
        self._running = True
        print("[Bot] CV loop starting...", flush=True)
        await self.db.init()
        print("[Bot] Database ready.", flush=True)
        try:
            self.expression.show("IDLE")
        except Exception:
            pass
        asyncio.create_task(self._tts_worker())
        asyncio.create_task(self._tts_precache())

        while self._running:
            try:
                if self.capture is not None:
                    frame = self.capture.get_frame()
                    if frame is not None:
                        self._process_frame(frame)
                now = time.monotonic()
                if now - self._last_tick_time >= 1.0:
                    self._last_tick_time = now
                    await self._tick_logic()
            except Exception as e:
                print(f"[Bot] CV pipeline error (continuing): {type(e).__name__}: {e}",
                      flush=True)
            await asyncio.sleep(1.0 / config.TARGET_FPS)

    def _process_frame(self, frame) -> None:
        import cv2
        face, pose, hand = self.mp_module.process(frame)
        yolo             = self.yolo_module.process(frame)
        flow_score       = self.flow_module.process(frame)
        self.aggregator.update(face, pose, yolo, flow_score, hand)

        # Collect calibration samples during PREPARE
        if (config.CALIBRATE_DURING_PREPARE
                and self.pomodoro.current_state == "PREPARE"
                and face.detected
                and face.confidence >= 0.75):
            self._calib_ear.append(face.ear_avg)
            self._calib_yaw.append(face.head_yaw)
            self._calib_pitch.append(face.head_pitch)
            # Collect identity signatures (only frontal frames produce one)
            if config.IDENTITY_VERIFY and face.signature is not None:
                self._calib_sig.append(face.signature)

        if self._debug:
            debug_frame = self.mp_module.draw_debug(frame, face, pose, hand)
            debug_frame = self.yolo_module.draw_debug(debug_frame, yolo)
            fv = self.aggregator.get_latest()
            if fv is not None:
                working = fv.work_confidence >= config.WORK_CONFIDENCE_THRESHOLD
                col = (0, 255, 0) if working else (0, 165, 255)
                label = "WORKING" if working else "idle"
                cv2.putText(debug_frame,
                            f"Work:{fv.work_confidence:.0f} [{label}]", (10, 130),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
                if fv.identity_known:
                    id_col = (0, 0, 255) if fv.face_mismatch else (0, 255, 0)
                    id_lbl = "DIFFERENT!" if fv.face_mismatch else "match"
                    cv2.putText(debug_frame,
                                f"ID dist:{fv.identity_distance:.3f} [{id_lbl}]", (10, 155),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, id_col, 2)
                if fv.face_present:
                    live_col = (0, 0, 255) if fv.face_static else (0, 255, 0)
                    live_lbl = "STATIC/PHOTO?" if fv.face_static else "LIVE"
                    talk = " TALKING" if fv.is_talking else ""
                    cv2.putText(debug_frame,
                                f"[{live_lbl}]{talk} MAR:{fv.mar:.2f}", (10, 180),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, live_col, 2)
            self.expression.update_debug_frame(debug_frame)
            cv2.imshow("Supervision Bot — Debug", debug_frame)
            cv2.waitKey(1)

    async def _tick_logic(self) -> None:
        self.pomodoro.tick()
        state = self.pomodoro.current_state
        fv    = self.aggregator.get_latest()
        if fv is None:
            return

        if self._session_id is not None:
            elapsed_min = self.pomodoro.elapsed_seconds // 60
            if elapsed_min > self._last_snapshot_min:
                self._last_snapshot_min = elapsed_min
                await self.db.log_snapshot(self._session_id, elapsed_min, fv)

        if state in ("PREPARE", "FOCUS", "BREAK", "RESUME_CHECK"):
            events = self.rules.evaluate(fv, state)
            for event in events:
                await self._handle_event(event)

        try:
            self.expression.show(_POMODORO_TO_EXPRESSION.get(state, "IDLE"))
        except Exception:
            pass

    def _on_state_change(self, old: str, new: str) -> None:
        # When PREPARE ends → FOCUS begins: finalize calibration
        if old == "PREPARE" and new == "FOCUS":
            self._finalize_calibration()

        import config as cfg
        announcement_map = {
            "PREPARE":      lambda: self.scripts.get("session_start",
                                                     focus_min=cfg.FOCUS_DURATION // 60),
            "FOCUS":        lambda: self.scripts.get("focus_complete",
                                                     break_min=cfg.SHORT_BREAK // 60)
                            if old == "BREAK" else None,
            "BREAK":        lambda: self.scripts.get("focus_complete",
                                                     break_min=cfg.SHORT_BREAK // 60),
            "RESUME_CHECK": lambda: self.scripts.get("break_ending"),
            "COMPLETE":     lambda: self.scripts.get("session_complete",
                                                     rounds=self.pomodoro.round_number),
        }
        getter = announcement_map.get(new)
        if getter:
            text = getter()
            if text:
                self._tts_queue.put_nowait(text)

    def _finalize_calibration(self) -> None:
        if not config.CALIBRATE_DURING_PREPARE:
            return
        n = len(self._calib_ear)
        if n < config.CALIB_MIN_SAMPLES:
            print(f"[Calib] Only {n} samples — need {config.CALIB_MIN_SAMPLES}. "
                  "Using config defaults.", flush=True)
            return

        # 30th percentile EAR to exclude blinks (blinks push EAR down, so use lower end)
        baseline_ear = float(np.percentile(self._calib_ear, config.CALIB_EAR_PERCENTILE))
        neutral_yaw  = float(np.mean(self._calib_yaw))
        neutral_pitch= float(np.mean(self._calib_pitch))

        profile = CalibrationProfile(
            baseline_ear=baseline_ear,
            ear_fatigue_threshold=baseline_ear * config.CALIB_EAR_FATIGUE_RATIO,
            perclos_ear_threshold=baseline_ear * config.PERCLOS_EAR_FRACTION,
            neutral_yaw=neutral_yaw,
            neutral_pitch=neutral_pitch,
            yaw_distract_range=float(config.YAW_DISTRACTED_DEG),
        )
        self._calibration = profile
        self.aggregator.set_calibration(profile)
        self.rules.set_calibration(profile)
        print(f"[Calib] Done — baseline_EAR={baseline_ear:.3f}, "
              f"neutral_yaw={neutral_yaw:.1f}°, "
              f"fatigue_threshold={profile.ear_fatigue_threshold:.3f}",
              flush=True)

        # Register identity from collected frontal signatures.
        # median   = robust center of the child's face
        # scale    = the child's own natural per-feature variation (for adaptive matching)
        if config.IDENTITY_VERIFY:
            if len(self._calib_sig) >= config.IDENTITY_MIN_SAMPLES:
                arr        = np.array(self._calib_sig)
                median_sig = np.median(arr, axis=0)
                # Spread per feature (std), with a floor so tiny variation can't blow up
                spread     = np.std(arr, axis=0)
                scale      = np.maximum(spread, 0.01)
                self.aggregator.set_identity(tuple(median_sig), tuple(scale))
                print(f"[Identity] Registered '{self._child_name}' from "
                      f"{len(self._calib_sig)} frontal frames (adaptive matching).",
                      flush=True)
            else:
                print(f"[Identity] Only {len(self._calib_sig)} frontal frames — "
                      f"need {config.IDENTITY_MIN_SAMPLES}. Identity guard OFF "
                      "(ask child to face the camera during setup).", flush=True)

        # Reset sample lists to free memory
        self._calib_ear.clear()
        self._calib_yaw.clear()
        self._calib_pitch.clear()
        self._calib_sig.clear()

    async def _handle_event(self, event: Event) -> None:
        # Suppress soft reminders while student is actively chatting with the AI.
        # Only HIGH priority alerts (phone, unknown person, spoof) still fire.
        _CHAT_SUPPRESSED = {
            EventType.WRITING_IDLE, EventType.DISTRACTED_GAZE,
            EventType.FATIGUE_DROWSY, EventType.BAD_POSTURE_CLOSE,
            EventType.BAD_POSTURE_SLOUCH, EventType.TALKING,
        }
        if self.llm_coach.is_chatting() and event.event_type in _CHAT_SUPPRESSED:
            return   # student is talking to AI — don't interrupt with reminders

        # Try LLM coach first; fall back to static ScriptBank if unavailable/slow
        text: str | None = None
        if config.LLM_ENABLED:
            fv = self.aggregator.get_latest()
            text = await self.llm_coach.alert(
                event_type=event.event_type.value,
                fv=fv,
                pomodoro_state=self.pomodoro.current_state,
                elapsed_sec=self.pomodoro.elapsed_seconds,
            )

        if text is None:
            try:
                text = self.scripts.get(event.message_intent,
                                        minutes=event.context.get("minutes", 0))
            except KeyError:
                return

        if event.priority.value >= 2:
            self._tts_queue.put_nowait(text)
        if self._session_id is not None:
            await self.db.log_event(self._session_id, event)
        expr = _EVENT_TO_EXPRESSION.get(event.event_type)
        if expr:
            self.expression.show(expr)

    async def _tts_worker(self) -> None:
        while self._running:
            try:
                text = await asyncio.wait_for(self._tts_queue.get(), timeout=1.0)
                await self.tts.speak(text)
            except asyncio.TimeoutError:
                pass

    async def _tts_precache(self) -> None:
        await asyncio.sleep(5)
        try:
            await self.tts.pre_cache_all(self.scripts)
        except Exception:
            pass

    def set_language(self, lang: str) -> None:
        lang = lang if lang in ("en", "zh") else "en"
        config.LANGUAGE  = lang
        config.TTS_VOICE = config.TTS_VOICES.get(lang, config.TTS_VOICES["en"])
        self.scripts = ScriptBank(language=lang)
        self.scripts.set_child(self._child_name, config.CHILD_AGE)
        self.llm_coach.set_language(lang)
        print(f"[Bot] Language switched to '{lang}', voice: {config.TTS_VOICE}", flush=True)

    def start_session(self, child_name: str) -> None:
        print(f"[Bot] Session starting for '{child_name}'", flush=True)
        self._child_name = child_name
        self.scripts.set_child(child_name, config.CHILD_AGE)
        self.llm_coach.set_child(child_name, config.CHILD_AGE)
        self.llm_coach.set_language(config.LANGUAGE)
        self.llm_coach.reset()
        self.rules.reset_session()
        self.aggregator.reset()
        if self.flow_module:
            self.flow_module.reset()
        self._last_snapshot_min = -1
        # Reset calibration for new session
        self._calib_ear.clear()
        self._calib_yaw.clear()
        self._calib_pitch.clear()
        self._calib_sig.clear()
        self._calibration = None
        if self.capture:
            self.capture.start()
        if self.pomodoro.current_state != "IDLE":
            self.pomodoro.reset()
        self.pomodoro.manual_start()
        print(f"[Bot] Pomodoro state: {self.pomodoro.current_state}", flush=True)

    def shutdown(self) -> None:
        self._running = False

    def end_session(self) -> dict:
        print("[Bot] Session ending.", flush=True)
        if self.capture:
            self.capture.stop()
        if self.pomodoro:
            self.pomodoro.session_end()
        summary = {
            "rounds_completed":    self.pomodoro.round_number - 1,
            "total_focus_seconds": self.pomodoro.total_focus_today,
            "focus_score_avg":     self._compute_focus_score(),
        }
        events = self.rules.get_session_events()
        event_counts: dict[str, int] = {}
        for ev in events:
            key = ev.event_type.value
            event_counts[key] = event_counts.get(key, 0) + 1
        summary["event_counts"] = event_counts
        self._session_id = None
        return summary

    def _compute_focus_score(self) -> float:
        events = self.rules.get_session_events()
        if not events:
            return 100.0
        score = 100.0
        for ev in events:
            if ev.event_type == EventType.PHONE_DETECTED:
                score -= 15
            elif ev.event_type in (EventType.DISTRACTED_GAZE, EventType.OUT_OF_SEAT):
                score -= 8
            elif ev.event_type == EventType.WRITING_IDLE:
                score -= 5
            elif ev.event_type == EventType.FATIGUE_DROWSY:
                score -= 5
            elif ev.event_type in (EventType.BAD_POSTURE_CLOSE, EventType.BAD_POSTURE_SLOUCH):
                score -= 3
        return max(0.0, min(100.0, score))
