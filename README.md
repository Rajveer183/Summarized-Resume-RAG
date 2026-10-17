# Resume Generation RAG (Summarized-Resume-RAG)

A full-stack **Retrieval-Augmented Generation (RAG)** application that generates professional, anonymized resumes for **24 job categories** using real resume data, NVIDIA NIM LLMs, and ChromaDB vector storage.

The app includes a React UI with resume generation and an accuracy evaluation dashboard, plus a FastAPI backend with ingestion, retrieval, LLM generation, PDF export, and evaluation APIs.

---

## Features

- **24 professional categories** — resumes synthesized from real PDF datasets per category
- **RAG pipeline** — MMR retrieval from ChromaDB (CrossEncoder reranking available but currently bypassed for speed)
- **Streaming UI** — real-time resume generation via Server-Sent Events (SSE)
- **Universal resume template** — fixed section order, category-based designation (e.g. *Professional Healthcare Specialist*), anonymized placeholders
- **PII protection** — names, emails, phones, URLs, and dates removed or replaced during ingest and generation
- **PDF export** — formatted download via ReportLab (WeasyPrint when available)
- **Accuracy dashboard** — evaluate retrieval, category match, content, and privacy metrics per category or all 24 at once

---

## Screenshots

_TODO: add screenshots of the Generator tab (category selection, streaming preview, PDF download) and the Accuracy dashboard, for example under `docs/screenshots/`._

---

## Project Structure

```
project-root/
├── data/data/                    ← 24 resume category folders (PDFs)
├── backend/
│   ├── app/
│   │   ├── main.py               ← FastAPI entry point
│   │   ├── config.py             ← Environment config
│   │   ├── api/                  ← Routes, schemas, evaluation routes
│   │   ├── services/             ← Ingest, retrieval, generation, PDF, sanitizer
│   │   ├── prompts/              ← LLM prompt templates
│   │   ├── templates/            ← HTML resume template
│   │   └── utils/                ← Helpers, category titles, logger
│   ├── evaluation/               ← Accuracy metrics & reports
│   ├── ingest.py                 ← Standalone ingestion script
│   ├── chroma_db/                ← Vector store (auto-created)
│   ├── generated_resumes/        ← PDF + text output (auto-created)
│   └── requirements.txt
├── frontend/                     ← React + Vite UI
├── .env.example
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- NVIDIA NIM API key → [build.nvidia.com](https://build.nvidia.com/)
- (Recommended) Hugging Face token → [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

---

### 1. Configure Environment

```bash
# From project root (this folder)
cp .env.example .env            # Windows: copy .env.example .env
# Edit .env and set NVIDIA_API_KEY (and optionally HF_TOKEN)
```

---

### 2. Backend Setup

```bash
cd backend

# Create a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# Run ingestion (one-time, builds the vector database)
cd ..
python backend/ingest.py

# Start the backend server
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Ingestion note:** First run processes all 24 category PDFs and builds ChromaDB. This typically takes 5–15 minutes depending on your machine. Use `INGEST_RESET_DB=true` in `.env` if you hit ChromaDB HNSW corruption errors, then re-run ingest.

---

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

### 4. Docker Setup (Alternative)

If you prefer to run the entire stack using Docker, you can use `docker-compose`:

```bash
# Make sure .env is created and configured
docker-compose up --build
```
This starts both services in containers. The backend listens on port 8000 and the frontend (nginx) is served on port 80. The compose file mounts `./data`, `backend/chroma_db` and `backend/generated_resumes` into the backend container, so run ingestion first.

---

## Services Overview

| Service  | URL                        |
| -------- | -------------------------- |
| Frontend | http://localhost:5173      |
| Backend  | http://localhost:8000      |
| API docs | http://localhost:8000/docs |


## Using the App

### Generator tab

1. Select a category from the dropdown.
2. Click **Generate Resume**.
3. Preview the structured resume in the UI.
4. Click **Download PDF** for the formatted file.

Generated resumes use a universal template:

- **Header:** category designation only (no name or contact line)
- **Sections:** Professional Summary → Technical Skills → Work Experience → Projects → Education → Certifications → Achievements
- **Placeholders:** XYZ / ABC / DEF Company, XYZ University, anonymized certifications

### Accuracy tab

- **Evaluate Category** — run metrics for one category
- **All Categories (24)** — view a table of retrieval, category match, content, and privacy scores

Reports are cached under `backend/evaluation/reports/`.

---

## API Endpoints

### Core

| Method   | Endpoint                 | Description                    |
| -------- | ------------------------ | ------------------------------ |
| `GET`  | `/health`              | Backend health check           |
| `GET`  | `/categories`          | List all 24 categories         |
| `POST` | `/ingest`              | Run ingestion pipeline         |
| `POST` | `/generate-resume`     | Generate resume for a category |
| `GET`  | `/download/{filename}` | Download generated PDF         |

### Evaluation

