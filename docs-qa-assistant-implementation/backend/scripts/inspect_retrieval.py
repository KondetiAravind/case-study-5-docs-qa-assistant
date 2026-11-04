
"""Inspect BM25 + ChromaDB hybrid retrieval scores."""

import argparse
import sys
from pathlib import Path

# Add the backend directory to Python's import path.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.retrieval import load_documents, HybridRetriever
from app.security import contains_high_risk_secret


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question", help="Natural-language question")
    parser.add_argument("--role", default="Standard User")
    args = parser.parse_args()

    data_path = BACKEND_DIR / "app" / "data" / "docs.json"

    docs = load_documents(data_path)
    safe_docs = [
        d for d in docs
        if not contains_high_risk_secret(d["content"])
    ]

    retriever = HybridRetriever(safe_docs)

    results = retriever.search(
        args.question,
        role=args.role,
        top_k=8
    )

    print("\nQUESTION:", args.question)
    print("ROLE:", args.role)
    print("VECTOR DATABASE: ChromaDB")
    print("COLLECTION:", retriever.collection.name)
    print("TOTAL CHUNKS:", len(retriever.chunks))
    print("-" * 90)

    if not results:
        print("No candidates found.")
        return

    for item in results:
        print(
            f"\nHybrid Rank #{item['hybrid_rank']} | "
            f"{item['chunk_id']} | {item['title']}"
        )

        print(
            f"BM25 Score: {item['lexical_score']:.5f} | "
            f"Rank: {item['lexical_rank']} | "
            f"Overlap: {item['lexical_overlap']}"
        )

        print(
            f"Semantic Similarity: "
            f"{item['semantic_similarity']:.5f} | "
            f"Rank: {item['semantic_rank']}"
        )

        print(
            f"RRF Hybrid Score: {item['hybrid_score']:.7f}"
        )

        print("Content:", item["text"][:260].replace("\n", " "))

        print("-" * 90)


if __name__ == "__main__":
    main()
