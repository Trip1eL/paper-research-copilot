"""External service adapters for models, embeddings, and academic sources."""

from paper_research_copilot.integrations.embeddings import (
    EmbeddingProvider,
    SiliconFlowEmbeddingProvider,
)
from paper_research_copilot.integrations.llm import (
    ChatCompletion,
    ChatProvider,
    ChatTokenUsage,
    ObservableChatProvider,
    OpenAICompatibleChatProvider,
)
from paper_research_copilot.integrations.reranking import (
    RerankerProvider,
    SiliconFlowRerankerProvider,
)

__all__ = [
    "ChatProvider",
    "ChatCompletion",
    "ChatTokenUsage",
    "EmbeddingProvider",
    "OpenAICompatibleChatProvider",
    "ObservableChatProvider",
    "SiliconFlowEmbeddingProvider",
    "RerankerProvider",
    "SiliconFlowRerankerProvider",
]
