"""Interactive account provisioning; never accept passwords in argv."""
import argparse
import getpass
import sys
from .infrastructure.database import database_url, make_engine, migrate, sessions
from .infrastructure.repository import Repository
from .infrastructure.passwords import Passwords

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["create-admin", "seed-demo", "seed-pump-demo", "bootstrap-local"])
    parser.add_argument("--login",default="niyaz")
    args=parser.parse_args()
    if args.command == "bootstrap-local":
        import json
        import os
        from .infrastructure.demo import seed_pump_demo
        if os.getenv("LOCAL_DEMO_ENABLED") != "true":
            parser.error("bootstrap-local разрешён только при LOCAL_DEMO_ENABLED=true")
        try:
            raw = sys.stdin.read(4097)
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
            print(json.dumps(result, ensure_ascii=False))
        except ValueError as exc:
            parser.error(str(exc))
        finally:
            engine.dispose()
        return
    if args.command in ("seed-demo", "seed-pump-demo"):
        import json
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
