"""ScoutDash's single-player SAM3 tracking worker.

The FastAPI backend stays CPU-only. It sends one coach-selected player and a
short ordered frame window to this Modal GPU service. The worker uses SAM3's
supported session API, returns normalized player boxes, and always writes a
terminal success or failure state back to ScoutDash.
"""

from __future__ import annotations

import hmac
import os
import tempfile
from collections.abc import Mapping
from typing import Any

import modal
from fastapi import Header, HTTPException

from worker_core import box_from_predictor_output, normalize_job


SAM3_REVISION = "46957e47805eaa273f4aa7bbbd25a88bca9108ce"
SAM3_MODEL_NAME = "sam3"
GPU = "L4"

app = modal.App("scoutdash-sam3")

# Pin the upstream commit so a Modal rebuild cannot silently change the model
# API. setuptools is explicit because SAM3 currently imports pkg_resources.
sam3_image = (
    modal.Image.from_registry("nvidia/cuda:12.6.2-cudnn-devel-ubuntu22.04", add_python="3.12")
    .apt_install("git", "ffmpeg")
    .pip_install("setuptools")
    .pip_install("torch==2.10.0", "torchvision", index_url="https://download.pytorch.org/whl/cu128")
    .run_commands(
        "git init /opt/sam3",
        "cd /opt/sam3 && git remote add origin https://github.com/facebookresearch/sam3.git",
        f"cd /opt/sam3 && git fetch --depth 1 origin {SAM3_REVISION} && git checkout --detach FETCH_HEAD && pip install -e .",
    )
    .pip_install("httpx", "huggingface_hub", "fastapi[standard]")
    .add_local_python_source("worker_core")
)

hf_secret = modal.Secret.from_name("huggingface")
backend_secret = modal.Secret.from_name("scoutdash-internal")


