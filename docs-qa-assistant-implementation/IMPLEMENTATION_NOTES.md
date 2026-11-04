# Implementation notes

## Implemented
- Next.js → FastAPI → permission-aware retrieval → Groq → cited answer.
- Six original seed documents and five original sample questions are preserved.
- Deterministic extractive fallback if Groq is absent or fails.
- Role/classification filtering before retrieval and LLM context construction.
- High-risk credential pattern exclusion and basic email/phone redaction.
- Structured output and citation ID validation.

## Be transparent with the panel
- Role selector is a demo identity simulator, not production authentication.
- Source docs default to Public because source data defines no access metadata.
- Retrieval score is not a probability.
- Evidence sufficiency is a lightweight lexical gate, not formal proof of entailment.
- No persistent feedback database, enterprise SSO, multi-tenancy or document versioning is claimed.

## Suggested demo
1. Ask the password reset question; show D-01.
2. Ask the CSV export limit; show 10,000 rows and D-03.
3. Ask about Salesforce; show abstention and no source.
4. Add an Internal test document allowed only to Administrator/Support Agent; verify Standard User cannot retrieve it.
5. Explain Groq only receives authorized top passages and the source fallback works if Groq is unavailable.
