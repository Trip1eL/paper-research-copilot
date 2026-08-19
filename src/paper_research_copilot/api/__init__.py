"""FastAPI transport layer for research tasks and health endpoints."""

from paper_research_copilot.api.app import app, create_app
from paper_research_copilot.api.models import (
    HealthResponse,
    ResearchRequest,
    ResearchStreamEvent,
    ResearchTaskAccepted,
    ResearchTaskStatus,
    ResearchTaskView,
)
from paper_research_copilot.api.service import AgentRuntimeProtocol, ResearchTaskService

__all__ = [
    "AgentRuntimeProtocol",
    "HealthResponse",
    "ResearchRequest",
    "ResearchStreamEvent",
    "ResearchTaskAccepted",
    "ResearchTaskService",
    "ResearchTaskStatus",
    "ResearchTaskView",
    "app",
    "create_app",
]