@app.cls(
    image=sam3_image,
    gpu=GPU,
    secrets=[hf_secret, backend_secret],
    timeout=1800,
    scaledown_window=300,
)
class Tracker:
    @modal.enter()
    def load(self) -> None:
        """Load the pinned SAM3 predictor once for each warm GPU container."""
        from huggingface_hub import login as hf_login
        from sam3.model_builder import build_sam3_video_predictor

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is required to download the SAM3 checkpoint")
        hf_login(token=token)

        # This is SAM3's public video interface. It owns the model, session
        # lifecycle, click prompt, and propagation API for a single GPU.
        self.predictor = build_sam3_video_predictor(
            gpus_to_use=[0],
            async_loading_frames=False,
            compile=False,
        )

    @modal.method()
    def track(self, job: dict[str, Any]) -> dict[str, Any]:
        """Track one coach-selected player and write a terminal result back."""
        track_id = job.get("track_id") if isinstance(job, dict) else None
        if not isinstance(track_id, str) or not track_id:
            raise ValueError("track_id is required")
        attempt_id = job.get("attempt_id") if isinstance(job, dict) else None
        if not isinstance(attempt_id, str) or not attempt_id:
            raise ValueError("attempt_id is required")

        try:
            tracked = self._track(job)
        except Exception as exc:  # noqa: BLE001 - errors must reach the coach UI
            self._writeback(
                track_id,
                attempt_id,
                frames=[],
                status="sam3_failed",
                error_message=_safe_error_message(exc),
            )
            return {"track_id": track_id, "attempt_id": attempt_id, "status": "sam3_failed", "frames_tracked": 0}

        if not tracked:
            self._writeback(
                track_id,
                attempt_id,
                frames=[],
                status="sam3_failed",
                error_message="SAM3 did not return a usable player mask for this frame window.",
            )
            return {"track_id": track_id, "attempt_id": attempt_id, "status": "sam3_failed", "frames_tracked": 0}

        self._writeback(track_id, attempt_id, frames=tracked, status="sam3_tracked")
        return {"track_id": track_id, "attempt_id": attempt_id, "status": "sam3_tracked", "frames_tracked": len(tracked)}

    def _track(self, job: Mapping[str, Any]) -> list[dict[str, Any]]:
        import httpx

        normalized = normalize_job(job)
        frames = normalized["frames"]
        selected_frame_index = normalized["selected_frame_index"]
        tracked_by_index: dict[int, dict[str, Any]] = {}

        with tempfile.TemporaryDirectory(prefix="scoutdash-sam3-") as frames_dir:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                for index, frame in enumerate(frames):
                    response = client.get(frame["frame_url"])
                    response.raise_for_status()
                    with open(os.path.join(frames_dir, f"{index}.jpg"), "wb") as file_handle:
                        file_handle.write(response.content)

            start = self.predictor.handle_request(
                {
                    "type": "start_session",
                    "resource_path": frames_dir,
                    "offload_video_to_cpu": False,
                    "offload_state_to_cpu": False,
                }
            )
            session_id = start["session_id"]
            try:
                prompt = self.predictor.handle_request(
                    {
                        "type": "add_prompt",
                        "session_id": session_id,
                        "frame_index": selected_frame_index,
                        "points": [[normalized["x_ratio"], normalized["y_ratio"]]],
                        "point_labels": [1],
                        "obj_id": 1,
                        "rel_coordinates": True,
                    }
                )
                _record_box(prompt, frames, tracked_by_index)

                for result in self.predictor.handle_stream_request(
                    {
                        "type": "propagate_in_video",
                        "session_id": session_id,
                        "propagation_direction": "both",
                        "start_frame_index": selected_frame_index,
                        "output_prob_thresh": 0.5,
                    }
                ):
                    _record_box(result, frames, tracked_by_index)
            finally:
                self.predictor.handle_request({"type": "close_session", "session_id": session_id})

        return [tracked_by_index[index] for index in sorted(tracked_by_index)]

    def _writeback(
        self,
        track_id: str,
        attempt_id: str,
        *,
        frames: list[dict[str, Any]],
        status: str,
        error_message: str | None = None,
    ) -> None:
        import httpx

        base_url = os.environ["BACKEND_API_URL"].rstrip("/")
        payload: dict[str, Any] = {
            "attempt_id": attempt_id,
            "status": status,
            "model": SAM3_MODEL_NAME,
            "version": SAM3_REVISION,
            "coach_validation": "required",
            "frames": frames,
        }
        if error_message:
            payload["error_message"] = error_message
        response = httpx.post(
            f"{base_url}/vision/tracks/{track_id}/segmentation",
            headers={"X-Internal-Token": os.environ.get("INTERNAL_TOKEN", "")},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()


def _record_box(
    result: Any,
    frames: list[dict[str, Any]],
    tracked_by_index: dict[int, dict[str, Any]],
) -> None:
    if not isinstance(result, Mapping):
        return
    frame_index = result.get("frame_index")
    outputs = result.get("outputs")
    if isinstance(frame_index, bool) or not isinstance(frame_index, int) or not isinstance(outputs, Mapping):
        return
    if frame_index < 0 or frame_index >= len(frames):
        return
    box = box_from_predictor_output(outputs, object_id=1)
    if box is not None:
        tracked_by_index[frame_index] = {"frame_number": frames[frame_index]["frame_number"], "box": box}


def _safe_error_message(exc: Exception) -> str:
    """Keep UI-facing errors actionable without leaking URLs, tokens, or stack data."""
    if isinstance(exc, ValueError):
        return str(exc)[:500]
    return f"SAM3 worker failed ({type(exc).__name__}). Check the worker logs and frame storage configuration."


@app.function(image=sam3_image, secrets=[backend_secret])
@modal.fastapi_endpoint(method="POST")
def dispatch(job: dict[str, Any], x_internal_token: str = Header(default="", alias="X-Internal-Token")):
    expected = os.environ.get("INTERNAL_TOKEN", "")
    if not expected or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=401, detail="A valid internal token is required")
    try:
        normalize_job(job)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    Tracker().track.spawn(job)
    return {"accepted": True, "track_id": job["track_id"]}


@app.local_entrypoint()
def main() -> None:
    print("Deploy with: modal deploy services/sam3-worker/app.py")
    print("Set SAM3_WORKER_URL and INTERNAL_API_TOKEN on the ScoutDash backend after deployment.")
