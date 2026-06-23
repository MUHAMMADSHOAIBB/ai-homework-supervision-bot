import collections
import time
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config
from vision.mediapipe_module import FaceResult, PoseResult, HandResult
from vision.yolo_module import YoloResult


@dataclass
class CalibrationProfile:
    """Personal baseline collected during PREPARE phase."""
    baseline_ear: float            # Natural resting EAR
    ear_fatigue_threshold: float   # = baseline_ear * CALIB_EAR_FATIGUE_RATIO
    perclos_ear_threshold: float   # = baseline_ear * PERCLOS_EAR_FRACTION
    neutral_yaw: float             # Natural head yaw angle
    neutral_pitch: float           # Natural head pitch angle
    yaw_distract_range: float      # Degrees from neutral = distracted
    calibrated: bool = True


@dataclass
class FeatureVector:
    timestamp: datetime
    # From MediaPipe face
    face_present: bool       = False
    face_confidence: float   = 0.0
    head_pitch: float        = 0.0
    head_yaw: float          = 0.0
    ear_avg: float           = 0.3
    gaze_x: float            = 0.0
    # From MediaPipe pose
    seat_present: bool       = True
    slouch_score: float      = 0.0
    distance_estimate: float = 50.0
    # From MediaPipe hands
    hand_writing: bool       = False   # pen-grip detected in desk area
    # From YOLO
    phone_detected: bool     = False
    phone_confidence: float  = 0.0
    # From optical flow
    writing_score: float     = 50.0
    # Derived
    is_distracted: bool      = False
    is_fatigued: bool        = False
    perclos: float           = 0.0     # fraction of last 60s where eyes were "closed"
    work_confidence: float   = 0.0     # fused 0-100 "is the child working?" score
    # Identity verification
    identity_known: bool     = False   # a registered face exists for this session
    identity_distance: float = 0.0     # signature distance from registered child
    face_mismatch: bool      = False   # current face differs from registered child
    # Multi-person / ArcFace
    person_count: int        = 0       # total faces detected in frame
    stranger_present: bool   = False   # non-child face present (ArcFace result)
    # Mouth / talking
    mar: float               = 0.0     # mouth aspect ratio
    is_talking: bool         = False   # mouth moving repeatedly = talking
    # Liveness / anti-spoof
    is_live: bool            = True    # real moving face (False = frozen/photo)
    face_static: bool        = False   # face present but completely still (photo-like)


