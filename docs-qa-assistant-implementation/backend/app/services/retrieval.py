import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
from rank_bm25 import BM25Okapi

from app.config import (
    CHROMA_COLLECTION, CHROMA_PERSIST_DIR, CHUNK_OVERLAP, CHUNK_SIZE,
    EMBEDDING_MODEL, HYBRID_TOP_K, LEXICAL_CANDIDATES,
    VECTOR_CANDIDATES, RRF_K
)
from app.security import allowed_classifications

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {"a","an","the","is","are","am","i","we","you","my","our","to","of","for","in","on","at","and","or","do","does","how","what","can","could","please","me","your","have","has","it","this","that","with","from","be","use","before"}
SYNONYMS = {
    "forgot":"reset", "forgotten":"reset", "recover":"reset",
    "expiry":"expire", "expires":"expire", "expired":"expire",
    "maximum":"limit", "max":"limit", "largest":"limit",
    "rows":"row", "exports":"export", "exporting":"export",
    "requests":"request", "calls":"request", "minutes":"minute",
    "minute":"minute", "integration":"integration", "connect":"connect",
    "salesforce":"salesforce", "growth":"growth", "enterprise":"enterprise",
    "last": "expire","duration": "expire","validity": "expire","valid": "expire"
}

def tokenize(text: str) -> list[str]:
    return [SYNONYMS.get(t, t) for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]

def load_documents(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    docs = payload.get("docs", [])
    if not isinstance(docs, list):
        raise ValueError("docs.json must contain a 'docs' array")
    valid = []
    for doc in docs:
        if not all(k in doc for k in ("doc_id", "title", "content")):
            raise ValueError("Each document needs doc_id, title and content")
        valid.append({
            **doc,
            "classification": doc.get("classification", "Public"),
            "allowed_roles": doc.get("allowed_roles", [
                "Administrator", "Knowledge Base Manager", "Support Agent", "Standard User"
            ])
        })
    return valid


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
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

        # Prefer sentence or word boundaries.
        if end < len(text):
            boundary = max(
                text.rfind(". ", start, end),
                text.rfind("; ", start, end),
                text.rfind(" ", start, end)
            )

            if boundary > start + int(chunk_size * 0.65):
                end = boundary + 1

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        # IMPORTANT: Move forward while preserving overlap.
        next_start = end - overlap

        # Safety check: guarantee forward progress.
        if next_start <= start:
            next_start = start + 1

        start = next_start

    return chunks

class SentenceTransformerEncoder:
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vectors, dtype=np.float32)

