import math
import urllib.request
import ssl
import numpy as np
import cv2
import mediapipe as mp
from dataclasses import dataclass
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config

LEFT_EYE_IDX  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]

FACE_3D_MODEL = np.array([
    [0.0,   0.0,   0.0],
    [0.0,  -330.0, -65.0],
    [-225.0, 170.0, -135.0],
    [225.0,  170.0, -135.0],
    [-150.0, -150.0, -125.0],
    [150.0,  -150.0, -125.0],
], dtype=np.float64)
FACE_3D_INDICES = [1, 152, 226, 446, 57, 287]

_L_EAR      = 7
_R_EAR      = 8
_L_SHOULDER = 11
_R_SHOULDER = 12

# Hand landmark indices
_THUMB_TIP  = 4
_INDEX_TIP  = 8
_INDEX_MCP  = 5
_WRIST      = 0

_MODEL_DIR  = os.path.join(os.path.dirname(__file__), '..', 'data', 'models')
_FACE_MODEL = os.path.join(_MODEL_DIR, 'face_landmarker.task')
_POSE_MODEL = os.path.join(_MODEL_DIR, 'pose_landmarker_lite.task')
_HAND_MODEL = os.path.join(_MODEL_DIR, 'hand_landmarker.task')
_HAND_URL   = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)


def _download_model(url: str, dest: str) -> bool:
    if os.path.exists(dest):
        return True
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"[MediaPipe] Downloading {os.path.basename(dest)}...", flush=True)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(url, context=ctx, timeout=60) as resp, \
             open(dest, 'wb') as f:
            total = int(resp.headers.get('Content-Length', 0))
            done  = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r[MediaPipe] {os.path.basename(dest)}: "
                          f"{done * 100 // total}%", end='', flush=True)
        print(f"\n[MediaPipe] {os.path.basename(dest)} ready.", flush=True)
        return True
    except Exception as e:
        print(f"\n[MediaPipe] Download failed: {e}", flush=True)
        if os.path.exists(dest):
            os.remove(dest)
        return False


@dataclass
class FaceResult:
    detected: bool
    confidence: float
    head_pitch: float   # Kalman-smoothed degrees
    head_yaw: float     # Kalman-smoothed degrees
    ear_left: float
    ear_right: float
    ear_avg: float
    gaze_x: float
    gaze_y: float
    mar: float = 0.0                  # Mouth Aspect Ratio (open mouth / talking)
    mouth_open: bool = False
    signature: tuple | None = None   # face-geometry fingerprint (None if not frontal)


# Landmark indices used for the identity signature (canonical FaceMesh points)
_SIG_PAIRS = [
    (33, 263),   # eye-to-eye outer span
    (133, 362),  # inner eye span
    (61, 291),   # mouth width
    (1, 152),    # nose tip to chin
    (168, 1),    # nose bridge to tip (nose length)
    (10, 152),   # forehead to chin (face height)
    (33, 133),   # one eye width
    (263, 362),  # other eye width
    (13, 14),    # lip thickness
    (1, 61),     # nose tip to mouth corner
    (168, 10),   # nose bridge to forehead
]
_SIG_NORM = (234, 454)   # face width — used to normalize (scale/distance invariant)


@dataclass
class PoseResult:
    detected: bool
    confidence: float
    seat_present: bool
    slouch_score: float
    distance_estimate: float


@dataclass
class HandResult:
    detected: bool
    pen_grip: bool       # thumb-index pinch = pen holding
    in_desk_area: bool   # hand in lower portion of frame
    hand_y: float        # normalized 0-1
    wrist_x: float       # normalized 0-1 wrist position (for micro-motion tracking)
    wrist_y: float       # normalized 0-1


def _null_face() -> FaceResult:
    return FaceResult(detected=False, confidence=0.0, head_pitch=0.0, head_yaw=0.0,
                      ear_left=0.3, ear_right=0.3, ear_avg=0.3, gaze_x=0.0, gaze_y=0.0,
                      mar=0.0, mouth_open=False)


