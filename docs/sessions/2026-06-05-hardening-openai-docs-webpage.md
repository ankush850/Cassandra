# Session Notes — Hardening, OpenAI re-wire, docs automation & animated explainer

**Date:** 2026-06-05
**Scope:** Take the project from "works" to "credibly wins": re-wire to OpenAI (escape the Vertex
429 bottleneck), fix the real loose ends, fix the Diagnostician's accuracy, harden a security
surface, install a durable "update docs every session" rule, build an animated explainer webpage,
and write a system-design + flaws + security doc. **No new product phases** — fixes and polish only.

Plan file: `~/.claude/plans/validated-yawning-comet.md`.

---

## 1. Flaw list reconciliation (important)

The provided flaw list was partly stale against the tree (full table in
[`docs/SYSTEM_DESIGN.md` §10](../SYSTEM_DESIGN.md)):
- #3 (lru_cache stale env) and #5 (`model_provider="GOOGLE"` hardcoded) were **real** → fixed.
- #2 (nested-key "failing test") was **not failing** (all tests passed; `_flat_str` was flat-only)
  → added defensive nested-key support + a test anyway.
- #4 (evaluator stubs returning `{"status":"queued"}`) was **outdated** — `evaluator.py` already
  scores live.
- #1 (port in `run_pipeline.py`) was cosmetic → now derived from settings.

## 2. OpenAI re-wire (A)
- `.env`: set `OPENAI_API_KEY` (active). `llm.py`, the Patient, and the experiment judge all route
  to OpenAI automatically (`gpt-4o-mini`), dodging the Vertex DSQ 429 throttling.
- Verified live: `llm.structured`/`text` both return cleanly, no 429s.

## 3. Confirmed loose ends (B)
- `config.py`: added `model_provider` / `model_name` properties + `reload_settings()`.
- `phoenix_mcp.create_prompt_version`: now uses `s.model_provider` / `s.model_name` (was `GOOGLE`).
- `phoenix_mcp._flat_str`: defensive nested-attribute fallback (`{"input":{"value":…}}`) + new test.
- `run_pipeline.py`: the "is it running?" message derives the port from `patient_endpoint`.

## 4. Diagnostician accuracy: 18% → 100% (C)
Root cause of the prior ~18%: the judge never saw the **tool results**, so it over-flagged grounded
answers. Fixes:
- Patient `/chat` now returns its `tool_calls`; `selfeval.py` forwards them to `judge()`.
- Sharpened `diagnostician._SYSTEM`: classify by the *nature* of the unsupported claim
  (invented facts/policy → hallucination; misreported lookup → tool_failure) + few-shot anchors.
- Made the judge **deterministic** (`llm.structured(..., temperature=0.0)`; threaded a `temperature`
  param through `llm.py`).
