"""Consolidated schema, with data-preserving upgrades from legacy revisions 0001–0005."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None

def _stage_1():
    op.create_table("workshops", sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String(120), unique=True, nullable=False))
    op.create_table("equipment_types", sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String(120), unique=True, nullable=False))
    op.create_table("users", sa.Column("id", sa.Integer, primary_key=True), sa.Column("login", sa.String(80), unique=True, nullable=False), sa.Column("full_name", sa.String(160), nullable=False), sa.Column("password_hash", sa.Text, nullable=False), sa.Column("role", sa.String(20), nullable=False), sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id")), sa.Column("active", sa.Boolean, nullable=False))
    op.create_table("equipment", sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String(160), nullable=False), sa.Column("inventory_number", sa.String(80), unique=True, nullable=False), sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id"), nullable=False), sa.Column("type_id", sa.Integer, sa.ForeignKey("equipment_types.id"), nullable=False), sa.Column("passport", sa.Text, nullable=False))
    op.create_index("ix_equipment_workshop_id", "equipment", ["workshop_id"])
    op.create_table("defect_types", sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.String(120), unique=True, nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("recommendation", sa.Text, nullable=False))
    op.create_table("browser_sessions", sa.Column("digest", sa.String(64), primary_key=True), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_browser_sessions_user_id", "browser_sessions", ["user_id"])
    op.create_table("api_keys", sa.Column("id", sa.Integer, primary_key=True), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False), sa.Column("digest", sa.String(64), unique=True, nullable=False), sa.Column("prefix", sa.String(16), nullable=False), sa.Column("name", sa.String(80), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked", sa.Boolean, nullable=False))
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_table("login_attempts", sa.Column("login", sa.String(80), primary_key=True), sa.Column("failures", sa.Integer, nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("audit_logs", sa.Column("id", sa.Integer, primary_key=True), sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")), sa.Column("action", sa.String(80), nullable=False), sa.Column("entity_id", sa.Integer), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

def _stage_2():
    op.create_table(
        "inspections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("equipment_id", sa.Integer, sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("processing_status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("photo_key", sa.String(32), unique=True, nullable=False),
        sa.Column("storage_backend", sa.String(16), nullable=False),
        sa.Column("media_type", sa.String(32)),
        sa.Column("checksum", sa.String(64)),
        sa.Column("result", JSONB(none_as_null=True)),
        sa.Column("error", JSONB(none_as_null=True)),
        sa.Column("response_status", sa.Integer),
        sa.Column("cleanup_pending", sa.Boolean, nullable=False),
        sa.UniqueConstraint("author_id", "idempotency_key", name="uq_inspection_author_key"),
        sa.CheckConstraint("processing_status IN ('PROCESSING', 'COMPLETED', 'FAILED')", name="ck_inspection_processing"),
        sa.CheckConstraint("source IN ('CAMERA', 'GALLERY')", name="ck_inspection_source"),
        sa.CheckConstraint("storage_backend IN ('local', 'nextcloud')", name="ck_inspection_storage"),
    )
    op.create_index("ix_inspections_equipment_created", "inspections", ["equipment_id", sa.text("created_at DESC"), sa.text("id DESC")])
    op.create_index("ix_inspections_processing_deadline", "inspections", ["processing_status", "deadline"])

def _stage_3():
    op.create_table("issues",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("equipment_id", sa.Integer, sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("defect_type_id", sa.Integer, sa.ForeignKey("defect_types.id"), nullable=False),
        sa.Column("analysis_source", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("analysis_source IN ('MOCK', 'MODEL')", name="ck_issue_source"))
    op.create_index("uq_open_issue", "issues", ["equipment_id", "workshop_id", "defect_type_id", "analysis_source"],
                    unique=True, postgresql_where=sa.text("closed_at IS NULL"))
    op.create_table("reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("inspection_id", sa.Integer, sa.ForeignKey("inspections.id"), nullable=False),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("equipment_id", sa.Integer, sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("comment", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("body", JSONB, nullable=False))
    op.create_index("ix_reports_inspection_id", "reports", ["inspection_id"])
    op.create_table("report_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("inspection_id", sa.Integer, sa.ForeignKey("inspections.id"), nullable=False),
        sa.Column("key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer, nullable=False),
        sa.Column("body", JSONB, nullable=False),
        sa.UniqueConstraint("author_id", "inspection_id", "key", name="uq_report_request"))
    op.create_table("notifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id"), nullable=False),
        sa.Column("recipient_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("analysis_source", sa.String(8), nullable=False),
        sa.UniqueConstraint("issue_id", "recipient_id", name="uq_notification_issue_recipient"))
    op.create_index("ix_notifications_recipient_created", "notifications", ["recipient_id", sa.text("created_at DESC"), sa.text("id DESC")])

def _stage_4():
    op.create_table("reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("inspection_id", sa.Integer, sa.ForeignKey("inspections.id"), nullable=False),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("comment", sa.String(2000), nullable=False),
        sa.Column("previous_review_id", sa.Integer, sa.ForeignKey("reviews.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        sa.Column("body", JSONB, nullable=False),
        sa.CheckConstraint("(decision = 'CONFIRMED' AND status IN ('OK','WARNING','CRITICAL')) OR (decision = 'REJECTED' AND status = 'UNKNOWN')", name="ck_review_decision"))
    op.create_index("ix_reviews_inspection_id", "reviews", ["inspection_id", sa.text("id DESC")])
    op.create_index("uq_review_first", "reviews", ["inspection_id"], unique=True, postgresql_where=sa.text("previous_review_id IS NULL"))
    op.create_index("uq_review_successor", "reviews", ["previous_review_id"], unique=True, postgresql_where=sa.text("previous_review_id IS NOT NULL"))
    op.add_column("issues", sa.Column("closed_by", sa.Integer, sa.ForeignKey("users.id")))
    op.add_column("issues", sa.Column("close_review_id", sa.Integer, sa.ForeignKey("reviews.id")))
    op.add_column("issues", sa.Column("close_reason", sa.Text))
    op.add_column("issues", sa.Column("resolution", sa.String(16)))
    op.create_table("workflow_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False), sa.Column("target_id", sa.Integer, nullable=False),
        sa.Column("key", sa.String(36), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer, nullable=False), sa.Column("body", JSONB, nullable=False),
        sa.UniqueConstraint("author_id", "action", "target_id", "key", name="uq_workflow_request"),
        sa.CheckConstraint("action IN ('review', 'close')", name="ck_workflow_action"))

def _stage_5():
    op.create_table("mobile_models",
        sa.Column("sha256", sa.String(64), primary_key=True),
        sa.Column("version", sa.String(160), nullable=False),
        sa.Column("threshold", sa.Double, nullable=False),
        sa.Column("labels", JSONB, nullable=False),
        sa.CheckConstraint("threshold >= 0 AND threshold < 1", name="ck_mobile_threshold"))
    op.create_table("equipment_components",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("equipment_id", sa.Integer, sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("specifications", JSONB, nullable=False),
        sa.Column("installed_on", sa.Date),
        sa.Column("lifetime_days", sa.Integer),
        sa.Column("lifetime_hours", sa.Double),
        sa.Column("lifetime_cycles", sa.Integer),
        sa.Column("operating_hours", sa.Double),
        sa.Column("operating_cycles", sa.Integer),
        sa.Column("service_interval_hours", sa.Double),
        sa.Column("last_service_hours", sa.Double),
        sa.Column("last_serviced_at", sa.DateTime(timezone=True)),
        sa.Column("last_event_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("lifetime_days > 0 AND lifetime_hours > 0 AND lifetime_cycles > 0 AND service_interval_hours > 0", name="ck_component_norms"),
        sa.CheckConstraint("operating_hours >= 0 AND operating_cycles >= 0 AND last_service_hours >= 0 AND last_service_hours <= operating_hours", name="ck_component_usage"))
    op.create_index("ix_equipment_components_equipment_id", "equipment_components", ["equipment_id"])
    op.create_table("component_work",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("component_id", sa.Integer, sa.ForeignKey("equipment_components.id"), nullable=False),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workshop_id", sa.Integer, sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("body", JSONB, nullable=False),
        sa.UniqueConstraint("author_id", "component_id", "key", name="uq_component_work_key"))
    op.create_index("ix_component_work_component_id", "component_work", ["component_id"])

def upgrade():
    upgrade_from(None)

def upgrade_from(previous: str | None):
    stages = (_stage_1, _stage_2, _stage_3, _stage_4, _stage_5)
    legacy = {None: 0, "0001": 1, "0002": 2, "0003": 3, "0004": 4, "0005": 5}
    if previous not in legacy:
        raise RuntimeError("Unknown legacy database revision")
    for stage in stages[legacy[previous]:]:
        stage()

def downgrade():
    raise RuntimeError("Data-destructive downgrade requires an explicit recovery plan")
