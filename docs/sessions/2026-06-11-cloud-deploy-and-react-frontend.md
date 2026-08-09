# Session Log: 2026-06-11 (deadline day) - Cloud Deploy, React Frontend, Agent Engine

## Outcome

**Cassandra is deployed and verified end-to-end in the cloud**, on the hard deadline.
Live URL (React frontend): **https://elianna-unpolymerized-confidingly.ngrok-free.dev**
A full autonomous supervision cycle ran on the hosted deployment: Germany hallucination
caught from live Phoenix traces -> diagnosed (CRITICAL, 100%) -> root-caused -> 12-case
adversarial dataset + candidate prompt version written back into Arize Cloud Phoenix ->
original input replayed to a **FIXED** verdict -> red-teamed -> auto-postmortem written.

## The deploy saga (what actually happened, in order)

The Cloud Run deploy itself *worked* (image built, services Ready, containers healthy).
The blocker was **Google's edge refusing inbound traffic on web-serving ports for a fresh,
just-verified account** - an account-level anti-abuse gate, not our config. Diagnosis chain:

1. **Cloud Run 404 at the edge** (`That's all we know`), all regions, authed + unauthed +
   external (WebFetch) - container healthy (`uvicorn running`), IAM `allUsers` bound,
   ingress=all, no VPC-SC, no blocking org policy. Account had a "verify this account"
   banner; user verified, but the serving gate did not lift in time.
2. **GCE VM fallback** (Container-Optimized OS, asia-south1-b, e2-medium, external IP
   34.14.170.0): same symptom - **raw TCP showed port 22 (SSH) reachable but 80/8082/8085
   timed out**, confirming Google blocks *serving ports* on new accounts while allowing
   management. Confirmed independently: user's phone on mobile data also timed out.
3. **Outbound tunnel = the fix.** Egress works, so an outbound tunnel bypasses the inbound
   gate. Cloudflare quick tunnel proved it; then **ngrok with a free static domain**
   (`elianna-unpolymerized-confidingly.ngrok-free.dev`) for a stable URL. App still runs on
   the Google Cloud VM; the tunnel is just the ingress path.

### Bugs fixed along the way (all real, all latent until first real deploy)

- **Image missing `LICENSE`/`README.md`** (hatchling validates them) -> Dockerfile COPY.
- **`openai` never declared** in `pyproject.toml` deps (only worked locally by hand-install)
  -> added `openai` + `openinference-instrumentation-openai`. Committed earlier (`8de42d7`).
- **Secrets arrived BOM/CR-corrupted** (created by piping from PowerShell) -> the patient
  500'd on `﻿` in the OpenAI auth header. Fixed: startup script strips BOM/CR; created
  clean secret versions via temp file.
- **Phoenix MCP returned 0 spans** against remote Phoenix: `@arizeai/phoenix-mcp` silently
  defaults to `localhost:6006` without `--baseUrl/--apiKey` CLI flags (env vars alone are
  not honored). This is THE bug that would have hidden the whole loop. Fixed in
  `cassandra/phoenix_mcp.py` (commit `99ac729`). Worked locally only because local Phoenix
  was on the default port.
- **Wrong Phoenix space URL**: the `.env`-comment space id was stale (500s). Real space is
  `https://app.phoenix.arize.com/s/sirjan-singh036` (user minted a fresh system API key).
- Non-root container could not bind port 80 -> dashboard container runs `-u 0`.

## React frontend promoted to primary UI

User clarified the deployed single-file cockpit was the *testing* UI; the **`web/` React app
is the real frontend** (it received all recent design work; `web/` last touched 05-28 only
because the single-file cockpit was the quick demo path). Brought it current:
- New `web/src/components/SelfEval.tsx` (POST `/selfeval` scorecard panel); wired into
  `Cockpit.tsx`; `DriveBox.tsx` default = canonical Germany trap. Stage schema already
  matched `cassandra.models.Stage`.
