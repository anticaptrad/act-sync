from __future__ import annotations

import unittest

from act_sync import (
    ChannelMismatch,
    ConflictingDuplicate,
    InvalidTransition,
    JobStatus,
    Reconciler,
)


def event(request_id: str, phase: str, **extra):
    value = {
        "requestId": request_id,
        "action": "startUpload",
        "phase": phase,
    }
    value.update(extra)
    return value


class ReconcilerTests(unittest.TestCase):
    def test_requested_then_succeeded_then_private_reconciliation(self):
        reducer = Reconciler()
        reducer.apply_event(event("req-1", "requested", mutating=True, fields={"title": "[redacted]"}))
        succeeded = reducer.apply_event(event("req-1", "succeeded", durationMs=125))
        self.assertEqual(succeeded.status, JobStatus.SUCCEEDED)

        reconciled = reducer.observe_provider(
            "req-1",
            channel_handle="@anticaptrad",
            video_id="video-1",
            privacy_status="private",
        )
        self.assertEqual(reconciled.status, JobStatus.RECONCILED_PRIVATE)
        self.assertIsNone(reconciled.review_reason)

    def test_identical_duplicate_is_a_no_op(self):
        reducer = Reconciler()
        requested = event("req-2", "requested", mutating=True, fields={})
        first = reducer.apply_event(requested)
        second = reducer.apply_event(dict(requested))
        self.assertEqual(first, second)

    def test_conflicting_duplicate_fails_closed(self):
        reducer = Reconciler()
        reducer.apply_event(event("req-3", "requested", mutating=True, fields={}))
        with self.assertRaises(ConflictingDuplicate):
            reducer.apply_event(event("req-3", "requested", mutating=False, fields={}))

    def test_request_id_cannot_change_action(self):
        reducer = Reconciler()
        reducer.apply_event(event("req-4", "requested", mutating=True, fields={}))
        changed = event("req-4", "succeeded", durationMs=10)
        changed["action"] = "publishVideo"
        with self.assertRaises(ConflictingDuplicate):
            reducer.apply_event(changed)

    def test_terminal_state_cannot_be_rewritten(self):
        reducer = Reconciler()
        reducer.apply_event(event("req-5", "requested", mutating=True, fields={}))
        reducer.apply_event(event("req-5", "failed", durationMs=10, errorCode="UPSTREAM"))
        with self.assertRaises(InvalidTransition):
            reducer.apply_event(event("req-5", "succeeded", durationMs=11))

    def test_first_event_must_be_requested(self):
        reducer = Reconciler()
        with self.assertRaises(InvalidTransition):
            reducer.apply_event(event("req-6", "succeeded", durationMs=1))

    def test_channel_mismatch_is_rejected(self):
        reducer = Reconciler()
        reducer.apply_event(event("req-7", "requested", mutating=True, fields={}))
        reducer.apply_event(event("req-7", "succeeded", durationMs=1))
        with self.assertRaises(ChannelMismatch):
            reducer.observe_provider(
                "req-7",
                channel_handle="@other-channel",
                video_id="video-7",
                privacy_status="private",
            )

    def test_non_private_observation_requires_review(self):
        reducer = Reconciler()
        reducer.apply_event(event("req-8", "requested", mutating=True, fields={}))
        reducer.apply_event(event("req-8", "succeeded", durationMs=1))
        observed = reducer.observe_provider(
            "req-8",
            channel_handle="@anticaptrad",
            video_id="video-8",
            privacy_status="public",
        )
        self.assertEqual(observed.status, JobStatus.NEEDS_REVIEW)
        self.assertIn("never infers", observed.review_reason)

    def test_provider_observation_cannot_create_a_job(self):
        reducer = Reconciler()
        with self.assertRaises(InvalidTransition):
            reducer.observe_provider(
                "missing",
                channel_handle="@anticaptrad",
                video_id="video-9",
                privacy_status="private",
            )

    def test_provider_video_id_cannot_change(self):
        reducer = Reconciler()
        reducer.apply_event(event("req-10", "requested", mutating=True, fields={}))
        reducer.apply_event(event("req-10", "succeeded", durationMs=1))
        reducer.observe_provider(
            "req-10",
            channel_handle="@anticaptrad",
            video_id="video-a",
            privacy_status="private",
        )
        with self.assertRaises(ConflictingDuplicate):
            reducer.observe_provider(
                "req-10",
                channel_handle="@anticaptrad",
                video_id="video-b",
                privacy_status="private",
            )


if __name__ == "__main__":
    unittest.main()
