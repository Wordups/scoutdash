# ScoutDash SAM3 Tracking Worker

This is the separate Modal GPU service for ScoutDash player tracking. It tracks
one coach-selected player through a bounded set of extracted basketball-film
frames. The CPU-only ScoutDash backend never imports PyTorch or SAM3.

## What it does

1. The coach clicks a player in a clear film frame.
2. ScoutDash sends the selected point and a short ordered frame window.
3. The Modal worker starts a SAM3 video-predictor session, applies the point prompt, and propagates the player through the window.
4. It writes normalized `{x, y, width, height}` boxes back to ScoutDash.
5. It always writes either `sam3_tracked` or `sam3_failed` so the Film Room never stays falsely complete.

This implementation intentionally uses the pinned base SAM3 video predictor for
the single-player workflow. It does not claim SAM3.1 Object Multiplex support.

## Requirements

- A Modal account and local `modal` CLI login.
- Hugging Face access to the gated `facebook/sam3` checkpoint and an `HF_TOKEN`.
- A public ScoutDash backend callback URL ending in `/api`.
- Public or presigned frame URLs reachable from Modal. `localhost`, Docker service names, and private MinIO addresses will not work.
- Persistent production storage such as S3 or R2. Local upload storage is not suitable for a remote worker.
- A nonempty shared internal token on both the backend and worker. The worker will reject unauthenticated dispatches.

## Configure Modal secrets

```bash
modal secret create huggingface HF_TOKEN=hf_your_token
modal secret create scoutdash-internal BACKEND_API_URL=https://your-backend.example/api INTERNAL_TOKEN=your-shared-token
```

`INTERNAL_TOKEN` must match the backend's `INTERNAL_API_TOKEN`. Keep both values private.

## Deploy

```bash
pip install modal
modal token new
modal deploy services/sam3-worker/app.py
```

Set the returned `/dispatch` URL and the shared token on the ScoutDash backend:

```env
SAM3_WORKER_URL=https://your-modal-dispatch-url
INTERNAL_API_TOKEN=your-shared-token
SAM3_MAX_TRACK_FRAMES=121
SAM3_TRACK_TIMEOUT_SECONDS=600
```

The worker pins the upstream SAM3 commit in `app.py`, so a later Modal image
rebuild cannot silently switch predictor APIs.

## First smoke test

Use a short 10 to 20 second basketball clip with a clearly visible player.

1. Confirm the backend has persistent storage and externally reachable frame URLs.
2. Upload the clip and run **Break Down Film**.
3. Select an athlete, choose a clean frame, and click the player.
4. Choose **Track selected player**.
5. Confirm the status changes from `Tracking... (SAM3)` to `Tracked`, and that the main frame shows a moving box.

If the worker cannot run, ScoutDash shows the reason and allows a retry. Inspect
the Modal logs for GPU or checkpoint issues before retrying.

## Scope and limits

- One selected player per track.
- SAM3 identifies and follows the player. Coaches still validate all evidence.
- The backend sends a bounded frame window around the selected frame to control GPU time.
- GPU inference still needs a real-film validation before calling the feature production-ready.