def _null_pose() -> PoseResult:
    return PoseResult(detected=False, confidence=0.0, seat_present=False,
                      slouch_score=0.0, distance_estimate=50.0)


def _null_hand() -> HandResult:
    return HandResult(detected=False, pen_grip=False, in_desk_area=False,
                      hand_y=0.5, wrist_x=0.5, wrist_y=0.5)


def _make_kalman() -> cv2.KalmanFilter:
    """Constant-velocity Kalman filter for [pitch, yaw, d_pitch, d_yaw]."""
    dt = 1.0 / config.TARGET_FPS
    kf = cv2.KalmanFilter(4, 2)
    kf.transitionMatrix = np.array([
        [1, 0, dt, 0],
        [0, 1,  0, dt],
        [0, 0,  1,  0],
        [0, 0,  0,  1],
    ], dtype=np.float32)
    kf.measurementMatrix = np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
    ], dtype=np.float32)
    kf.processNoiseCov     = np.eye(4, dtype=np.float32) * 0.03
    kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 5.0
    kf.errorCovPost        = np.eye(4, dtype=np.float32)
    kf.statePost           = np.zeros((4, 1), dtype=np.float32)
    return kf


class MediaPipeModule:
    def __init__(self):
        self._face_lm        = None
        self._pose_lm        = None
        self._hand_lm        = None
        self._ts_ms          = 0
        self._kf             = _make_kalman()
        self._kf_initialized = False
        # Raw landmarks kept from the last frame, for the debug overlay
        self._dbg_face_lm    = None
        self._dbg_hand_lm    = None
        self._init()

    def _init(self) -> None:
        if not os.path.exists(_FACE_MODEL) or not os.path.exists(_POSE_MODEL):
            print(f"[MediaPipe] Core model files missing in {_MODEL_DIR}. "
                  "Face/pose tracking disabled.", flush=True)
            return
        try:
            RunningMode = mp.tasks.vision.RunningMode
            BaseOptions = mp.tasks.BaseOptions

            face_opts = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=_FACE_MODEL),
                running_mode=RunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=config.FACE_CONFIDENCE_MIN,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._face_lm = mp.tasks.vision.FaceLandmarker.create_from_options(face_opts)

            pose_opts = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=_POSE_MODEL),
                running_mode=RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=config.FACE_CONFIDENCE_MIN,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._pose_lm = mp.tasks.vision.PoseLandmarker.create_from_options(pose_opts)
            print("[MediaPipe] FaceLandmarker + PoseLandmarker + Kalman filter ready.",
                  flush=True)
        except Exception as e:
            print(f"[MediaPipe] Init error: {e}", flush=True)
            self._face_lm = None
            self._pose_lm = None

        # HandLandmarker — optional, download if missing, skip if unavailable
        try:
            if _download_model(_HAND_URL, _HAND_MODEL):
                BaseOptions = mp.tasks.BaseOptions
                hand_opts = mp.tasks.vision.HandLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=_HAND_MODEL),
                    running_mode=mp.tasks.vision.RunningMode.VIDEO,
                    num_hands=2,   # track both hands — pick the pen hand
                    min_hand_detection_confidence=0.6,
                    min_hand_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._hand_lm = mp.tasks.vision.HandLandmarker.create_from_options(hand_opts)
                print("[MediaPipe] HandLandmarker ready (pen-grip detection active).",
                      flush=True)
        except Exception as e:
            print(f"[MediaPipe] HandLandmarker skipped (optical flow fallback): {e}",
                  flush=True)
            self._hand_lm = None

    def process(self, frame: np.ndarray) -> tuple[FaceResult, PoseResult, HandResult]:
        if self._face_lm is None:
            return _null_face(), _null_pose(), _null_hand()

        self._ts_ms += int(1000.0 / config.TARGET_FPS)
        rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        try:
            fr   = self._face_lm.detect_for_video(mp_image, self._ts_ms)
            face = self._parse_face(fr, frame.shape)
            self._dbg_face_lm = fr.face_landmarks[0] if fr.face_landmarks else None
        except Exception as e:
            print(f"[MediaPipe] Face error: {e}", flush=True)
            face = _null_face()
            self._dbg_face_lm = None

        try:
            pr   = self._pose_lm.detect_for_video(mp_image, self._ts_ms)
            pose = self._parse_pose(pr, frame.shape)
        except Exception as e:
            print(f"[MediaPipe] Pose error: {e}", flush=True)
            pose = _null_pose()

        hand = _null_hand()
        self._dbg_hand_lm = None
        if self._hand_lm is not None:
            try:
                hr   = self._hand_lm.detect_for_video(mp_image, self._ts_ms)
                hand = self._parse_hand(hr)
                self._dbg_hand_lm = hr.hand_landmarks if hr.hand_landmarks else None
            except Exception as e:
                print(f"[MediaPipe] Hand error: {e}", flush=True)

        return face, pose, hand

    # Hand skeleton connections (MediaPipe Hands topology)
    _HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),        # thumb
        (0, 5), (5, 6), (6, 7), (7, 8),        # index
        (5, 9), (9, 10), (10, 11), (11, 12),   # middle
        (9, 13), (13, 14), (14, 15), (15, 16), # ring
        (13, 17), (17, 18), (18, 19), (19, 20),# pinky
        (0, 17),                               # palm base
    ]

    def draw_debug(self, frame: np.ndarray, face: FaceResult, pose: PoseResult,
                   hand: HandResult | None = None) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]
        color = (0, 255, 0) if face.detected else (0, 0, 255)

        # ── Draw FACE box + key points ───────────────────────────────────────
        if self._dbg_face_lm is not None:
            xs = [lm.x for lm in self._dbg_face_lm]
            ys = [lm.y for lm in self._dbg_face_lm]
            x1, y1 = int(min(xs) * w), int(min(ys) * h)
            x2, y2 = int(max(xs) * w), int(max(ys) * h)
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(out, "FACE", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            # Highlight eyes, nose, mouth corners
            for idx in (33, 263, 133, 362, 1, 61, 291):
                if idx < len(self._dbg_face_lm):
                    lm = self._dbg_face_lm[idx]
                    cv2.circle(out, (int(lm.x * w), int(lm.y * h)), 2, (255, 255, 0), -1)

        # ── Draw HAND skeleton(s) — both hands ───────────────────────────────
        if self._dbg_hand_lm is not None:
            for hand_lm in self._dbg_hand_lm:
                pts  = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lm]
                grip = self._detect_pen_grip(hand_lm)
                hand_col = (0, 0, 255) if grip else (0, 200, 255)
                for a, b in self._HAND_CONNECTIONS:
                    if a < len(pts) and b < len(pts):
                        cv2.line(out, pts[a], pts[b], hand_col, 2)
                for p in pts:
                    cv2.circle(out, p, 3, hand_col, -1)
                label = "PEN GRIP" if grip else "HAND"
                cv2.putText(out, label, (pts[0][0] - 20, pts[0][1] + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, hand_col, 2)

        # ── Text readouts (top-left) ─────────────────────────────────────────
        cv2.putText(out, f"Pitch:{face.head_pitch:.1f} Yaw:{face.head_yaw:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cv2.putText(out, f"EAR:{face.ear_avg:.2f} GazeX:{face.gaze_x:.2f}", (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cv2.putText(out, f"Seat:{pose.seat_present} Slouch:{pose.slouch_score:.2f}", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
        if hand is not None:
            grip_txt = "PEN" if hand.pen_grip else "---"
            cv2.putText(out, f"Hand:{hand.detected} Grip:{grip_txt}", (10, 105),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
        return out

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse_face(self, result, frame_shape) -> FaceResult:
        if not result.face_landmarks:
            if self._kf_initialized:
                self._kf.predict()
            return _null_face()
        lm    = result.face_landmarks[0]
        ear_l = self._ear(lm, LEFT_EYE_IDX)
        ear_r = self._ear(lm, RIGHT_EYE_IDX)
        raw_pitch, raw_yaw = self._head_pose(lm, frame_shape)
        gx, gy = self._gaze(lm)
        mar    = self._mar(lm)

        # Seed Kalman state on first detection
        if not self._kf_initialized:
            self._kf.statePost[0, 0] = raw_pitch
            self._kf.statePost[1, 0] = raw_yaw
            self._kf_initialized = True

        measurement = np.array([[raw_pitch], [raw_yaw]], dtype=np.float32)
        self._kf.correct(measurement)
        predicted = self._kf.predict()
        pitch = float(predicted[0, 0])   # (4,1) array — need [row, col]
        yaw   = float(predicted[1, 0])

        # Identity signature — only when near-frontal (head turns distort geometry)
        signature = None
        if abs(raw_yaw) < config.IDENTITY_FRONTAL_DEG and \
           abs(raw_pitch) < config.IDENTITY_FRONTAL_DEG:
            signature = self._face_signature(lm)

        return FaceResult(
            detected=True, confidence=0.9,
            head_pitch=pitch, head_yaw=yaw,
            ear_left=ear_l, ear_right=ear_r, ear_avg=(ear_l + ear_r) / 2.0,
            gaze_x=gx, gaze_y=gy,
            mar=mar, mouth_open=mar > config.MAR_OPEN_THRESHOLD,
            signature=signature,
        )

    def _mar(self, lm) -> float:
        """Mouth Aspect Ratio: vertical lip gap / mouth width. High = mouth open."""
        def d(a, b): return math.sqrt((lm[a].x - lm[b].x)**2 + (lm[a].y - lm[b].y)**2)
        try:
            vertical   = d(13, 14)          # inner upper lip ↔ inner lower lip
            horizontal = d(61, 291) + 1e-6  # mouth corner ↔ mouth corner
            return vertical / horizontal
        except (IndexError, AttributeError):
            return 0.0

    def _face_signature(self, lm) -> tuple | None:
        """Normalized facial-proportion fingerprint — person-specific, scale-invariant."""
        def d(a, b): return math.sqrt((lm[a].x - lm[b].x)**2 + (lm[a].y - lm[b].y)**2)
        try:
            norm = d(_SIG_NORM[0], _SIG_NORM[1])
            if norm < 1e-6:
                return None
            return tuple(d(a, b) / norm for a, b in _SIG_PAIRS)
        except (IndexError, AttributeError):
            return None

    def _parse_pose(self, result, frame_shape) -> PoseResult:
        if not result.pose_landmarks:
            return _null_pose()
        lm     = result.pose_landmarks[0]
        seat   = self._seat(lm)
        slouch = self._slouch(lm)
        dist   = self._distance(lm)
        return PoseResult(detected=True, confidence=0.8,
                          seat_present=seat, slouch_score=slouch,
                          distance_estimate=dist)

    def _parse_hand(self, result) -> HandResult:
        if not result.hand_landmarks:
            return _null_hand()

        # Evaluate every detected hand, then choose the "writing hand":
        #   1st choice: a hand with a pen grip inside the desk area
        #   fallback : the lowest hand in the desk area (closest to paper)
        candidates = []
        for lm in result.hand_landmarks:
            hand_y  = float(np.mean([lm[i].y for i in range(21)]))
            in_desk = hand_y > config.YOLO_DESK_ROI_FRAC
            grip    = self._detect_pen_grip(lm)
            candidates.append((lm, hand_y, in_desk, grip))

        pen_hands = [c for c in candidates if c[3] and c[2]]   # grip AND in desk
        if pen_hands:
            lm, hand_y, in_desk, grip = max(pen_hands, key=lambda c: c[1])
        else:
            lm, hand_y, in_desk, grip = max(candidates, key=lambda c: c[1])

        return HandResult(detected=True, pen_grip=grip,
                          in_desk_area=in_desk, hand_y=hand_y,
                          wrist_x=float(lm[_WRIST].x), wrist_y=float(lm[_WRIST].y))

    def _detect_pen_grip(self, lm) -> bool:
        """Normalized pinch ratio: thumb tip to index tip distance vs hand scale."""
        def d2(a, b): return math.sqrt((a.x - b.x)**2 + (a.y - b.y)**2)
        pinch      = d2(lm[_THUMB_TIP], lm[_INDEX_TIP])
        hand_scale = d2(lm[_WRIST], lm[_INDEX_MCP]) + 1e-6
        return (pinch / hand_scale) < 0.50

    # ── Geometry ──────────────────────────────────────────────────────────────

    def _ear(self, lm, indices: list[int]) -> float:
        pts = [(lm[i].x, lm[i].y) for i in indices]
        def d(a, b): return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)
        return (d(pts[1], pts[5]) + d(pts[2], pts[4])) / (2.0 * d(pts[0], pts[3]) + 1e-6)

    def _head_pose(self, lm, frame_shape) -> tuple[float, float]:
        h, w = frame_shape[:2]
        face_2d = np.array([[lm[i].x * w, lm[i].y * h] for i in FACE_3D_INDICES],
                            dtype=np.float64)
        focal = float(w)
        cam   = np.array([[focal, 0, w/2], [0, focal, h/2], [0, 0, 1]], dtype=np.float64)
        ok, rvec, _ = cv2.solvePnP(FACE_3D_MODEL, face_2d, cam, np.zeros((4, 1)))
        if not ok:
            return 0.0, 0.0
        rmat, _ = cv2.Rodrigues(rvec)
        angles, *_ = cv2.RQDecomp3x3(rmat)
        # RQDecomp3x3 already returns Euler angles in DEGREES — do NOT scale by 360.
        pitch, yaw = float(angles[0]), float(angles[1])
        # solvePnP can flip pitch to ~±180 when looking down; normalize to [-90, 90]
        if pitch > 90:
            pitch -= 180
        elif pitch < -90:
            pitch += 180
        return pitch, yaw

    def _gaze(self, lm) -> tuple[float, float]:
        try:
            li, ri = lm[468], lm[473]
            l_cx = (lm[133].x + lm[33].x) / 2
            r_cx = (lm[362].x + lm[263].x) / 2
            lw   = abs(lm[33].x  - lm[133].x) + 1e-6
            rw   = abs(lm[263].x - lm[362].x) + 1e-6
            gx   = ((li.x - l_cx) / lw + (ri.x - r_cx) / rw) / 2.0
            gy   = (li.y + ri.y) / 2.0 - 0.5
            return float(gx), float(gy)
        except (IndexError, AttributeError):
            return 0.0, 0.0

    def _seat(self, lm) -> bool:
        ls, rs = lm[_L_SHOULDER], lm[_R_SHOULDER]
        return ls.visibility > 0.5 and rs.visibility > 0.5 and ls.y < 0.85

    def _slouch(self, lm) -> float:
        ear_y      = (lm[_L_EAR].y + lm[_R_EAR].y) / 2
        shoulder_y = (lm[_L_SHOULDER].y + lm[_R_SHOULDER].y) / 2
        diff = shoulder_y - ear_y
        return max(0.0, min(1.0, 1.0 - (diff - 0.05) / 0.25))

    def _distance(self, lm) -> float:
        w = abs(lm[_R_SHOULDER].x - lm[_L_SHOULDER].x)
        return 100.0 if w < 1e-4 else 30.0 / w


if __name__ == "__main__":
    from vision.capture import CameraCapture
    cam = CameraCapture()
    cam.start()
    module = MediaPipeModule()
    print("MediaPipe module running. Press 'q' to quit.")
    while True:
        frame = cam.get_frame()
        if frame is not None:
            face, pose, hand = module.process(frame)
            debug = module.draw_debug(frame, face, pose, hand)
            cv2.imshow("MediaPipe Debug", debug)
            if face.detected:
                print(f"Face: pitch={face.head_pitch:.1f} yaw={face.head_yaw:.1f} "
                      f"ear={face.ear_avg:.2f} | Hand: grip={hand.pen_grip}")
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cam.stop()
    cv2.destroyAllWindows()
