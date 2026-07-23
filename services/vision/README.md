# ScoutDash Vision Service

This module is the backend boundary for ScoutDash vision work.

The MVP scope is intentionally narrow:

- capture a coach's manual athlete selection
- dispatch coach-selected player tracks to the configured SAM3 GPU worker
- store athlete tracks across frame ranges
- preserve bounding data and segmentation metadata

The worker integration lives at `services/sam3-worker`. The thin adapter in this
folder remains for non-GPU integration experiments and is not the production
tracking path.

This service must not perform sport-specific behavior detection. Future phases can use these tracks to suggest possible behaviors, but coach confirmation remains the source of evidence in Phase 1.
