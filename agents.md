# act-sync agent instructions

## Blacklisted operations and dependencies

- Do not run `git reset`, `git filter-repo`, or `git clean`.
- Do not run `rm` except when explicitly deleting known temporary or scratch files.
- `dotenv` is blacklisted. Do not install or use it.

## Repository role and invariants

- This repository currently owns an executable reconciliation specification, not a deployed network service.
- Do not add credentials, provider tokens, OAuth material, API keys, raw payload bodies, or production deployment claims.
- Preserve request-ID idempotency, fail-closed conflicting duplicates, monotonic state transitions, exact `@anticaptrad` channel verification, and private-by-default publication.
- Never infer public or unlisted publication from incomplete lifecycle events or provider observations.
- A failed attempt may only be retried through an explicit new attempt/event; do not silently rewrite history.
- Keep the reference model deterministic, side-effect free, and dependency-light until the production runtime boundary is explicitly approved.

## Instruction discovery

Resolve `$PWD`, walk upward through every parent directory to the filesystem root, read every readable lowercase `agents.md` on that ancestor chain, and apply them root-to-leaf. Do not search siblings. Deduplicate resolved paths/inodes, avoid symlink cycles, and report unreadable files.

## Git and remote synchronization

Before editing, inspect status, branch, remotes, and the remote default branch. Fetch and prune before branching and again before pushing. Avoid rebase in favor of merge.

- Do not force-push or rewrite shared history.
- Do not bypass review or required CI.

## Semantic conflict resolution

Resolve conflicts by combining both sides' intent. Do not mechanically choose ours, theirs, current, or incoming. Preserve state-machine safety, duplicate handling, channel identity, publication gates, tests, documentation, and the distinction between specification and production runtime.

After resolving, reread every affected file, run `python3 -m unittest discover -s tests -v`, and search the worktree for conflict markers:

```sh
grep -RInE '^(<<<<<<<|=======|>>>>>>>)' --exclude-dir=.git .
```
