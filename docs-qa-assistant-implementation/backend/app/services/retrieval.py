
import json
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    HYBRID_TOP_K,
    LEXICAL_CANDIDATES,
)
from app.security import allowed_classifications


TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "a", "an", "the", "is", "are", "am", "i", "we", "you",
    "my", "our", "to", "of", "for", "in", "on", "at", "and",
    "or", "do", "does", "how", "what", "can", "could", "please",
    "me", "your", "have", "has", "it", "this", "that", "with",
    "from", "be", "use", "before"
}

SYNONYMS = {
    "forgot": "reset",
    "forgotten": "reset",
    "recover": "reset",
    "expiry": "expire",
    "expires": "expire",
    "expired": "expire",
    "maximum": "limit",
    "max": "limit",
    "largest": "limit",
    "rows": "row",
    "exports": "export",
    "exporting": "export",
    "requests": "request",
    "calls": "request",
    "minutes": "minute",
    "last": "expire",
    "duration": "expire",
    "validity": "expire",
    "valid": "expire",
}


def tokenize(text: str) -> list[str]:
    return [
        SYNONYMS.get(token, token)
        for token in TOKEN_RE.findall(text.lower())
        if token not in STOPWORDS
    ]


def load_documents(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    docs = payload.get("docs", [])

    if not isinstance(docs, list):
        raise ValueError("docs.json must contain a 'docs' array")

    valid = []

    for doc in docs:
        if not all(k in doc for k in ("doc_id", "title", "content")):
            raise ValueError(
                "Each document needs doc_id, title and content"
            )

        valid.append({
            **doc,
            "classification": doc.get("classification", "Public"),
            "allowed_roles": doc.get(
                "allowed_roles",
                [
                    "Administrator",
                    "Knowledge Base Manager",
                    "Support Agent",
                    "Standard User",
                ],
            ),
        })

    return valid


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:

    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size > overlap >= 0")

    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            boundary = max(
                text.rfind(". ", start, end),
                text.rfind("; ", start, end),
                text.rfind(" ", start, end),
            )

            if boundary > start + int(chunk_size * 0.65):
                end = boundary + 1

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        next_start = end - overlap

        if next_start <= start:
            next_start = start + 1

        start = next_start

    return chunks


class HybridRetriever:
    """
    Lightweight BM25-only retriever.

    Semantic embeddings, ChromaDB and RRF are intentionally
    disabled to reduce memory consumption on small instances.
    """

    def __init__(
        self,
        docs: list[dict[str, Any]],
        encoder=None,
        persist_dir=None,
        collection_name=None,
        rebuild: bool = False,
    ):
        self.chunks = []

        for doc in docs:
            parts = chunk_text(doc["content"])

            for index, part in enumerate(parts):
                roles = doc["allowed_roles"]

                self.chunks.append({
                    "chunk_id": f"{doc['doc_id']}-C{index + 1:03d}",
                    "doc_id": doc["doc_id"],
                    "title": doc["title"],
                    "text": part,
                    "chunk_index": index + 1,
                    "classification": doc["classification"],
                    "allowed_roles": roles,
                })

        self.chunk_by_id = {
            chunk["chunk_id"]: chunk
            for chunk in self.chunks
        }

        self.tokenized_chunks = [
            tokenize(chunk["title"] + " " + chunk["text"])
            for chunk in self.chunks
        ]

        self.bm25 = (
            BM25Okapi(self.tokenized_chunks)
            if self.tokenized_chunks
            else None
        )

    def search(
        self,
        question: str,
        role: str,
        top_k: int = HYBRID_TOP_K,
    ) -> list[dict[str, Any]]:

        query_tokens = tokenize(question)

        if not query_tokens or not self.chunks or self.bm25 is None:
            return []

        role_classes = allowed_classifications(role)

        if not role_classes:
            return []

        # Authorization is applied before retrieval.
        eligible_indices = [
            i
            for i, chunk in enumerate(self.chunks)
            if (
                role in chunk["allowed_roles"]
                and chunk["classification"] in role_classes
            )
        ]

        if not eligible_indices:
            return []

        eligible_tokens = [
            self.tokenized_chunks[i]
            for i in eligible_indices
        ]

        authorized_bm25 = BM25Okapi(eligible_tokens)
        scores = authorized_bm25.get_scores(query_tokens)

        ranked = []

        for local_index, score in enumerate(scores):
            original_index = eligible_indices[local_index]
            chunk = self.chunks[original_index]
            chunk_tokens = set(eligible_tokens[local_index])

            overlap = len(set(query_tokens) & chunk_tokens)

            if score > 0:
                ranked.append({
                    **chunk,
                    "lexical_score": float(score),
                    "lexical_overlap": overlap,
                })

        ranked.sort(
            key=lambda item: item["lexical_score"],
            reverse=True,
        )

        ranked = ranked[:LEXICAL_CANDIDATES]

        results = []

        for rank, item in enumerate(ranked, start=1):
            item["lexical_rank"] = rank

            # Compatibility fields for the existing API response
            # and frontend diagnostics. These are NOT semantic scores.
            item["semantic_similarity"] = 0.0
            item["semantic_rank"] = None
            item["hybrid_rank"] = rank
            item["hybrid_score"] = round(
                1.0 / (60 + rank), 7
            )

            results.append(item)

        return results[:top_k]
