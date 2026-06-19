# ScoutDash SAM 3 Tracking Worker

A **separate GPU service** that owns all SAM 3 code. The ScoutDash backend runs CPU /
Python 3.14 on a buildpack and **cannot** import `sam3`/`torch`, so it dispatches a job to
this worker and receives per-frame boxes back. SAM 3 needs Python 3.12, PyTorch 2.7+, a
CUDA 12.6+ GPU, and the HF-gated `facebook/sam3.1` checkpoint — all isolated here.

## Architecture

```
coach click ──▶ POST /vision/track-seeds (backend, CPU)
                     │  status → "sam3_processing"
                     ▼
              POST {worker}/dispatch  ──▶  .spawn() GPU job (returns immediately)
                                              │  init_state → add_new_points_or_box
                                              │  → propagate_in_video → ratio boxes
                                              ▼
              POST /vision/tracks/{id}/segmentation (backend write-back)
                     │  replace bounding_data.frames[*].box, status → "sam3_tracked"
                     ▼
              GET /vision/tracks/{id}/timeline  ◀── frontend (scout-lite.html) re-fetches
```

The backend never imports `sam3`/`torch`; `backend/requirements.txt` carries no ML deps.

## Deploy (Modal)

```bash
pip install modal
modal token new

# 1. Request access to https://huggingface.co/facebook/sam3.1, make an HF token:
modal secret create huggingface HF_TOKEN=hf_xxx

# 2. Backend callback URL + shared secret (same token the backend uses as INTERNAL_API_TOKEN):
modal secret create scoutdash-internal \
  BACKEND_API_URL=https://<backend-host>/api INTERNAL_TOKEN=<shared-secret>

# 3. Deploy
modal deploy services/sam3-worker/app.py
```

Then set on the **backend**:
- `SAM3_WORKER_URL` = the printed `dispatch` endpoint URL
- `INTERNAL_API_TOKEN` = the same `<shared-secret>` as `INTERNAL_TOKEN` above

## Notes

- `gpu="L4"`, `scaledown_window=120` → per-second billing, zero idle cost.
- Boxes are emitted as `{x, y, width, height}` **ratios** to match the seed box shape the
  backend stores and the frontend renders.
- Point-tracking only (single object). No text-concept segmentation, no coaching evaluation —
  SAM 3 identifies and tracks; coach validation stays `required`.
- **Untested on real GPU/Modal** until the first `modal deploy`. The `TODO(CC)` markers in
  `app.py` flag the exact SAM3 call-surface details to confirm against the installed version.
- Order of operations: ffprobe/extraction must work so frames exist (0.jpg…N.jpg input) before
  this worker has anything to track.
