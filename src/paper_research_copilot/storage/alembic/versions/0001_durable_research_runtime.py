"""Create durable research task and event tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_durable_research_runtime"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_tasks",
        sa.Column("task_id", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.String(length=40), nullable=True),
        sa.Column("completed_at", sa.String(length=40), nullable=True),
        sa.Column("current_node", sa.String(length=100), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("ix_research_tasks_status", "research_tasks", ["status"])
    op.create_table(
        "research_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("agent_event_json", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["research_tasks.task_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "sequence",
            name="uq_research_events_task_sequence",
        ),
    )
    op.create_index(
        "ix_research_events_task_sequence",
        "research_events",
        ["task_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_events_task_sequence", table_name="research_events")
    op.drop_table("research_events")
    op.drop_index("ix_research_tasks_status", table_name="research_tasks")
    op.drop_table("research_tasks")
