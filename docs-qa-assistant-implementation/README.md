# Solstice Learning — Conversational Hybrid RAG Docs Assistant (V2)

A full-stack documentation assistant for Case Study 5. V2 uses **hybrid retrieval**: BM25 lexical search + Sentence Transformers semantic embeddings stored in a persistent ChromaDB vector database. Reciprocal Rank Fusion (RRF) combines both rankings. Groq generates answers from authorized retrieved chunks only.

## V1 and V2

- **V1 — Lexical Retrieval:** the earlier baseline. Preserve it in Git with tag `v1-lexical-retrieval` before replacing the working folder.
- **V2 — Hybrid RAG:** this package. It adds sentence embeddings, persistent ChromaDB, BM25 + vector retrieval, RRF, chunk-level citations and retrieval diagnostics.

## Architecture

### Offline ingestion/indexing (runs at backend startup)

1. Load the supplied six documentation articles from `backend/app/data/docs.json`.
2. Split each article into overlapping chunks. Every chunk gets an ID such as `D-01-C001`.
3. Generate a Sentence Transformers embedding for each chunk using `sentence-transformers/all-MiniLM-L6-v2`.
4. Store chunk text, vector, chunk ID and access metadata in a persistent ChromaDB collection (`backend/chroma_db` by default).
5. Build a BM25 lexical index over the same chunks in process.
6. A content hash detects changed documents and refreshes the Chroma collection.

### Online query path

1. Receive a question, demo identity and conversation ID.
2. Resolve short follow-up questions using recent user turns.
3. Apply role and classification restrictions to both retrieval channels.
4. BM25 ranks exact lexical matches; ChromaDB ranks semantically similar vectors.
5. Reciprocal Rank Fusion combines the rankings into a hybrid score.
6. An evidence gate checks lexical overlap or semantic similarity; unsupported questions abstain.
7. Send only authorized top chunks and limited conversation context to Groq.
8. Validate JSON response and every cited chunk ID against the retrieved authorized chunk IDs.
9. Return the answer, document/chunk citations, lexical score, semantic similarity, hybrid score and ranking diagnostics.
10. If Groq is not configured or fails, return the complete best authorized chunk as an extractive fallback.

## Tech stack

| Layer | Technology |
|---|---|
| UI | Next.js 15, React, TypeScript |
| API | FastAPI |
| Chunking | Python |
| Embeddings | Sentence Transformers `all-MiniLM-L6-v2` |
| Vector database | ChromaDB persistent local collection, cosine distance |
| Keyword retrieval | BM25 via `rank-bm25` |
| Hybrid fusion | Reciprocal Rank Fusion (RRF) |
| Answer generation | Groq API |
| Tests | Pytest |

## Windows PowerShell setup

Use Python 3.11. You already have Python 3.11 installed.

### 1. Backend

```powershell
cd backend
py -3.11 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`:

```env
GROQ_API_KEY=your_actual_groq_key
GROQ_MODEL=llama-3.3-70b-versatile
APP_ENV=development
CORS_ORIGINS=http://localhost:3000
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION=solstice_docs_v2
```

Start the API:

```powershell
uvicorn app.main:app --reload --port 8000
```

The first startup downloads the embedding model from Hugging Face and creates the ChromaDB collection. This requires internet access. Later starts reuse the local model cache and persisted vector collection unless source content changes.

API docs: http://localhost:8000/docs  
Health: http://localhost:8000/health

Inspect retrieval scores directly from a backend terminal:

```powershell
python scripts/inspect_retrieval.py "How long does a password reset link last?"
```

The script prints candidate chunk IDs, BM25 scores/ranks, semantic cosine similarities/ranks and final RRF scores.

### 2. Frontend (second terminal)

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Open http://localhost:3000.

## Tests

Run from `backend`:

```powershell
pytest -q
```

The tests set `APP_ENV=test` in `tests/conftest.py` before application imports, then use a deterministic test-only embedding encoder and a temporary ChromaDB collection. They do not need to download the Sentence Transformers model. Normal development and production use the real Sentence Transformers encoder.

## What the retrieval diagnostics mean

- **Chunk ID:** stable identifier such as `D-01-C001`.
- **Lexical score (BM25):** keyword relevance score; useful for exact terms, IDs and numbers. It is not a probability.
- **Semantic similarity:** cosine similarity derived from ChromaDB cosine distance (`1 - distance`). It is not a calibrated probability.
- **Lexical rank:** position in the BM25 result list.
- **Semantic rank:** position in the vector result list.
- **Hybrid score:** Reciprocal Rank Fusion score, `sum(1 / (k + rank))` over channels in which the chunk appears. It is a ranking score, not a confidence percentage.
- **Hybrid rank:** final combined position.
- **CITED / RETRIEVED:** whether Groq cited the chunk or it was another top retrieved candidate.

