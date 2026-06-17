# ScoutDash Vision Service

This module is the SAM3-ready boundary for future computer vision work.

The MVP scope is intentionally narrow:

- capture a coach's manual athlete selection
- call SAM3 for segmentation when a configured adapter is available
- store athlete tracks across frame ranges
- preserve bounding data and segmentation metadata

This service must not perform sport-specific behavior detection. Future phases can use these tracks to suggest possible behaviors, but coach confirmation remains the source of evidence in Phase 1.

