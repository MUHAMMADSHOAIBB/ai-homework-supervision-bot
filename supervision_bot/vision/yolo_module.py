import time
import numpy as np
import cv2
from dataclasses import dataclass, field
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config


@dataclass
class YoloResult:
    phone_detected: bool
    phone_confidence: float
    person_detected: bool
    book_detected: bool
    raw_detections: list[dict] = field(default_factory=list)


_PHONE_CLASSES  = {"cell phone"}
_PERSON_CLASSES = {"person"}
_BOOK_CLASSES   = {"book"}


class YoloModule:
    def __init__(self):
        self._model        = None
        self._model_name   = config.YOLO_MODEL      # yolov8s.pt — 2× more accurate than nano
        self._last_result: YoloResult = YoloResult(
            phone_detected=False, phone_confidence=0.0,
            person_detected=False, book_detected=False,
        )
        self._last_run_time = 0.0
        self._min_interval  = 0.15  # max ~7 YOLO runs/sec to spare CPU

    def process(self, frame: np.ndarray) -> YoloResult:
        now = time.monotonic()
        if (now - self._last_run_time) < self._min_interval:
            return self._last_result

        self._load_model()
        if self._model is None:
            return self._last_result

        self._last_run_time = now

        # Crop to desk area — phones are on the desk, not on the ceiling
        h, w = frame.shape[:2]
        desk_y = int(h * config.YOLO_DESK_ROI_FRAC)
        desk_roi = frame[desk_y:, :]

        results = self._model(desk_roi, verbose=False, conf=config.YOLO_CONFIDENCE_MIN)

        phone_det  = False
        phone_conf = 0.0
        person_det = False
        book_det   = False
        detections = []

        for r in results:
            for box in r.boxes:
                cls_id   = int(box.cls[0])
                cls_name = self._model.names[cls_id].lower()
                conf     = float(box.conf[0])
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                # Shift bbox back to full-frame coordinates
                y1 += desk_y
                y2 += desk_y
                detections.append({"class": cls_name, "conf": conf,
                                   "bbox": [x1, y1, x2, y2]})
                if cls_name in _PHONE_CLASSES and conf > phone_conf:
                    phone_det  = True
                    phone_conf = conf
                if cls_name in _PERSON_CLASSES:
                    person_det = True
                if cls_name in _BOOK_CLASSES:
                    book_det = True

        self._last_result = YoloResult(
            phone_detected=phone_det,
            phone_confidence=phone_conf,
            person_detected=person_det,
            book_detected=book_det,
            raw_detections=detections,
        )
        return self._last_result

    def draw_debug(self, frame: np.ndarray, result: YoloResult) -> np.ndarray:
        out = frame.copy()
        # Draw desk ROI boundary (YOLO only scans below this line)
        h, w = out.shape[:2]
        desk_y = int(h * config.YOLO_DESK_ROI_FRAC)
        cv2.line(out, (0, desk_y), (w, desk_y), (100, 100, 255), 1)
        cv2.putText(out, "desk scan zone", (w - 160, desk_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 100, 255), 1)
        for det in result.raw_detections:
            x1, y1, x2, y2 = det["bbox"]
            cls = det["class"]
            if cls in _PHONE_CLASSES:
                color, tag = (0, 0, 255), "PHONE"        # red — alert
            elif cls in _BOOK_CLASSES:
                color, tag = (0, 165, 255), "BOOK"       # orange
            elif cls in _PERSON_CLASSES:
                color, tag = (255, 150, 0), "PERSON"     # blue
            else:
                color, tag = (0, 255, 0), cls            # green — other
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            cv2.putText(out, f"{tag} {det['conf']:.2f}",
                        (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        return out

    def _load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO
            print(f"[YOLO] Loading {self._model_name}...", flush=True)
            self._model = YOLO(self._model_name)
            print(f"[YOLO] {self._model_name} ready.", flush=True)
        except Exception as e:
            print(f"[YOLO] Failed to load {self._model_name}: {e}", flush=True)
            # Try falling back to nano if small model fails
            if self._model_name != "yolov8n.pt":
                try:
                    from ultralytics import YOLO
                    print("[YOLO] Falling back to yolov8n.pt...", flush=True)
                    self._model = YOLO("yolov8n.pt")
                    print("[YOLO] yolov8n.pt ready (fallback).", flush=True)
                except Exception as e2:
                    print(f"[YOLO] Fallback also failed: {e2}", flush=True)
                    self._model = None


if __name__ == "__main__":
    from vision.capture import CameraCapture
    cam = CameraCapture()
    cam.start()
    yolo = YoloModule()
    print("YOLO module running. Hold phone over desk area. Press 'q' to quit.")
    while True:
        frame = cam.get_frame()
        if frame is not None:
            result = yolo.process(frame)
            debug  = yolo.draw_debug(frame, result)
            cv2.imshow("YOLO Debug", debug)
            if result.phone_detected:
                print(f"PHONE DETECTED! conf={result.phone_confidence:.2f}")
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cam.stop()
    cv2.destroyAllWindows()
