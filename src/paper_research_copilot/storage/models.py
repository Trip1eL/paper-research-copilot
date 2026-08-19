"""SQLAlchemy models for application-owned durable research state."""

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ResearchTaskRow(Base):
    __tablename__ = "research_tasks"

    task_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[str | None] = mapped_column(String(40))
    completed_at: Mapped[str | None] = mapped_column(String(40))
    current_node: Mapped[str | None] = mapped_column(String(100))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    events: Mapped[list["ResearchEventRow"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class ResearchEventRow(Base):
    __tablename__ = "research_events"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_research_events_task_sequence"),
        Index("ix_research_events_task_sequence", "task_id", "sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.task_id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    agent_event_json: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)

    task: Mapped[ResearchTaskRow] = relationship(back_populates="events")


class PaperAssetRow(Base):
    __tablename__ = "paper_assets"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_id",
            "revision",
            name="uq_paper_assets_provider_external_revision",
        ),
    )

    asset_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(80), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    doi: Mapped[str | None] = mapped_column(String(255), unique=True)
    candidate_json: Mapped[str] = mapped_column(Text, nullable=False)
    acquisition_query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    local_path: Mapped[str | None] = mapped_column(Text)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    collection_name: Mapped[str | None] = mapped_column(String(255))
    index_version: Mapped[str | None] = mapped_column(String(255))
    parse_summary_json: Mapped[str | None] = mapped_column(Text)
    duplicate_of_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("paper_assets.asset_id")
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


class AcquisitionRunRow(Base):
    __tablename__ = "acquisition_runs"

    acquisition_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_id: Mapped[str | None] = mapped_column(String(32), index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    budget_json: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downloaded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    indexed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[str] = mapped_column(String(40), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
