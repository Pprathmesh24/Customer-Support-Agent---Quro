"""
Runs all SQL migration files in supabase/migrations/ in order against the
Supabase PostgreSQL database.

Usage:
    uv run scripts/run_migrations.py <db_password>

The project ref is read from SUPABASE_URL in .env.
"""
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parents[2] / ".env")

def get_conn_params(password: str) -> dict:
    supabase_url = os.environ["SUPABASE_URL"]
    project_ref = supabase_url.replace("https://", "").split(".")[0]
    return {
        "host": f"db.{project_ref}.supabase.co",
        "port": 5432,
        "dbname": "postgres",
        "user": "postgres",
        "password": password,
        "sslmode": "require",
    }

def run(password: str) -> None:
    migrations_dir = Path(__file__).parents[2] / "supabase" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("No migration files found.")
        return

    conn = psycopg2.connect(**get_conn_params(password))
    conn.autocommit = True
    cursor = conn.cursor()

    for path in migration_files:
        print(f"Running {path.name} ...", end=" ")
        sql = path.read_text()
        try:
            cursor.execute(sql)
            print("OK")
        except psycopg2.errors.DuplicateTable as e:
            print(f"SKIPPED (already exists: {e.pgerror.strip()})")
        except psycopg2.errors.DuplicateObject as e:
            print(f"SKIPPED (already exists: {e.pgerror.strip()})")
        except Exception as e:
            print(f"FAILED\n  {e}")
            conn.close()
            sys.exit(1)

    conn.close()
    print("\nAll migrations complete.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run scripts/run_migrations.py <db_password>")
        sys.exit(1)
    run(sys.argv[1])
