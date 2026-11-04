from typing import Literal
from pydantic import BaseModel, Field

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    conversation_id: str | None = Field(default=None, min_length=8, max_length=80)

class Source(BaseModel):
    doc_id: str
    title: str
    chunk_id: str
    chunk_index: int
    excerpt: str
    lexical_score: float
    semantic_similarity: float
    hybrid_score: float
    lexical_rank: int | None = None
    semantic_rank: int | None = None
    hybrid_rank: int
    is_cited: bool = False

class AskResponse(BaseModel):
    status: Literal["answered", "not_found", "access_denied", "error"]
    answer: str
    sources: list[Source] = []
    mode: Literal["groq", "extractive", "abstention", "none"] = "none"
    request_id: str
    conversation_id: str | None = None
    show_evidence: bool = False
    show_diagnostics: bool = False

class FeedbackRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    helpful: bool
    comment: str | None = Field(default=None, max_length=500)
