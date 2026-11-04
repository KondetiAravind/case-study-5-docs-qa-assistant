import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {"a","an","the","is","are","am","i","we","you","my","our","to","of","for","in","on","at","and","or","do","does","how","what","can","could","please","me","your","have","has","it","this","that","with","from","be","use","before"}
SYNONYMS = {
    "forgot":"reset", "forgotten":"reset", "recover":"reset",
    "expiry":"expire", "expires":"expire", "expired":"expire",
    "maximum":"limit", "max":"limit", "largest":"limit",
    "rows":"row", "exports":"export", "exporting":"export",
    "requests":"request", "calls":"request", "minute":"minute",
    "minutes":"minute", "csv":"csv", "password":"password",
    "link":"link", "salesforce":"salesforce", "connect":"connect",
    "integration":"integration", "growth":"growth", "api":"api"
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
            raise ValueError("Every document must contain doc_id, title and content")
        valid.append({**doc, "classification": doc.get("classification", "Public"),
                      "allowed_roles": doc.get("allowed_roles", ["Administrator","Knowledge Base Manager","Support Agent","Standard User"])})
    return valid

def chunk_text(text: str, chunk_size: int = 420, overlap: int = 60) -> list[str]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size > overlap >= 0")
    text = text.strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks

class Retriever:
    def __init__(self, docs: list[dict[str, Any]], chunk_size: int = 420, overlap: int = 60):
        self.chunks = []
        for doc in docs:
            for idx, part in enumerate(chunk_text(doc["content"], chunk_size, overlap)):
                self.chunks.append({"doc_id":doc["doc_id"],"title":doc["title"],"text":part,
                    "chunk_index":idx,"classification":doc["classification"],"allowed_roles":doc["allowed_roles"]})
        self.doc_freq = Counter()
        self.tokens_by_chunk = []
        for chunk in self.chunks:
            tokens = tokenize(chunk["title"] + " " + chunk["text"])
            counts = Counter(tokens)
            self.tokens_by_chunk.append(counts)
            self.doc_freq.update(set(tokens))
        self.total = max(len(self.chunks), 1)

    def search(self, question: str, role: str, top_k: int = 4) -> list[dict[str, Any]]:
        q_tokens = tokenize(question)
        if not q_tokens:
            return []
        q_counts = Counter(q_tokens)
        scored = []
        # Authorization filter is applied before ranking and before LLM context construction.
        role_classes = {
            "Administrator":{"Public","Internal","Confidential"},
            "Knowledge Base Manager":{"Public","Internal"},
            "Support Agent":{"Public","Internal"},
            "Standard User":{"Public"}
        }.get(role, set())
        for chunk, counts in zip(self.chunks, self.tokens_by_chunk):
            if role not in chunk["allowed_roles"] or chunk["classification"] not in role_classes:
                continue
            score, overlap = 0.0, 0
            for token, qtf in q_counts.items():
                tf = counts.get(token, 0)
                if tf:
                    overlap += 1
                    idf = math.log(1 + (self.total - self.doc_freq[token] + 0.5) / (self.doc_freq[token] + 0.5))
                    score += idf * (tf * 2.2) / (tf + 1.2) * min(qtf, 2)
            if overlap:
                scored.append(({**chunk,"score":round(score,4),"overlap":overlap}, score))
        scored.sort(key=lambda x:x[1], reverse=True)
        return [item[0] for item in scored[:top_k]]
