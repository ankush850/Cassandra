# Session Log: 2026-06-10 (2) - Pre-deploy Hardening, Cockpit Rework, Pitch

## Scope

Pre-deployment pass before the gcloud/Cloud Run deploy for the hackathon: full project audit, security fixes, frontend rework of the cockpit, a written pitch, and doc updates.

## Security audit findings and fixes

### 1. system_override hijack on public deploys (HIGH, fixed)

`deploy/cloudbuild.yaml` deploys the Patient with `--allow-unauthenticated`, and the only gate on `system_override` (which replaces the whole system prompt of a tool-using agent) was `session_id == "test"`. Both fields are attacker-controlled on a public endpoint, so anyone could fully hijack ShopBot's prompt.

**Fix:** added `REPLAY_SHARED_SECRET` (new `Settings.replay_shared_secret` in `cassandra/config.py`). When set, `patient.agent.resolve_override()` additionally requires the caller to present the secret in the `X-Cassandra-Token` header. New helper `cassandra.config.replay_auth_headers()` attaches it; wired into every override caller: `replay.py`, `evaluator.py`, `redteam.py`, `phoenix_experiments.py`. Unset (local dev) keeps the old session-gate-only behavior, so nothing breaks locally. **Important: on a deployed pair, the secret must be set on BOTH services or replay/eval/red-team silently lose the override** (the Patient drops it and scores the baseline prompt twice).

### 2. Unbounded input on public LLM endpoints (MEDIUM, fixed)

`/chat` (Patient) and `/ask` (dashboard proxy) accepted arbitrarily long messages: a cost/abuse vector against the LLM backends. Added Pydantic `min_length`/`max_length` caps (4000 chars on `/chat`, 2000 on `/ask`).

### 3. Container ran as root (LOW, fixed)

`deploy/cloudrun.Dockerfile` now creates and switches to a non-root `appuser` (uid 1001).

### 4. Verified non-issues

- `.env` is gitignored (`.env`, `.env.*`, `!.env.example`) and was never committed (`git log --all -- .env` is empty).
- Dashboard UI escapes all event payload fields through `esc()` before insertion (no XSS from pipeline/SSE data, including the diff viewer which escapes before splitting).
- No `os.environ` reads outside `cassandra/config.py`; secrets flow through Secret Manager in `cloudbuild.yaml`.
- The Watcher's three-signal feedback-loop filter from the earlier session is intact.

## Deploy manifest fixes

`deploy/cloudbuild.yaml`:
- Both services now mount the `replay-shared-secret` Secret Manager secret as `REPLAY_SHARED_SECRET` (create it before running the build: `gcloud secrets create replay-shared-secret ...`).
- New `_PATIENT_URL` substitution sets `PATIENT_ENDPOINT` on the dashboard service so its in-process pipeline drives the deployed Patient instead of localhost. Set it after the Patient's first deploy.

`.env.example`: ports fixed to match the documented/config defaults (dashboard 8085, patient 8082; they previously said 8080/8081) and the new `REPLAY_SHARED_SECRET` documented. CLAUDE.md port-mismatch note updated accordingly. Reminder: settings are cached; servers must restart to pick up `.env` changes.

## Frontend rework (`dashboard/ui/index.html`)

- **Pipeline tracker promoted.** The 8-stage supervision tracker moved from the bottom of the left rail to a horizontal stepper directly above the live feed, with connector segments between stages. Same element ids (`st-<stage>`), so `markStage()` logic is unchanged.
- **Pitch hero strip** added under the header: one-sentence pitch ("Agents fail silently in production. Cassandra catches the failure in live traces, diagnoses it, proves a fix, and red-teams it: autonomously, in one loop.") plus three value chips (8-stage autonomous loop, Arize Phoenix native, grades its own accuracy). Chips hide under 920px.
- Left rail keeps Drive-the-Patient, Session stats, and Self-evaluation panels.

## Pitch

New `docs/PITCH.md`: problem, idea, the 8-stage loop, the recursive self-evaluation twist, demo narrative, judging-criteria mapping, stack, tagline ("Agents fail silently. Cassandra hears them."). Written for the website/Devpost/video. Linked from the README docs table.

## Verification

- `pytest` full suite passes (29 tests; security tests extended to cover the token gate and `replay_auth_headers()`).
- `ruff check .` clean on changed files.
- Live smoke test: dashboard served on a scratch port; `/healthz` ok, `/` renders with the new hero and horizontal tracker.

## Files touched

`cassandra/config.py`, `patient/agent.py`, `cassandra/replay.py`, `cassandra/evaluator.py`, `cassandra/redteam.py`, `cassandra/phoenix_experiments.py`, `dashboard/main.py`, `dashboard/ui/index.html`, `deploy/cloudrun.Dockerfile`, `deploy/cloudbuild.yaml`, `.env.example`, `tests/test_patient_security.py`, `docs/PITCH.md`, `README.md`, `CLAUDE.md`.

## Open items

- Create the `replay-shared-secret` and `phoenix-api-key` secrets in Secret Manager, run the Cloud Build, then set `_PATIENT_URL` and redeploy the dashboard.
- Vertex Agent Engine deployment still pending (needs GCP credentials).
- Demo video recording.
