from alembic import context
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from app.infrastructure.models import Base

connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=Base.metadata)
with context.begin_transaction():
    # The consolidated graph has no legacy revisions. Upgrade their remaining
    # stages before Alembic tries to resolve the old revision in that graph.
    if inspect(connection).has_table("alembic_version"):
        versions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        legacy_revisions = {"0001", "0002", "0003", "0004", "0005", "0006_initial"}
        schema_inspector = inspect(connection)
        current_tables = set(schema_inspector.get_table_names())
        # Old and consolidated bases both used 0001. The three new tables
        # distinguish a completed new base from the historical foundation.
        new_base = versions == ["0001"] and {"mobile_models", "equipment_components", "component_work"}.issubset(current_tables)
        if len(versions) == 1 and versions[0] in legacy_revisions and not new_base:
            previous = "0005" if versions[0] == "0006_initial" else versions[0]
            required = {"workshops", "equipment", "users", "defect_types", "audit_logs", "browser_sessions", "api_keys", "login_attempts", "equipment_types"}
            if previous >= "0002":
                required.add("inspections")
            if previous >= "0003":
                required.update({"issues", "reports", "report_requests", "notifications"})
            if previous >= "0004":
                required.update({"reviews", "workflow_requests"})
            if previous >= "0005":
                required.update({"mobile_models", "equipment_components", "component_work"})
            if not required.issubset(current_tables):
                raise RuntimeError("Legacy revision does not match the database schema; refusing to stamp")
            for table in required:
                expected_columns = set(Base.metadata.tables[table].columns.keys())
                if table == "equipment_components":
                    expected_columns -= {"runtime_state", "run_started_at"}
                if table == "equipment":
                    expected_columns -= {"serial_number"}
                if table == "issues" and previous < "0004":
                    expected_columns -= {"closed_by", "close_review_id", "close_reason", "resolution"}
                existing_columns = {column["name"] for column in schema_inspector.get_columns(table)}
                if not expected_columns.issubset(existing_columns):
                    raise RuntimeError("Legacy revision has missing columns; refusing to stamp")
            head = ScriptDirectory.from_config(context.config).get_revision("0001")
            with Operations.context(context.get_context()):
                head.module.upgrade_from(previous)
            connection.execute(text("UPDATE alembic_version SET version_num = :head"), {"head": head.revision})
    context.run_migrations()
