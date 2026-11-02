"""
MCP server for the Booking API production database (MariaDB).

Exposes tools to query, inspect and modify the database.
Destructive operations (UPDATE/DELETE/INSERT) require explicit confirmation
via a two-step flow: the agent must set `confirm: true`.

Environment variables (read from .env in the repo root):
  DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASS

Usage:
  python mcp/db_server.py
"""

import os
import re
import sys
import pymysql
import pymysql.cursors
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from mcp.server.mcpserver import MCPServer

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.isfile(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

DB_CONFIG = {
    "host": os.environ.get("MCP_DB_HOST", os.environ.get("DATABASE_HOST", "localhost")),
    "port": int(os.environ.get("MCP_DB_PORT", os.environ.get("DATABASE_PORT", "3306"))),
    "database": os.environ.get("MCP_DB_NAME", os.environ.get("DATABASE_NAME", "")),
    "user": os.environ.get("MCP_DB_USER", os.environ.get("DATABASE_USER", "")),
    "password": os.environ.get("MCP_DB_PASS", os.environ.get("DATABASE_PASS", "")),
    "charset": "utf8mb4",
    "connect_timeout": 10,
    "read_timeout": 30,
}

MAX_ROWS = 500
FORBIDDEN_PATTERNS = [
    re.compile(r"\b(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|RENAME)\b", re.IGNORECASE),
]

mcp = MCPServer(
    "booking-db",
    instructions=(
        "Database tools for the Booking API's MariaDB production database. "
        "Use `list_tables` and `describe_table` to explore the schema. "
        "Use `query` for SELECT statements. "
        "Use `execute` for INSERT/UPDATE/DELETE — these require `confirm=True`. "
        "DDL statements (DROP, ALTER, CREATE, TRUNCATE) are blocked."
    ),
)


def _serialize_value(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, timedelta):
        return str(val)
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, bytes):
        return val.hex()
    return val


def _serialize_row(row: dict) -> dict:
    return {k: _serialize_value(v) for k, v in row.items()}


@contextmanager
def _get_connection():
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    try:
        yield conn
    finally:
        conn.close()


def _check_forbidden(sql: str) -> str | None:
    for pat in FORBIDDEN_PATTERNS:
        m = pat.search(sql)
        if m:
            return f"Statement blocked: `{m.group()}` is not allowed. Only SELECT, INSERT, UPDATE and DELETE are permitted."
    return None


