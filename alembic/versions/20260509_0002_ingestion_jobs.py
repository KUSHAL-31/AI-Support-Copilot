"""ingestion jobs

Revision ID: 20260509_0002
Revises: 20260509_0001
Create Date: 2026-05-09 00:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_0002"
down_revision: str | None = "20260509_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_ingestion_jobs_document_id_documents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_ingestion_jobs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_jobs")),
    )
    op.create_index(
        op.f("ix_ingestion_jobs_document_id"), "ingestion_jobs", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_ingestion_jobs_job_type"), "ingestion_jobs", ["job_type"], unique=False
    )
    op.create_index(
        "ix_ingestion_jobs_status_created", "ingestion_jobs", ["status", "created_at"], unique=False
    )
    op.create_index(op.f("ix_ingestion_jobs_status"), "ingestion_jobs", ["status"], unique=False)
    op.create_index(
        "ix_ingestion_jobs_tenant_status", "ingestion_jobs", ["tenant_id", "status"], unique=False
    )
    op.create_index(
        op.f("ix_ingestion_jobs_tenant_id"), "ingestion_jobs", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_jobs_tenant_id"), table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_tenant_status", table_name="ingestion_jobs")
    op.drop_index(op.f("ix_ingestion_jobs_status"), table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_status_created", table_name="ingestion_jobs")
    op.drop_index(op.f("ix_ingestion_jobs_job_type"), table_name="ingestion_jobs")
    op.drop_index(op.f("ix_ingestion_jobs_document_id"), table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
