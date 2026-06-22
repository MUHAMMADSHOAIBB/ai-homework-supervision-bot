import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from output.script_bank import ScriptBank


def test_phone_script_contains_name():
    sb = ScriptBank(language="zh")
    sb.set_child("小明", 10)
    text = sb.get("phone_detected_high")
    assert "小明" in text, f"Expected child name in script, got: {text}"


def test_english_script_contains_name():
    sb = ScriptBank(language="en")
    text = sb.get("phone_detected_high", name="Tom")
    assert "Tom" in text


def test_repeated_calls_return_different_scripts():
    sb = ScriptBank(language="zh")
    sb.set_child("小明", 10)
    results = {sb.get("distracted_gaze_medium") for _ in range(20)}
    # With 3 templates, should get at least 2 different ones in 20 tries
    assert len(results) >= 2, "Expected random variation across calls"


def test_missing_key_raises_key_error():
    sb = ScriptBank()
    with pytest.raises(KeyError) as exc_info:
        sb.get("nonexistent_key_xyz")
    assert "nonexistent_key_xyz" in str(exc_info.value)


def test_set_child_updates_default_name():
    sb = ScriptBank(language="en")
    sb.set_child("Alice", 8)
    text = sb.get("session_start", focus_min=25)
    assert "Alice" in text


def test_focus_complete_interpolates_break_min():
    sb = ScriptBank(language="en")
    text = sb.get("focus_complete", break_min=5)
    assert "5" in text


def test_good_focus_interpolates_minutes():
    sb = ScriptBank(language="en")
    text = sb.get("good_focus_positive", minutes=10)
    assert "10" in text


def test_all_keys_have_at_least_one_template():
    sb = ScriptBank(language="zh")
    for key, templates in sb.all_scripts().items():
        assert len(templates) >= 1, f"Key '{key}' has no templates"
