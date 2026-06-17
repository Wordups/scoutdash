# ScoutDash

ScoutDash is a sports development intelligence platform for organizing game film around athlete identification, athlete timelines, and coach-reviewed evidence.

The current product foundation is the Video Intelligence Engine: upload or import film, extract frames, select the athlete, create a SAM3-ready player track, review that athlete's timeline, and turn moments into evidence tags. SAM3 is the identification layer only. Coaches validate, and ScoutDash stores evidence.

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

## Current Scope

- organizations, teams, athletes, events
- film uploads, direct URL imports, and video review
- FFmpeg frame extraction
- coach-click player track seeds for future SAM3 segmentation and tracking
- athlete timeline review from stored track metadata
- universal categories and tags
- timestamped behavior evidence
- athlete profiles with strengths, development areas, frequency, consistency, clips, and coach notes
- athlete development reports generated from traceable evidence and notes

No automatic behavior detection, player ratings, or coaching recommendations are included.

