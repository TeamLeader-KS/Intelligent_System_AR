"""Track elapsed operating time without counting stopped intervals."""
from alembic import op
import sqlalchemy as sa

revision = "0002_runtime"
down_revision = "0001"

def upgrade():
    op.add_column("equipment", sa.Column("serial_number", sa.String(120)))
    op.create_index("ix_equipment_serial_number", "equipment", ["serial_number"])
    op.add_column("equipment_components", sa.Column("runtime_state", sa.String(8), nullable=False, server_default="STOPPED"))
    op.add_column("equipment_components", sa.Column("run_started_at", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_component_runtime", "equipment_components", "(runtime_state = 'STOPPED' AND run_started_at IS NULL) OR (runtime_state = 'RUNNING' AND run_started_at IS NOT NULL AND operating_hours IS NOT NULL)")

def downgrade():
    raise RuntimeError("Downgrade would discard operating state; use a reviewed recovery plan")