| Method  | Endpoint                   | Description                   |
| ------- | -------------------------- | ----------------------------- |
| `GET` | `/evaluate/all`          | Evaluate all categories       |
| `GET` | `/evaluate/{category}`   | Evaluate one category         |
| `GET` | `/accuracy/report/all`   | Cached all-categories report  |
| `GET` | `/accuracy/report`       | Latest single-category report |
| `GET` | `/accuracy/cache/status` | Cache availability            |

### Example: Generate Resume

```bash
curl -X POST http://localhost:8000/generate-resume \
  -H "Content-Type: application/json" \
  -d "{\"category\": \"INFORMATION-TECHNOLOGY\"}"
```

---

## Architecture

```mermaid
flowchart LR
    subgraph Ingest["Ingestion (one-time)"]
        P[Resume PDFs<br/>24 categories] --> L[PDF loader]
        L --> C1[PII cleaner]
        C1 --> CH[Section-aware chunker]
        CH --> EM[Embeddings<br/>all-MiniLM-L6-v2]
        EM --> DB[(ChromaDB<br/>resume_chunks, cosine)]
    end
    subgraph Gen["Generation (per request)"]
        U[User picks category] --> R[MMR retrieval<br/>category-filtered]
        DB --> R
        R --> LLM[NVIDIA NIM LLM<br/>streaming via SSE]
        LLM --> S[Sanitizer<br/>anonymize, strip dates, enforce template]
        S --> T[Resume text]
        T --> PDF[PDF export<br/>ReportLab]
    end
    T --> UI[React UI]
    EV[Evaluation suite] -.-> R
    EV -.-> T
```

See [EXPLANATION.md](EXPLANATION.md) for a step-by-step walkthrough of each stage.

**Key services**

| Service              | Role                                              |
| -------------------- | ------------------------------------------------- |
| `ingest_service`   | Parallel PDF processing and vector upsert         |
| `retriever`        | Category-filtered MMR retrieval                   |
| `reranker`         | CrossEncoder relevance scoring                    |
| `resume_generator` | Prompt build + NVIDIA NIM call                    |
| `resume_sanitizer` | Anonymization, date removal, template enforcement |
| `pdf_generator`    | Parse structured text → ReportLab / HTML PDF     |

---

## Dataset

