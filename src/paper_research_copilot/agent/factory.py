"""Production builder for the bounded LangGraph research runtime."""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from paper_research_copilot.agent.guardrails import QuestionAmbiguityGate
from paper_research_copilot.agent.models import AgentRuntimeConfig
from paper_research_copilot.agent.planner import CachedResearchPlanner
from paper_research_copilot.agent.runtime import ResearchAgentRuntime
from paper_research_copilot.config import PROJECT_ROOT, Settings
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.integrations import OpenAICompatibleChatProvider
from paper_research_copilot.pipeline import (
    build_dynamic_acquisition_service,
    build_federated_retrieval_runtime,
)
from paper_research_copilot.reporting import AnswerGenerator
from paper_research_copilot.storage import AcquisitionRepository


def build_agent_runtime(
    settings: Settings,
    *,
    version: int = 3,
    collection_name: str = "agent_seed_v3_bge_m3_chunking_v1",
    planner_cache_path: Path | None = None,
    config: AgentRuntimeConfig | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    repository: AcquisitionRepository | None = None,
    close_callback: Callable[[], None] | None = None,
) -> ResearchAgentRuntime:
    relay_url, relay_key = settings.require_relay_credentials()
    llm_url, llm_key = settings.require_llm_credentials()
    catalog = CorpusCatalogLoader(PROJECT_ROOT).load(version)
    aliases = (
        alias
        for asset in catalog.papers
        for alias in (
            asset.spec.slug,
            asset.spec.title,
            asset.spec.title.partition(":")[0],
        )
    )
    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", settings.gpt_model_name)
    cache_path = planner_cache_path or (
        PROJECT_ROOT
        / "data"
        / "agent"
        / f"research_plans_v1_corpus_v{version}_{safe_model}.jsonl"
    )
    runtime_config = config or AgentRuntimeConfig(
        top_k=settings.agent_top_k,
        candidate_pool_per_task=settings.agent_candidate_pool_per_task,
        max_retries=settings.agent_max_retries,
        max_acquisition_rounds=(
            1 if settings.agent_dynamic_acquisition_enabled else 0
        ),
        min_chunks_per_task=settings.agent_min_chunks_per_task,
    )
    if runtime_config.max_acquisition_rounds and repository is None:
        raise ValueError("Acquisition-enabled Agent Runtime requires a Repository")
    retrieval_runtime = build_federated_retrieval_runtime(settings, collection_name)
    acquisition = None
    try:
        if retrieval_runtime.curated_vector_store.count() == 0:
            raise LookupError("Qdrant collection is empty; run ingest-corpus first")
        planner = CachedResearchPlanner(
            OpenAICompatibleChatProvider(
                base_url=relay_url,
                api_key=relay_key,
                model=settings.gpt_model_name,
                max_tokens=settings.agent_planner_max_tokens,
            ),
            model=settings.gpt_model_name,
            cache_path=cache_path,
            forbidden_aliases=aliases,
            retry_attempts=3,
        )
        answer_writer = AnswerGenerator(
            OpenAICompatibleChatProvider(
                base_url=llm_url,
                api_key=llm_key,
                model=settings.deepseek_model,
                max_tokens=settings.answer_max_tokens,
            )
        )
        if runtime_config.max_acquisition_rounds:
            if repository is None:
                raise RuntimeError("Acquisition Repository unexpectedly missing")
            acquisition = build_dynamic_acquisition_service(
                settings,
                repository,
                embeddings=retrieval_runtime.embeddings,
                vector_store=retrieval_runtime.dynamic_vector_store,
            )

        def close_runtime_resources() -> None:
            try:
                if acquisition is not None:
                    acquisition.close()
            finally:
                retrieval_runtime.close()
                if close_callback is not None:
                    close_callback()

        return ResearchAgentRuntime(
            planner,
            retrieval_runtime.retriever,
            answer_writer,
            acquirer=acquisition,
            question_gate=QuestionAmbiguityGate(),
            config=runtime_config,
            checkpointer=checkpointer,
            close_callback=close_runtime_resources,
        )
    except Exception:
        try:
            if acquisition is not None:
                acquisition.close()
        finally:
            retrieval_runtime.close()
        raise
