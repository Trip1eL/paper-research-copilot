"""Add durable parent-child relations for clarification follow-ups."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_task_clarification_relation"
down_revision: str | None = "0002_dynamic_acquisition"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_task_clarifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_task_id", sa.String(length=32), nullable=False),
        sa.Column("child_task_id", sa.String(length=32), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("response_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_task_id"], ["research_tasks.task_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["child_task_id"], ["research_tasks.task_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_task_id"),
        sa.UniqueConstraint(
            "parent_task_id",
            "response_hash",
            name="uq_research_task_clarifications_parent_response",
        ),
    )
    op.create_index(
        "ix_research_task_clarifications_parent",
        "research_task_clarifications",
        ["parent_task_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_task_clarifications_parent",
        table_name="research_task_clarifications",
    )
    op.drop_table("research_task_clarifications")
