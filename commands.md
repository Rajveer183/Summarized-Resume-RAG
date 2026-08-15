# commands.md — Deploying Summarized-Resume-RAG to GCP

Exact, copy-pasteable commands to take this repository from a fresh GCP project to a running production deployment on Cloud Run (backend + frontend), Artifact Registry, Cloud Storage, and Secret Manager.

This file reflects the actual repository structure:

```
backend/
  Dockerfile            local dev image (docker-compose only, context=./backend)
  Dockerfile.gcp         Cloud Run image (this guide), context=project root
  requirements.txt
  ingest.py
  app/{main,config}.py, app/api/, app/services/, app/utils/, app/prompts/, app/templates/
  evaluation/            accuracy reports (evaluation/reports/cache/*.json is checked into git)
frontend/
  Dockerfile             local dev image (docker-compose only, nginx.conf proxies to "backend:8000")
  Dockerfile.gcp         Cloud Run image (this guide), nginx.gcp.conf, no proxy
  nginx.conf / nginx.gcp.conf
  firebase.json          alternative: static hosting instead of a frontend container
  src/api/resumeApi.js   reads VITE_API_URL at build time
data/data/<CATEGORY>/*.pdf   gitignored, must exist locally before building the backend image
.dockerignore, .gcloudignore
```

Two deliberate design decisions, both explained in comments inside the files themselves:

1. **`data/data/` and `backend/chroma_db/` are baked into the backend image** (via `backend/Dockerfile.gcp`, built with the project root as context), not mounted from Cloud Storage. Both are read-mostly after ingestion, and ChromaDB's SQLite/HNSW index files don't behave reliably over a GCS FUSE mount. Trade-off: rebuild + redeploy after re-ingesting.
2. **`backend/generated_resumes/` is a real Cloud Storage volume mount** on the Cloud Run backend service. This is a good fit for GCS FUSE (whole-file PDF writes, no locking) and it also fixes a latent bug: with more than one Cloud Run instance, a resume generated on instance A and downloaded from instance B would 404 without shared storage.

---

## 0. Prerequisites

Install locally:

