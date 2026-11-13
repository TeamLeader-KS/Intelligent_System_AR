"""Exercise the consolidated file against isolated schemas, including historical data."""
import os
from uuid import uuid4
import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from app.infrastructure.database import make_engine, migrate


@pytest.mark.parametrize("previous", [None,"0001","0002","0003","0004","0005","0006_initial"])
def test_consolidated_schema_preserves_legacy_data(previous):
    url = os.environ["IV_TEST_DATABASE_URL"]
    assert url.rsplit("/",1)[-1] == "iv_step2_test"
    schema = "migration_" + uuid4().hex
    admin_engine = make_engine(url)
    engine = create_engine(url,connect_args={"options":f"-csearch_path={schema}"})
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        cfg = Config()
        cfg.set_main_option("script_location",str(Path(__file__).resolve().parents[1]/"migrations"))
        head = ScriptDirectory.from_config(cfg).get_revision("head")
        if previous:
            with engine.begin() as conn:
                with Operations.context(MigrationContext.configure(conn)):
                    for stage in range(1,(5 if previous == "0006_initial" else int(previous))+1):
                        getattr(head.module,f"_stage_{stage}")()
                conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) NOT NULL PRIMARY KEY)"))
                conn.execute(text("INSERT INTO alembic_version VALUES (:v)"),{"v":previous})
                conn.execute(text("INSERT INTO workshops (id,name) VALUES (101,'Сохранённый цех')"))
                conn.execute(text("INSERT INTO equipment_types (id,name) VALUES (101,'Насос')"))
                conn.execute(text("INSERT INTO users (id,login,full_name,password_hash,role,active) VALUES (101,'existing','Existing','hash','ADMIN',true)"))
                conn.execute(text("INSERT INTO equipment (id,name,inventory_number,workshop_id,type_id,passport) VALUES (101,'Existing pump','pump_old',101,101,'Паспорт сохранён')"))
                conn.execute(text("INSERT INTO browser_sessions (digest,user_id,expires_at) VALUES ('retained-session',101,now()+interval '1 day')"))
                if previous >= "0002":
                    conn.execute(text("""INSERT INTO inspections
                        (id,equipment_id,workshop_id,author_id,source,idempotency_key,request_hash,processing_status,
                         deadline,photo_key,storage_backend,media_type,checksum,result,response_status,cleanup_pending)
                        VALUES (101,101,101,101,'CAMERA','old-key','old-hash','COMPLETED',now(),
                                'old-photo-key','local','image/png','old-checksum','{"status":"WARNING"}',201,false)"""))
        migrate(engine)
        # Running a second time must be a no-op.
        migrate(engine)
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == head.revision
            assert {"inspections","reviews","mobile_models","equipment_components","component_work"}.issubset(inspect(conn).get_table_names())
            if previous:
                assert conn.scalar(text("SELECT passport FROM equipment WHERE id=101")) == "Паспорт сохранён"
                assert conn.scalar(text("SELECT digest FROM browser_sessions WHERE user_id=101")) == "retained-session"
                if previous >= "0002":
                    row = conn.execute(text("SELECT photo_key,checksum,result FROM inspections WHERE id=101")).one()
                    assert tuple(row) == ("old-photo-key","old-checksum",{"status":"WARNING"})
    finally:
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
