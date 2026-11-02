from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from models import Base


def migration_config():
    return Config(str(Path(__file__).resolve().parents[2] / "apps/backend/alembic.ini"))


def migrate(engine, config, operation, revision):
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        getattr(command, operation)(config, revision)
    config.attributes.pop("connection", None)


def test_initial_migration_roundtrip_and_model_parity(bank, monkeypatch):
    import core.config

    monkeypatch.setattr(core.config, "get_settings", lambda: bank["settings"])
    engine = bank["engine"]
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    config = migration_config()
    migrate(engine, config, "upgrade", "head")
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert (
            compare_metadata(MigrationContext.configure(connection), Base.metadata)
            == []
        )
    migrate(engine, config, "downgrade", "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    migrate(engine, config, "upgrade", "head")
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())


def test_legacy_risk_assessments_remain_readable_but_not_purchase_eligible(
    bank, monkeypatch
):
    import core.config

    monkeypatch.setattr(core.config, "get_settings", lambda: bank["settings"])
    engine = bank["engine"]
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    config = migration_config()
    migrate(engine, config, "upgrade", "0001")
    with engine.begin() as connection:
        connection.execute(
            text(
                """INSERT INTO users
                (id, username, password_hash, client_id, tenant, is_admin, active,
                 otp_locked_until, login_failures, login_locked_until)
                VALUES
                ('legacy-user', 'legacy', 'hash', 999, 'default', false, true,
                 null, 0, null)"""
            )
        )
        connection.execute(
            text(
                """INSERT INTO risk_assessments
                (id, user_id, answers, score, level, version, created_at, expires_at)
                VALUES
                ('legacy-risk', 'legacy-user', '[5,5,5,5,5]', 25, 5,
                 'demo-v1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""
            )
        )
    migrate(engine, config, "upgrade", "head")
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT purpose, used_at, action_id FROM risk_assessments "
                "WHERE id='legacy-risk'"
            )
        ).one()
    assert tuple(row) == ("legacy", None, None)
    migrate(engine, config, "downgrade", "base")
