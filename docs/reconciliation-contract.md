# Reconciliation contract

## Inputs

The reference reducer accepts only redacted control-plane lifecycle events and explicit provider observations.

Lifecycle events use:

- `requestId` — stable idempotency identity;
- `action` — the control action;
- `phase` — `requested`, `succeeded`, or `failed`;
- bounded audit metadata such as `durationMs`, `errorCode`, `mutating`, and redacted `fields`.

Provider observations include the expected channel handle, provider video ID, and observed privacy status.

## Transition rules

```text
missing --requested--> requested --succeeded--> succeeded --private observation--> reconciled_private
                              \--failed-----> failed

succeeded --public/unlisted observation--> needs_review
```

Rules:

1. A request begins only with `requested`.
2. An identical duplicate event is a no-op.
3. A non-identical duplicate or action change under the same request ID is a conflict.
4. `failed` and other terminal states cannot be rewritten by a later lifecycle event.
5. Provider evidence cannot create a missing request or reconcile a failed request.
6. Provider evidence must belong to `@anticaptrad`.
7. Private evidence may reconcile a successful upload.
8. Public or unlisted evidence is recorded as `needs_review`; it never proves approval by itself.

## Out of scope for this baseline

- NATS subscription and consumer acknowledgements;
- durable database schema and leases;
- Apps Script, Drive, Gmail, or YouTube credentials;
- polling schedules, retry budgets, and dead-letter queues;
- multi-region ownership and leader election;
- public/unlisted publication authorization.

Those concerns require the live evidence and operational design tracked in DEN-401 through DEN-403. The reducer is intentionally an executable specification that can later be ported into the production runtime without changing the state contract silently.
