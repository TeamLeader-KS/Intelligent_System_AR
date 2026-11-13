"""Interactive account provisioning; never accept passwords in argv."""
import argparse
import getpass
import sys
import os
import json
import secrets
from pathlib import Path
from .infrastructure.database import database_url, make_engine, migrate, sessions
from .infrastructure.repository import Repository
from .infrastructure.passwords import Passwords

LOCAL_KEYS = ("IV_LOCAL_DB_PASSWORD", "IV_LOCAL_ADMIN_PASSWORD", "IV_DEMO_PASSWORD", "IV_DEMO_ADMIN_PASSWORD")

def prepare_local_files(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for key in LOCAL_KEYS:
        path = directory / key
        try:
            with path.open("x") as file:
                file.write(secrets.token_hex(24))
            # This Docker volume is shared read-only with the application and PostgreSQL.
            path.chmod(0o444)
        except FileExistsError:
            pass
        value = path.read_text().strip()
        if len(value) < 12 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"Некорректный сохранённый секрет {key}; существующие данные не изменены")

def local_database(directory: Path) -> None:
    password = (directory / "IV_LOCAL_DB_PASSWORD").read_text().strip()
    os.environ["DATABASE_URL"] = f"postgresql+psycopg://iv_app:{password}@database:5432/industrial_vision"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["create-admin", "seed-demo", "seed-pump-demo", "bootstrap-local", "prepare-local", "serve-local", "bootstrap-local-files"])
    parser.add_argument("--login",default="niyaz")
    parser.add_argument("--secrets-dir", type=Path, default=Path("/app/local-secrets"))
    args=parser.parse_args()
    if args.command in ("prepare-local", "serve-local", "bootstrap-local-files"):
        if os.getenv("LOCAL_DEMO_ENABLED") != "true":
            parser.error("Локальные команды разрешены только при LOCAL_DEMO_ENABLED=true")
        if args.command == "prepare-local":
            prepare_local_files(args.secrets_dir)
            downloads = Path("/app/downloads")
            if not (downloads / "app-debug.apk").exists():
                status = downloads / ".setup-build-status.tmp"
                status.write_text('{"state":"BUILDING"}')
                status.chmod(0o644)
                status.replace(downloads / "build-status.json")
            print("Локальные пароли подготовлены; существующие пароли сохранены.")
            return
        local_database(args.secrets_dir)
        if args.command == "serve-local":
            os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
    if args.command in ("bootstrap-local", "bootstrap-local-files"):
        from .infrastructure.demo import seed_pump_demo, seed_gallery_cards
        if os.getenv("LOCAL_DEMO_ENABLED") != "true":
            parser.error("bootstrap-local разрешён только при LOCAL_DEMO_ENABLED=true")
        try:
            raw = json.dumps({"employee_password": (args.secrets_dir / "IV_DEMO_PASSWORD").read_text().strip(),
                              "admin_password": (args.secrets_dir / "IV_DEMO_ADMIN_PASSWORD").read_text().strip()}) if args.command == "bootstrap-local-files" else sys.stdin.read(4097)
            if len(raw) > 4096:
                parser.error("Слишком большой запрос подготовки демоданных")
            credentials = json.loads(raw)
            if not isinstance(credentials, dict) or set(credentials) != {"employee_password", "admin_password"} or not all(isinstance(value, str) for value in credentials.values()):
                parser.error("Ожидаются employee_password и admin_password через JSON stdin")
        except json.JSONDecodeError:
            parser.error("Некорректный JSON подготовки демоданных")
        engine = make_engine(database_url())
        try:
            migrate(engine)
            result = seed_pump_demo(sessions(engine), credentials["employee_password"], admin_password=credentials["admin_password"])
            examples = os.getenv("CV_EXAMPLE_PATH")
            if examples:
                result["new_gallery_cards"] = seed_gallery_cards(sessions(engine), result["equipment_id"], Path(examples).parent / "pumps" / "manifest.json")
            organizer_directory = os.getenv("ORGANIZER_DATA_PATH")
            if organizer_directory:
                from sqlalchemy import select
                from .infrastructure.models import Equipment
                from .infrastructure.organizer_import import import_organizer_data
                with sessions(engine)() as db:
                    workshop_id = db.scalar(select(Equipment.workshop_id).where(Equipment.id == result["equipment_id"]))
                # Prepared facts are shipped in Git. Raw originals are optional and
                # are independently SHA-verified whenever an original is downloaded.
                result["organizer_data"] = import_organizer_data(sessions(engine), Path(organizer_directory), workshop_id,
                                                                verify_originals=False)
            print(json.dumps(result, ensure_ascii=False))
            if args.command == "bootstrap-local-files":
                print("Сайт: http://localhost:8001/industrial-vision/")
                print("Администратор: demo_admin /", credentials["admin_password"])
                print("Android: pump_worker или pump_engineer /", credentials["employee_password"])
        except ValueError as exc:
            parser.error(str(exc))
        finally:
            engine.dispose()
        return
    if args.command in ("seed-demo", "seed-pump-demo"):
        from .infrastructure.demo import seed_demo, seed_pump_demo
        password = getpass.getpass("Пароль демонстрационных сотрудников (от 12 символов): ")
        if password != getpass.getpass("Повторите пароль: "):
            parser.error("Пароли не совпадают")
        engine = make_engine(database_url())
        try:
            migrate(engine)
            seed = seed_pump_demo if args.command == "seed-pump-demo" else seed_demo
            result = seed(sessions(engine), password)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            engine.dispose()
        return
    import re
    login=args.login.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{1,80}",login):parser.error("Invalid login")
    password=getpass.getpass("Пароль администратора (от 12 символов): ")
    if len(password)<12 or len(password)>256:parser.error("Пароль: 12–256 символов")
    if password!=getpass.getpass("Повторите пароль: "):parser.error("Пароли не совпадают")
    engine=make_engine(database_url())
    try:
        migrate(engine);repo=Repository(sessions(engine))
        if repo.find_user(login):parser.error("Пользователь уже существует")
        repo.create_user({"login":login,"full_name":login,"role":"ADMIN","password_hash":Passwords().hash(password),"workshop_id":None,"active":True})
        print("Администратор создан:",login)
    finally:engine.dispose()

if __name__=="__main__":main()
