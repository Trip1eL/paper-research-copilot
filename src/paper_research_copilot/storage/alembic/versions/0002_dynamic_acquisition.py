"""Add dynamic paper registry and acquisition run tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_dynamic_acquisition"
down_revision: str | None = "0001_durable_research_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_assets",
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=80), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("candidate_json", sa.Text(), nullable=False),
        sa.Column("acquisition_query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("collection_name", sa.String(length=255), nullable=True),
        sa.Column("index_version", sa.String(length=255), nullable=True),
        sa.Column("parse_summary_json", sa.Text(), nullable=True),
        sa.Column("duplicate_of_asset_id", sa.String(length=32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["duplicate_of_asset_id"], ["paper_assets.asset_id"]),
        sa.PrimaryKeyConstraint("asset_id"),
        sa.UniqueConstraint("doi"),
        sa.UniqueConstraint(
            "provider",
            "external_id",
            "revision",
            name="uq_paper_assets_provider_external_revision",
        ),
        sa.UniqueConstraint("sha256"),
    )
    op.create_index("ix_paper_assets_status", "paper_assets", ["status"])
    op.create_table(
        "acquisition_runs",
        sa.Column("acquisition_id", sa.String(length=32), nullable=False),
        sa.Column("task_id", sa.String(length=32), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("budget_json", sa.Text(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("selected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("downloaded_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("indexed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.String(length=40), nullable=False),
        sa.Column("completed_at", sa.String(length=40), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("acquisition_id"),
    )
    op.create_index("ix_acquisition_runs_status", "acquisition_runs", ["status"])
    op.create_index("ix_acquisition_runs_task_id", "acquisition_runs", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_acquisition_runs_task_id", table_name="acquisition_runs")
    op.drop_index("ix_acquisition_runs_status", table_name="acquisition_runs")
    op.drop_table("acquisition_runs")
    op.drop_index("ix_paper_assets_status", table_name="paper_assets")
    op.drop_table("paper_assets")
