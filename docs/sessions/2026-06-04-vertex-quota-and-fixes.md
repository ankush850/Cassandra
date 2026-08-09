# Session Notes — Vertex AI switch, 429 quota investigation & resilience fixes

**Date:** 2026-06-04
**Scope:** Point Cassandra at a new GCP project via Vertex AI, get frontend+backend running, fix the `/selfeval` crash, bump the model, and resolve (definitively) the Gemini 429 quota question.

---

## 1. Credentials / environment

New GCP project adopted for inference via **Vertex AI**:

- `GOOGLE_CLOUD_PROJECT=project-c22b7a3a-10c5-463c-9d0` ("My First Project", billing **enabled**).
- Auth: **Application Default Credentials (ADC)** already present at
  `C:\Users\Sirjan\AppData\Roaming\gcloud\application_default_credentials.json` — verified working.
- Vertex AI API (`aiplatform.googleapis.com`) is **Enabled**.

### Key learnings about credentials
- The pasted `AQ.Ab8…` value was a **short-lived OAuth access token** (`gcloud auth print-access-token`). It **cannot** go in `.env` — the `google-genai` SDK does not read a token env var, and it expires in ~1h.
- Vertex auth is **IAM/ADC**, *not* API keys. With `vertexai=True`, the SDK calls `google.auth.default()` which discovers credentials from (in order): `GOOGLE_APPLICATION_CREDENTIALS` → ADC file → metadata server. ADC is **per-user**, so it works across all the user's projects.

### `.env` final state (relevant keys)
```
GOOGLE_CLOUD_PROJECT=project-c22b7a3a-10c5-463c-9d0
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=true
GEMINI_MODEL=gemini-3.5-flash
# OPENAI_API_KEY=...  ← COMMENTED OUT (see gotcha below)
GEMINI_API_KEY=AIza…   # ignored while USE_VERTEXAI=true; kept for fallback
```

### ⚠️ Gotcha that silently disables Gemini
`cassandra/config.py` `is_openai` returns `True` whenever `OPENAI_API_KEY` is set, and
`cassandra/llm.py` checks `if s.is_openai or s.is_openrouter:` **first** — so a set
`OPENAI_API_KEY` routes **all** LLM calls to OpenAI and bypasses Vertex/Gemini entirely.
It must stay commented to use Vertex.

---

## 2. Running the app (local)

Two long-running services + an optional one-shot pipeline (per README "Run Locally"):

```
python -m uvicorn patient.agent:app   --port 8082 --host 127.0.0.1   # backend victim agent (ShopBot)
python -m uvicorn dashboard.main:app   --port 8085 --host 127.0.0.1   # frontend cockpit (SSE + UI) + APIs
python scripts/run_pipeline.py                                         # drive one supervision cycle
```

- **Frontend cockpit:** http://127.0.0.1:8085 (self-contained `dashboard/ui/index.html`, no Node build).
- **Backend:** http://127.0.0.1:8082 (`/chat`, `/healthz`; `/` returns 404 by design).
- The legacy `web/` React app is **not** wired in anymore.
- Servers cache settings at startup → **restart after any `.env` or code change** (not run with `--reload`).

---

## 3. The `/selfeval` 500 bug — diagnosed & fixed

**Symptom (browser):** `self-eval failed: Unexpected token 'I', "Internal S"... is not valid JSON`.

**Root cause:** `SelfEvaluator.evaluate()` fired **all 11 labeled traps at once** via `asyncio.gather`,
and each trap makes **2 Gemini calls** (patient reply + diagnostician judge) = **22 concurrent calls**.
On the new project's Dynamic Shared Quota this burst returned `429 RESOURCE_EXHAUSTED`; the dashboard
didn't catch it, so the browser got raw HTML "Internal Server Error" → JSON parse error.

**Fixes applied:**
1. `cassandra/llm.py` — added `_gen_with_retry()`: exponential backoff (4→8→16→32→60s, capped) **+ jitter**,
   7 attempts, retries on `429`/`503`. Wraps both `structured()` and `text()` Gemini calls.
2. `patient/agent.py` — routed its direct `generate_content` call through the same `_gen_with_retry`.
3. `cassandra/selfeval.py` — bounded concurrency via `asyncio.Semaphore` (param `concurrency`, default 3).
4. `dashboard/main.py` — `/selfeval` now runs at `concurrency=1` and returns **JSON on failure**
   (with a helpful "Vertex quota exhausted" hint) instead of an HTML 500.