- [`gcloud` CLI](https://cloud.google.com/sdk/docs/install), authenticated: `gcloud auth login`
- Docker Desktop (you already have this — used for local validation before deploying; Cloud Build does the actual production image builds, so Docker isn't required for the deploy itself, only for the local test pass below)
- Node.js 18+ (`node --version`)
- Optional, only if you choose Firebase Hosting for the frontend instead of Cloud Run: `npm install -g firebase-tools`

You'll also need:
- An NVIDIA NIM API key: https://build.nvidia.com/
- Optionally a Hugging Face token: https://huggingface.co/settings/tokens
- `data/data/` present locally with your 24 category PDF folders (it's gitignored — this repo does not ship the dataset)

Set these once, reuse everywhere below:

```bash
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1
export AR_REPO=resume-rag
export BACKEND_SVC=resume-rag-backend
export FRONTEND_SVC=resume-rag-frontend

gcloud config set project $PROJECT_ID
```

---

## 1. Build the vector database (once, locally)

Skip if `backend/chroma_db/` already exists and is populated.

```bash
cp .env.example .env
# edit .env: set NVIDIA_API_KEY (and optionally HF_TOKEN)

cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
python backend/ingest.py
```

Confirm it worked: `ls backend/chroma_db` should show Chroma's SQLite + segment files, not be empty.

> Note: `backend/requirements.txt` pins `torch==2.13.0+cpu` / `torchvision==0.28.0+cpu` / `torchaudio==2.13.0+cpu`. If you're reading this after having pulled an older copy of the repo, check that all three share the same `2.13`/`0.28` line — an earlier revision had `torchaudio==2.11.0+cpu` pinned against `torch==2.13.0+cpu`, an incompatible pairing that breaks `pip install`. This has been corrected on the `gcp-deployment` branch.

---

## 2. Local Docker validation (do this before touching GCP)

Validate both images build and actually serve traffic on your machine first. Run from the **project root**.

### Backend

```bash
docker build -f backend/Dockerfile.gcp -t resume-rag-backend:local .

docker run --rm -p 8000:8000 --env-file .env --name resume-rag-backend-test resume-rag-backend:local
```

In another terminal:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/categories
# should list your 24 categories if data/data/ was present at build time

# only if backend/chroma_db was populated before building:
curl -N -X POST http://localhost:8000/generate-resume \
  -H "Content-Type: application/json" \
  -d "{\"category\": \"INFORMATION-TECHNOLOGY\"}"

docker inspect --format='{{json .State.Health}}' resume-rag-backend-test
```

Stop with `docker stop resume-rag-backend-test`.

### Frontend

```bash
docker build -f frontend/Dockerfile.gcp \
  --build-arg VITE_API_URL=http://localhost:8000 \
  -t resume-rag-frontend:local frontend/

docker run --rm -p 8080:8080 --name resume-rag-frontend-test resume-rag-frontend:local
```

```bash
curl http://localhost:8080/healthz
open http://localhost:8080   # or just visit it in a browser; with the backend container also running,
                              # category selection and generation should work end to end
```

Stop with `docker stop resume-rag-frontend-test`.

If either build/run step fails, fix it here before moving on to GCP — everything below assumes both images work locally first.

---

## 3. One-time GCP project setup

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com

gcloud artifacts repositories create $AR_REPO \
  --repository-format=docker \
  --location=$REGION \
  --description="Resume RAG images"

gcloud auth configure-docker ${REGION}-docker.pkg.dev

gcloud storage buckets create gs://${PROJECT_ID}-resume-outputs \
  --location=$REGION \
  --uniform-bucket-level-access
```

### Secrets

```bash
printf "%s" "your_nvidia_api_key_here" | gcloud secrets create NVIDIA_API_KEY --data-file=-
printf "%s" "your_hf_token_here"       | gcloud secrets create HF_TOKEN --data-file=-

export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
export RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding NVIDIA_API_KEY \
  --member="serviceAccount:${RUNTIME_SA}" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding HF_TOKEN \
  --member="serviceAccount:${RUNTIME_SA}" --role="roles/secretmanager.secretAccessor"

gcloud storage buckets add-iam-policy-binding gs://${PROJECT_ID}-resume-outputs \
  --member="serviceAccount:${RUNTIME_SA}" --role="roles/storage.objectAdmin"
```

`RUNTIME_SA` here is the default Compute Engine service account Cloud Run uses unless you specify `--service-account`. If your org requires a dedicated service account, create one with `gcloud iam service-accounts create` and pass it explicitly to every `gcloud run deploy` below.

---

## 4. Build and push the backend image

```bash
gcloud builds submit \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/backend:v1 \
  --file backend/Dockerfile.gcp \
  --timeout=30m \
  .
```

Run from the **project root** — the trailing `.` is the build context and needs to see both `backend/` and `data/`.

---

## 5. Deploy the backend to Cloud Run

```bash
gcloud run deploy $BACKEND_SVC \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/backend:v1 \
  --region $REGION \
  --platform managed \
  --port 8000 \
  --memory 4Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 4 \
  --concurrency 4 \
  --timeout 600 \
  --execution-environment gen2 \
  --allow-unauthenticated \
  --set-env-vars="NVIDIA_MODEL=meta/llama-3.1-70b-instruct,EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2,LLM_TEMPERATURE=0.3,LLM_TOP_P=0.9,LLM_MAX_TOKENS=3000,RETRIEVAL_TOP_K=12,RETRIEVAL_FETCH_K=30,RERANKER_TOP_N=7" \
  --set-secrets="NVIDIA_API_KEY=NVIDIA_API_KEY:latest,HF_TOKEN=HF_TOKEN:latest" \
  --add-volume=name=outputs,type=cloud-storage,bucket=${PROJECT_ID}-resume-outputs \
  --add-volume-mount=volume=outputs,mount-path=/backend/generated_resumes
```

Why these flags, tied to the actual code:

- `--memory 4Gi --cpu 2`: `requirements.txt` pulls in `torch`, `sentence-transformers`, `chromadb` — 2–4GB is what the README itself calls for.
- `--min-instances 1`: `main.py`'s `startup_event` warms up ChromaDB, and the embedding model loads lazily on first use (`embedding_service.py`). Without a warm instance, first request after scale-to-zero is slow. Set to `0` to save cost if that's acceptable.
- `--timeout 600`: `/generate-resume` streams from an LLM (`stream_generate_resume` in `routes.py`) — longer than Cloud Run's 5-minute default.
- `--port 8000`: matches `EXPOSE 8000` / `CMD` in `backend/Dockerfile.gcp`.
- The volume mount lands at `/backend/generated_resumes`, exactly `config.GENERATED_RESUMES_PATH`'s default — `pdf_generator.py` and `/download/{filename}` need no code changes.
- `FRONTEND_ORIGIN` is deliberately not set yet — you don't have the frontend URL until step 7.

```bash
export BACKEND_URL=$(gcloud run services describe $BACKEND_SVC --region $REGION --format='value(status.url)')
echo $BACKEND_URL
curl $BACKEND_URL/health
curl $BACKEND_URL/categories
```

---

## 6. Build, push, and deploy the frontend (Cloud Run — primary path)

`gcloud builds submit --tag` alone doesn't support `--build-arg`, and this build needs one (`VITE_API_URL`). Two options:

**Option A — build locally with Docker, push to Artifact Registry** (simplest, since you already have Docker Desktop running):

```bash
docker build -f frontend/Dockerfile.gcp \
  --build-arg VITE_API_URL=$BACKEND_URL \
  -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/frontend:v1 \
  frontend/

docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/frontend:v1
```

**Option B — build in Cloud Build** using `frontend/cloudbuild.yaml` (already in the repo), no local Docker required:

```bash
cd frontend
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=_VITE_API_URL=$BACKEND_URL,_IMAGE=${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/frontend:v1 \
  .
cd ..
```

Deploy:

```bash
gcloud run deploy $FRONTEND_SVC \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/frontend:v1 \
  --region $REGION \
  --platform managed \
  --port 8080 \
  --memory 256Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 4 \
  --allow-unauthenticated

export FRONTEND_URL=$(gcloud run services describe $FRONTEND_SVC --region $REGION --format='value(status.url)')
echo $FRONTEND_URL
```

`frontend/nginx.gcp.conf` serves static files only — it does not proxy to a `backend` hostname the way `frontend/nginx.conf` does for local docker-compose, because Cloud Run services don't share a network namespace and nginx would fail to start trying to resolve it. The frontend calls `$BACKEND_URL` directly, baked in via `VITE_API_URL` at build time.

### Alternative: Firebase Hosting instead of a frontend container

If you'd rather not run the frontend as a container at all:

```bash
cd frontend
echo "VITE_API_URL=$BACKEND_URL" > .env.production
npm install && npm run build

firebase login
firebase projects:addfirebase $PROJECT_ID
firebase use --add
firebase deploy --only hosting
# uses frontend/firebase.json, already in the repo
```

This prints a `https://${PROJECT_ID}.web.app` URL — use that in place of `$FRONTEND_URL` in step 7 if you go this route.

---

## 7. Close the loop: CORS

`main.py` hardcodes the CORS allow-list to `config.FRONTEND_ORIGIN` plus three localhost origins — no wildcard. Point it at your real frontend URL and redeploy:

```bash
gcloud run services update $BACKEND_SVC \
  --region $REGION \
  --update-env-vars="FRONTEND_ORIGIN=${FRONTEND_URL}"
```

---

## 8. Verify end to end

```bash
curl $BACKEND_URL/health
curl $BACKEND_URL/categories
curl $FRONTEND_URL/healthz   # only if you deployed the frontend container; Firebase Hosting has no /healthz

# full round trip: open $FRONTEND_URL in a browser, pick a category, Generate, then Download PDF
```

If `/categories` 404s or comes back empty: `data/data/` didn't make it into the backend image — confirm it existed locally when you ran `gcloud builds submit` in step 4.

If generation succeeds but retrieval is empty: `backend/chroma_db` wasn't populated before building — go back to step 1.

---

## 9. Updating data or re-ingesting

`data/` and `chroma_db` are baked in, so any change means rebuild + redeploy:

```bash
python backend/ingest.py   # re-run locally; set INGEST_RESET_DB=true in .env first if needed

gcloud builds submit \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/backend:v2 \
  --file backend/Dockerfile.gcp --timeout=30m .

gcloud run deploy $BACKEND_SVC \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/backend:v2 \
  --region $REGION
```

Cloud Run keeps prior revisions, so this is a zero-downtime rolling update.

---

## 10. Rollback

```bash
# list revisions
gcloud run revisions list --service $BACKEND_SVC --region $REGION

# send all traffic back to a known-good revision
gcloud run services update-traffic $BACKEND_SVC \
  --region $REGION \
  --to-revisions=RESUME-RAG-BACKEND-00001-abc=100
```

Same pattern with `$FRONTEND_SVC` if you deployed the frontend to Cloud Run.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `pip install` fails on `torchaudio` | version mismatch vs `torch` pin | confirm `backend/requirements.txt` has matching `2.13`/`0.28` lines (fixed on this branch) |
| `/categories` returns 404 or empty list | `data/data/` missing from build context | confirm it exists locally before `gcloud builds submit` / `docker build`, check `.gcloudignore` and `.dockerignore` aren't excluding it |
| `/health` OK but generation returns "No data found for category" | `chroma_db` wasn't populated before building | run `python backend/ingest.py`, rebuild |
| nginx container exits immediately on Cloud Run | using `frontend/nginx.conf` (proxies to unresolvable `backend` host) instead of `frontend/nginx.gcp.conf` | use `frontend/Dockerfile.gcp`, not `frontend/Dockerfile`, for Cloud Run |
| CORS error in browser console | `FRONTEND_ORIGIN` not updated after frontend deploy | re-run step 7 |
| First request after idle is slow | `--min-instances 0`, cold start reloading embedding model | set `--min-instances 1`, or accept the tradeoff |
| Intermittent 404 on `/download/{filename}` | generated_resumes volume mount missing | confirm `--add-volume`/`--add-volume-mount` flags applied: `gcloud run services describe $BACKEND_SVC` |
| Cloud Build times out | large image build (torch etc.) | `--timeout=30m` (already set above); consider `E2_HIGHCPU_8` machine type for a custom `cloudbuild.yaml` |
| `docker build` fails locally on `COPY data/ data/` | `data/data/` doesn't exist in your local working copy | it's gitignored — you need the dataset locally first, ingestion instructions are in step 1 |

---

## Cost notes

- `--min-instances 1` on the 2 vCPU / 4Gi backend is the main recurring cost — roughly $50–70/month at current Cloud Run pricing if left running 24/7 in `us-central1`. Set to `0` for a personal/demo project.
- The frontend container is tiny (256Mi/1 vCPU, `--min-instances 0`) — effectively free at low traffic.
- Add a lifecycle rule to the outputs bucket to auto-delete old generated PDFs if storage cost matters: `gcloud storage buckets update gs://${PROJECT_ID}-resume-outputs --lifecycle-file=lifecycle.json`.

---

## Scaling beyond this

- **Large/frequently-changing dataset:** mount `data/` from Cloud Storage instead of baking it in (`--add-volume type=cloud-storage,bucket=...,mount-path=/data,readonly=true` on the backend service, with `DATA_PATH=data` set as an env var override). Fine for `data/` since it's read-only PDFs, not a database.
- **ChromaDB outgrowing a single container:** run Chroma in client/server mode on a small Compute Engine VM or GKE, and point `vector_store.py`'s `chromadb.PersistentClient` calls at `chromadb.HttpClient` instead. This is an application code change, not just deployment config — flagged in the original README's own "GCP Deployment Considerations" section.
- **PDF downloads at higher scale:** the GCS volume mount handles multi-instance consistency today; if you outgrow gcsfuse throughput, switch `pdf_generator.py`/`routes.py` to upload directly to GCS and return a signed URL instead of a local file path.
