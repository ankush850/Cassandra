# Session log

One file per working session: `YYYY-MM-DD-short-topic.md`. This is the project's durable,
human-readable memory — each session leaves a record so the next one starts with full context
instead of re-deriving it.

**This is a hard convention for anyone (human or AI) working in this repo.** See the
"Session Protocol" section in [`/CLAUDE.md`](../../CLAUDE.md) for exactly when and what to write.

Each entry should cover:

- **Scope** — what this session set out to do.
- **What changed & why** — the decisions, not just the diffs (the diffs are in git).
- **Files touched.**
- **Verification** — what was run and the result (test counts, live runs, numbers).
- **Open items** — anything deliberately left undone, with enough context to resume.

Newest entries are the most relevant. When in doubt, read the latest one first.
