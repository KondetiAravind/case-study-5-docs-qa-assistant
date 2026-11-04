from typing import Literal
from pydantic import BaseModel, Field

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)

class Source(BaseModel):
    doc_id: str
    title: str
    excerpt: str
    relevance_score: float

class AskResponse(BaseModel):
    status: Literal["answered", "not_found", "access_denied", "error"]
    answer: str
    sources: list[Source] = []
    mode: Literal["groq", "extractive", "abstention", "none"] = "none"
    request_id: str

class FeedbackRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    helpful: bool
    comment: str | None = Field(default=None, max_length=500)
