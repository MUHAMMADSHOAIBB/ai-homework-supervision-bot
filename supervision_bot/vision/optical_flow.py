import numpy as np
import cv2
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config


class OpticalFlowModule:
    def __init__(self, roi: tuple[int, int, int, int] | None = None):
        self._roi = roi  # (x1, y1, x2, y2)
        self._prev_gray: np.ndarray | None = None

    def set_roi(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self._roi = (x1, y1, x2, y2)
        self._prev_gray = None  # Reset on ROI change

    def process(self, frame: np.ndarray) -> float:
        """Returns writing_activity_score (0.0 to 100.0). Higher = more motion in desk ROI."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self._roi is None:
            # Default: lower-center 40% of frame
            h, w = gray.shape
            x1 = w // 4
            y1 = int(h * 0.55)
            x2 = w * 3 // 4
            y2 = h
            roi_gray = gray[y1:y2, x1:x2]
        else:
            x1, y1, x2, y2 = self._roi
            roi_gray = gray[y1:y2, x1:x2]

        if self._prev_gray is None:
            self._prev_gray = gray.copy()
            return 0.0

        # Compute global flow to subtract camera/head motion
        prev_roi = self._prev_gray[y1:y2, x1:x2] if self._roi is None else \
                   self._prev_gray[self._roi[1]:self._roi[3], self._roi[0]:self._roi[2]]

        score = self._compute_farneback(prev_roi, roi_gray)
        self._prev_gray = gray.copy()
        return min(100.0, score)

    def reset(self) -> None:
        self._prev_gray = None

    def _compute_farneback(self, prev_gray: np.ndarray, curr_gray: np.ndarray) -> float:
        if prev_gray.shape != curr_gray.shape or prev_gray.size == 0:
            return 0.0
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2,
            flags=0
        )
        # Compute mean magnitude of flow vectors
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])

        # Subtract global motion (median) to remove head/body movement
        global_motion = float(np.median(mag))
        local_motion = float(np.mean(mag))
        adjusted = max(0.0, local_motion - global_motion * 0.5)

        # Scale to 0-100: motion of ~2px/frame maps to score ~50
        score = adjusted * 25.0
        return score


if __name__ == "__main__":
    from vision.capture import CameraCapture
    cam = CameraCapture()
    cam.start()
    flow = OpticalFlowModule()
    print("Optical flow running. Move hand over desk ROI. Press 'q' to quit.")
    import time
    while True:
        frame = cam.get_frame()
        if frame is not None:
            score = flow.process(frame)
            status = "WRITING" if score > config.FLOW_IDLE_THRESHOLD else "IDLE"
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (w//4, int(h*0.55)), (w*3//4, h), (0, 255, 255), 2)
            cv2.putText(frame, f"Flow:{score:.1f} [{status}]", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Optical Flow", frame)
            print(f"\rFlow score: {score:.2f} [{status}]", end="")
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cam.stop()
    cv2.destroyAllWindows()
