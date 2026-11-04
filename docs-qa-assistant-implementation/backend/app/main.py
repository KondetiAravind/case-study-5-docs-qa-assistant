import logging, time, uuid
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import BACKEND_DIR, CORS_ORIGINS, RETRIEVAL_MIN_SCORE, RETRIEVAL_MIN_OVERLAP
from app.models import AskRequest, AskResponse, Source, FeedbackRequest
from app.security import resolve_demo_user, DEMO_USERS, contains_high_risk_secret, redact_sensitive
from app.services.retrieval import load_documents, Retriever
from app.services.answering import generate_answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docs-qa")
DATA_PATH = BACKEND_DIR / "app" / "data" / "docs.json"

def build_retriever():
    docs = load_documents(DATA_PATH)
    safe_docs = [d for d in docs if not contains_high_risk_secret(d["content"])]
    return docs, Retriever(safe_docs)

DOCS, RETRIEVER = build_retriever()
app = FastAPI(title="Solstice Docs Q&A API", version="1.0.0",
              description="Permission-aware, evidence-grounded documentation Q&A.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["GET","POST"], allow_headers=["Content-Type","X-Demo-User"])

@app.get("/health")
def health():
    return {"status":"ok","documents_loaded":len(DOCS),"chunks_indexed":len(RETRIEVER.chunks)}

@app.get("/api/demo-users")
def demo_users():
    return [{"id":uid,"label":data["label"],"role":data["role"]} for uid,data in DEMO_USERS.items()]

@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest, x_demo_user: str | None = Header(default=None)):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    user = resolve_demo_user(x_demo_user)
    if not user:
        raise HTTPException(status_code=401, detail="Select a valid demo identity.")
    question = payload.question.strip()
    results = RETRIEVER.search(question, role=user.role, top_k=4)
    if not results:
        return AskResponse(status="not_found",answer="I don't have an answer for that in the documentation available to your role.",
                           sources=[],mode="abstention",request_id=request_id)
    best = results[0]
    if best["score"] < RETRIEVAL_MIN_SCORE or best["overlap"] < RETRIEVAL_MIN_OVERLAP:
        return AskResponse(status="not_found",answer="I don't have an answer for that in the available documentation.",
                           sources=[],mode="abstention",request_id=request_id)
    answer, source_ids, mode = generate_answer(question, results[:3])
    if not source_ids:
        return AskResponse(status="not_found",answer=answer,sources=[],mode="abstention",request_id=request_id)
    authorized = {p["doc_id"]:p for p in results}
    sources = []
    for doc_id in source_ids:
        if doc_id not in authorized:
            logger.warning("Invalid source escaped validation request_id=%s",request_id)
            continue
        p = authorized[doc_id]
        sources.append(Source(doc_id=doc_id,title=p["title"],excerpt=redact_sensitive(p["text"]),relevance_score=p["score"]))
    if not sources:
        return AskResponse(status="not_found",answer="I don't have an answer for that in the available documentation.",
                           sources=[],mode="abstention",request_id=request_id)
    logger.info("request_id=%s user=%s role=%s source_ids=%s latency_ms=%d",request_id,user.user_id,user.role,
                [s.doc_id for s in sources],int((time.perf_counter()-started)*1000))
    return AskResponse(status="answered",answer=answer,sources=sources,mode=mode,request_id=request_id)

@app.post("/api/feedback")
def feedback(payload: FeedbackRequest, x_demo_user: str | None = Header(default=None)):
    user = resolve_demo_user(x_demo_user)
    if not user:
        raise HTTPException(status_code=401,detail="Select a valid demo identity.")
    logger.info("feedback request_id=%s user=%s helpful=%s",payload.request_id,user.user_id,payload.helpful)
    return {"status":"received"}
