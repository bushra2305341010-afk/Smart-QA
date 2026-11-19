"""Security layer: runtime role grants, row-level security, audit hash chain, vector indexes.

docs/07-database.md §4-5, ADR-008. Hand-written: review any change with the sector 10 checklist.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "saq_app"

# Every table with a project_id column and the standard isolation policy.
SCOPED_TABLES = (
    "environment",
    "identity",
    "source",
    "chunk",
    "graph_version",
    "node",
    "edge",
    "node_citation",
    "plan",
    "segment",
    "test_case",
    "step",
    "run",
    "result",
    "evidence",
    "verdict",
    "bug",
    "regression_memory",
    "feedback",
    "project_rule",
    "lesson",
    "trained_model",
    "model_call",
    "replay_cache",
    "pipeline_state",
    "outbox",
)
DML_TABLES = ("app_user", "project", "membership", *SCOPED_TABLES)
RLS_TABLES = ("project", "membership", "audit_event", *SCOPED_TABLES)

CHAIN_FN = r"""
CREATE FUNCTION audit_event_chain() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    last_seq bigint;
    last_hash text;
BEGIN
    -- One writer per project at a time, so seq has no gaps or duplicates.
    PERFORM pg_advisory_xact_lock(hashtextextended('audit_event:' || NEW.project_id::text, 0));
    SELECT seq, hash INTO last_seq, last_hash
      FROM audit_event WHERE project_id = NEW.project_id ORDER BY seq DESC LIMIT 1;
    NEW.seq := COALESCE(last_seq, 0) + 1;
    NEW.prev_hash := COALESCE(last_hash, repeat('0', 64));
    NEW.created_at := clock_timestamp();
    -- Keep in sync with apps/api/db/audit.py canonical().
    NEW.hash := encode(sha256(convert_to(concat_ws('|',
        NEW.prev_hash, NEW.project_id::text, NEW.seq::text, NEW.actor, NEW.action, NEW.entity,
        NEW.payload::text,
        to_char(NEW.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
    ), 'UTF8')), 'hex');
    RETURN NEW;
END $$;
"""

IMMUTABLE_FN = """
CREATE FUNCTION audit_event_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_event is append-only' USING ERRCODE = 'insufficient_privilege';
END $$;
"""


def upgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END $$;
    """)
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(DML_TABLES)} TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON audit_event TO {APP_ROLE}")

    # NULLIF: once set in a session, an unset local GUC reads as '' rather than NULL.
    for name, setting in (
        ("app_current_project", "app.project_id"),
        ("app_current_user", "app.user_id"),
    ):
        op.execute(f"""
            CREATE FUNCTION {name}() RETURNS uuid LANGUAGE sql STABLE AS
            $$ SELECT NULLIF(current_setting('{setting}', true), '')::uuid $$
        """)

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    for table in (*SCOPED_TABLES, "audit_event"):
        op.execute(f"""
            CREATE POLICY project_isolation ON {table}
            USING (project_id = app_current_project())
            WITH CHECK (project_id = app_current_project())
        """)
    # A signed-in user may list the projects they belong to without a project scope (M08b).
    op.execute("""
        CREATE POLICY project_isolation ON membership
        USING (project_id = app_current_project() OR user_id = app_current_user())
        WITH CHECK (project_id = app_current_project())
    """)
    op.execute("""
        CREATE POLICY project_isolation ON project
        USING (id = app_current_project() OR id IN (
            SELECT project_id FROM membership WHERE user_id = app_current_user()))
        WITH CHECK (id = app_current_project())
    """)

    op.execute(CHAIN_FN)
    op.execute(IMMUTABLE_FN)
    op.execute("""
        CREATE TRIGGER audit_event_chain BEFORE INSERT ON audit_event
        FOR EACH ROW EXECUTE FUNCTION audit_event_chain()
    """)
    op.execute("""
        CREATE TRIGGER audit_event_no_change BEFORE UPDATE OR DELETE ON audit_event
        FOR EACH ROW EXECUTE FUNCTION audit_event_immutable()
    """)
    op.execute("""
        CREATE TRIGGER audit_event_no_truncate BEFORE TRUNCATE ON audit_event
        FOR EACH STATEMENT EXECUTE FUNCTION audit_event_immutable()
    """)

    for table in ("chunk", "lesson"):
        op.execute(
            f"CREATE INDEX ix_{table}_embedding_hnsw ON {table} "
            "USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    for table in ("chunk", "lesson"):
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_embedding_hnsw")
    for trigger in ("audit_event_chain", "audit_event_no_change", "audit_event_no_truncate"):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON audit_event")
    op.execute("DROP FUNCTION IF EXISTS audit_event_chain()")
    op.execute("DROP FUNCTION IF EXISTS audit_event_immutable()")
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS project_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS app_current_project()")
    op.execute("DROP FUNCTION IF EXISTS app_current_user()")
    op.execute(f"REVOKE ALL ON {', '.join((*DML_TABLES, 'audit_event'))} FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