- **Discovered the Patient was no longer fragile on gpt-4o-mini** (it honestly refused on missing
  data, so the canonical hallucination demo didn't fire). Strengthened `FRAGILE_SYSTEM_PROMPT` to
  fabricate confident specifics when a tool returns nothing — restoring the demo *and* making the
  ground-truth labels correct.
- Corrected a mislabeled `tool_failure` trap (A1002 *exists* and is correctly reported as
  "processing" → that's `ok`). Added a malformed order `A1003` (null carrier/eta) and pointed both
  `tool_failure` traps at incomplete-data orders the fragile agent fabricates fields for.
- Result (OpenAI): **100%** (11/11) — hallucination 4/4, tool_failure 2/2, prompt_drift 2/2, ok 3/3.
  Arc: 18 → 64 (plumb tools) → 91 (fragile patient + taxonomy) → 100 (genuine traps + temp 0).

## 5. Security (D)
- **`system_override` gated**: `patient/agent.py:resolve_override` honors it only on
  `session_id=="test"` (Cassandra's sandbox); ignored for any other caller. Was an unauthenticated
  system-prompt-override surface on a tool-using agent.
- New `tests/test_patient_security.py` (3 tests) + live check: external override → ignored,
  test-session override → honored ("PWNED").
- Audit: git history + tracked files are **clean** of secrets; `.env` gitignored. Action for owner:
  **rotate** the Gemini/OpenAI/Phoenix keys that were in the local `.env` (checklist in SYSTEM_DESIGN §11).

## 6. Docs-every-session rule (E)
- New `docs/sessions/` structure (+ README); moved the 2026-06-04 note in.
- `CLAUDE.md`: added a **Session Protocol** section (read newest session note first; update the
  session note after behavior-changing work and at session end; keep README/ARCHITECTURE/
  SYSTEM_DESIGN + `MEMORY.md` in sync; restart servers after `.env` changes).
- `.claude/settings.local.json`: added a `Stop` hook that prints a protocol reminder. (First
  version had a bash syntax error from unquoted `()`/`<>`; fixed by single-quoting the message and
  dropping shell metacharacters — verified it runs `bash -c` cleanly, exit 0.)

## 7. Animated explainer webpage (F)
- New self-contained `dashboard/ui/how-it-works.html` (inline SVG/CSS/JS, no build step), served at
  `/how` and `/how-it-works` (`dashboard/main.py`); linked from the cockpit header.
- Scenes: two-agent topology, the live **pipeline player** (play/step through all stages with
  input/op/output + the MCP tool each calls), the before→after incident, the **MCP call I/O** flow
  (request → reasoning → response for each `cassandra-mcp` tool), and the self-eval grading to 100%.
- Verified: HTTP 200, JS syntax-checked with `node --check`, and headless-Chrome screenshots of the
  full page (renders correctly top to bottom).

## 8. System-design doc (G)
- New `docs/SYSTEM_DESIGN.md`: plain-language design, every workflow narrated (pipeline stages +
  MCP tools, the published MCP server, self-eval, dashboard SSE), the flaws reconciliation table,
  the security audit + rotation checklist, and simplification recommendations.

---

## Files changed
- `.env`, `cassandra/config.py`, `cassandra/llm.py`, `cassandra/phoenix_mcp.py`,
  `cassandra/diagnostician.py`, `cassandra/selfeval.py`, `cassandra/traps.py`
- `patient/agent.py`, `patient/tools.py`
- `scripts/run_pipeline.py`
- `dashboard/main.py`, `dashboard/ui/index.html`, `dashboard/ui/how-it-works.html` (new)
- `tests/test_phoenix_mcp_helpers.py`, `tests/test_selfeval.py`, `tests/test_diagnostician.py`,
  `tests/test_patient_security.py` (new)
- `CLAUDE.md`, `.claude/settings.local.json`, `README.md`, `docs/SYSTEM_DESIGN.md` (new),
  `docs/sessions/` (new structure)

## Verification
- `pytest`: **23 passed** (offline; LLM + MCP mocked).
- Live on OpenAI: self-eval **100%**; Evaluator baseline (fragile) **50%** → candidate (hardened)
  **100%** (+50%); security gate confirmed; `/how` + cockpit serve 200.
- Not run: full Phoenix-backed `run_pipeline.py` (local Phoenix at :6006 not running in this
  environment) — Phoenix-writeback stages (Watcher/annotate/dataset/upsert) pending a live Phoenix.

## Open items
- [ ] **Owner: rotate** the Gemini/OpenAI/Phoenix keys that were in `.env`.
- [ ] Run the full `run_pipeline.py` against a live Phoenix to verify the writeback stages.
- [ ] (Optional, documented in SYSTEM_DESIGN §12) centralize OpenAI/Gemini client construction;
      retire the legacy `web/` app.
- [ ] Commit this session's work (nothing committed yet) + the prior 2026-06-04 changes still in the tree.
- [ ] `LoopAgent` is deprecated in google-adk → migrate to `Workflow` eventually.
