"""Phzyx schema engine — introspect, diff, push, migrate."""

from phzyx.engine.apply_ops import apply_plan, archive_column_name, render_op
from phzyx.engine.capabilities import (
    CAP_COMPOSITE_PK,
    CAP_JSON_TYPE,
    CapabilitySet,
    Version,
    capabilities_for,
    parse_version,
)
from phzyx.engine.config import EngineConfig, load_config
from phzyx.engine.connection import connect
from phzyx.engine.diff import diff_manifests
from phzyx.engine.dsn import DatabaseURL, parse_database_url
from phzyx.engine.errors import ConnectionError, EngineError, MigrationError, PolicyError
from phzyx.engine.introspect_mssql import MssqlAdapter
from phzyx.engine.introspect_mysql import MySQLAdapter
from phzyx.engine.introspect_postgres import PostgresAdapter
from phzyx.engine.introspect_sqlite import SQLiteAdapter
from phzyx.engine.lint import (
    LintFinding,
    LintResult,
    assert_lint_clean,
    lint_exit_code,
    lint_plan,
)
from phzyx.engine.migrate import (
    HISTORY_TABLE,
    MigrateStatus,
    MigrationFile,
    create_migration,
    ensure_history_table,
    list_migration_files,
    migrate_apply,
    migrate_status,
    render_downgrade_sql,
    render_downgrade_stub,
    render_upgrade_sql,
)
from phzyx.engine.ops import SchemaOp
from phzyx.engine.plan import SchemaPlan, build_plan
from phzyx.engine.policy import DEFAULT_POLICY, SchemaPolicy
from phzyx.engine.push import PushResult, is_production_like_env, push_schema
from phzyx.engine.tui_push import confirm_plan, push_with_tui, render_plan_view

# The scaffold and the qualification both looked these up on phzyx.engine.
# The implementation stays in phzyx.orm. These names are the same objects.
from phzyx.orm import (
    AsyncEngine,
    AsyncSession,
    Engine,
    Session,
    create_async_engine,
    create_async_session,
    create_engine,
    create_session,
)

# phzyx.engine.create_sync_engine was the name the scaffold guessed.
create_sync_engine = create_engine

__version__ = "0.1.10"

__all__ = [
    "CAP_COMPOSITE_PK",
    "CAP_JSON_TYPE",
    "DEFAULT_POLICY",
    "HISTORY_TABLE",
    "CapabilitySet",
    "ConnectionError",
    "DatabaseURL",
    "EngineConfig",
    "EngineError",
    "LintFinding",
    "LintResult",
    "MigrationError",
    "MigrationFile",
    "MigrateStatus",
    "MssqlAdapter",
    "MySQLAdapter",
    "PostgresAdapter",
    "PolicyError",
    "PushResult",
    "SQLiteAdapter",
    "SchemaOp",
    "SchemaPlan",
    "SchemaPolicy",
    "Version",
    "__version__",
    "apply_plan",
    "archive_column_name",
    "assert_lint_clean",
    "build_plan",
    "capabilities_for",
    "confirm_plan",
    "AsyncEngine",
    "AsyncSession",
    "Engine",
    "Session",
    "connect",
    "create_async_engine",
    "create_async_session",
    "create_engine",
    "create_migration",
    "create_session",
    "create_sync_engine",
    "diff_manifests",
    "ensure_history_table",
    "is_production_like_env",
    "lint_exit_code",
    "lint_plan",
    "list_migration_files",
    "load_config",
    "migrate_apply",
    "migrate_status",
    "parse_database_url",
    "parse_version",
    "push_schema",
    "push_with_tui",
    "render_downgrade_sql",
    "render_downgrade_stub",
    "render_op",
    "render_plan_view",
    "render_upgrade_sql",
]
