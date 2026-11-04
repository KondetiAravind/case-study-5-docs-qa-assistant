# Implementation notes — V2 Hybrid RAG

## Implemented architecture
- Sentence Transformers `all-MiniLM-L6-v2` embeddings.
- Persistent ChromaDB collection using cosine similarity.
- BM25 keyword retrieval over the same chunks.
- Reciprocal Rank Fusion to combine lexical and vector rankings.
- Stable chunk IDs and visible BM25, semantic similarity and RRF diagnostics.
- Permission filters in both retrieval channels before evidence is returned.
- Groq grounded answer generation with chunk-ID citation validation.
- Explicit abstention and source-based fallback.
- Multi-turn chat with bounded in-memory context.

## Important terminology
- V1 = lexical retrieval baseline.
- V2 = hybrid RAG with a real vector database.
- ChromaDB is the vector database.
- Sentence Transformers is the embedding model.
- Groq is the answer-generation LLM.
- BM25 is the keyword retrieval method.
- RRF is the rank-fusion method.

## Known POC limitations
- Demo identity header is not production authentication.
- Seed documents default to Public.
- PII/secret detection is pattern-based and not full DLP.
- Local Chroma persistence requires a persistent disk in cloud deployment.
- In-memory conversation history is lost on restart.
- Thresholds require tuning against a labelled evaluation dataset.
- Do not claim measured retrieval quality improvements until evaluation is run.

## Suggested live demo
1. Ask the reset-link expiry question; inspect document D-01 and chunk ID.
2. Expand retrieval diagnostics to show BM25, semantic and RRF scores.
3. Ask a paraphrased question and explain how semantic search helps.
4. Ask an unsupported question such as Salesforce; show abstention.
5. Ask Growth API limit, then follow up with “What about Enterprise?”.
6. Demonstrate role filtering with a synthetic Internal-only document.
7. Explain that ChromaDB persists the vectors, while Groq generates the final answer.
