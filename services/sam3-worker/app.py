"""
services/sam3-worker/app.py — ScoutDash SAM 3 tracking worker (Modal, serverless GPU)

WHAT THIS IS
  A separate GPU service that owns ALL SAM 3 code. The ScoutDash backend (CPU/py3.14)
  never imports sam3 — it POSTs a job to this worker's `dispatch` endpoint; the worker runs
  the tracker on GPU and POSTs per-frame boxes back to the backend write-back endpoint
  (POST /vision/tracks/{track_id}/segmentation).

PREREQS (you, once)
  1. `pip install modal` and `modal token new`
  2. Request access to the gated checkpoint at https://huggingface.co/facebook/sam3.1,
     create an HF token, then:
       modal secret create huggingface HF_TOKEN=hf_xxx
       modal secret create scoutdash-internal \
         BACKEND_API_URL=https://<backend-host>/api INTERNAL_TOKEN=<shared-secret>
  3. Deploy:  modal deploy services/sam3-worker/app.py
     The printed `dispatch` URL goes into the backend env as SAM3_WORKER_URL, and the same
     INTERNAL_TOKEN goes into the backend env as INTERNAL_API_TOKEN.

API VERIFIED AGAINST github.com/facebookresearch/sam3 (README + examples/
sam3_for_sam2_video_task_example.ipynb + examples/sam3_video_predictor_example.ipynb):
  - The video TRACKER (init_state / add_new_points_or_box / propagate_in_video, SAM2-style)
    lives on `build_sam3_video_model().tracker`. `build_sam3_predictor(version="sam3.1")` is a
    different, higher-level session predictor (handle_request/handle_stream_request).
  - Points are RELATIVE by default (`rel_coordinates=True`) → ScoutDash ratios pass straight in.
  - `propagate_in_video(...)` YIELDS a 5-tuple: (frame_idx, obj_ids, low_res_masks,
    video_res_masks, obj_scores). Use `video_res_masks` (original resolution); threshold `> 0.0`.
  - Gated checkpoint auto-downloads via huggingface_hub, which honors the HF_TOKEN env var.

TODO(CC) — confirm on the FIRST `modal deploy` against the installed sam3 version (this is
syntax-clean but GPU-untested; the call surface above is from the pinned repo but minor
arg/return names can shift between sam3 and sam3.1 builds):
  - `build_sam3_video_model()` vs needing an explicit version arg for the sam3.1 weights.
  - `.tracker` / `.detector.backbone` wiring exactly as the SAM2-task notebook does it.
  - `add_new_points_or_box` / `propagate_in_video` arg + return names against the installed build.
"""

import modal
from fastapi import Header, HTTPException

app = modal.App("scoutdash-sam3")

# ---- container image: CUDA 12.6 + py3.12 + torch cu128 + sam3 from source ----
sam3_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.6.2-cudnn-devel-ubuntu22.04", add_python="3.12"
    )
    .apt_install("git", "ffmpeg")
    .pip_install(
        "torch==2.10.0",
        "torchvision",
        index_url="https://download.pytorch.org/whl/cu128",
    )
    .run_commands(
        "git clone https://github.com/facebookresearch/sam3.git /opt/sam3",
        "cd /opt/sam3 && pip install -e .",
    )
    .pip_install("pillow", "numpy", "httpx", "huggingface_hub", "fastapi[standard]")
)

hf_secret = modal.Secret.from_name("huggingface")               # -> HF_TOKEN
backend_secret = modal.Secret.from_name("scoutdash-internal")   # -> BACKEND_API_URL, INTERNAL_TOKEN

GPU = "L4"  # 24GB is ample for single-object tracking; bump to A10G/A100 only if needed.


