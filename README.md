# ScoutDash

ScoutDash is a sports development intelligence platform for organizing game film around athlete behaviors, habits, decisions, and coach-reviewed evidence.

Phase 1 is intentionally manual. Coaches upload film, pause video, tag athlete behavior at timestamps, and build athlete profiles from supporting clips and notes. SAM3 is present as future infrastructure only.

## Stack

- Frontend: Next.js, TypeScript, Tailwind
- Backend: FastAPI, SQLAlchemy
- Database: PostgreSQL in Docker, SQLite fallback for quick local backend runs
- Video: FFmpeg/FFprobe metadata hooks
- Storage: local uploads by default, S3-compatible settings prepared
- Vision: SAM3-ready module at `services/vision`

## Local Development

```bash
cd scoutdash
docker compose up --build
```

Then open:

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

For backend-only development:

```bash
cd scoutdash/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Phase 1 Scope

- organizations, teams, athletes, events
- film uploads and video review
- universal categories and tags
- timestamped behavior evidence
- athlete profiles with strengths, development areas, frequency, consistency, clips, and coach notes
- vision track storage for manual SAM3-assisted segmentation

No automatic behavior detection is included in this phase.

