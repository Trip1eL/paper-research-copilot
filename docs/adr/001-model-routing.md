# ADR 001: Task-Aware Model Routing

- Status: Accepted
- Date: 2026-08-14

## Context

The workflow has a small number of reasoning-critical operations and a larger
number of routine or high-volume operations. Using the strongest model for all
requests would add latency and cost without improving every stage equally.

## Decision

Use explicit task classes instead of asking another model to classify task
complexity.

### Critical or complex tasks

Route through `RELAY_BASE_URL` using `GPT_MODEL_NAME`, with `gpt-5.5` as the
project default:

- research planning and plan revision;
- evidence-gap reflection and conflict resolution;
- claim-evidence and citation entailment verification;
- final cross-paper synthesis;
- LLM-based evaluation judgments when deterministic metrics are insufficient.

### Ordinary or high-volume tasks

Route through `DEEPSEEK_API_URL` using `DEEPSEEK_MODEL`, with
`deepseek-v4-flash` as the project default:

- routine query rewriting;
- metadata normalization assistance;
- paper and chunk-level structured extraction;
- intermediate summarization;
- formatting and other low-risk transformations.

### Embeddings

Use the provider configured by `SILICONFLOW_BASE_URL` and
`SILICONFLOW_EMBEDDING_MODEL` for document and query embeddings.

## Implementation constraints

- Agent nodes select a semantic task class, not a concrete provider or model.
- Provider URLs, keys, and model names are read only from environment settings.
- Traces record task class, provider, model, latency, and token usage.
- Evaluation results record the routing configuration used by the run.
- Fallback behavior must be explicit and observable; provider failures must not
  silently switch models and invalidate evaluation comparisons.

## Consequences

Critical reasoning quality is concentrated where it matters, while a faster
model handles high-volume work. Routing choices remain reproducible and testable.