class HashTestEncoder:
    """Deterministic test-only encoder; never selected in normal development/production."""
    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions
        self.model_name = f"hash-test-{dimensions}"

    def encode(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in tokenize(text):
                idx = int(hashlib.sha256(token.encode()).hexdigest(), 16) % self.dimensions
                matrix[row, idx] += 1.0
            norm = np.linalg.norm(matrix[row])
            if norm:
                matrix[row] /= norm
        return matrix

class HybridRetriever:
    def __init__(self, docs: list[dict[str, Any]], encoder=None,
                 persist_dir: Path = CHROMA_PERSIST_DIR,
                 collection_name: str = CHROMA_COLLECTION,
                 rebuild: bool = False):
        self.encoder = encoder or SentenceTransformerEncoder()
        self.chunks: list[dict[str, Any]] = []
        for doc in docs:
            parts = chunk_text(doc["content"])
            for index, part in enumerate(parts):
                chunk_id = f"{doc['doc_id']}-C{index+1:03d}"
                roles = doc["allowed_roles"]
                self.chunks.append({
                    "chunk_id": chunk_id, "doc_id": doc["doc_id"],
                    "title": doc["title"], "text": part, "chunk_index": index + 1,
                    "classification": doc["classification"], "allowed_roles": roles,
                    "allow_administrator": "Administrator" in roles,
                    "allow_knowledge_manager": "Knowledge Base Manager" in roles,
                    "allow_support_agent": "Support Agent" in roles,
                    "allow_standard_user": "Standard User" in roles
                })
        self.chunk_by_id = {c["chunk_id"]: c for c in self.chunks}
        self.tokenized_chunks = [tokenize(c["title"] + " " + c["text"]) for c in self.chunks]
        self.bm25 = BM25Okapi(self.tokenized_chunks) if self.tokenized_chunks else None
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.embedding_model_id = getattr(self.encoder, "model_name", self.encoder.__class__.__name__)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",
                "description": "Solstice docs chunk embeddings",
                "embedding_model": self.embedding_model_id
            }
        )
        current_payload = self.collection.get(include=["metadatas"])
        current_ids = set(current_payload["ids"])
        current_hashes = {
            cid: (meta or {}).get("content_hash")
            for cid, meta in zip(current_payload["ids"], current_payload.get("metadatas") or [])
        }
        desired_ids = {c["chunk_id"] for c in self.chunks}
        desired_hashes = {
            c["chunk_id"]: hashlib.sha256((c["title"] + "\n" + c["text"]).encode()).hexdigest()
            for c in self.chunks
        }
        stored_model = (self.collection.metadata or {}).get("embedding_model")
        changed = (
            current_ids != desired_ids
            or any(current_hashes.get(cid) != digest for cid, digest in desired_hashes.items())
            or stored_model != self.embedding_model_id
        )
        if rebuild or changed:
            if current_ids:
                self.collection.delete(ids=list(current_ids))
            if self.chunks:
                embeddings = self.encoder.encode([c["title"] + "\n" + c["text"] for c in self.chunks])
                self.collection.add(
                    ids=[c["chunk_id"] for c in self.chunks],
                    embeddings=embeddings.tolist(),
                    documents=[c["text"] for c in self.chunks],
                    metadatas=[{
                        "doc_id": c["doc_id"], "title": c["title"],
                        "chunk_index": c["chunk_index"],
                        "content_hash": desired_hashes[c["chunk_id"]],
                        "classification": c["classification"],
                        "allow_administrator": c["allow_administrator"],
                        "allow_knowledge_manager": c["allow_knowledge_manager"],
                        "allow_support_agent": c["allow_support_agent"],
                        "allow_standard_user": c["allow_standard_user"]
                    } for c in self.chunks]
                )
            self.collection.modify(metadata={
                "description": "Solstice docs chunk embeddings",
                "embedding_model": self.embedding_model_id
            })

    def search(self, question: str, role: str, top_k: int = HYBRID_TOP_K) -> list[dict[str, Any]]:
        q_tokens = tokenize(question)
        if not q_tokens or not self.chunks:
            return []
        role_classes = allowed_classifications(role)
        role_field = {
            "Administrator": "allow_administrator",
            "Knowledge Base Manager": "allow_knowledge_manager",
            "Support Agent": "allow_support_agent",
            "Standard User": "allow_standard_user"
        }.get(role)
        if not role_field or not role_classes:
            return []

        # Apply authorization in both retrieval channels before ranking/returning passages.
        eligible = [
            c for c in self.chunks
            if role in c["allowed_roles"] and c["classification"] in role_classes
        ]
        if not eligible:
            return []
        eligible_ids = {c["chunk_id"] for c in eligible}

        eligible_chunks = [c for c in self.chunks if c["chunk_id"] in eligible_ids]
        eligible_tokens = [tokenize(c["title"] + " " + c["text"]) for c in eligible_chunks]
        lexical_ranked = []
        if eligible_tokens:
            authorized_bm25 = BM25Okapi(eligible_tokens)
            scores = authorized_bm25.get_scores(q_tokens)
            for idx, score in enumerate(scores):
                c = eligible_chunks[idx]
                overlap = len(set(q_tokens) & set(eligible_tokens[idx]))
                lexical_ranked.append((c["chunk_id"], float(score), overlap))
        lexical_ranked.sort(key=lambda x: x[1], reverse=True)
        lexical_ranked = [x for x in lexical_ranked if x[1] > 0][:LEXICAL_CANDIDATES]
        lexical_ranks = {chunk_id: rank for rank, (chunk_id, _, _) in enumerate(lexical_ranked, 1)}
        lexical_scores = {chunk_id: score for chunk_id, score, _ in lexical_ranked}
        lexical_overlaps = {chunk_id: overlap for chunk_id, _, overlap in lexical_ranked}

        where = {"$and": [
            {"classification": {"$in": list(role_classes)}},
            {role_field: True}
        ]}
        query_embedding = self.encoder.encode([question])[0].tolist()
        vector_result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(VECTOR_CANDIDATES, len(eligible)),
            where=where,
            include=["distances", "metadatas", "documents"]
        )
        vector_ranked = []
        ids = (vector_result.get("ids") or [[]])[0]
        distances = (vector_result.get("distances") or [[]])[0]
        for rank, (chunk_id, distance) in enumerate(zip(ids, distances), 1):
            similarity = max(-1.0, min(1.0, 1.0 - float(distance)))
            vector_ranked.append((chunk_id, similarity, rank))
        vector_ranks = {chunk_id: rank for chunk_id, _, rank in vector_ranked}
        semantic_scores = {chunk_id: score for chunk_id, score, _ in vector_ranked}

        # Reciprocal Rank Fusion combines lexical and vector ranks.
        combined_ids = set(lexical_ranks) | set(vector_ranks)
        fused = []
        for chunk_id in combined_ids:
            rrf = 0.0
            if chunk_id in lexical_ranks:
                rrf += 1.0 / (RRF_K + lexical_ranks[chunk_id])
            if chunk_id in vector_ranks:
                rrf += 1.0 / (RRF_K + vector_ranks[chunk_id])
            c = self.chunk_by_id[chunk_id]
            fused.append({
                **c,
                "lexical_score": round(lexical_scores.get(chunk_id, 0.0), 5),
                "lexical_overlap": lexical_overlaps.get(chunk_id, 0),
                "lexical_rank": lexical_ranks.get(chunk_id),
                "semantic_similarity": round(semantic_scores.get(chunk_id, 0.0), 5),
                "semantic_rank": vector_ranks.get(chunk_id),
                "hybrid_score": round(rrf, 7)
            })
        fused.sort(key=lambda x: x["hybrid_score"], reverse=True)
        for rank, item in enumerate(fused, 1):
            item["hybrid_rank"] = rank
        return fused[:top_k]