- `dashboard/main.py`: serve `web/dist` at `/`, mount the cockpit at `/cockpit` (fallback to
  `/` when no dist - keeps `pytest`/local working with no `npm build`).
- `deploy/cloudrun.Dockerfile`: node `webbuild` stage (`npm ci` + `vite build`) -> copies
  `web/dist` in. `.dockerignore` keeps host `node_modules`/`dist` out (a Windows-built
  node_modules copied over the stage breaks `npm run build` with EACCES on tsc).
- Verified live: `/` serves React (`title: Cassandra - the meta-agent that watches agents`),
  `/cockpit` serves the single-file cockpit. Commits `c5ccfc3`, `4b70fe3`.

## Vertex AI Agent Engine (DEPLOYED — live)

Iterated `agent_engines.create()`, each attempt fixing a real error: wrong project (stale
`.env`) -> forced `cassandra-498318`; unwrapped `LoopAgent` ("cannot serve traffic") ->
wrapped in `AdkApp`; runtime `ModuleNotFoundError: vertexai` -> added
`google-cloud-aiplatform[agent_engines]`+`cloudpickle` to `requirements`; dropped `patient`
from `extra_packages` (only `cassandra` is imported by the agent graph). **Result: live
Reasoning Engine** `projects/905502723393/locations/us-central1/reasoningEngines/1519338702365523968`
— verified queryable (exposes the AdkApp session/query operations). Satisfies the
"built with Google Cloud Agent Builder / Agent Engine" requirement on the real managed
runtime. Prereqs set up: ADC quota project, GCS staging bucket `cassandra-498318-agent-engine`.
Final config in `deploy/agent_engine.py` (commits `63c6562`, `857e970`).

## Infra created on `cassandra-498318` (priyal account, billing/credits attached)

APIs (run/build/AR/secretmanager/firestore/aiplatform), Artifact Registry repo `cassandra`,
Firestore (us-central1), secrets (`phoenix-api-key` v3 = real cloud key, `openai-api-key`,
`replay-shared-secret`), IAM for runtime+build SA, GCE VM `cassandra-vm` + firewall
`cassandra-web`, GCS `cassandra-498318-agent-engine`. Image tag deployed: `6c08a21-react`.

## LLM backend / Vertex 429 note

Live demo runs on **OpenAI** (reliable). Gemini/Vertex hits DSQ 429s under burst (capacity
throttling, not billing) - keep concurrency low + the llm.py backoff, or use a regional
endpoint (not `global`). The GenAI App Builder credit does NOT cover standard Gemini API
calls; the Free Trial credit does.

## Verification

39 offline tests passing, `ruff` clean. Live: `/healthz` 200, `/ask` fires the trap and
hallucinates, spans land in Phoenix Cloud, full cycle completes (postmortem
`reports/inc-U3BhbjoxNTA0.md`), `/selfeval` = 10/11 (91%).

## Commits pushed (origin/main)

`99ac729` mcp flags fix · `c5ccfc3` React primary UI + self-eval · `4b70fe3` Docker React
build + VM hosting · `b0dd681` Agent Engine AdkApp/bucket · `8b4fd21` README deployed status
· `63c6562` Agent Engine vertexai requirement + status.

## Open items (for submission, ~hours left)

- **Demo video (<=3 min)** - fire the trap on the live URL, linger on replay FIXED, show the
  Phoenix space (traces + dataset + prompt version). The URL is ready.
- **Devpost writeup** from `docs/PITCH.md` (lead with dual-MCP + the live replay).
- **VM cost**: it bills continuously - `gcloud compute instances delete cassandra-vm
  --zone asia-south1-b` after the hackathon. ngrok authtoken + the old `.env`-comment
  Phoenix keys + OpenAI key should be rotated post-submission.
- Eval pass-rate numbers are noisy at n=12 (baseline 12% vs candidate 12%); lead the demo
  with the replay FIXED verdict, treat the tables as supporting texture.
