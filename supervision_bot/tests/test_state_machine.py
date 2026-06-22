import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import config


def test_manual_start_transitions_to_prepare():
    from logic.state_machine import PomodoroMachine
    m = PomodoroMachine()
    assert m.current_state == "IDLE"
    m.manual_start()
    assert m.current_state == "PREPARE"


def test_tick_prepare_transitions_to_focus(monkeypatch):
    monkeypatch.setattr(config, 'PREPARE_DURATION', 0)
    from logic.state_machine import PomodoroMachine
    import importlib, logic.state_machine as sm_mod
    importlib.reload(sm_mod)
    m = sm_mod.PomodoroMachine()
    m.manual_start()
    assert m.current_state == "PREPARE"
    m.tick()
    assert m.current_state == "FOCUS"


def test_tick_focus_transitions_to_break(monkeypatch):
    monkeypatch.setattr(config, 'PREPARE_DURATION', 0)
    monkeypatch.setattr(config, 'FOCUS_DURATION', 0)
    from logic.state_machine import PomodoroMachine
    import importlib, logic.state_machine as sm_mod
    importlib.reload(sm_mod)
    m = sm_mod.PomodoroMachine()
    m.manual_start()
    m.tick()  # PREPARE → FOCUS
    assert m.current_state == "FOCUS"
    m.tick()  # FOCUS → BREAK
    assert m.current_state == "BREAK"


def test_force_break_from_focus():
    from logic.state_machine import PomodoroMachine
    m = PomodoroMachine()
    m.manual_start()
    # Manually put in FOCUS state
    m.state = "FOCUS"
    m._prev_state = "FOCUS"
    m.force_break()
    assert m.current_state == "BREAK"


def test_on_state_change_callback():
    from logic.state_machine import PomodoroMachine
    transitions_seen = []
    m = PomodoroMachine(on_state_change=lambda o, n: transitions_seen.append((o, n)))
    m.manual_start()
    assert any(n == "PREPARE" for _, n in transitions_seen)


def test_elapsed_seconds_resets_on_transition(monkeypatch):
    monkeypatch.setattr(config, 'PREPARE_DURATION', 0)
    from logic.state_machine import PomodoroMachine
    import importlib, logic.state_machine as sm_mod
    importlib.reload(sm_mod)
    m = sm_mod.PomodoroMachine()
    m.manual_start()
    time.sleep(0.05)
    m.tick()  # → FOCUS
    assert m.elapsed_seconds < 2  # reset on transition


def test_session_end_goes_to_complete():
    from logic.state_machine import PomodoroMachine
    m = PomodoroMachine()
    m.manual_start()
    m.session_end()
    assert m.current_state == "COMPLETE"


def test_reset_goes_to_idle():
    from logic.state_machine import PomodoroMachine
    m = PomodoroMachine()
    m.manual_start()
    m.reset()
    assert m.current_state == "IDLE"
