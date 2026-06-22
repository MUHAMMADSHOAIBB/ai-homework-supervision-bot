import time
from typing import Callable
from transitions import Machine
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config

STATES = ["IDLE", "PREPARE", "FOCUS", "BREAK", "RESUME_CHECK", "COMPLETE"]

TRANSITIONS = [
    {"trigger": "start_session",  "source": "IDLE",         "dest": "PREPARE"},
    {"trigger": "ready",          "source": "PREPARE",      "dest": "FOCUS"},
    {"trigger": "focus_complete", "source": "FOCUS",        "dest": "BREAK"},
    {"trigger": "break_complete", "source": "BREAK",        "dest": "RESUME_CHECK"},
    {"trigger": "child_returned", "source": "RESUME_CHECK", "dest": "FOCUS"},
    {"trigger": "session_end",    "source": "*",            "dest": "COMPLETE"},
    {"trigger": "reset",          "source": "*",            "dest": "IDLE"},
]

_STATE_DURATIONS = {
    "PREPARE":      config.PREPARE_DURATION,
    "FOCUS":        config.FOCUS_DURATION,
    "BREAK":        config.SHORT_BREAK,
    "RESUME_CHECK": 30,
}


class PomodoroMachine:
    def __init__(self, on_state_change: Callable[[str, str], None] | None = None):
        self._on_state_change = on_state_change
        self._machine = Machine(
            model=self,
            states=STATES,
            transitions=TRANSITIONS,
            initial="IDLE",
            after_state_change="_after_state_change",
        )
        self._state_start: float = time.monotonic()
        self._round_number: int = 1
        self._total_focus: int = 0
        self._prev_state: str = "IDLE"

    def _after_state_change(self) -> None:
        old = self._prev_state
        new = self.state
        self._prev_state = new
        self._state_start = time.monotonic()
        if self._on_state_change:
            self._on_state_change(old, new)

    def tick(self) -> None:
        elapsed = int(time.monotonic() - self._state_start)
        state = self.state

        if state == "PREPARE" and elapsed >= config.PREPARE_DURATION:
            self.ready()
        elif state == "FOCUS":
            self._total_focus += 1
            duration = self._long_or_short_break_duration()
            if elapsed >= config.FOCUS_DURATION:
                self.focus_complete()
        elif state == "BREAK":
            dur = self._long_or_short_break_duration()
            if elapsed >= dur:
                self._round_number += 1
                self.break_complete()
        elif state == "RESUME_CHECK" and elapsed >= 30:
            # Auto-resume if child returned (seat presence checked externally)
            self.child_returned()

    def force_break(self) -> None:
        if self.state == "FOCUS":
            self.focus_complete()

    def manual_start(self) -> None:
        if self.state == "IDLE":
            self.start_session()

    @property
    def current_state(self) -> str:
        return self.state

    @property
    def elapsed_seconds(self) -> int:
        return int(time.monotonic() - self._state_start)

    @property
    def round_number(self) -> int:
        return self._round_number

    @property
    def total_focus_today(self) -> int:
        return self._total_focus

    def _long_or_short_break_duration(self) -> int:
        if self._round_number % config.ROUNDS_BEFORE_LONG == 0:
            return config.LONG_BREAK
        return config.SHORT_BREAK


if __name__ == "__main__":
    import config as cfg
    # Override durations for testing
    cfg.PREPARE_DURATION = 2
    cfg.FOCUS_DURATION   = 5
    cfg.SHORT_BREAK      = 3

    events = []

    def on_change(old, new):
        print(f"  State: {old} → {new}")
        events.append((old, new))

    m = PomodoroMachine(on_state_change=on_change)
    m.manual_start()

    print("Running mock 30-second session test...")
    for i in range(30):
        time.sleep(1)
        m.tick()
        print(f"t={i+1}s state={m.current_state} elapsed={m.elapsed_seconds}s")
        if m.current_state == "COMPLETE":
            break

    print(f"\nTransitions observed: {events}")
    expected = {"IDLE", "PREPARE", "FOCUS", "BREAK"}
    visited   = {s for _, s in events}
    print(f"All expected states visited: {expected.issubset(visited)}")
