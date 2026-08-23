# act-sync

Deterministic reconciliation model for Anticaptrad YouTube control-plane jobs.

## Lifecycle

**Profile:** executable specification / pre-production baseline  
**Status:** not deployed; no network or credential handling  
**Owner:** Anticaptrad platform maintainers

This repository defines how requested, succeeded, failed, and observed provider states converge without duplicating mutations or silently promoting content. It consumes the language-neutral lifecycle concepts owned by `act-interfaces`; the production runtime may later be implemented in Rust after the live rehearsal in DEN-402 establishes the durable store and polling boundaries.

## Safety contract

- `requestId` is the idempotency identity.
- Duplicate events are no-ops only when their content is identical.
- Conflicting reuse of a request ID fails closed.
- A failed operation cannot become succeeded without a new explicit attempt.
- Provider observation can reconcile a successful private upload, but cannot infer public or unlisted publication.
- Channel observations must match `@anticaptrad`.
- Credentials, API keys, OAuth tokens, raw payloads, and raw upstream bodies are outside the model.

## State model

`act_sync/reducer.py` is a dependency-free reference reducer. It is intentionally small enough to review as a state-machine specification and is not a claim of production deployment.

```bash
python3 -m unittest discover -s tests -v
```

The tests cover duplicates, conflicting duplicates, impossible transitions, channel mismatch, private reconciliation, and refusal to infer public publication.

## Integration boundary

Inputs are redacted lifecycle events and provider observations. Durable storage, NATS subscriptions, Apps Script credentials, Drive access, YouTube polling, retry scheduling, and dead-letter handling remain deployment concerns tracked under DEN-401 through DEN-403.

Licensed under the MIT License.

## Environment secrets

Secrets live in this repo **encrypted** with [sops](https://github.com/getsops/sops) + [age](https://github.com/FiloSottile/age):
`env/enc/<dev|prod>.env.enc` is committed; `just env-use <name>` decrypts it to
`env/dec/<name>.env` (gitignored, mode 0600) and symlinks `./.env` to it. The
Nix dev shell provides the tooling, `just env-audit` runs keyless in CI, and
containers decrypt at `docker run` — never at build. See [`env/README.md`](env/README.md).
