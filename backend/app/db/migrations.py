"""Small idempotent schema upgrades for deployments created before Phase 6."""

from sqlalchemy import Engine, text


def migrate_audit_log_schema(engine: Engine) -> None:
    """Add Phase 6 audit columns without replacing existing records.

    Fresh databases receive these columns from SQLAlchemy metadata. PostgreSQL
    deployments created in Phase 4 are upgraded in place using idempotent DDL.
    """
    if engine.dialect.name != "postgresql":
        return

    statements = (
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_id VARCHAR(64)",
        "ALTER TABLE audit_logs "
        "ADD COLUMN IF NOT EXISTS sanitized_parameters JSONB",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS rules_evaluated JSONB",
        "ALTER TABLE audit_logs "
        "ADD COLUMN IF NOT EXISTS enforcement_mode VARCHAR(16)",
        "ALTER TABLE audit_logs "
        "ADD COLUMN IF NOT EXISTS latency_ms DOUBLE PRECISION",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_request_id "
        "ON audit_logs (request_id)",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_id VARCHAR(128)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
