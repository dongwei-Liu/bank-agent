"""Run tests against a separate PostgreSQL database; provisions only bank_agent_test."""

import os, sys, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend"))
from dotenv import dotenv_values
from core.config import get_settings
from sqlalchemy.engine import make_url
from psycopg import connect

url = make_url(get_settings().database_url)
admin = os.environ.get("POSTGRES_ADMIN_PASSWORD") or dotenv_values(ROOT / ".env").get(
    "POSTGRES_ADMIN_PASSWORD"
)
with connect(
    host=url.host,
    port=url.port or 5432,
    dbname="postgres",
    user="postgres",
    password=admin,
    autocommit=True,
) as db:
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname='bank_agent_test'")
        if not cur.fetchone():
            cur.execute("CREATE DATABASE bank_agent_test OWNER bank_agent")
env = {
    **os.environ,
    "BANK_TEST_DATABASE_URL": url.set(database="bank_agent_test").render_as_string(
        hide_password=False
    ),
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
}
raise SystemExit(
    subprocess.call(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration",
            "-q",
            "--tb=short",
            *sys.argv[1:],
        ],
        cwd=ROOT,
        env=env,
    )
)