**Result:** full 11-trap self-eval returns **HTTP 200 + valid scorecard, zero hard failures** on Vertex.

---

## 4. Model

- Switched `GEMINI_MODEL` from `gemini-2.5-flash` → **`gemini-3.5-flash`** (confirmed available on the
  project and working end-to-end). Model is read in one place (`s.gemini_model`), so it applies to the
  patient, diagnostician, judge, and every pipeline stage at once.
- Available Gemini models on the project include: `gemini-3.5-flash`, `gemini-3.1-pro-preview`,
  `gemini-3-flash-preview`, `gemini-2.5-pro/flash/flash-lite`, `gemini-2.0-flash-001`, `gemini-1.5-pro-002`,
  plus embeddings `gemini-embedding-2`. Model choice is just an env var — nothing is hardcoded.

---

## 5. The 429 quota question — DEFINITIVE conclusion

**You cannot raise the request-rate quota for Gemini *text* generation on this project. It is Dynamic
Shared Quota (DSQ), managed by Google, with no adjustable number.**

Verified **four independent ways**:
1. Manual scroll of the full quota console.
2. Cloud Quotas REST API → **0 adjustable generate-content metrics**.
3. `gcloud quotas info list` → no `generate_content` request metrics.
4. The API's own Quotas page (76 rows), which shows:
   - `gemini-2.5-flash-ga` **input tokens/min = `Unlimited`** (not token-capped).
   - The only adjustable **`requests per minute`** rows are `-tts` / `-image` variants (value 5) —
     **no request-per-minute row exists for any text flash model**, global or regional.

So the `429 RESOURCE_EXHAUSTED` is **shared request-capacity throttling**, not a project cap.

### Things that are NOT the fix (for this case)
- Editing quota in the console — there's no relevant row to edit.
- Switching region (`global` → regional) — text flash RPM is DSQ everywhere; no regional row either.
- The `gemini-2.5-pro` token/min row (1M, adjustable) — that's *tokens* (already Unlimited on flash) and *pro*.

### What actually works (ranked)
1. **Client-side retry/backoff** ← implemented & proven. The supported way to live on DSQ. Trade-off: latency under bursts, never a hard failure.
2. **Provisioned Throughput** (Vertex AI → Provisioned Throughput) — paid reserved capacity; overkill for a hackathon.
3. **Wait** — DSQ headroom grows automatically as the project accrues billing over days.
4. **Gemini API-key path** (`GOOGLE_GENAI_USE_VERTEXAI=false`) — separate, higher free-tier RPM; user chose to **stay on Vertex** instead.

### Optional knobs to reduce (not eliminate) waits, still on Vertex
- Lighter model: `GEMINI_MODEL=gemini-2.5-flash-lite`.
- Lower burst (self-eval already at `concurrency=1`; live supervision loop is naturally low-rate).

---

## 6. Files changed this session
- `.env` — Vertex project/location/model; `OPENAI_API_KEY` commented out.
- `cassandra/llm.py` — `_gen_with_retry()` + wrapped Gemini calls; `import asyncio, random, genai errors`.
- `patient/agent.py` — import + wrap `generate_content` in `_gen_with_retry`.
- `cassandra/selfeval.py` — semaphore-bounded concurrency.
- `dashboard/main.py` — `/selfeval` JSON error handling + `concurrency=1`; import `JSONResponse`.

---

## 7. Open items (NOT done)
- [ ] **Commit** all of the above — still in the working tree, nothing committed to git.
- [ ] **Diagnostician accuracy ≈ 18%** — real logic bug, independent of quota. Self-eval shows it flags
      legitimate `ok` traffic (US/UK refund, order status) as `hallucination` (0/3), labels `tool_failure`
      cases as `hallucination` (0/2), and confuses `hallucination` ↔ `prompt_drift`. Likely the
      Diagnostician prompt / label definitions (possibly tuned for a different model than 3.5-flash).
      Worth fixing before relying on the scorecard for the submission.

---

## 8. Quick reference — restart everything
```powershell
# kill listeners on 8082/8085, then:
python -m uvicorn patient.agent:app  --port 8082 --host 127.0.0.1
python -m uvicorn dashboard.main:app --port 8085 --host 127.0.0.1
# smoke test:
#   GET  http://127.0.0.1:8082/healthz
#   GET  http://127.0.0.1:8085/healthz
#   POST http://127.0.0.1:8085/selfeval   (slow on DSQ; returns scorecard JSON)
```
