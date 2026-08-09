# Session Log: 2026-06-11 (deadline day) - Brutally Honest Feature Review & Final Priorities

## Scope

A full feature-by-feature review of the project on deadline day: every feature rated /10,
ranked by how much it matters to the judging, with the honest weaknesses called out and a
strict priority order for the remaining hours. No code changed in this session (review only);
39 offline tests pass, `ruff` clean, working tree was in sync with origin/main.

## The headline

The product is top-quartile for the Arize track, but the risk is logistics, not features:
**no hosted URL and no demo video yet** (both hard submission requirements). Every rating
below is worth 0 if those two are not done today.

## Tier 1 - the features that win or lose this

| Feature | Rating | Verdict |
|---|---|---|
| Trace Replay (before/after FIXED) | 9/10 | The money shot. Centerpiece of the video; change nothing. |
| 8-stage supervision pipeline | 8.5/10 | Clean Incident-threading architecture; demo-deterministic. "Works on any agent" claim is one day old (decoupling shipped 06-11) and untested on a real third-party agent. |
| `cassandra-mcp` published server (6 tools) | 9/10 | Best differentiator: consume the partner MCP AND publish our own. Lead the Devpost writeup with this. |
| `cassandra-gate` CI regression gate | 8.5/10 | Best *idea* in the project (failure -> dataset -> CI suite flywheel). New, never demo'd; live-agent dependency is real friction. |
| Self-evaluation / trap library | 7.5/10 | Targets the Arize bonus criterion. **Warning: the "100% accuracy" is overfit** - judge, labels, and Patient were iterated until 11/11 on self-written traps. Present as "11/11 on a hand-labeled trap suite" with per-class breakdown, never as a headline "100%". |

## Tier 2 - solid, necessary, not differentiating

| Feature | Rating | Verdict |
|---|---|---|
| Diagnostician (LLM-as-judge) | 8/10 | Side-effect-free `judge()` shared across pipeline/MCP/self-eval is good engineering. Same overfit caveat on the accuracy number. |
| Patcher + unified prompt diff | 8/10 | Inspectable fix = Design points. |
| Live Evaluator (baseline vs candidate) | 7.5/10 | Real numbers (the old stub would have been fatal). **n=8 cases means pass-rate deltas are statistically noise** - frame as a smoke signal gating replay/red-team, not rigorous A/B. |
| Red Team runner | 6.5/10 | **Oversold**: it re-fires the same `dataset_examples[:6]` the Evaluator scored - no novel attack generation. If asked "how do red-team attacks differ from the eval set?" the honest answer is "they don't". Reframe as "live adversarial verification". |
| Auto-postmortems | 7.5/10 | Pure-function renderer, lands in existing on-call processes. Second-best adoption hook. |
| Synthesizer | 7/10 | Does its job; writes real datasets into Phoenix (deep partner usage). |
| Dashboard cockpit | 7/10 | Pragmatic single-file UI; wins on information design (watch the pipeline think), not beauty. |
| Docs suite (WORKFLOWS/PITCH/DEPLOYMENT/SYSTEM_DESIGN/sessions) | 8/10 | Unusually good for a hackathon; serves the Impact score directly. |
| BYO-agent decoupling (`baseline.py`, `patient_client.py`, adapter) | 7/10 | Right move, converts demo into tool - but shipped yesterday, unproven in practice. Don't claim battle-tested portability. |
| Security hardening (REPLAY_SHARED_SECRET, input caps, non-root) | 7/10 | The `system_override` hijack was a real HIGH catch. **Post-deploy, verify the secret is live on BOTH services** - if dropped, replay/eval/red-team silently score the baseline twice and all demo deltas are ~0. |

## Tier 3 - checkbox or low-impact

| Feature | Rating | Verdict |
|---|---|---|
| ADK wrapper | 5/10 | Scoring risk: thin envelope, `max_iterations=1`, **LoopAgent deprecation warning on every pytest run**, zero Agent Engine runs ever, `GOOGLE_GENAI_USE_VERTEXAI=false` in deploy env. Defend the "logic stays testable Python" rationale proactively in the writeup. |
| LLM backend choice | **biggest non-logistics worry** | Mandated stack is Gemini; runtime precedence puts OpenAI first and deploys wire an OpenAI key. **Record the demo on the Gemini backend** or be loudly upfront that Gemini is the primary supported path. Silently shipping on OpenAI is the worst option. |
| Patient/ShopBot | 6/10 | Necessary rigged demo prop; BYO layer keeps it from being a liability. |
| Root Cause Analyst | 6/10 | Garnish, not protein - enriches the postmortem, drives nothing downstream. |
| State backends (Firestore/GCS/local) | 6/10 | Correct Cloud Run plumbing, invisible to judges. The memoized-singleton fix mattered. |
| Test suite (39 offline) | 8/10 eng, 4/10 judge-visible | Smart offline-by-design; nobody scores it directly. |
| `/how` animated explainer | 5/10 | Pleasant, zero scoring weight. Don't touch. |
| `phoenix_experiments.py` optional A/B | 4/10 | Lowest-value code in the repo; the honest "we evaluate live" reframing in evaluator.py is better. Leave it, never mention it. |

## Winnability by judging criterion (25% each)

- **Idea: 9/10.** Meta-agent supervising agents via observability is the perfect Arize-track fit; recursive self-supervision targets their bonus criterion.
- **Tech: 8/10 if deployed and on Gemini; 5/10 as it stands.** Dual-direction MCP is top-tier; thin ADK, no Agent Engine run, and OpenAI-under-the-hood drag it down.
- **Impact: 8/10.** CI gate + postmortems + BYO flywheel is a real business story; WORKFLOWS.md sells it.
- **Design: 7.5/10.** The architecture (Incident threading, single gateways, one source of truth) is the design strength, not the cockpit.

## Final priority order for the remaining hours

1. **Deploy to Cloud Run now** (docs/DEPLOYMENT.md has every command). Blockers: Arize Cloud
   Phoenix space + key, Secret Manager secrets. After deploy, explicitly verify
   `REPLAY_SHARED_SECRET` works end-to-end (one replay; confirm before/after actually differ).
2. **Record the <=3-min video** immediately after: trap -> caught -> diagnosed -> dataset in
   Phoenix -> patch diff -> **replay before/after FIXED (linger)** -> red-team table ->
   postmortem. On the Gemini backend if at all feasible.
3. **Devpost writeup** from docs/PITCH.md, mapping each criterion, leading with the dual-MCP
   story and the flywheel, proactively defending the thin-ADK decision.
4. Only if 1-3 are done: one real Agent Engine invocation so "ran on Agent Engine" is literally true.

Skip everything else - no red-team generation upgrade, no UI polish, no new features.
The codebase is good. The submission is what's unfinished.

## Verification

- `pytest -q`: 39 passed (1 deprecation warning from google-adk LoopAgent).
- `git status`: clean; local main in sync with origin/main at review time.
- Review grounded in code reads of `loop_agent.py`, `mcp_server.py`, `evaluator.py`,
  `redteam.py`, `selfeval.py`, `traps.py`, deploy manifests, and the 06-10 session logs.
