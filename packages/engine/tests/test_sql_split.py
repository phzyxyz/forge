"""Statement splitter used by migrate_apply."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from phzyx.engine.migrate import migrate_apply
from phzyx.engine.sql_split import split_statements
from phzyx.schema.types import Dialect


@pytest.mark.unit
def test_check_constraint_semicolon_stays_one_statement() -> None:
    script = (
        "CREATE TABLE notes (\n  body TEXT CHECK (body <> 'a;b')\n);\n"
        "INSERT INTO notes VALUES ('x');\n"
    )
    assert split_statements(script) == [
        "CREATE TABLE notes (\n  body TEXT CHECK (body <> 'a;b')\n);",
        "INSERT INTO notes VALUES ('x');",
    ]


@pytest.mark.unit
def test_dollar_quoted_function_body_stays_one_statement() -> None:
    script = (
        "CREATE FUNCTION add_one(n integer) RETURNS integer AS $$\n"
        "BEGIN\n  n := n + 1;\n  RETURN n;\nEND;\n$$ LANGUAGE plpgsql;\n"
        "CREATE FUNCTION tagged() RETURNS text AS $body$ SELECT 'x;$$y' $body$ LANGUAGE sql;"
    )
    assert split_statements(script) == [
        "CREATE FUNCTION add_one(n integer) RETURNS integer AS $$\n"
        "BEGIN\n  n := n + 1;\n  RETURN n;\nEND;\n$$ LANGUAGE plpgsql;",
        "CREATE FUNCTION tagged() RETURNS text AS $body$ SELECT 'x;$$y' $body$ LANGUAGE sql;",
    ]


@pytest.mark.unit
def test_comments_and_quoted_identifiers_hide_semicolons() -> None:
    script = (
        "-- phzyx-engine upgrade (generated); header\n"
        "/* outer /* nested; */ still comment; */\n"
        'CREATE TABLE "we;ird" ("a""b;" TEXT); -- trailing; note\n'
        "SELECT E'it\\'s; fine', 'x''y;z';\n"
        "-- only a comment;\n"
    )
    assert split_statements(script) == [
        'CREATE TABLE "we;ird" ("a""b;" TEXT);',
        "SELECT E'it\\'s; fine', 'x''y;z';",
    ]


@pytest.mark.unit
def test_placeholders_do_not_open_dollar_bodies() -> None:
    assert split_statements("SELECT $1; SELECT a$b; SELECT 1") == [
        "SELECT $1;",
        "SELECT a$b;",
        "SELECT 1",
    ]


@pytest.mark.unit
def test_unterminated_quote_and_multibyte_identifiers_stay_one_statement() -> None:
    assert split_statements("SELECT 'unterminated") == ["SELECT 'unterminated"]
    assert split_statements("") == []
    assert split_statements("-- only\n/* still */\n") == []
    script = 'SELECT café FROM "naïve;name";'
    assert split_statements(script) == ['SELECT café FROM "naïve;name";']


@pytest.mark.unit
def test_migrate_apply_keeps_semicolon_inside_literal(tmp_path: Path) -> None:
    folder = tmp_path / "20260101010101_check"
    folder.mkdir()
    (folder / "upgrade.sql").write_text(
        "CREATE TABLE notes (\n  body TEXT CHECK (body <> 'a;b')\n);\n"
        "INSERT INTO notes (body) VALUES ('ok');\n",
        encoding="utf-8",
    )
    conn = sqlite3.connect(":memory:")
    applied = migrate_apply(conn, tmp_path, dialect=Dialect.SQLITE)
    assert applied == ["20260101010101_check"]
    assert conn.execute("SELECT body FROM notes").fetchone()[0] == "ok"
