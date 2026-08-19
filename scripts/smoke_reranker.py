"""Run one real SiliconFlow reranker request without exposing credentials."""

from paper_research_copilot.config import get_settings
from paper_research_copilot.integrations import SiliconFlowRerankerProvider


def main() -> int:
    settings = get_settings()
    base_url, api_key = settings.require_siliconflow_credentials()
    provider = SiliconFlowRerankerProvider(
        base_url,
        api_key,
        settings.siliconflow_reranker_model,
    )
    scores = provider.score(
        "语言模型智能体如何通过外部工具与环境交互？",
        (
            "Language agents interleave reasoning, tool actions, and environment observations.",
            "Convolutional neural networks classify images using spatial filters.",
        ),
    )
    if scores[0] <= scores[1]:
        raise RuntimeError("Reranker did not rank the relevant Agent evidence first")
    print(f"Model: {provider.model}")
    print(f"Scores: relevant={scores[0]:.6f}, irrelevant={scores[1]:.6f}")
    print("Smoke test: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
