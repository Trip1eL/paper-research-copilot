"""Production builder for the bounded LangGraph research runtime."""

import re
from pathlib import Path

from paper_research_copilot.agent.models import AgentRuntimeConfig
from paper_research_copilot.agent.planner import CachedResearchPlanner
from paper_research_copilot.agent.runtime import ResearchAgentRuntime
from paper_research_copilot.config import PROJECT_ROOT, Settings
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.integrations import OpenAICompatibleChatProvider
from paper_research_copilot.pipeline import build_retrieval_runtime
from paper_research_copilot.reporting import AnswerGenerator
from paper_research_copilot.retrieval import RetrievalMode


def build_agent_runtime(
    settings: Settings,
    *,
    version: int = 3,
    collection_name: str = "agent_seed_v3_bge_m3_chunking_v1",
    planner_cache_path: Path | None = None,
    config: AgentRuntimeConfig | None = None,
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
    retrieval_runtime = build_retrieval_runtime(settings, collection_name)
    try:
        if retrieval_runtime.vector_store.count() == 0:
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
        return ResearchAgentRuntime(
            planner,
            retrieval_runtime.retriever_for(RetrievalMode.DISCOVERY),
            answer_writer,
            config=config
            or AgentRuntimeConfig(
                top_k=settings.agent_top_k,
                candidate_pool_per_task=settings.agent_candidate_pool_per_task,
                max_retries=settings.agent_max_retries,
                min_chunks_per_task=settings.agent_min_chunks_per_task,
            ),
            close_callback=retrieval_runtime.close,
        )
    except Exception:
        retrieval_runtime.close()
        raise
