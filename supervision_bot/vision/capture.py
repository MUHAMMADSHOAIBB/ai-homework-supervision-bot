import threading
import collections
import time
import cv2
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config


class CameraCapture:
    """Runs in a background thread. Puts frames into a deque buffer."""

    def __init__(self, camera_index=config.CAMERA_INDEX,
                 width=config.FRAME_WIDTH, height=config.FRAME_HEIGHT,
                 fps=config.TARGET_FPS):
        self._camera_index = camera_index
        self._width = width
        self._height = height
        self._fps = fps
        self._buffer: collections.deque = collections.deque(maxlen=2)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._cap: cv2.VideoCapture | None = None
        self._camera_error: str | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap and self._cap.isOpened():
            self._cap.release()

    def get_frame(self) -> np.ndarray | None:
        if not self._buffer:
            return None
        return self._buffer[-1]

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _capture_loop(self) -> None:
        try:
            # Try DirectShow first on Windows (more reliable than MSMF)
            import sys as _sys
            if _sys.platform == "win32":
                self._cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
            else:
                self._cap = cv2.VideoCapture(self._camera_index)
            if not self._cap.isOpened():
                print(f"[Camera] ERROR: Cannot open camera index {self._camera_index}. "
                      f"Try a different index via CAMERA_INDEX in config.py", flush=True)
                self._camera_error = "cannot_open"
                return
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._cap.set(cv2.CAP_PROP_FPS, self._fps)
            print(f"[Camera] Opened camera index {self._camera_index} OK", flush=True)
            self._camera_error = None
            interval = 1.0 / self._fps
            consecutive_failures = 0
            while not self._stop_event.is_set():
                t0 = time.monotonic()
                ret, frame = self._cap.read()
                if ret and frame is not None:
                    self._buffer.append(frame)
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures == 30:
                        print(f"[Camera] WARNING: 30 consecutive read failures — "
                              f"camera may be disconnected or in use", flush=True)
                elapsed = time.monotonic() - t0
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except Exception as e:
            print(f"[Camera] FATAL error in capture loop: {e}", flush=True)
            self._camera_error = str(e)
        finally:
            if self._cap and self._cap.isOpened():
                self._cap.release()


if __name__ == "__main__":
    cam = CameraCapture()
    cam.start()
    print("Camera started. Press 'q' to quit.")
    while True:
        frame = cam.get_frame()
        if frame is not None:
            cv2.imshow("Camera Test", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cam.stop()
    cv2.destroyAllWindows()
