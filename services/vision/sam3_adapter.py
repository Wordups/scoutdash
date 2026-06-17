from __future__ import annotations

from typing import Any

from .contracts import ManualSelection, SegmentationMetadata


class SAM3UnavailableError(RuntimeError):
    """Raised when SAM3 is not configured for the vision service."""


class SAM3Adapter:
    """Thin adapter for future SAM3 calls.

    The MVP records manual selections and track metadata. This adapter exists so
    SAM3 can be wired in later without leaking model-specific calls into film
    management or evidence-tag routes.
    """

    def __init__(self, model: Any | None = None, model_name: str = "sam3") -> None:
        self.model = model
        self.model_name = model_name

    @property
    def available(self) -> bool:
        return self.model is not None

    def segment_manual_selection(self, selection: ManualSelection, frame: Any) -> SegmentationMetadata:
        if self.model is None:
            raise SAM3UnavailableError("SAM3 model is not configured")

        result = self.model.segment(frame=frame, prompt=selection.prompt)
        return SegmentationMetadata(
            model_name=self.model_name,
            prompt_type=result.get("prompt_type"),
            mask_ref=result.get("mask_ref"),
            confidence=result.get("confidence"),
            raw=result,
        )

