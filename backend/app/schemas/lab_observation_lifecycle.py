"""HC-017 E3 lifecycle request schemas."""

from __future__ import annotations

from pydantic import model_validator

from app.schemas.lab_observation import CorrectLabObservationRequest


class CorrectLabObservationLifecycleRequest(CorrectLabObservationRequest):
    acknowledge_source_matches: bool
    acknowledge_unit_and_range: bool
    acknowledge_observed_at: bool
    acknowledge_profile: bool
    acknowledge_structured_record: bool
    acknowledge_not_present_assignment: bool = False

    @model_validator(mode="after")
    def validate_fresh_acknowledgements(
        self,
    ) -> "CorrectLabObservationLifecycleRequest":
        required = (
            self.acknowledge_source_matches,
            self.acknowledge_unit_and_range,
            self.acknowledge_observed_at,
            self.acknowledge_profile,
            self.acknowledge_structured_record,
        )
        if not all(required):
            raise ValueError("all correction acknowledgements are required")
        return self
