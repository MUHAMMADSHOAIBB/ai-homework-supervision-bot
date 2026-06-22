import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vision.feature_aggregator import FeatureAggregator
from vision.mediapipe_module import FaceResult, PoseResult
from vision.yolo_module import YoloResult


def _make_face(detected=True, ear_avg=0.3, yaw=0.0, gaze_x=0.0):
    return FaceResult(detected=detected, confidence=0.9, head_pitch=0.0, head_yaw=yaw,
                      ear_left=ear_avg, ear_right=ear_avg, ear_avg=ear_avg,
                      gaze_x=gaze_x, gaze_y=0.0)

def _make_pose(seat=True):
    return PoseResult(detected=True, confidence=0.8, seat_present=seat,
                      slouch_score=0.0, distance_estimate=50.0)

def _make_yolo(phone=False, person=True):
    return YoloResult(phone_detected=phone, phone_confidence=0.8 if phone else 0.0,
                      person_detected=person, book_detected=False)


def test_phone_propagates():
    agg = FeatureAggregator()
    yolo = _make_yolo(phone=True)
    fv = agg.update(_make_face(), _make_pose(), yolo, 50.0)
    assert fv.phone_detected is True
    assert fv.phone_confidence > 0.0


def test_phone_false_when_not_detected():
    agg = FeatureAggregator()
    fv = agg.update(_make_face(), _make_pose(), _make_yolo(phone=False), 50.0)
    assert fv.phone_detected is False


def test_ear_rolling_average():
    agg = FeatureAggregator(window_seconds=1)
    for _ in range(3):
        fv = agg.update(_make_face(ear_avg=0.15), _make_pose(), _make_yolo(), 50.0)
    assert fv.ear_avg < 0.20, f"Expected ear_avg < 0.20, got {fv.ear_avg}"


def test_ear_normal_above_threshold():
    agg = FeatureAggregator(window_seconds=1)
    for _ in range(3):
        fv = agg.update(_make_face(ear_avg=0.35), _make_pose(), _make_yolo(), 50.0)
    assert fv.ear_avg > 0.20


def test_face_present_propagates():
    agg = FeatureAggregator()
    fv = agg.update(_make_face(detected=True), _make_pose(), _make_yolo(), 50.0)
    assert fv.face_present is True

def test_face_absent_propagates():
    agg = FeatureAggregator()
    fv = agg.update(_make_face(detected=False), _make_pose(), _make_yolo(), 50.0)
    assert fv.face_present is False


def test_reset_clears_state():
    agg = FeatureAggregator()
    agg.update(_make_face(), _make_pose(), _make_yolo(), 50.0)
    agg.reset()
    assert agg.get_latest() is None
