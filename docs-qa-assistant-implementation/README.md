# Solstice Learning — Docs Q&A Assistant

End-to-end implementation for Case Study 5 using the supplied six-article dataset, FastAPI, permission-aware lexical retrieval, explicit abstention, Groq answer generation, citations, feedback, and a Next.js UI.

## Windows PowerShell quick start

### Backend (terminal 1)

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your Groq key to `backend/.env`:

```env
GROQ_API_KEY=your_actual_key
GROQ_MODEL=llama-3.3-70b-versatile
CORS_ORIGINS=http://localhost:3000
```

Start API:

```powershell
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

If the key is empty or Groq fails, a deterministic source-passage fallback is used. The Salesforce question abstains before the LLM call.

### Frontend (terminal 2)

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Open http://localhost:3000

## Demo roles

- `admin`: Administrator — Public, Internal, Confidential
- `kb_manager`: Knowledge Base Manager — Public, Internal
- `support`: Support Agent — Public, Internal
- `standard`: Standard User — Public

The role selector sends a POC-only demo identity header. This is **not real authentication**. Seed documents default to Public because the source dataset does not define classification or permissions. To demonstrate filtering, add `classification` and `allowed_roles` fields to a document in `backend/app/data/docs.json`. Example:

```json
{"doc_id":"D-07","title":"Internal runbook","content":"Synthetic internal-only content.","classification":"Internal","allowed_roles":["Administrator","Support Agent"]}
```

The backend filters by role and classification before ranking/retrieval. Production must validate signed identity-provider tokens and derive permissions server-side.

## Tests

From `backend`:

```powershell
pytest -q
```

Tests cover chunk tail preservation, supported seed retrieval, Salesforce abstention, role filtering, API health, auth requirement and source citation.

## API endpoints

- `GET /health`
- `GET /api/demo-users`
- `POST /api/ask` (requires `X-Demo-User`)
- `POST /api/feedback` (POC metadata-only logging)

## Technical behavior

1. Validate and load seed JSON.
2. Chunk documents without dropping the final partial chunk.
3. Filter candidate chunks by role and classification before retrieval.
4. Rank with a small BM25-style lexical scorer and synonym normalization.
5. Abstain when there is no adequate lexical evidence.
6. If configured, Groq generates a JSON answer from only the authorized top passages.
7. Validate JSON schema and citation IDs.
8. If Groq is unavailable or malformed, return the best authorized passage as a safe fallback.

Retrieval scores are ranking signals, not calibrated confidence probabilities.

## Security and limitations

- Demo identities are not authentication; do not use with real customer data as-is.
- The six supplied articles are synthetic and Public by default.
- High-confidence credential patterns are excluded from indexing; email/phone-like values are redacted before Groq transmission. Pattern matching is not complete DLP.
- Only top authorized passages are sent to Groq. Confirm provider/data-processing policy before production use.
- Feedback is acknowledged and logged as metadata; it is not persisted in a database.
- Index is in-memory. Persistent storage, ingestion/versioning, enterprise SSO, tenant isolation, rate limiting, production DLP and retention/deletion workflows are future work.
- LLM confidence is not treated as a probability; lightweight evidence gating is not a formal entailment proof.

## Deployment

### Render backend
Set root directory to `backend`.
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Env vars: `GROQ_API_KEY`, `GROQ_MODEL`, `CORS_ORIGINS` (exact Vercel origin), `APP_ENV=production`.

### Vercel frontend
Set project root to `frontend`. Add `NEXT_PUBLIC_API_URL=https://YOUR-RENDER-SERVICE.onrender.com`.

A `backend/render.yaml` and Dockerfile are included as deployment references.

## Project structure

```text
.
├── SOLUTION_DESIGN.md
├── README.md
├── IMPLEMENTATION_NOTES.md
├── backend/
│   ├── app/data/                  # supplied docs and example questions
│   ├── app/services/              # retrieval and Groq generation
│   ├── app/config.py
│   ├── app/main.py
│   ├── app/models.py
│   ├── app/security.py
│   ├── tests/
│   └── requirements.txt
└── frontend/
    ├── app/
    └── package.json
```

## Requirement mapping

| Requirement / design control | Code |
|---|---|
| Plain-English questions | `frontend/app/page.tsx`, `backend/app/main.py` |
| Search supplied docs | `backend/app/services/retrieval.py` |
| Grounded answers / abstention | `backend/app/services/answering.py`, `main.py` |
| Five seed questions | `backend/app/data/example_questions.json`, tests |
| Citations | `models.py`, `main.py`, frontend source panel |
| Role-aware retrieval | `security.py`, `retrieval.py` |
| Sensitive-data safeguards | `security.py`, `answering.py`, `main.py` |
| Feedback | `/api/feedback` |
| Provider failure fallback | `answering.py` |