The corpus is a set of real resume PDFs grouped into **24 category folders** under `data/data/<CATEGORY>/*.pdf` (see [Categories](#categories)). The dataset is **not included** in this repository (`data/` is git-ignored); place your own copy at `data/data/` (or point `DATA_PATH` to it) before running ingestion. Resumes are cleaned of personal information during ingestion (see [Privacy & PII](#privacy--pii)).

## Models

| Role | Model | Notes |
|---|---|---|
| Generation LLM | `meta/llama-3.1-70b-instruct` via NVIDIA NIM (default, `NVIDIA_MODEL`) | Streamed over an OpenAI-compatible API; temperature 0.2 by default |
| Retrieval embeddings | `sentence-transformers/all-MiniLM-L6-v2` (default, `EMBEDDING_MODEL`) | Stored in ChromaDB with cosine distance |
| Reranker | CrossEncoder (implemented in `reranker.py`) | Currently bypassed for speed; top chunks from MMR are used directly |
| Evaluation embeddings | `BAAI/bge-base-en-v1.5` (default, `EVAL_EMBEDDING_MODEL`) | Used only by the evaluation suite, deliberately different from the ingestion model |

Retrieval fetches `RETRIEVAL_FETCH_K` (default 30) candidates filtered by category, applies Maximal Marginal Relevance for diversity, and passes the top results to the LLM.

## Evaluation and results

The Accuracy tab (and `/evaluate/*` endpoints) score each category on four metrics, combined with fixed weights:

| Metric | Weight | What it measures |
|---|---|---|
| Retrieval accuracy | 30% | Share of retrieved chunks whose metadata category matches the selected category |
| Category accuracy | 25% | Whether an embedding-based classifier (BGE) assigns the generated resume to the requested category (100% or 0%) |
| Content accuracy | 30% | Cosine similarity between the generated resume and the retrieved context (BGE embeddings) |
| Privacy accuracy | 15% | 100 minus a penalty for detected PII leaks (emails, phones, URLs, addresses, real-looking names, real organisations) |

**Latest saved all-category report** (`backend/evaluation/reports/report_all.json`, 24 categories, evaluated 31 May – 1 June 2026):

| Retrieval | Category | Content | Privacy | Overall |
|---|---|---|---|---|
| 100.0% | 100.0% | 79.8% | 81.2% | 88.4% |

Per-category overall scores range from 82.9% (ENGINEERING) to 94.9% (APPAREL). Per-category results are in `backend/evaluation/reports/cache/`.

**How to read these numbers.** Retrieval accuracy is 100% largely by construction, because retrieval already filters on the category metadata. Content accuracy measures semantic similarity to retrieved context, not factual quality or recruiter judgment. These are self-evaluation metrics on generated data, not a human evaluation or an external benchmark.

---

## Privacy & PII

Personal information is removed or anonymized at ingest and again after LLM generation:

| Data                          | Handling                                                          |
| ----------------------------- | ----------------------------------------------------------------- |
| Names                         | Removed from output; no “Candidate” header in generated resumes |
| Emails                        | `[EMAIL]` (ingest) / stripped from final resume                 |
| Phone numbers                 | `[PHONE]` (ingest) / stripped from final resume                 |
| URLs (LinkedIn, GitHub, etc.) | `[URL]` (ingest) / stripped from final resume                   |
| Dates & tenure                | Removed (no years, ranges, or “X years experience”)             |
| Real companies / universities | Replaced with XYZ / ABC / DEF Company and XYZ University          |

---

## Categories

ACCOUNTANT, ADVOCATE, AGRICULTURE, APPAREL, ARTS, AUTOMOBILE, AVIATION, BANKING, BPO, BUSINESS-DEVELOPMENT, CHEF, CONSTRUCTION, CONSULTANT, DESIGNER, DIGITAL-MEDIA, ENGINEERING, FINANCE, FITNESS, HEALTHCARE, HR, INFORMATION-TECHNOLOGY, PUBLIC-RELATIONS, SALES, TEACHER

---

## Environment Variables

See `.env.example` for the full list. Important settings:

| Variable                                 | Purpose                                             |
| ---------------------------------------- | --------------------------------------------------- |
| `NVIDIA_API_KEY`                       | Required for resume generation                      |
| `NVIDIA_MODEL`                         | LLM model (default:`meta/llama-3.1-70b-instruct`) |
| `HF_TOKEN`                             | Faster Hugging Face model downloads                 |
| `DATA_PATH`                            | Resume PDF dataset location                         |
| `CHROMA_PERSIST_PATH`                  | ChromaDB storage                                    |
| `INGEST_PDF_WORKERS`                   | Parallel ingest workers                             |
| `INGEST_RESET_DB`                      | Wipe and rebuild ChromaDB on ingest                 |
| `RETRIEVAL_TOP_K` / `RERANKER_TOP_N` | Retrieval tuning                                    |
| `LLM_TEMPERATURE` / `LLM_TOP_P`      | Generation consistency                              |

---

## Tech Stack

- **Backend:** FastAPI, ChromaDB, sentence-transformers, CrossEncoder, ReportLab, NVIDIA NIM (OpenAI-compatible API)
- **Frontend:** React, Vite, Axios, Lucide icons
- **Data:** 24 category PDF corpora under `data/data/` (not included in the repo)
- **Deployment:** Docker, docker-compose, Google Cloud Run / Firebase Hosting

---

## Deployment (GCP)

The repository includes a ready deployment path for **Google Cloud Run**:

- `backend/Dockerfile.gcp` and `frontend/Dockerfile.gcp` (with `nginx.gcp.conf`) for Cloud Run images, plus `frontend/cloudbuild.yaml`.
- `frontend/firebase.json` if you prefer Firebase Hosting for the static frontend.
- Deployment steps: store `NVIDIA_API_KEY` and `HF_TOKEN` in Secret Manager, build the vector database locally, then build and deploy both images to Cloud Run (via Artifact Registry).

Design decisions for the Cloud Run images:

1. `data/data/` and `backend/chroma_db/` are **baked into the backend image**, because ChromaDB's SQLite/HNSW files do not behave reliably on a Cloud Storage FUSE mount. The trade-off is rebuilding and redeploying after re-ingesting.
2. `backend/generated_resumes/` is a **Cloud Storage volume mount**, so a PDF generated on one Cloud Run instance can be downloaded from another.

Allocate at least 2–4 GB of RAM to the backend so the embedding models can load on cold start, and set `VITE_API_URL` to the backend URL before building the frontend.

---

## Troubleshooting

| Issue                           | Fix                                                                                 |
| ------------------------------- | ----------------------------------------------------------------------------------- |
| ChromaDB HNSW / segment errors  | Set `INGEST_RESET_DB=true`, run `python backend/ingest.py`                      |
| Empty categories / no retrieval | Confirm ingest completed and `/health` shows chunks loaded                        |
| Backend unreachable in UI       | Start uvicorn from project root; check `VITE_API_URL` if not using localhost:8000 |
| Slow first generation           | Embedding and reranker models load on first request; subsequent runs are faster     |

---

## License

No open-source license has been specified; all rights reserved by the repository owner unless stated otherwise.

---

## Version Control

Secrets (`.env`), virtual environments, `node_modules`, the dataset (`data/`), the vector store (`backend/chroma_db/`) and generated PDFs (`backend/generated_resumes/`) are excluded by `.gitignore`. Evaluation reports under `backend/evaluation/reports/` are committed.
