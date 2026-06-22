import numpy as np
import cv2
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

EXPRESSION_MAP = {
    "IDLE":        ("😴", "Standby",      (100, 100, 100)),
    "PREPARE":     ("🔧", "Getting Ready", (50,  150,  50)),
    "FOCUS":       ("📚", "Focused",       (50,  100, 200)),
    "CONCERNED":   ("🤔", "Hmm...",        (200, 150,  50)),
    "PHONE_ALERT": ("📵", "No Phone!",     (200,  50,  50)),
    "GOOD_FOCUS":  ("⭐", "Great Work!",   (50,  180,  50)),
    "BREAK":       ("☕", "Break Time",    (50,  180, 100)),
    "FATIGUE":     ("😪", "Stay Awake!",   (180, 100,  50)),
    "COMPLETE":    ("🎉", "Well Done!",    (180,  50, 180)),
}


class ExpressionDisplay:
    def __init__(self, window_name: str = "Bot Expression"):
        self._window_name = window_name
        self._current_state = "IDLE"
        self._canvas = np.zeros((200, 400, 3), dtype=np.uint8)

    def show(self, state: str) -> None:
        self._current_state = state
        self._canvas[:] = 30  # Dark background

        expr = EXPRESSION_MAP.get(state, EXPRESSION_MAP["IDLE"])
        emoji, label, color = expr

        # Draw colored header band
        cv2.rectangle(self._canvas, (0, 0), (400, 60), color, -1)

        # State label
        cv2.putText(self._canvas, f"[{state}]", (10, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

        # Description
        cv2.putText(self._canvas, label, (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # Draw bot "face" as simple circles
        cx, cy = 320, 110
        cv2.circle(self._canvas, (cx, cy), 50, color, 2)
        cv2.circle(self._canvas, (cx - 15, cy - 10), 8, (255, 255, 255), -1)
        cv2.circle(self._canvas, (cx + 15, cy - 10), 8, (255, 255, 255), -1)

        if state in ("FOCUS", "GOOD_FOCUS"):
            cv2.ellipse(self._canvas, (cx, cy + 15), (20, 10), 0, 0, 180, (255, 255, 255), 2)
        elif state in ("PHONE_ALERT", "FATIGUE", "CONCERNED"):
            cv2.ellipse(self._canvas, (cx, cy + 25), (20, 10), 0, 180, 360, (255, 255, 255), 2)
        else:
            cv2.line(self._canvas, (cx - 15, cy + 20), (cx + 15, cy + 20), (255, 255, 255), 2)

        cv2.imshow(self._window_name, self._canvas)
        cv2.waitKey(1)

    def update_debug_frame(self, frame: np.ndarray) -> None:
        expr = EXPRESSION_MAP.get(self._current_state, EXPRESSION_MAP["IDLE"])
        _, label, color = expr
        cv2.putText(frame, f"Bot: {self._current_state}", (frame.shape[1] - 200, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    def close(self) -> None:
        cv2.destroyWindow(self._window_name)
