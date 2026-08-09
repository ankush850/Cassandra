# Session Log: 2026-06-11 (late night) - First Real Cloud Run Deploy

## Scope

Executed the Cloud Run deployment from docs/DEPLOYMENT.md for the first time, on the NEW
GCP project **`cassandra-498318`** (account priyalm2503@gmail.com - note: this replaces
`project-c22b7a3a-10c5-463c-9d0` referenced in older notes). Both services are deployed
and healthy server-side; one external blocker remains (see "Where this stopped").

**DEADLINE REMINDER: submission closes 2026-06-12 02:30 IST (= 2026-06-11 14:00 PDT).**

## One-time GCP setup completed (all on cassandra-498318)

- APIs enabled: run, cloudbuild, artifactregistry, secretmanager, firestore, aiplatform.
- Artifact Registry docker repo `cassandra` (us-central1).
- Firestore native database (us-central1) for the Watcher cursor / dedupe state.
- Secrets created in Secret Manager: `phoenix-api-key` (the ACTIVE key from `.env` -
  verified it authenticates against the Arize Cloud space), `openai-api-key` (from `.env`),
  `replay-shared-secret` (freshly generated 48-hex-char random).
- IAM: runtime SA (`905502723393-compute@...`) got `secretmanager.secretAccessor` +
  `datastore.user`; the same SA acting as the Cloud Build agent got
  `storage.objectViewer`, `logging.logWriter`, `artifactregistry.writer`, `run.admin`,
  and `iam.serviceAccountUser` on itself (user-approved; required since Cloud Build
  stopped auto-granting these on new projects).

## Phoenix

- Cloud space URL: `https://app.phoenix.arize.com/s/U3BhY2U6NDU1NTU6TGIrYw==` (was only in
  `.env` comments; the active `PHOENIX_API_KEY` works against it - verified via
  `/v1/projects`). The space is currently EMPTY; deployed services will populate it.
- `.env` still points local (`127.0.0.1:6006`) for local dev; the cloud URL is passed to
  the services via the `_PHOENIX_BASE_URL` build substitution.

## Build failures fixed along the way (commit 8de42d7, pushed)

1. **403 on source bucket** - build agent lacked storage read; fixed by the IAM grants above.
2. **Empty image tag** - `$SHORT_SHA` is only set by build triggers; manual
   `gcloud builds submit` must pass `--substitutions=SHORT_SHA=<git short sha>,...`.
3. **PowerShell comma-splitting** - the `--substitutions` value must be ONE quoted string
   or PS splits it into an array at the comma.
4. **`OSError: License file does not exist: LICENSE`** - pyproject declares
   `license = {file="LICENSE"}` + `readme = "README.md"` but the Dockerfile never copied
   them; now `COPY pyproject.toml LICENSE README.md ./`.
5. **`ModuleNotFoundError: No module named 'openai'`** (patient crashed at startup) -
   `openai` was never a declared dependency; it only worked locally because it was
   installed by hand. Added `openai>=1.50.0` AND `openinference-instrumentation-openai`
   (without the latter, self-tracing into `cassandra-meta` silently no-ops in prod).
   Swept all module-level third-party imports; the rest are covered (dotenv comes via
   pydantic-settings; `phoenix` is lazily imported in the flag-gated experiments module).

## Deployed state (server-side verified healthy)

- **patient**:  https://patient-m7jvqfpdba-uc.a.run.app   (revision patient-00002-r88)
- **dashboard**: https://dashboard-m7jvqfpdba-uc.a.run.app (revision dashboard-00002-hvz,
  `PATIENT_ENDPOINT` already updated to the patient URL + `/chat` - pass 2 done)
- Both: Ready=True, RoutesReady=True, 100% traffic, ingress=all, allUsers invoker.
- Containers passed startup probes => the app code serves fine on :8080.

## Where this stopped (THE one open blocker)

**Google's edge returns the www-style 404 ("That's all we know") for both public URLs**,
on both URL formats (`*-uc.a.run.app` and `patient-905502723393.us-central1.run.app`),
>25 minutes after deploy. DNS resolves correctly to genuine Cloud Run GFE IPs
(34.143.72-79.x) from both local and 8.8.8.8; no request ever reaches the containers
(zero request logs). Service config is fully correct, so this is hostname registration
at Google's frontend, not our bug.

### Resume checklist for tomorrow morning (in order)

1. `curl https://patient-m7jvqfpdba-uc.a.run.app/healthz` - it may simply have propagated
   overnight. If 200: also check dashboard `/healthz`, then open the dashboard `/`,
   send the canonical trap ("refund window for orders shipped to Germany?"), and watch a
   full cycle run against the Arize Cloud space.
2. If still 404: `gcloud run services delete patient dashboard --region us-central1`,
   then rerun the build (one quoted string!):
   `gcloud builds submit --config deploy/cloudbuild.yaml --substitutions="SHORT_SHA=$(git rev-parse --short HEAD),_PHOENIX_BASE_URL=https://app.phoenix.arize.com/s/U3BhY2U6NDU1NTU6TGIrYw=="`
   then re-run pass 2:
   `gcloud run services update dashboard --region us-central1 --update-env-vars "PATIENT_ENDPOINT=<patient-url>/chat"`
3. Verify the replay token gate end-to-end (one replay; before/after must DIFFER -
   if they are identical the secret is not round-tripping and all demo deltas will be ~0).
4. Then the remaining submission items: demo video (<=3 min, replay before/after is the
   centerpiece), Devpost writeup from docs/PITCH.md, optional Agent Engine run
   (`python -m deploy.agent_engine`), and update the README status table (hosted URL).

## Security follow-ups (post-submission)

- Two old Phoenix API keys sit in plaintext COMMENTS in `.env` - delete/rotate them.
- Rotate the OpenAI key (flagged since 06-05; it has been pasted in working sessions).

## Also this session

- Wrote the deadline-day feature review with ratings + priorities:
  `docs/sessions/2026-06-11-feature-review-and-priorities.md` (commit 5615876).
- 39 offline tests pass; `.env` unchanged (servers would need restart anyway, but no
  config values were edited - only Secret Manager copies were made).
