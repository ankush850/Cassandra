# Deploying Cassandra to Google Cloud

Verified against project `project-c22b7a3a-10c5-463c-9d0` on 2026-06-10 (dry run: project ACTIVE, billing ENABLED, only `aiplatform.googleapis.com` enabled so far). Two distinct deployments exist; do not confuse them:

1. **Cloud Run (the website + the demo agent).** Deploys two HTTP services from one image: `patient` (ShopBot, the supervised agent) and `dashboard` (the cockpit UI, which also runs the supervision pipeline in-process). This is the hosted URL judges click.
2. **Vertex AI Agent Engine (the meta-agent as a managed agent).** Deploys the same `SupervisionPipeline`, wrapped in an ADK `LoopAgent` (`deploy/agent_engine.py`), to Google's managed agent runtime. Functionally it duplicates what the dashboard's background loop already does; it exists to satisfy and demonstrate the "built with ADK / Agent Engine" requirement. The demo works without it.

## Blockers found in the dry run

- `.env` currently points to a local Phoenix (`http://127.0.0.1:6006`). Cloud Run cannot reach your laptop. Create a free Arize Cloud Phoenix space (https://app.phoenix.arize.com), get its API key and base URL, and use those below.
- `STATE_BACKEND=local` must become `firestore` in the cloud (the cloudbuild manifest now sets this for the dashboard).

## One-time setup (step 0)

```powershell
$PROJECT = "project-c22b7a3a-10c5-463c-9d0"
$REGION  = "us-central1"
gcloud config set project $PROJECT

# Enable required APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com `
  artifactregistry.googleapis.com secretmanager.googleapis.com firestore.googleapis.com

# Docker repo for the image
gcloud artifacts repositories create cassandra --repository-format=docker --location=$REGION

# Firestore database (native mode) for the Watcher cursor + dedupe state
gcloud firestore databases create --location=$REGION

# Secrets (paste each value when prompted; use your Arize Cloud key, not the local one)
"YOUR_PHOENIX_CLOUD_API_KEY" | gcloud secrets create phoenix-api-key --data-file=-
"YOUR_OPENAI_API_KEY"        | gcloud secrets create openai-api-key --data-file=-
"any-long-random-string"     | gcloud secrets create replay-shared-secret --data-file=-

# Let Cloud Run services read the secrets and Firestore
$PROJECT_NUM = gcloud projects describe $PROJECT --format="value(projectNumber)"
gcloud projects add-iam-policy-binding $PROJECT `
  --member="serviceAccount:$PROJECT_NUM-compute@developer.gserviceaccount.com" `
  --role="roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding $PROJECT `
  --member="serviceAccount:$PROJECT_NUM-compute@developer.gserviceaccount.com" `
  --role="roles/datastore.user"
```

## Deploy (step 1: first pass)

```powershell
gcloud builds submit --config deploy/cloudbuild.yaml `
  --substitutions=_PHOENIX_BASE_URL=https://app.phoenix.arize.com
```

This builds the shared image and deploys both services. On the first pass the dashboard's `PATIENT_ENDPOINT` still points at localhost, so:

## Deploy (step 2: wire the dashboard to the Patient)

```powershell
$PATIENT_URL = gcloud run services describe patient --region $REGION --format="value(status.url)"
gcloud run services update dashboard --region $REGION `
  --set-env-vars "SERVICE=dashboard,PATIENT_ENDPOINT=$PATIENT_URL/chat,PHOENIX_BASE_URL=https://app.phoenix.arize.com,GOOGLE_GENAI_USE_VERTEXAI=false,STATE_BACKEND=firestore"
```

(Or rerun the build with `--substitutions=_PATIENT_URL=$PATIENT_URL/chat,...`.)

## Verify

```powershell
$DASH = gcloud run services describe dashboard --region $REGION --format="value(status.url)"
Invoke-RestMethod "$DASH/healthz"      # {"ok":true,...}
Invoke-RestMethod "$PATIENT_URL/healthz"
# open $DASH in a browser, send a customer message, watch the loop run
```

## Vertex AI Agent Engine (the separate, second deployment)

With `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and application-default credentials set (`gcloud auth application-default login`):

```powershell
python -m deploy.agent_engine
```

This packages `build_adk_agent()` (the ADK `LoopAgent` wrapping one supervision cycle per invocation) and creates a managed agent named `cassandra-meta-agent` on Vertex AI Agent Engine. Note: the engine-side runtime still needs network access to your Phoenix URL and the deployed Patient URL via its environment, and it duplicates the dashboard's in-process loop, so treat it as the architecture checkbox, not the demo path.

## Cost notes

Cloud Run scales to zero, but the dashboard's background loop polls Phoenix continuously, which keeps one instance warm; expect a few dollars per day at most with min-instances=0 and the 10 to 30 second poll cadence. Delete with `gcloud run services delete patient dashboard --region $REGION` when done.
