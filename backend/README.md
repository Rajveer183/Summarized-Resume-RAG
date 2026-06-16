# Backend — Resume Generation RAG API

FastAPI backend for the Resume Generation RAG application.

## Quick Start

```bash
# From project root
python -m venv venv
venv\Scripts\activate

pip install -r backend/requirements.txt

# Add HF_TOKEN to .env (faster embedding model downloads from Hugging Face)

# Run ingestion (build ChromaDB, ~15 min full dataset)
# After HNSW/index errors, set INGEST_RESET_DB=true in .env first
python backend/ingest.py

# Start server
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Docs
Visit → http://localhost:8000/docs

## Directory Structure
```
backend/
├── app/
│   ├── main.py              ← FastAPI app
│   ├── config.py            ← Environment settings
│   ├── api/
│   │   ├── routes.py        ← All endpoints
│   │   └── schemas.py       ← Pydantic models
│   ├── services/
│   │   ├── pdf_loader.py    ← PDF text extraction
│   │   ├── pii_cleaner.py   ← PII removal
│   │   ├── chunker.py       ← Section-aware chunking
│   │   ├── embedding_service.py  ← sentence-transformers
│   │   ├── vector_store.py  ← ChromaDB operations
│   │   ├── retriever.py     ← MMR retrieval
│   │   ├── reranker.py      ← CrossEncoder reranking
│   │   ├── resume_generator.py  ← LLM orchestration
│   │   └── pdf_generator.py ← ReportLab PDF output
│   ├── prompts/
│   │   └── resume_prompt.py ← LLM prompt templates
│   ├── templates/
│   │   └── resume_template.html  ← HTML template
│   └── utils/
│       ├── logger.py        ← Structured logging
│       └── file_utils.py    ← File helpers
├── ingest.py                ← Standalone ingestion script
├── chroma_db/               ← Vector store (auto-created)
├── generated_resumes/       ← PDF output (auto-created)
└── requirements.txt
```
