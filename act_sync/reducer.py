"""Side-effect-free reference reducer for Anticaptrad reconciliation.

This module is an executable specification, not a production worker. It models
only redacted lifecycle events and provider observations; it never handles
credentials, network calls, or raw payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
import hashlib
import json
from typing import Any, Mapping

EXPECTED_CHANNEL_HANDLE = "@anticaptrad"
TERMINAL_EVENT_PHASES = {"succeeded", "failed"}


class ReconciliationError(ValueError):
    """Base class for fail-closed reconciliation errors."""


class InvalidTransition(ReconciliationError):
    """Raised when event order would rewrite job history."""


class ConflictingDuplicate(ReconciliationError):
    """Raised when the same logical event key is reused with different data."""


class ChannelMismatch(ReconciliationError):
    """Raised when provider evidence belongs to a different channel."""


class JobStatus(StrEnum):
    REQUESTED = "requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RECONCILED_PRIVATE = "reconciled_private"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True)
class Job:
    request_id: str
    action: str
    status: JobStatus
    event_fingerprints: Mapping[str, str] = field(default_factory=dict)
    provider_video_id: str | None = None
    observed_privacy_status: str | None = None
    review_reason: str | None = None


def _non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReconciliationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _fingerprint(event: Mapping[str, Any]) -> str:
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class Reconciler:
    """In-memory reducer used to prove the state-machine contract."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def get(self, request_id: str) -> Job | None:
        return self._jobs.get(request_id)

    def apply_event(self, event: Mapping[str, Any]) -> Job:
        request_id = _non_empty_string(event.get("requestId"), "requestId")
        action = _non_empty_string(event.get("action"), "action")
        phase = _non_empty_string(event.get("phase"), "phase")
        if phase not in {"requested", "succeeded", "failed"}:
            raise ReconciliationError(f"unsupported phase: {phase}")

        fingerprint = _fingerprint(event)
        existing = self._jobs.get(request_id)
        if existing is None:
            if phase != "requested":
                raise InvalidTransition("the first event for a request must be requested")
            job = Job(
                request_id=request_id,
                action=action,
                status=JobStatus.REQUESTED,
                event_fingerprints={phase: fingerprint},
            )
            self._jobs[request_id] = job
            return job

        if existing.action != action:
            raise ConflictingDuplicate("requestId cannot be reused for a different action")

        previous_fingerprint = existing.event_fingerprints.get(phase)
        if previous_fingerprint is not None:
            if previous_fingerprint != fingerprint:
                raise ConflictingDuplicate(
                    f"conflicting duplicate {phase} event for requestId {request_id}"
                )
            return existing

        if existing.status != JobStatus.REQUESTED:
            raise InvalidTransition(
                f"cannot apply {phase} after terminal status {existing.status}"
            )
        if phase == "requested":
            raise ConflictingDuplicate("a second non-identical requested event is forbidden")

        next_status = JobStatus.SUCCEEDED if phase == "succeeded" else JobStatus.FAILED
        fingerprints = dict(existing.event_fingerprints)
        fingerprints[phase] = fingerprint
        job = replace(existing, status=next_status, event_fingerprints=fingerprints)
        self._jobs[request_id] = job
        return job

    def observe_provider(
        self,
        request_id: str,
        *,
        channel_handle: str,
        video_id: str,
        privacy_status: str,
    ) -> Job:
        request_id = _non_empty_string(request_id, "requestId")
        channel_handle = _non_empty_string(channel_handle, "channelHandle")
        video_id = _non_empty_string(video_id, "videoId")
        privacy_status = _non_empty_string(privacy_status, "privacyStatus")

        if channel_handle != EXPECTED_CHANNEL_HANDLE:
            raise ChannelMismatch(
                f"provider evidence belongs to {channel_handle}, not {EXPECTED_CHANNEL_HANDLE}"
            )

        existing = self._jobs.get(request_id)
        if existing is None:
            raise InvalidTransition("provider evidence cannot create a missing request")
        if existing.status not in {JobStatus.SUCCEEDED, JobStatus.RECONCILED_PRIVATE, JobStatus.NEEDS_REVIEW}:
            raise InvalidTransition(
                f"provider evidence requires a succeeded request, found {existing.status}"
            )

        if existing.provider_video_id and existing.provider_video_id != video_id:
            raise ConflictingDuplicate("provider video ID changed for the same request")

        if privacy_status == "private":
            status = JobStatus.RECONCILED_PRIVATE
            review_reason = None
        else:
            status = JobStatus.NEEDS_REVIEW
            review_reason = (
                "non-private provider state requires explicit publication evidence; "
                "reconciliation never infers public or unlisted approval"
            )

        job = replace(
            existing,
            status=status,
            provider_video_id=video_id,
            observed_privacy_status=privacy_status,
            review_reason=review_reason,
        )
        self._jobs[request_id] = job
        return job
