"""Keep organizer facts, provenance and reference datasets separate from demo readings."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_sources"
down_revision = "0002_runtime"

def upgrade():
    for table in ("equipment", "equipment_components"):
        op.add_column(table, sa.Column("data_origin", sa.String(32), nullable=False, server_default="USER"))
        op.add_column(table, sa.Column("facts", JSONB, nullable=False, server_default="[]"))
    op.create_table("source_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("source_path", sa.Text, nullable=False),
        sa.Column("original_path", sa.Text, nullable=False),
        sa.Column("public_source", sa.Text, nullable=False),
        sa.Column("bytes", sa.BigInteger, nullable=False),
        sa.Column("media_type", sa.String(128), nullable=False),
        sa.Column("details", JSONB, nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_source_documents_workshop_id", "source_documents", ["workshop_id"])
    op.create_table("reference_datasets",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("equipment_id", sa.Integer, sa.ForeignKey("equipment.id")),
        sa.Column("document_id", sa.String(64), sa.ForeignKey("source_documents.id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("sheet", sa.String(256), nullable=False),
        sa.Column("headers", JSONB, nullable=False),
        sa.Column("rows", JSONB, nullable=False),
        sa.Column("details", JSONB, nullable=False))

def downgrade():
    raise RuntimeError("Source and reference data must be retained; use an explicit recovery plan")
