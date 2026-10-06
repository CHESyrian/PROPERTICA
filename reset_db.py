#!/usr/bin/env python3
"""
PROPERTICA — reset database and migrations.

What this script does:
  1. Drop and recreate the PostgreSQL database (propertica_db from .env)
  2. Delete all migration files (keeps migrations/__init__.py)
  3. Regenerate migrations and apply them (migrate)
  4. Create superuser: owner@propertica.com / password
  5. Optionally run seed_data if available

Usage:
  python reset_db.py

Requires:
  - .env with POSTGRES_* variables
  - PostgreSQL reachable with a user that can CREATE/DROP databases
  - Project dependencies installed (Django, psycopg, python-dotenv)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    print("python-dotenv not installed; relying on existing environment variables.")

DB_NAME = os.environ.get("POSTGRES_DB", "propertica_db")
DB_USER = os.environ.get("POSTGRES_USER", "propertica")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", "5432")

# Apps that own migration packages in this project
PROJECT_APPS = ("accounts", "listings", "messaging", "search_app", "core")

SUPERUSER_EMAIL = "owner@propertica.com"
SUPERUSER_PASSWORD = "password"


def step(msg: str) -> None:
    print(f"\n==> {msg}")


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"    $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, cwd=str(BASE_DIR))


def drop_and_recreate_database() -> None:
    """Drop and recreate PostgreSQL database using psycopg."""
    step(f"Drop & recreate PostgreSQL database '{DB_NAME}'")

    try:
        import psycopg
    except ImportError:
        print("ERROR: psycopg is not installed. Run: pip install 'psycopg[binary]'")
        sys.exit(1)

    # Connect to the maintenance database to DROP/CREATE the app DB
    conninfo = (
        f"host={DB_HOST} port={DB_PORT} dbname=postgres "
        f"user={DB_USER} password={DB_PASSWORD}"
    )

    try:
        with psycopg.connect(conninfo, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Terminate open connections to the target DB
                cur.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                    """,
                    (DB_NAME,),
                )
                cur.execute(f'DROP DATABASE IF EXISTS "{DB_NAME}"')
                print(f"    Dropped database '{DB_NAME}' (if it existed)")
                cur.execute(f'CREATE DATABASE "{DB_NAME}" OWNER "{DB_USER}"')
                print(f"    Created database '{DB_NAME}' owned by '{DB_USER}'")
    except Exception as exc:
        print(f"ERROR connecting to PostgreSQL / recreating DB:\n  {exc}")
        print(
            "\nHints:\n"
            f"  - Is PostgreSQL running on {DB_HOST}:{DB_PORT}?\n"
            f"  - Can user '{DB_USER}' connect to database 'postgres' and CREATE DATABASE?\n"
            "  - Check POSTGRES_* values in .env"
        )
        sys.exit(1)


def remove_migration_files() -> None:
    step("Remove migration files (keep __init__.py)")

    for app in PROJECT_APPS:
        migrations_dir = BASE_DIR / app / "migrations"
        if not migrations_dir.is_dir():
            migrations_dir.mkdir(parents=True, exist_ok=True)
            (migrations_dir / "__init__.py").touch()
            print(f"    {app}/migrations/ — created empty package")
            continue

        removed = 0
        for path in migrations_dir.iterdir():
            if path.name == "__init__.py":
                continue
            if path.name == "__pycache__" and path.is_dir():
                shutil.rmtree(path)
                removed += 1
                continue
            if path.suffix == ".py" and path.name != "__init__.py":
                path.unlink()
                removed += 1
        # Ensure __init__.py exists
        init = migrations_dir / "__init__.py"
        if not init.exists():
            init.touch()
        print(f"    {app}/migrations/ — removed {removed} file(s)/dirs")


def regenerate_and_migrate() -> None:
    step("Regenerate migrations")
    run([sys.executable, "manage.py", "makemigrations", *PROJECT_APPS])

    step("Apply migrations")
    run([sys.executable, "manage.py", "migrate"])


def create_superuser() -> None:
    step(f"Create superuser ({SUPERUSER_EMAIL})")

    # Non-interactive via Django shell so custom Account manager is used
    script = f"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from accounts.models import Account, AccountType

email = {SUPERUSER_EMAIL!r}
password = {SUPERUSER_PASSWORD!r}

if Account.objects.filter(email=email).exists():
    u = Account.objects.get(email=email)
    u.set_password(password)
    u.is_staff = True
    u.is_superuser = True
    u.is_active = True
    u.save()
    print(f"Updated existing superuser: {{u.email}} ({{u.username}})")
else:
    u = Account.objects.create_superuser(
        email=email,
        password=password,
        account_type=AccountType.PERSONAL,
    )
    print(f"Created superuser: {{u.email}} ({{u.username}})")
"""
    result = subprocess.run(
        [sys.executable, "manage.py", "shell", "-c", script],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        print("ERROR: failed to create superuser")
        sys.exit(1)
    # Print relevant output lines
    for line in (result.stdout or "").splitlines():
        if line.strip():
            print(f"    {line}")


def maybe_seed() -> None:
    seed = BASE_DIR / "listings" / "management" / "commands" / "seed_data.py"
    if seed.exists():
        step("Run seed_data (demo categories & sample listings)")
        run([sys.executable, "manage.py", "seed_data"], check=False)


def main() -> None:
    print("PROPERTICA database reset")
    print(f"  Database : {DB_NAME}")
    print(f"  Host     : {DB_HOST}:{DB_PORT}")
    print(f"  User     : {DB_USER}")

    drop_and_recreate_database()
    remove_migration_files()
    regenerate_and_migrate()
    create_superuser()
    maybe_seed()

    print("\nDone.")
    print(f"  Superuser email    : {SUPERUSER_EMAIL}")
    print(f"  Superuser password : {SUPERUSER_PASSWORD}")
    print("  Admin               : http://127.0.0.1:8000/admin/")


if __name__ == "__main__":
    main()