@mcp.tool()
def list_tables() -> str:
    """List all tables in the database with their row counts."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name, table_rows, table_comment "
                "FROM information_schema.tables "
                "WHERE table_schema = %s ORDER BY table_name",
                (DB_CONFIG["database"],),
            )
            rows = cur.fetchall()
    if not rows:
        return "No tables found."
    lines = []
    for r in rows:
        comment = f"  -- {r['table_comment']}" if r.get("table_comment") else ""
        lines.append(f"  {r['table_name']} (~{r['table_rows']} rows){comment}")
    return f"Tables in `{DB_CONFIG['database']}`:\n" + "\n".join(lines)


@mcp.tool()
def describe_table(table: str) -> str:
    """Show columns, types, keys and foreign keys for a table.

    Args:
        table: Table name to describe.
    """
    safe_table = re.sub(r"[^a-zA-Z0-9_]", "", table)
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SHOW FULL COLUMNS FROM `{safe_table}`")
            cols = cur.fetchall()
            cur.execute(f"SHOW INDEX FROM `{safe_table}`")
            indexes = cur.fetchall()
            cur.execute(
                "SELECT column_name, referenced_table_name, referenced_column_name "
                "FROM information_schema.key_column_usage "
                "WHERE table_schema = %s AND table_name = %s "
                "AND referenced_table_name IS NOT NULL",
                (DB_CONFIG["database"], safe_table),
            )
            fks = cur.fetchall()

    lines = [f"Table `{safe_table}`:\n", "Columns:"]
    for c in cols:
        extra = []
        if c.get("Key") == "PRI":
            extra.append("PK")
        if c.get("Key") == "UNI":
            extra.append("UNIQUE")
        if c.get("Extra"):
            extra.append(c["Extra"])
        nullable = "NULL" if c.get("Null") == "YES" else "NOT NULL"
        default = f" default={c['Default']}" if c.get("Default") is not None else ""
        tags = f" [{', '.join(extra)}]" if extra else ""
        lines.append(f"  {c['Field']}: {c['Type']} {nullable}{default}{tags}")

    if fks:
        lines.append("\nForeign keys:")
        for fk in fks:
            lines.append(f"  {fk['column_name']} -> {fk['referenced_table_name']}.{fk['referenced_column_name']}")

    pk_cols = [i["Column_name"] for i in indexes if i.get("Key_name") == "PRIMARY"]
    if pk_cols:
        lines.append(f"\nPrimary key: ({', '.join(pk_cols)})")

    return "\n".join(lines)


@mcp.tool()
def query(sql: str, params: list | None = None, limit: int = 100) -> str:
    """Execute a read-only SQL query (SELECT only).

    Args:
        sql: A SELECT statement. Other statement types are rejected.
        params: Optional list of parameter values for %s placeholders.
        limit: Max rows to return (default 100, max 500).
    """
    stripped = sql.strip().rstrip(";")
    if not re.match(r"^\s*SELECT\b", stripped, re.IGNORECASE):
        # Also allow SHOW and DESCRIBE/EXPLAIN for convenience
        if not re.match(r"^\s*(SHOW|DESCRIBE|EXPLAIN)\b", stripped, re.IGNORECASE):
            return "Error: only SELECT, SHOW, DESCRIBE and EXPLAIN statements are allowed in `query`. Use `execute` for writes."

    err = _check_forbidden(stripped)
    if err:
        return err

    limit = min(max(1, limit), MAX_ROWS)
    if not re.search(r"\bLIMIT\b", stripped, re.IGNORECASE):
        stripped += f" LIMIT {limit}"

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(stripped, tuple(params) if params else None)
            rows = cur.fetchall()

    if not rows:
        return "Query returned 0 rows."

    serialized = [_serialize_row(r) for r in rows]
    header = list(serialized[0].keys())
    lines = [" | ".join(header), " | ".join("---" for _ in header)]
    for r in serialized:
        lines.append(" | ".join(str(r.get(h, "")) for h in header))

    result = "\n".join(lines)
    suffix = f"\n\n({len(rows)} row{'s' if len(rows) != 1 else ''})"
    return result + suffix


@mcp.tool()
def count(table: str, where: str | None = None, params: list | None = None) -> str:
    """Count rows in a table, optionally filtered by a WHERE clause.

    Args:
        table: Table name.
        where: Optional WHERE clause (without the WHERE keyword). E.g. "status = 'C'"
        params: Optional list of parameter values for %s placeholders in the WHERE clause.
    """
    safe_table = re.sub(r"[^a-zA-Z0-9_]", "", table)
    sql = f"SELECT COUNT(*) as cnt FROM `{safe_table}`"
    if where:
        err = _check_forbidden(where)
        if err:
            return err
        sql += f" WHERE {where}"

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params) if params else None)
            row = cur.fetchone()

    return f"`{safe_table}`: {row['cnt']} rows" + (f" (where {where})" if where else "")


@mcp.tool()
def execute(sql: str, params: list | None = None, confirm: bool = False) -> str:
    """Execute a write statement (INSERT, UPDATE, DELETE).

    IMPORTANT: This modifies production data. The `confirm` parameter must be set
    to `true` to actually execute. Call first with `confirm=false` to preview what
    will run, then with `confirm=true` after the user approves.

    Args:
        sql: An INSERT, UPDATE or DELETE statement.
        params: Optional list of parameter values for %s placeholders.
        confirm: Must be true to execute. When false, the statement is validated
                 but not run — use this to show the user what will execute.
    """
    stripped = sql.strip().rstrip(";")

    if re.match(r"^\s*SELECT\b", stripped, re.IGNORECASE):
        return "Error: use the `query` tool for SELECT statements."

    err = _check_forbidden(stripped)
    if err:
        return err

    if not re.match(r"^\s*(INSERT|UPDATE|DELETE)\b", stripped, re.IGNORECASE):
        return "Error: only INSERT, UPDATE and DELETE are allowed. DDL (CREATE, ALTER, DROP, TRUNCATE) is blocked."

    is_update_or_delete = re.match(r"^\s*(UPDATE|DELETE)\b", stripped, re.IGNORECASE)
    if is_update_or_delete and not re.search(r"\bWHERE\b", stripped, re.IGNORECASE):
        return "Error: UPDATE and DELETE without a WHERE clause are blocked. Add a WHERE clause to target specific rows."

    if not confirm:
        param_str = f"\n  params: {params}" if params else ""
        return (
            f"**Preview** (not executed yet):\n"
            f"```sql\n{stripped}\n```{param_str}\n\n"
            f"To execute, call `execute` again with `confirm=true`."
        )

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(stripped, tuple(params) if params else None)
            affected = cur.rowcount
        conn.commit()

    return f"Executed successfully. Rows affected: {affected}"


@mcp.tool()
def show_databases() -> str:
    """List all databases the connected user can see (for orientation)."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW DATABASES")
            rows = cur.fetchall()
    return "Databases:\n" + "\n".join(f"  {r['Database']}" for r in rows)


if __name__ == "__main__":
    mcp.run(transport="stdio")
