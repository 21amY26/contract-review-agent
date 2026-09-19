# Contract-Review

**Agentic AI for Contract Review and Compliance Risk Management**

A multi-agent AI system that automates contract review, compliance verification, and risk assessment using LLMs, RAG, and agent orchestration — built with free/open-source tools for learning and prototyping.

---

## Architecture

1. **User Interface** – Upload contracts, view analysis, dashboards, download reports
2. **Backend API Layer** – FastAPI for auth, file handling, endpoints, report generation
3. **Agent Orchestration Layer** – LangGraph multi-agent workflow
4. **RAG & Knowledge Layer** – Embeddings + vector store for company policies, regulations, clause library
5. **Multi-Agent Workflow** – 6 specialized agents backed by an LLM layer
6. **Output & Reporting** – Risk scores, heatmaps, clause results, recommendations, PDF export
7. **Database & Storage** – PostgreSQL/SQLite + local or S3-compatible storage
8. **Infrastructure** – Local Docker setup, deployable to free-tier cloud

---

## Tech Stack 

| Layer | Technology | Free Tier / Cost |
|---|---|---|
| Frontend | React, Tailwind CSS, ShadCN UI | Free, open-source |
| Backend | Python, FastAPI, Uvicorn | Free, open-source |
| Agent Framework | LangGraph, LangChain | Free, open-source |
| LLM (primary) | Groq API (Llama 3.1/3.3, free tier, very fast) | Free tier (generous rate limits) |
| LLM (alternative) | Google Gemini API (gemini-1.5-flash) | Free tier |
| LLM (local) | Ollama (Llama 3, Mistral, Phi-3) | 100% free, runs locally |
| RAG / Orchestration | LangChain | Free, open-source |
| Embeddings | sentence-transformers (HuggingFace, local) | Free, runs locally |
| Embeddings (API alt) | Google Gemini Embeddings / Cohere (free tier) | Free tier |
| Vector DB | ChromaDB (local, embedded) | Free, open-source |
| Vector DB (cloud alt) | Pinecone (free tier, 1 index) / Qdrant Cloud (free tier) | Free tier |
| Database | SQLite (dev) / PostgreSQL | Free, open-source |
| File Storage | Local filesystem / MinIO (S3-compatible, self-hosted) | Free |
| PDF Parsing | PyMuPDF (fitz), pdfplumber | Free, open-source |
| DOCX Parsing | python-docx | Free, open-source |
| OCR | Tesseract OCR + pytesseract | Free, open-source |
| Authentication | python-jose + passlib (JWT) | Free, open-source |
| PDF Report Generation | ReportLab / WeasyPrint | Free, open-source |
| Deployment | Docker, Render free tier, Railway free tier, Fly.io free tier | Free tier |

---

## Project Structure

> The authoritative, always-current layout lives in
> [`docs/contract-review-doc.md`](docs/contract-review-doc.md) §4. Summary:

```
Contract-Review-dev/
├── main.py                     # FastAPI entrypoint (CORS, routers, /health)
├── requirements.txt
├── app.db                      # SQLite (users, analysis jobs)
├── build_kb.sh                 # Populates the ChromaDB knowledge base
├── .env.example                # Copy to .env and fill in keys
│
├── api/                        # FastAPI route handlers
│   ├── analyze.py              # /analyze, /analyze/{id}/status, /history, /reports
│   ├── auth.py                 # /signup, /login, /settings (JWT)
│   ├── database.py             # SQLAlchemy engine + session factory
│   └── models.py               # ORM models: User, AnalysisJob
│
├── agents/                     # LLM agents
│   ├── llm_router.py           # Groq → Ollama → HuggingFace waterfall
│   ├── contract_review_agent.py
│   ├── clause_classification_agent.py
│   ├── document_understanding_agent.py   # also performs RAG retrieval
│   ├── compliance_agent.py
│   ├── risk_agent.py
│   ├── recommendation_agent.py
│   ├── legal_explanation_agent.py
│   ├── schemas.py
│   └── orchestration/orchestration.py    # LangGraph StateGraph
│
├── ingestion/                  # Parsing + chunking
│   ├── parsers/                # pdf_parser.py (PyMuPDF/pdfplumber), docx_parser.py
│   └── chunking/splitter.py    # Clause-aware two-stage chunker
│
├── src/                        # RAG infrastructure
│   ├── embeddings/             # sentence-transformers (BAAI/bge-small-en-v1.5)
│   ├── vectordb/               # ChromaDB client (persists to kb/chroma)
│   ├── retrieval/              # Citation-aware search
│   ├── ingestion/              # Offline KB ingestion (run via build_kb.sh)
│   └── metadata/               # Metadata builders + classifier
│
├── kb/                         # Knowledge-base sources + built chroma store
├── schemas/api_models.py       # Shared Pydantic API models
├── scripts/                    # Auxiliary/dev helpers (not part of the request flow)
├── test/                       # pytest unit tests + fixtures
│
└── frontend/frontend/          # React + Vite SPA
    ├── vite.config.js          # Dev proxy to :8000
    └── src/{App.jsx, lib/api.js, hooks/, pages/, components/}
```

> **Not yet implemented:** server-side PDF report generation (ReportLab) is on the
> roadmap. Today the frontend "Download report" button produces a client-side
> `.txt` export (`frontend/frontend/src/lib/api.js:generateReportBlob`).

### Run with Docker

The backend ships with a `Dockerfile` and `docker-compose.yml`:

```bash
cp .env.example .env          # then fill in GROQ_API_KEY, JWT_SECRET, etc.
./build_kb.sh                 # build the knowledge base into ./kb/chroma (first run)
docker compose up --build     # API on http://localhost:8000
```

`app.db` (SQLite) and `kb/` (ChromaDB) are bind-mounted so data survives
restarts. Set `ALLOWED_ORIGINS` in `.env` to your frontend origin(s) for
production CORS.

---

## Getting Started

```bash
# Clone the repo
git clone https://github.com/yourusername/contract-review-ai.git
cd contract-review-ai

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend setup
cd ../frontend
npm install
npm run dev

# (Optional) Run Ollama locally for free local LLM
ollama pull llama3
ollama serve
```

---

## Environment Variables (.env.example)

```
# LLM APIs (use any/all - free tier)
GROQ_API_KEY=
GOOGLE_API_KEY=
OPENROUTER_API_KEY=
HUGGINGFACEHUB_API_TOKEN=

# Local LLM (no key needed)
OLLAMA_BASE_URL=http://localhost:11434

# Vector DB (ChromaDB is local, no key needed)
CHROMA_PERSIST_DIR=./rag/chroma_db

# Database
DATABASE_URL=sqlite:///./app.db

# Auth
JWT_SECRET=
```

---

## Roadmap

- [ ] Document upload and parsing (PyMuPDF, OCR)
- [ ] Multi-agent LangGraph pipeline with Groq/Ollama
- [ ] ChromaDB RAG knowledge base
- [ ] Risk scoring and dashboard
- [ ] PDF report generation (ReportLab)
- [ ] Deploy to Render/Railway free tier

