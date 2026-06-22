# config.py — Single source of truth for all thresholds and durations.
# Never hard-code a number elsewhere — always reference this file.

import sys

# ── Camera ────────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0          # Default webcam. Change to 1 for external camera.
FRAME_WIDTH  = 640
FRAME_HEIGHT = 480
TARGET_FPS   = 15         # Run CV at 15fps to reduce CPU load on laptops

# ── Pomodoro Durations (seconds) ──────────────────────────────────────────────
FOCUS_DURATION      = 7  * 60   # 7 minutes
SHORT_BREAK         = 2  * 60   # 2 minutes break
LONG_BREAK          = 5  * 60   # 5 minutes long break (after ROUNDS_BEFORE_LONG rounds)
ROUNDS_BEFORE_LONG  = 4
PREPARE_DURATION    = 30        # 30 seconds for personal calibration

# ── Detection Thresholds ──────────────────────────────────────────────────────
FACE_CONFIDENCE_MIN = 0.4   # Min MediaPipe face detection confidence (lowered for better detection)
YOLO_CONFIDENCE_MIN = 0.65  # Min YOLO detection confidence

# Eye closure — PERCLOS method (industry standard for drowsiness detection)
EAR_CLOSED_THRESHOLD = 0.14  # Fallback threshold when calibration not done
EAR_FATIGUE_SECONDS  = 10    # Fallback: sustained EAR below threshold
PERCLOS_WINDOW_SECONDS = 60  # Rolling 60s window for PERCLOS
PERCLOS_THRESHOLD      = 0.25 # 25% of frames with closed eyes = fatigued
PERCLOS_EAR_FRACTION   = 0.80 # EAR < baseline * 0.80 counts as "closed"

# Head pose — combined check: BOTH yaw and gaze must exceed threshold
YAW_DISTRACTED_DEG  = 30    # Degrees from personal neutral (was 50, now tighter+combined)
PITCH_DOWN_DEG      = 40    # Looking down — allow more for writing
GAZE_X_DISTRACTED   = 0.30  # Iris offset > this AND yaw > threshold = distracted

# Face confidence gating — skip non-critical alerts for shaky/low-confidence detections
MIN_FACE_CONF_FOR_ALERTS = 0.55

# Writing activity
FLOW_IDLE_THRESHOLD = 8.0   # Optical flow magnitude below this = pen idle
FLOW_IDLE_SECONDS   = 5     # Pen idle 5 seconds during focus = alert

# ── Work-confidence fusion ────────────────────────────────────────────────────
# Combine several weak signals into ONE robust "is the child working?" score (0-100).
# Position-independent: works at a desk, lying on the floor, any camera angle.
# Weights sum to 100 — a fully-confident writer scores ~100.
WORK_WEIGHT_PEN_GRIP   = 35   # Hand in pen-holding grip (strongest signal)
WORK_WEIGHT_WRIST_MOVE = 20   # Writing hand making small rhythmic motion
WORK_WEIGHT_HEAD_DOWN  = 15   # Head pitched down toward paper
WORK_WEIGHT_FLOW       = 15   # Optical-flow motion in frame
WORK_WEIGHT_BOOK       = 10   # YOLO sees a book/paper
WORK_WEIGHT_FACE       =  5   # Face present (baseline)

WORK_CONFIDENCE_THRESHOLD = 40   # Score >= this = "working" (suppress false alerts)
WRIST_MOTION_MIN  = 0.002   # Normalized per-frame wrist displacement = active hand
WRIST_MOTION_MAX  = 0.06    # Above this = big gesture (waving), not writing
HEAD_DOWN_PITCH   = 8       # Pitch beyond this (down) = looking at paper
HEAD_YAW_MAX_FOR_WORK = 35  # A real writer faces the paper; turned > this = not writing

# Anti-cheat: real writing requires MOVEMENT. A child can hold a pen still in a
# writing grip to fake it — without wrist/desk motion it won't count as working.
REQUIRE_MOTION_FOR_WORK = True

# Anti-cheat: real writing requires LOOKING DOWN at the paper. A hand can grip any
# object (tissue, toy) — but a genuine writer's head is tilted down at the desk.
# Without head-down, a grip + hand-waving won't count as working.
REQUIRE_HEAD_DOWN_FOR_WORK = True

# Seat presence
OUT_OF_SEAT_SECONDS  = 10   # No person detected this long = out of seat alert
SEAT_WRITING_GRACE   = True  # Suppress out-of-seat when writing (child leaned forward)

# Gaze
GAZE_DISTRACTED_SEC = 60   # Combined yaw+gaze must persist this long = alert

# Phone
PHONE_ALERT_SECONDS = 1    # Phone detected even 1 second = immediate alert

# ── YOLO ─────────────────────────────────────────────────────────────────────
YOLO_MODEL         = "yolov8s.pt"  # Small model — 2× more accurate than nano (yolov8n)
YOLO_DESK_ROI_FRAC = 0.40          # Only scan below this height fraction (desk area)

