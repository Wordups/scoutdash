# Architecture

ScoutDash separates film management from computer vision.

## Backend

FastAPI owns the API boundary and stores development evidence:

- `app/models.py`: SQLAlchemy database model
- `app/schemas.py`: Pydantic request/response contracts
- `app/api/routes`: API-first route modules
- `app/services/storage.py`: local and S3-compatible upload boundary
- `app/services/video.py`: FFprobe metadata extraction

## Frontend

The Next.js app is an operations workspace. The first screen is the review workflow: film player, timestamp tagging, evidence clips, and athlete profile context.

## Vision

`services/vision` is a dedicated SAM3-ready module. It stores contracts for manual selections, segmentation metadata, and athlete tracks. It does not run sport-specific intelligence or automatic behavior classification.

Future phases can turn stored tracks into movement paths, then coach-assisted suggestions, then higher-order behavior intelligence.

