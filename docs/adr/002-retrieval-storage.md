# ADR 002: Corpus and Retrieval Storage

- Status: Accepted for v1; partially superseded by ADR 004 and ADR 005 for v2
- Date: 2026-08-14

## Context

The MVP focuses on Agent research and must support reproducible demonstrations
as well as fresh academic search. It also needs dense and sparse retrieval
without operating two separate retrieval databases.

## Decision

- Maintain a curated seed corpus of roughly 30 to 50 open-access Agent papers.
- Search OpenAlex and arXiv for papers outside the seed corpus.
- Download and cache open PDFs on demand instead of mirroring all papers.
- Store dense and sparse vectors as named vectors in Qdrant.
- Perform hybrid fusion with Qdrant RRF and rerank the fused candidates.
- Use `BAAI/bge-m3` through SiliconFlow for 1024-dimensional dense embeddings.
- Use SQLite for research tasks, LangGraph checkpoints, and report metadata.
- Build the UI with React and keep presentation logic outside FastAPI.

Qdrant and SQLite have different responsibilities. Qdrant is the retrieval
engine; SQLite is the transactional application store. A second search database
is not required for hybrid retrieval.

## Framework decision

Use LangGraph for state transitions, bounded loops, interrupts, and checkpoints.
Do not build the retrieval and domain layers on LangChain chains or high-level
retriever abstractions. `langchain-core` may exist as a LangGraph dependency,
but project services expose their own typed interfaces.

## Consequences

The local corpus makes demos and future evaluations reproducible, while online
search prevents the system from being limited to a static collection. Qdrant
keeps hybrid retrieval in one engine and is lighter to operate than Milvus for
the MVP corpus size.