@app.cls(
    image=sam3_image,
    gpu=GPU,
    secrets=[hf_secret, backend_secret],
    timeout=1800,
    scaledown_window=120,  # spin down 2 min after idle → per-second billing only while tracking
)
class Tracker:
    @modal.enter()
    def load(self):
        """Load weights once per warm container. Gated ckpt downloads via HF_TOKEN."""
        import os

        from huggingface_hub import login as hf_login

        token = os.environ.get("HF_TOKEN")
        if token:
            hf_login(token=token)

        # The SAM2-style video tracker (init_state/add_new_points_or_box/propagate_in_video)
        # is exposed on build_sam3_video_model().tracker. See module docstring + TODO(CC).
        from sam3.model_builder import build_sam3_video_model

        model = build_sam3_video_model()  # downloads facebook/sam3.1 weights (HF-gated)
        self.predictor = model.tracker
        self.predictor.backbone = model.detector.backbone

    @modal.method()
    def track(self, job: dict) -> dict:
        """
        job = {
          track_id, video_id,
          frames: [{frame_number:int, frame_url:str}, ...],
          selected_frame_number:int, x_ratio:float, y_ratio:float
        }
        """
        import os
        import tempfile

        import httpx
        import numpy as np
        import torch

        frames = sorted(job["frames"], key=lambda f: f["frame_number"])
        order = {f["frame_number"]: i for i, f in enumerate(frames)}
        sel_idx = order[job["selected_frame_number"]]

        with tempfile.TemporaryDirectory() as frames_dir:
            # 1) Materialize frames as 0.jpg, 1.jpg, ... — SAM3's video-tracker input format.
            with httpx.Client(timeout=60) as client:
                for i, frame in enumerate(frames):
                    resp = client.get(frame["frame_url"])
                    resp.raise_for_status()
                    with open(os.path.join(frames_dir, f"{i}.jpg"), "wb") as fh:
                        fh.write(resp.content)

            # 2) Prompt the tracker on the SELECTED frame with the coach click.
            #    Coords are RELATIVE [0,1] (rel_coordinates default True) → ScoutDash ratios
            #    pass straight in, no pixel conversion needed.
            points = torch.tensor([[job["x_ratio"], job["y_ratio"]]], dtype=torch.float32)
            labels = torch.tensor([1], dtype=torch.int32)  # 1 = positive click

            state = self.predictor.init_state(video_path=frames_dir)
            self.predictor.add_new_points_or_box(
                inference_state=state,
                frame_idx=sel_idx,
                obj_id=1,
                points=points,
                labels=labels,
                rel_coordinates=True,
            )

            # 3) Propagate across all frames → one tight box per frame (as ratios).
            tracked = []
            for out in self.predictor.propagate_in_video(state):
                # yields (frame_idx, obj_ids, low_res_masks, video_res_masks, obj_scores)
                out_frame_idx, _obj_ids, _low_res, video_res_masks = out[0], out[1], out[2], out[3]
                mask = (video_res_masks[0] > 0.0).cpu().numpy()  # single object → index 0
                box = _ratio_bbox_from_mask(mask)
                if box is not None and out_frame_idx in range(len(frames)):
                    tracked.append({"frame_number": frames[out_frame_idx]["frame_number"], "box": box})

        self._writeback(job["track_id"], tracked)
        return {"track_id": job["track_id"], "frames_tracked": len(tracked)}

    def _writeback(self, track_id: str, frames: list):
        import os

        import httpx

        base = os.environ["BACKEND_API_URL"].rstrip("/")
        token = os.environ.get("INTERNAL_TOKEN", "")
        resp = httpx.post(
            f"{base}/vision/tracks/{track_id}/segmentation",
            headers={"X-Internal-Token": token},
            json={
                "status": "sam3_tracked",
                "model": "sam3.1",
                "version": "sam3.1",
                "coach_validation": "required",
                "frames": frames,
            },
            timeout=60,
        )
        resp.raise_for_status()


def _ratio_bbox_from_mask(mask):
    """Tight {x, y, width, height} as ratios in [0, 1] from a boolean mask, or None if empty.

    Matches the box shape the ScoutDash backend stores (bounding_data.frames[*].box) and the
    frontend renders, so the write-back is a drop-in replacement for the seed boxes.
    """
    import numpy as np

    ys, xs = np.where(mask)
    if xs.size == 0:
        return None
    h, w = mask.shape[-2], mask.shape[-1]
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return {
        "x": x0 / w,
        "y": y0 / h,
        "width": (x1 - x0 + 1) / w,
        "height": (y1 - y0 + 1) / h,
    }


# ---- dispatch endpoint the backend calls (returns immediately; GPU work runs async) ----
@app.function(image=sam3_image, secrets=[backend_secret])
@modal.fastapi_endpoint(method="POST")
def dispatch(job: dict, x_internal_token: str = Header(default="", alias="X-Internal-Token")):
    import os

    # Shared-secret check so only the ScoutDash backend can trigger GPU spend.
    expected = os.environ.get("INTERNAL_TOKEN")
    if expected and x_internal_token != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")

    Tracker().track.spawn(job)  # enqueue on GPU, return now
    return {"accepted": True, "track_id": job.get("track_id")}


# ---- local smoke test:  modal run services/sam3-worker/app.py ----
@app.local_entrypoint()
def main():
    print("Deploy with: modal deploy services/sam3-worker/app.py")
    print("Then set SAM3_WORKER_URL (printed dispatch URL) + INTERNAL_API_TOKEN in the backend.")