## Demo roles

- `admin`: Administrator — Public, Internal, Confidential
- `kb_manager`: Knowledge Base Manager — Public, Internal
- `support`: Support Agent — Public, Internal
- `standard`: Standard User — Public

The role selector sends a POC-only demo identity header. This is **not production authentication**. Supplied docs default to Public because the starter dataset does not define classifications or permissions. Add `classification` and `allowed_roles` to a document to demonstrate filtering.

Example:

```json
{
  "doc_id": "D-07",
  "title": "Internal runbook",
  "content": "Synthetic internal-only content.",
  "classification": "Internal",
  "allowed_roles": ["Administrator", "Support Agent"]
}
```

Authorization filters are applied before lexical ranking and through ChromaDB metadata filters before vector search. Do not treat the demo header as a secure identity mechanism.

## API

- `GET /health`
- `GET /api/demo-users`
- `POST /api/ask` — requires `X-Demo-User`; body contains `question` and optional `conversation_id`
- `POST /api/feedback` — requires `X-Demo-User`

## Conversation behavior

The frontend maintains a chat transcript and sends a conversation ID. The backend stores a bounded recent-turn window in memory, scoped to demo identity + conversation ID. Previous user questions help resolve follow-up references. Previous assistant messages are not used as factual evidence. New Chat creates a fresh conversation ID. Production should use Redis or a database with TTL and tenant-aware access.

## Security and limitations

- Demo identities are not authentication; integrate customer SSO/OIDC and validate signed tokens for production.
- The supplied articles are synthetic and Public by default.
- Credential pattern matching excludes obvious high-risk secret-bearing documents; email/phone patterns are redacted before Groq. This is not complete enterprise DLP.
- Only top authorized chunks are sent to Groq. Review the provider's data-processing terms before using real customer data.
- LLM output is constrained and citations are validated, but this is not a formal entailment proof. Human evaluation and a labelled test set are needed to measure faithfulness.
- Feedback is metadata-only logging, not persisted.
- ChromaDB persists locally on one backend instance. For multi-instance deployment, use a shared persistent volume or managed vector database and a coordinated ingestion pipeline.
- Conversation memory is in-process and resets on restart.
- Add rate limiting, robust authentication, tenant isolation, retention/deletion workflows, document versioning and production monitoring before handling real enterprise data.

## Deployment

### Render backend
Set root directory to `backend`.
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Add environment variables from `.env`; set `CORS_ORIGINS` to the exact Vercel origin.
- Configure a persistent disk mounted at the Chroma path (for example `/var/data/chroma`) and set `CHROMA_PERSIST_DIR=/var/data/chroma`. Without persistent storage, the vector collection may be lost when the service is redeployed.

### Vercel frontend
Set project root to `frontend`.
- `NEXT_PUBLIC_API_URL=https://YOUR-RENDER-SERVICE.onrender.com`

## Requirement mapping

| Requirement | Implementation |
|---|---|
| Natural-language and follow-up questions | `frontend/app/page.tsx`, `backend/app/main.py` |
| Chunking and stable chunk IDs | `backend/app/services/retrieval.py` |
| Semantic vector retrieval | Sentence Transformers + ChromaDB in `retrieval.py` |
| Keyword retrieval | BM25 in `retrieval.py` |
| Hybrid ranking | RRF in `retrieval.py` |
| Access-aware retrieval | `security.py`, `retrieval.py` |
| Grounded Groq generation | `answering.py` |
| Abstention and fallback | `main.py`, `answering.py` |
| Citation and score diagnostics | `models.py`, `main.py`, frontend |
| Sensitive-data safeguards | `security.py`, `answering.py`, `main.py` |
| Tests | `backend/tests/` |

## Project structure

```text
.
├── SOLUTION_DESIGN.md
├── README.md
├── IMPLEMENTATION_NOTES.md
├── backend/
│   ├── app/data/
│   ├── app/services/retrieval.py
│   ├── app/services/answering.py
│   ├── app/main.py
│   ├── app/security.py
│   ├── tests/
│   ├── chroma_db/              # generated persistent vector database (gitignored)
│   └── requirements.txt
└── frontend/
    └── app/
```
