# MVP Definition of Done

## User experience

A user submits a question about Agent research. The application shows the
generated research plan and live execution progress, then returns a concise,
structured explanation with traceable evidence and sources.

The plan may be approved or adjusted before execution. This human-in-the-loop
step is optional for the user; the default path remains autonomous.

## Required workflow

1. Turn the question into structured research tasks.
2. Search a curated local corpus and public academic sources.
3. Normalize and deduplicate candidate papers.
4. Run dense and sparse retrieval, RRF fusion, and reranking.
5. Analyze paper content and collect evidence for each research task.
6. Allow at most one reflection-driven supplementary search.
7. Generate a concise report with evidence-backed citations.
8. Verify claim-citation relationships before returning the final report.

## Required deliverables

- FastAPI backend and a small React interface.
- Persisted research state and inspectable execution events.
- A reproducible Agent-domain seed corpus.
- Vector, hybrid, and hybrid-plus-reranker comparisons.
- Unit, integration, and one fixed end-to-end demonstration case.
- Docker-based local startup and project documentation.

## Deferred

- General-purpose research across multiple disciplines.
- Multi-agent role-play, unrestricted research loops, and open-ended chat.
- Scanned PDFs, formula understanding, and complex table extraction.
- Large evaluation datasets and production multi-user infrastructure.
