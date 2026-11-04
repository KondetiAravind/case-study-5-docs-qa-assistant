import logging, time, uuid, re, tempfile
from collections import defaultdict, deque
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import BACKEND_DIR, CORS_ORIGINS, APP_ENV, MIN_SEMANTIC_SIMILARITY, MIN_LEXICAL_OVERLAP, HYBRID_TOP_K
from app.models import AskRequest, AskResponse, Source, FeedbackRequest
from app.security import (
    resolve_demo_user,
    DEMO_USERS,
    contains_high_risk_secret,
    redact_sensitive,
    EVIDENCE_ACCESS,
    DIAGNOSTICS_ACCESS,
)
from app.services.retrieval import load_documents, HybridRetriever
from app.services.answering import generate_answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docs-qa-hybrid")
DATA_PATH = BACKEND_DIR / "app" / "data" / "docs.json"

def build_retriever():
    docs = load_documents(DATA_PATH)

    # Exclude documents containing detected high-risk secrets.
    safe_docs = [
        d for d in docs
        if not contains_high_risk_secret(d["content"])
    ]

    # Lightweight BM25-only retrieval.
    retriever = HybridRetriever(safe_docs)

    return docs, retriever

DOCS, RETRIEVER = build_retriever()
CONVERSATIONS = defaultdict(lambda: deque(maxlen=8))
FOLLOWUP_MARKERS = re.compile(r"\b(it|that|this|they|them|those|these|what about|how about|and the|its|their)\b", re.I)

app = FastAPI(title="Solstice Docs Q&A API", version="2.0.0",
              description="Conversational permission-aware hybrid RAG using ChromaDB, Sentence Transformers, BM25 and Groq.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Demo-User"])

@app.get("/health")
def health():
    return {
        "status": "ok",
        "documents_loaded": len(DOCS),
        "chunks_indexed": len(RETRIEVER.chunks),
        "vector_database": "ChromaDB",
        "collection": RETRIEVER.collection.name,
        "retrieval": "hybrid_bm25_plus_vector_rrf"
    }

@app.get("/api/demo-users")
def demo_users():
    return [{"id": uid, "label": data["label"], "role": data["role"]} for uid, data in DEMO_USERS.items()]

@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest, x_demo_user: str | None = Header(default=None)):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    user = resolve_demo_user(x_demo_user)
    if not user:
        raise HTTPException(status_code=401, detail="Select a valid demo identity.")
    question = payload.question.strip()
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", conversation_id):
        raise HTTPException(status_code=422, detail="Invalid conversation ID.")

    key = (user.user_id, conversation_id)
    history = list(CONVERSATIONS[key])
    context = history[-6:]
    contextual_query = question

    # Use conversation context only when the user explicitly asks a follow-up.
    if history and FOLLOWUP_MARKERS.search(question):
        prior_questions = [
            m["content"]
            for m in history
            if m["role"] == "user"
        ]

        if prior_questions:
            contextual_query = f"{prior_questions[-1]} {question}"

    # HybridRetriever filters by role/classification in both channels before returning candidates.
    results = RETRIEVER.search(contextual_query, role=user.role, top_k=HYBRID_TOP_K)
    if not results:
        answer = "I don't have an answer for that in the documentation available to your role."
        CONVERSATIONS[key].extend([{"role": "user", "content": question}, {"role": "assistant", "content": answer}])
        return AskResponse(status="not_found", answer=answer, sources=[], mode="abstention",
                           request_id=request_id, conversation_id=conversation_id)

    best = results[0]
    has_lexical_evidence = any(
        item["lexical_overlap"] >= MIN_LEXICAL_OVERLAP and item["lexical_score"] > 0
        for item in results
    )
    has_semantic_evidence = any(
        item["semantic_similarity"] >= MIN_SEMANTIC_SIMILARITY
        for item in results
    )
    if not (has_lexical_evidence or has_semantic_evidence):
        answer = "I don't have an answer for that in the available documentation."
        CONVERSATIONS[key].extend([{"role": "user", "content": question}, {"role": "assistant", "content": answer}])
        return AskResponse(status="not_found", answer=answer, sources=[], mode="abstention",
                           request_id=request_id, conversation_id=conversation_id)

    answer, cited_chunk_ids, mode = generate_answer(question, results[:3], context)
    if not cited_chunk_ids:
        CONVERSATIONS[key].extend([{"role": "user", "content": question}, {"role": "assistant", "content": answer}])
        return AskResponse(status="not_found", answer=answer, sources=[], mode="abstention",
                           request_id=request_id, conversation_id=conversation_id)

    cited_set = set(cited_chunk_ids)
    authorized = {p["chunk_id"]: p for p in results}

    # Return only the highest-ranked source actually cited by the answer.
    sources = []

    for p in results:
        if p["chunk_id"] not in cited_set:
            continue

        sources.append(Source(
            doc_id=p["doc_id"],
            title=p["title"],
            chunk_id=p["chunk_id"],
            chunk_index=p["chunk_index"],
            excerpt=redact_sensitive(p["text"]),
            lexical_score=p["lexical_score"],
            semantic_similarity=p["semantic_similarity"],
            hybrid_score=p["hybrid_score"],
            lexical_rank=p["lexical_rank"],
            semantic_rank=p["semantic_rank"],
            hybrid_rank=p["hybrid_rank"],
            is_cited=True
        ))

        break  # Only one supporting evidence card

    if not sources:
        answer = "I don't have an answer for that in the available documentation."
        return AskResponse(status="not_found", answer=answer, sources=[], mode="abstention",
                           request_id=request_id, conversation_id=conversation_id)

    CONVERSATIONS[key].extend([{"role": "user", "content": question}, {"role": "assistant", "content": answer}])
    logger.info("request_id=%s user=%s role=%s chunks=%s latency_ms=%d", request_id, user.user_id,
                user.role, [s.chunk_id for s in sources], int((time.perf_counter()-started)*1000))
    
    visible_sources = sources if user.role in EVIDENCE_ACCESS else []

    return AskResponse(
        status="answered",
        answer=answer,
        sources=visible_sources,
        mode=mode,
        request_id=request_id,
        conversation_id=conversation_id,
        show_evidence=user.role in EVIDENCE_ACCESS,
        show_diagnostics=user.role in DIAGNOSTICS_ACCESS,
    )

@app.post("/api/feedback")
def feedback(payload: FeedbackRequest, x_demo_user: str | None = Header(default=None)):
    user = resolve_demo_user(x_demo_user)
    if not user:
        raise HTTPException(status_code=401, detail="Select a valid demo identity.")
    logger.info("feedback request_id=%s user=%s helpful=%s", payload.request_id, user.user_id, payload.helpful)
    return {"status": "received"}