class FeatureAggregator:
    def __init__(self, window_seconds: int = 5):
        fps = config.TARGET_FPS
        max_samples = window_seconds * fps

        # Short rolling buffers (5s) for averaged values
        self._ear_buf     = collections.deque(maxlen=max_samples)
        self._gaze_x_buf  = collections.deque(maxlen=max_samples)
        self._writing_buf = collections.deque(maxlen=max_samples)
        self._phone_buf   = collections.deque(maxlen=max_samples)
        self._seat_buf    = collections.deque(maxlen=max_samples)  # for seat stability

        # Wrist micro-motion: ~1.5s of recent wrist positions for writing detection
        wrist_samples       = max(2, int(1.5 * fps))
        self._wrist_x_buf   = collections.deque(maxlen=wrist_samples)
        self._wrist_y_buf   = collections.deque(maxlen=wrist_samples)
        # work_confidence smoothing buffer (2s) — avoids flicker
        self._work_conf_buf = collections.deque(maxlen=2 * fps)

        # PERCLOS buffer — 60s window
        perclos_samples = config.PERCLOS_WINDOW_SECONDS * fps
        self._perclos_buf = collections.deque(maxlen=perclos_samples)

        # Calibration-derived thresholds (updated when calibration completes)
        self._baseline_ear          = 0.30
        self._perclos_ear_threshold = self._baseline_ear * config.PERCLOS_EAR_FRACTION

        # Registered identity (set after PREPARE): median signature + per-feature spread
        self._identity_sig:   np.ndarray | None = None
        self._identity_scale: np.ndarray | None = None
        # Smooth identity distance over ~1.5s to avoid single-frame false mismatches
        self._identity_buf = collections.deque(maxlen=max(2, int(1.5 * fps)))

        # Talking + liveness windows (store recent face dynamics)
        self._mar_buf   = collections.deque(maxlen=max(2, int(config.TALKING_WINDOW_SEC * fps)))
        live_n          = max(2, int(config.LIVENESS_WINDOW_SEC * fps))
        self._live_ear_buf   = collections.deque(maxlen=live_n)
        self._live_yaw_buf   = collections.deque(maxlen=live_n)
        self._live_pitch_buf = collections.deque(maxlen=live_n)
        self._live_mar_buf   = collections.deque(maxlen=live_n)

        # Sustained-duration trackers
        self._no_face_since:  float | None = None
        self._gaze_off_since: float | None = None
        self._ear_low_since:  float | None = None

        self._latest: FeatureVector | None = None

    def set_calibration(self, profile: CalibrationProfile) -> None:
        self._baseline_ear          = profile.baseline_ear
        self._perclos_ear_threshold = profile.perclos_ear_threshold
        print(f"[Aggregator] Calibration applied: baseline_EAR={profile.baseline_ear:.3f}, "
              f"PERCLOS_threshold={profile.perclos_ear_threshold:.3f}", flush=True)

    def set_identity(self, signature: tuple, scale: tuple) -> None:
        """Register the child's face: median signature + per-feature natural variation."""
        self._identity_sig   = np.array(signature, dtype=np.float64)
        self._identity_scale = np.array(scale, dtype=np.float64)
        self._identity_buf.clear()
        print(f"[Aggregator] Identity registered ({len(signature)} features, adaptive).",
              flush=True)

    def update(self, face: FaceResult, pose: PoseResult, yolo: YoloResult,
               flow_score: float, hand: HandResult,
               face_id_result=None) -> FeatureVector:
        now = time.monotonic()

        # Rolling buffers
        self._ear_buf.append(face.ear_avg)
        self._gaze_x_buf.append(face.gaze_x)
        self._writing_buf.append(flow_score)
        self._phone_buf.append(1.0 if yolo.phone_detected else 0.0)
        self._seat_buf.append(1.0 if pose.seat_present else 0.0)

        # PERCLOS: track frames where EAR is "closed" relative to personal baseline
        ear_closed = face.ear_avg < self._perclos_ear_threshold
        self._perclos_buf.append(1.0 if (ear_closed and face.detected) else 0.0)
        perclos = float(np.mean(self._perclos_buf)) if self._perclos_buf else 0.0

        # Sustained face-absent tracking
        if not face.detected:
            if self._no_face_since is None:
                self._no_face_since = now
        else:
            self._no_face_since = None

        # Sustained gaze-off tracking
        if abs(face.gaze_x) > 0.4:
            if self._gaze_off_since is None:
                self._gaze_off_since = now
        else:
            self._gaze_off_since = None

        # Sustained low EAR tracking (fallback when PERCLOS buffer not full)
        if face.detected and face.ear_avg < config.EAR_CLOSED_THRESHOLD:
            if self._ear_low_since is None:
                self._ear_low_since = now
        else:
            self._ear_low_since = None

        no_face_dur  = (now - self._no_face_since)  if self._no_face_since  else 0.0
        gaze_off_dur = (now - self._gaze_off_since) if self._gaze_off_since else 0.0
        ear_low_dur  = (now - self._ear_low_since)  if self._ear_low_since  else 0.0

        # Averaged values
        avg_writing = float(np.mean(self._writing_buf)) if self._writing_buf else flow_score

        # is_distracted: gaze wanders OR face absent (but NOT while writing — looking down is ok)
        is_distracted = (gaze_off_dur > 3.0) or (
            no_face_dur > 2.0 and avg_writing <= config.FLOW_IDLE_THRESHOLD
        )

        # is_fatigued: use PERCLOS if buffer is reasonably full, else fallback
        if len(self._perclos_buf) >= config.PERCLOS_WINDOW_SECONDS * config.TARGET_FPS * 0.3:
            is_fatigued = perclos > config.PERCLOS_THRESHOLD
        else:
            is_fatigued = ear_low_dur > config.EAR_FATIGUE_SECONDS

        # Seat stability: use rolling average to avoid immediate seat-lost flag
        avg_seat = float(np.mean(self._seat_buf)) if self._seat_buf else float(pose.seat_present)
        # "Seat lost" only if absent >70% of the last 5 seconds
        seat_stable = avg_seat > 0.30

        # Hand writing = pen grip in desk area (MediaPipe Hands primary signal)
        hand_writing = hand.detected and hand.pen_grip and hand.in_desk_area

        # ── Wrist micro-motion ────────────────────────────────────────────────
        # Track the writing hand's wrist; writing = small, sustained motion.
        wrist_active = False
        if hand.detected:
            self._wrist_x_buf.append(hand.wrist_x)
            self._wrist_y_buf.append(hand.wrist_y)
            if len(self._wrist_x_buf) >= 3:
                dxs = np.diff(self._wrist_x_buf)
                dys = np.diff(self._wrist_y_buf)
                motion = float(np.mean(np.sqrt(dxs**2 + dys**2)))
                # Writing band: above idle, below big-gesture (waving/reaching)
                wrist_active = config.WRIST_MOTION_MIN < motion < config.WRIST_MOTION_MAX
        else:
            self._wrist_x_buf.clear()
            self._wrist_y_buf.clear()

        # ── Work-confidence fusion (0-100) ────────────────────────────────────
        # Position-independent: any combination of these signals confirms working.
        # Hand signals ONLY count when the hand is down on the writing surface —
        # a grip up in the air (not on paper) is not writing.
        hand_on_surface = hand.detected and hand.in_desk_area
        work = 0.0
        if hand_on_surface and hand.pen_grip:
            work += config.WORK_WEIGHT_PEN_GRIP
        if hand_on_surface and wrist_active:
            work += config.WORK_WEIGHT_WRIST_MOVE
        if face.detected and face.head_pitch > config.HEAD_DOWN_PITCH:
            work += config.WORK_WEIGHT_HEAD_DOWN
        if avg_writing > config.FLOW_IDLE_THRESHOLD:
            work += config.WORK_WEIGHT_FLOW
        if yolo.book_detected:
            work += config.WORK_WEIGHT_BOOK
        if face.detected:
            work += config.WORK_WEIGHT_FACE

        # ── Anti-cheat gates — REAL writing requires movement AND looking down ─
        # Grip alone can be faked (hold a tissue/toy, wave the hand). Genuine
        # writing always has (a) wrist/desk motion AND (b) head tilted down at
        # the paper. If either is missing, a posed hand cannot count as working.
        motion_active = (hand_on_surface and wrist_active) or \
                        (avg_writing > config.FLOW_IDLE_THRESHOLD)
        # Head-down is satisfied two ways:
        #  1. Face visible AND tilted down at the paper AND facing it (not turned
        #     sideways / leaning back), OR
        #  2. Face dipped so low the camera lost it WHILE the hand is writing on
        #     the desk (looking far down at paper) — but NOT a face that's clearly
        #     looking up at the camera (that's the tissue/fake case).
        facing_paper = abs(face.head_yaw) < config.HEAD_YAW_MAX_FOR_WORK
        looking_down = (face.detected
                        and face.head_pitch > config.HEAD_DOWN_PITCH
                        and facing_paper)
        head_down = looking_down or \
                    (not face.detected and hand_on_surface and hand.pen_grip)
        genuine = True
        if config.REQUIRE_MOTION_FOR_WORK and not motion_active:
            genuine = False
        if config.REQUIRE_HEAD_DOWN_FOR_WORK and not head_down:
            genuine = False
        if not genuine:
            work = min(work, config.WORK_CONFIDENCE_THRESHOLD - 1.0)

        self._work_conf_buf.append(min(100.0, work))
        work_confidence = float(np.mean(self._work_conf_buf)) if self._work_conf_buf else work

        # ── Identity verification ─────────────────────────────────────────────
        identity_known   = self._identity_sig is not None
        identity_distance = 0.0
        face_mismatch     = False
        if identity_known and face.detected and face.signature is not None:
            cur = np.array(face.signature, dtype=np.float64)
            # Normalized distance: how many "sigmas" of the child's own variation away.
            dist = float(np.mean(np.abs(cur - self._identity_sig) / self._identity_scale))
            self._identity_buf.append(dist)
            identity_distance = float(np.mean(self._identity_buf))
            face_mismatch = identity_distance > config.IDENTITY_MATCH_THRESHOLD
        elif not (face.detected and face.signature is not None):
            # No frontal face this frame — don't accumulate stale distance
            self._identity_buf.clear()

        # ── Talking + liveness (anti-spoof) ──────────────────────────────────
        is_talking  = False
        is_live     = True
        face_static = False
        if face.detected:
            self._mar_buf.append(face.mar)
            self._live_ear_buf.append(face.ear_avg)
            self._live_yaw_buf.append(face.head_yaw)
            self._live_pitch_buf.append(face.head_pitch)
            self._live_mar_buf.append(face.mar)

            # Talking: the mouth opens/closes repeatedly (high MAR variation)
            if len(self._mar_buf) >= self._mar_buf.maxlen * 0.6:
                if float(np.std(self._mar_buf)) > config.TALKING_MAR_STD:
                    is_talking = True

            # Liveness: a real face blinks / micro-moves / changes expression.
            # If EVERY dynamic signal is flat for the whole window → frozen photo.
            if config.LIVENESS_CHECK and len(self._live_ear_buf) >= self._live_ear_buf.maxlen:
                ear_std   = float(np.std(self._live_ear_buf))
                yaw_std   = float(np.std(self._live_yaw_buf))
                pitch_std = float(np.std(self._live_pitch_buf))
                mar_std   = float(np.std(self._live_mar_buf))
                face_static = (ear_std   < config.LIVE_EAR_STD_MIN  and
                               yaw_std   < config.LIVE_POSE_STD_MIN and
                               pitch_std < config.LIVE_POSE_STD_MIN and
                               mar_std   < config.LIVE_MAR_STD_MIN)
                is_live = not face_static
        else:
            # No face — clear dynamics so a returning face starts fresh
            self._mar_buf.clear()
            self._live_ear_buf.clear()
            self._live_yaw_buf.clear()
            self._live_pitch_buf.clear()
            self._live_mar_buf.clear()

        # ── ArcFace multi-person results ──────────────────────────────────────
        arc_person_count  = 0
        arc_stranger      = False
        # ArcFace overrides geometric identity check when available
        if face_id_result is not None:
            arc_person_count = face_id_result.person_count
            arc_stranger     = face_id_result.stranger_present
            if face_id_result.faces:
                # Use ArcFace result for identity_known / face_mismatch
                identity_known    = face_id_result.is_enrolled if hasattr(face_id_result, 'is_enrolled') else identity_known
                face_mismatch     = arc_stranger or face_mismatch

        fv = FeatureVector(
            timestamp=datetime.utcnow(),
            face_present=face.detected,
            face_confidence=face.confidence,
            head_pitch=face.head_pitch,
            head_yaw=face.head_yaw,
            ear_avg=float(np.mean(self._ear_buf)) if self._ear_buf else face.ear_avg,
            gaze_x=float(np.mean(self._gaze_x_buf)) if self._gaze_x_buf else face.gaze_x,
            seat_present=seat_stable,
            slouch_score=pose.slouch_score,
            distance_estimate=pose.distance_estimate,
            hand_writing=hand_writing,
            phone_detected=yolo.phone_detected,
            phone_confidence=yolo.phone_confidence,
            writing_score=avg_writing,
            is_distracted=is_distracted,
            is_fatigued=is_fatigued,
            perclos=perclos,
            work_confidence=work_confidence,
            identity_known=identity_known,
            identity_distance=identity_distance,
            face_mismatch=face_mismatch,
            mar=face.mar,
            is_talking=is_talking,
            is_live=is_live,
            face_static=face_static,
            person_count=arc_person_count,
            stranger_present=arc_stranger,
        )
        self._latest = fv
        return fv

    def get_latest(self) -> FeatureVector | None:
        return self._latest

    def reset(self) -> None:
        self._ear_buf.clear()
        self._gaze_x_buf.clear()
        self._writing_buf.clear()
        self._phone_buf.clear()
        self._seat_buf.clear()
        self._perclos_buf.clear()
        self._wrist_x_buf.clear()
        self._wrist_y_buf.clear()
        self._work_conf_buf.clear()
        self._identity_sig   = None
        self._identity_scale = None
        self._identity_buf.clear()
        self._mar_buf.clear()
        self._live_ear_buf.clear()
        self._live_yaw_buf.clear()
        self._live_pitch_buf.clear()
        self._live_mar_buf.clear()
        self._no_face_since  = None
        self._gaze_off_since = None
        self._ear_low_since  = None
        self._latest = None