# ── Calibration — personal baseline collected during PREPARE phase ────────────
CALIBRATE_DURING_PREPARE = True    # Auto-calibrate to this person's face
CALIB_MIN_SAMPLES        = 40      # Minimum good frames needed for calibration
CALIB_EAR_PERCENTILE     = 30      # 30th percentile EAR to exclude blinks
CALIB_EAR_FATIGUE_RATIO  = 0.55    # Personal fatigue threshold = baseline * ratio

# ── Identity verification — "is this the SAME child who started?" ─────────────
# During PREPARE the registered child's face-geometry signature is saved.
# During FOCUS every face is compared; a different person triggers an alert.
IDENTITY_VERIFY          = True    # Enable face-identity guarding
IDENTITY_FRONTAL_DEG     = 25      # Only register/verify when head is near-frontal
IDENTITY_MIN_SAMPLES     = 25      # Min frontal frames to register an identity
# Adaptive matching: distance is measured in "sigmas" of the registered child's own
# natural frame-to-frame variation. 4.0 = a face 4x more different than the child
# ever varies = a different person. Raise if it falsely flags the real child.
IDENTITY_MATCH_THRESHOLD = 4.0     # Normalized (sigma) distance above this = different person
IDENTITY_ALERT_SECONDS   = 5       # Different face this long = "who are you?" alert

# ── Mouth / talking detection (uses existing face landmarks, no new model) ────
MAR_OPEN_THRESHOLD = 0.45   # Mouth Aspect Ratio above this = mouth open
TALKING_MAR_STD    = 0.035  # MAR wobble over the window this high = talking
TALKING_WINDOW_SEC = 3      # Window for talking detection
TALKING_ALERT      = False  # If True, alert when child talks during focus (off by default —
                            #   reading aloud is also "talking", so keep conservative)
TALKING_ALERT_SEC  = 10     # Sustained talking this long = alert (when enabled)

# ── Liveness / anti-spoof (defeats a photo held to the camera) ───────────────
# A real face blinks, makes micro head-motions, and changes expression. A printed
# photo is frozen. If a face is present but completely static, treat it as fake.
LIVENESS_CHECK      = True   # Reject a static photo of the registered child
LIVENESS_WINDOW_SEC = 4      # How long to watch for natural motion
LIVE_EAR_STD_MIN    = 0.006  # Below this eye-openness variation = no blinking
LIVE_POSE_STD_MIN   = 0.4    # Below this head-angle variation (deg) = frozen
LIVE_MAR_STD_MIN    = 0.004  # Below this mouth variation = frozen
SPOOF_ALERT_SECONDS = 5      # Static (photo-like) face this long = alert

# ── Alert Escalation ──────────────────────────────────────────────────────────
ALERT_COOLDOWN_SEC      = 15   # Min seconds between same-type alerts (lowered for testing)
MAX_ALERTS_PER_SESSION  = 20   # After this, stop alerting (avoid alert fatigue)

# ── TTS ───────────────────────────────────────────────────────────────────────
TTS_VOICE        = "en-US-JennyNeural"
TTS_RATE         = "+0%"
TTS_CACHE_DIR    = "data/tts_cache/"
USE_FALLBACK_TTS = True
LANGUAGE         = "en"

TTS_VOICES = {
    "en": "en-US-JennyNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
}

# ── API ───────────────────────────────────────────────────────────────────────
API_HOST     = "127.0.0.1"
API_PORT     = 8000
DATABASE_URL = "sqlite+aiosqlite:///data/supervision.db"

# ── Windows asyncio policy fix ────────────────────────────────────────────────
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ── Child Profile (default — override via UI or CLI) ─────────────────────────
CHILD_NAME = "小明"
CHILD_AGE  = 10

# ── LLM Coach (yunwu.ai — OpenAI-compatible) ──────────────────────────────────
# Put your key in a .env file: LLM_API_KEY=sk-...
import os as _os
LLM_ENABLED        = True
LLM_API_BASE       = "https://yunwu.ai/v1"
LLM_API_KEY        = _os.environ.get("LLM_API_KEY", "")
LLM_MODEL          = "deepseek-v4-flash"
LLM_FALLBACK_MODEL = "deepseek-chat"   # used when primary hits 429
LLM_MAX_HISTORY    = 10    # conversation turns to remember
LLM_TIMEOUT_SEC    = 25    # yunwu.ai can be slow — give it time
LLM_MAX_TOKENS      = 120   # for spoken alerts (TTS) — short for voice
LLM_CHAT_MAX_TOKENS = 2048  # for chat — no artificial limit, let AI give complete answers
LLM_TEMPERATURE    = 1.0   # higher = more varied wording, avoids repetition
LLM_MAX_RETRIES    = 2     # retries on 429 rate-limit before giving up
