"""Application-owned persistence boundaries and SQLite implementations."""

from paper_research_copilot.storage.checkpoints import SqliteCheckpointStore
from paper_research_copilot.storage.memory import InMemoryResearchRepository
from paper_research_copilot.storage.repositories import (
    AcquisitionNotFoundError,
    AcquisitionRepository,
    PaperAssetNotFoundError,
    ResearchEventRecord,
    ResearchEventType,
    ResearchRepository,
    ResearchTaskRecord,
    ResearchTaskStatus,
    TaskNotFoundError,
    TaskStateConflictError,
)
from paper_research_copilot.storage.sqlite import SqliteResearchRepository

__all__ = [
    "InMemoryResearchRepository",
    "AcquisitionNotFoundError",
    "AcquisitionRepository",
    "PaperAssetNotFoundError",
    "ResearchEventRecord",
    "ResearchEventType",
    "ResearchRepository",
    "ResearchTaskRecord",
    "ResearchTaskStatus",
    "SqliteCheckpointStore",
    "SqliteResearchRepository",
    "TaskNotFoundError",
    "TaskStateConflictError",
]
