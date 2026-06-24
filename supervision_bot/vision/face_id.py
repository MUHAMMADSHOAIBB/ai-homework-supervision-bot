"""
face_id.py — ArcFace-based face recognition using InsightFace.

Replaces the geometric-ratio identity system with real deep embeddings:
  - Detects ALL faces in each frame (multi-person support)
  - During PREPARE: enrolls the child (avg of N embeddings)
  - During FOCUS: compares every face against the child's embedding
  - Cosine similarity >= FACE_SIMILARITY_THRESHOLD → same person
  - Any other face while child enrolled → STRANGER alert

Install deps once:
    pip install insightface onnxruntime
"""

from __future__ import annotations
import os
import sys
import numpy as np
import cv2
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config

_IF_OK = False
_FaceAnalysis = None
try:
    from insightface.app import FaceAnalysis as _FaceAnalysis  # type: ignore
    _IF_OK = True
except ImportError:
    pass


@dataclass
class PersonDetection:
    bbox: tuple[int, int, int, int]   # (x1, y1, x2, y2)
    det_score: float                   # detection confidence 0–1
    embedding: np.ndarray | None       # 512-dim ArcFace embedding (normalized)
    is_child: bool = False             # matches registered child
    is_stranger: bool = False          # registered child exists and this isn't them
    similarity: float = 0.0           # cosine similarity to child (-1 to 1)


@dataclass
class FaceIDResult:
    faces: list[PersonDetection] = field(default_factory=list)
    person_count: int = 0
    child_present: bool = False
    stranger_present: bool = False    # someone who is NOT the child is in frame


