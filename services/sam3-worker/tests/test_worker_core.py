from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "worker_core.py"
SPEC = importlib.util.spec_from_file_location("sam3_worker_core", MODULE_PATH)
assert SPEC and SPEC.loader
worker_core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker_core)


def _job() -> dict:
    return {
        "track_id": "track-1",
        "attempt_id": "attempt-1",
        "frames": [
            {"frame_number": 12, "frame_url": "https://frames.example/12.jpg"},
            {"frame_number": 10, "frame_url": "https://frames.example/10.jpg"},
        ],
        "selected_frame_number": 12,
        "x_ratio": 0.5,
        "y_ratio": 0.5,
        "box_width_ratio": 0.2,
        "box_height_ratio": 0.4,
    }


def test_normalize_job_orders_frames_and_finds_selected_frame():
    job = worker_core.normalize_job(_job())

    assert [frame["frame_number"] for frame in job["frames"]] == [10, 12]
    assert job["selected_frame_index"] == 1


def test_normalize_job_rejects_missing_selected_frame():
    job = _job()
    job["selected_frame_number"] = 99

    with pytest.raises(ValueError, match="not present"):
        worker_core.normalize_job(job)


def test_box_from_predictor_output_selects_the_prompted_player_and_clamps_box():
    outputs = {
        "out_obj_ids": [2, 1],
        "out_boxes_xywh": [[0.1, 0.2, 0.2, 0.3], [0.95, 0.9, 0.3, 0.2]],
    }

    box = worker_core.box_from_predictor_output(outputs, object_id=1)
    assert box is not None
    assert box["x"] == pytest.approx(0.95)
    assert box["y"] == pytest.approx(0.9)
    assert box["width"] == pytest.approx(0.05)
    assert box["height"] == pytest.approx(0.1)


def test_box_from_predictor_output_ignores_missing_or_invalid_player_boxes():
    assert worker_core.box_from_predictor_output({"out_obj_ids": [1], "out_boxes_xywh": [[0.2, 0.1, 0, 0.2]]}, 1) is None
    assert worker_core.box_from_predictor_output({"out_obj_ids": [2], "out_boxes_xywh": [[0.2, 0.1, 0.3, 0.2]]}, 1) is None