class FaceIdentifier:
    """
    Drop-in upgrade for the geometric identity system.
    Uses InsightFace buffalo_sc (SCRFD detector + MobileFaceNet ArcFace).
    Falls back silently if insightface is not installed.
    """

    def __init__(self):
        self._app = None
        self._child_emb: np.ndarray | None = None   # registered child embedding
        self._enroll_buf: list[np.ndarray] = []      # collected during PREPARE
        self._threshold = config.FACE_SIMILARITY_THRESHOLD
        self._initialized = False
        # Throttle: run ArcFace max N times/sec (heavy on CPU)
        self._last_identify_time: float = 0.0
        self._last_enroll_time:   float = 0.0
        self._last_result: FaceIDResult = FaceIDResult()
        self._init()

    def _init(self) -> None:
        if not _IF_OK:
            print("[FaceID] insightface not installed — run:\n"
                  "         pip install insightface onnxruntime\n"
                  "         Identity will fall back to geometry mode.", flush=True)
            return
        try:
            self._app = _FaceAnalysis(
                name='buffalo_sc',
                providers=['CPUExecutionProvider'],
            )
            # det_size must be multiple of 32; 320 is fast on CPU
            self._app.prepare(ctx_id=0, det_size=(320, 320))
            self._initialized = True
            print("[FaceID] InsightFace buffalo_sc ready "
                  "(ArcFace embeddings + multi-face detection).", flush=True)
        except Exception as e:
            print(f"[FaceID] Init failed: {e} — falling back to geometry mode.", flush=True)
            self._app = None

    # ── Enrollment (call during PREPARE) ─────────────────────────────────────

    def enroll_frame(self, frame: np.ndarray) -> int:
        """
        Feed one frame during PREPARE.
        Returns number of embeddings collected so far.
        """
        if not self._initialized or self._app is None:
            return 0
        import time
        now = time.monotonic()
        # Enroll at most 2 frames/sec — no need to run faster
        if now - self._last_enroll_time < 0.5:
            return len(self._enroll_buf)
        self._last_enroll_time = now
        try:
            faces = self._app.get(frame)
        except Exception:
            return len(self._enroll_buf)
        if not faces:
            return len(self._enroll_buf)
        # Pick the largest face (closest to camera = child)
        biggest = max(faces, key=lambda f: _face_area(f.bbox))
        if biggest.embedding is not None and float(biggest.det_score) >= 0.6:
            emb = _normalize(biggest.embedding)
            self._enroll_buf.append(emb)
        return len(self._enroll_buf)

    def finalize_enrollment(self) -> bool:
        """
        Average collected embeddings → one stable child embedding.
        Called when PREPARE → FOCUS transition fires.
        """
        n = len(self._enroll_buf)
        if n < config.FACE_ENROLL_MIN_FRAMES:
            print(f"[FaceID] Only {n} enrollment frames — need "
                  f"{config.FACE_ENROLL_MIN_FRAMES}. "
                  "Keep your face visible during the Prepare phase.", flush=True)
            return False
        avg = np.mean(self._enroll_buf, axis=0)
        self._child_emb = _normalize(avg)
        self._enroll_buf.clear()
        print(f"[FaceID] Child enrolled from {n} frames — "
              "identity guard active.", flush=True)
        return True

    # ── Per-frame identification ──────────────────────────────────────────────

    def identify(self, frame: np.ndarray) -> FaceIDResult:
        """Run at most 2×/sec. Returns cached result between runs."""
        if not self._initialized or self._app is None:
            return self._last_result
        import time
        now = time.monotonic()
        # Run ArcFace max 2 times per second — it's heavy on CPU
        if now - self._last_identify_time < 0.5:
            return self._last_result
        self._last_identify_time = now
        try:
            raw_faces = self._app.get(frame)
        except Exception:
            return self._last_result
        if not raw_faces:
            self._last_result = FaceIDResult()
            return self._last_result

        persons: list[PersonDetection] = []
        child_present = False
        stranger_present = False

        for f in raw_faces:
            bbox = _to_int_bbox(f.bbox)
            emb = None
            is_child = False
            is_stranger = False
            sim = 0.0

            if f.embedding is not None:
                emb = _normalize(f.embedding)
                if self._child_emb is not None:
                    sim = float(np.dot(emb, self._child_emb))
                    is_child = sim >= self._threshold
                    is_stranger = not is_child   # child enrolled → others are strangers

            if is_child:
                child_present = True
            if is_stranger and self._child_emb is not None:
                stranger_present = True

            persons.append(PersonDetection(
                bbox=bbox,
                det_score=float(f.det_score),
                embedding=emb,
                is_child=is_child,
                is_stranger=is_stranger,
                similarity=sim,
            ))

        # Sort largest face first
        persons.sort(key=lambda p: _bbox_area(p.bbox), reverse=True)

        self._last_result = FaceIDResult(
            faces=persons,
            person_count=len(persons),
            child_present=child_present,
            stranger_present=stranger_present,
        )
        return self._last_result

    # ── Annotated frame for live view ─────────────────────────────────────────

    def draw(self, frame: np.ndarray, result: FaceIDResult) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]

        for det in result.faces:
            x1, y1, x2, y2 = det.bbox
            # Clamp to frame
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if self._child_emb is None:
                # Not enrolled yet — show all faces as orange (unknown)
                color = (0, 165, 255)
                label = f"FACE {det.det_score:.2f}"
            elif det.is_child:
                color = (0, 220, 0)
                label = f"CHILD  {det.similarity:.2f}"
            elif det.is_stranger:
                color = (0, 0, 255)
                label = f"STRANGER  {det.similarity:.2f}"
            else:
                color = (0, 165, 255)
                label = f"? {det.det_score:.2f}"

            cv2.rectangle(out, (x1, y1), (x2, y2), color, 3)
            # Label background pill
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            by1 = max(0, y1 - th - 10)
            cv2.rectangle(out, (x1, by1), (x1 + tw + 8, by1 + th + 8), color, -1)
            cv2.putText(out, label, (x1 + 4, by1 + th + 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Banner when stranger in frame
        if result.stranger_present:
            cv2.rectangle(out, (0, 0), (w, 36), (0, 0, 200), -1)
            cv2.putText(out, f"  STRANGER DETECTED  ({result.person_count} person(s))",
                        (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        elif result.person_count > 1 and self._child_emb is not None:
            cv2.rectangle(out, (0, 0), (w, 36), (0, 120, 220), -1)
            cv2.putText(out, f"  MULTIPLE PEOPLE: {result.person_count}",
                        (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return out

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_enrolled(self) -> bool:
        return self._child_emb is not None

    @property
    def available(self) -> bool:
        return self._initialized

    def reset(self) -> None:
        self._child_emb = None
        self._enroll_buf.clear()


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / (n + 1e-9)


def _face_area(bbox) -> float:
    return max(0.0, float(bbox[2] - bbox[0])) * max(0.0, float(bbox[3] - bbox[1]))


def _to_int_bbox(bbox) -> tuple[int, int, int, int]:
    return (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))


def _bbox_area(bbox: tuple) -> float:
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
