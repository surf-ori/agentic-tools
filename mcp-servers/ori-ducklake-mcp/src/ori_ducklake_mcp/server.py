"""
DuckLake MCP server.

Exposes a public/frozen DuckLake catalog (a .ducklake DuckDB file served over
HTTPS from object storage) as a set of MCP tools for read-only SQL querying.

Target: DuckLake v1.0 spec (catalog version 1.0), DuckDB >= 1.5.2, mcp >= 1.2.

Default catalog (override via env DUCKLAKE_URL):
    https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any

import duckdb
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging: stderr only — stdout is reserved for MCP's JSON-RPC on stdio.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("DUCKLAKE_MCP_LOG_LEVEL", "INFO"),
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s ori-ducklake-mcp %(message)s",
)
log = logging.getLogger("ori-ducklake-mcp")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_DUCKLAKE_URL = (
    "https://objectstore.surf.nl/"
    "cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake"
)
DUCKLAKE_URL = os.environ.get("DUCKLAKE_URL", DEFAULT_DUCKLAKE_URL)
LAKE_ALIAS = os.environ.get("DUCKLAKE_ALIAS", "lake")
DEFAULT_ROW_LIMIT = int(os.environ.get("DUCKLAKE_ROW_LIMIT", "1000"))
MAX_ROW_LIMIT = int(os.environ.get("DUCKLAKE_MAX_ROW_LIMIT", "10000"))

# ---------------------------------------------------------------------------
# Connection: one in-memory DuckDB process, DuckLake attached read-only.
# ---------------------------------------------------------------------------
def _build_connection() -> duckdb.DuckDBPyConnection:
    """Create an in-memory DuckDB connection with the DuckLake attached RO."""
    log.info("Opening in-memory DuckDB; attaching DuckLake at %s", DUCKLAKE_URL)
    con = duckdb.connect(":memory:")

    # DuckDB auto-loads the extension on first ATTACH ... 'ducklake:...',
    # but being explicit makes failures easier to diagnose.
    con.execute("INSTALL ducklake;")
    con.execute("LOAD ducklake;")
    # httpfs is needed for the https:// catalog path and for any s3:// data
    # files the catalog might point at.
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")

    attach_sql = (
        f"ATTACH 'ducklake:{DUCKLAKE_URL}' AS {LAKE_ALIAS} "
        f"(READ_ONLY, CREATE_IF_NOT_EXISTS false);"
    )
    con.execute(attach_sql)
    con.execute(f"USE {LAKE_ALIAS};")
    log.info("DuckLake '%s' attached read-only.", LAKE_ALIAS)
    return con


# Single long-lived connection. DuckDB is thread-safe for a single
# connection's queries, and FastMCP will serialise tool calls well enough
# for a read-only analytics workload.
_con: duckdb.DuckDBPyConnection | None = None


def get_con() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        _con = _build_connection()
    return _con


# ---------------------------------------------------------------------------
# SQL safety: only allow read-only statements in `query`.
# ---------------------------------------------------------------------------
_FORBIDDEN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|MERGE|TRUNCATE|"
    r"CREATE|DROP|ALTER|REPLACE|"
    r"ATTACH|DETACH|COPY|EXPORT|IMPORT|"
    r"CHECKPOINT|VACUUM|PRAGMA|SET|CALL|"
    r"INSTALL|LOAD|GRANT|REVOKE"
    r")\b",
    re.IGNORECASE,
)

_ALLOWED_START = re.compile(
    r"^\s*(WITH|SELECT|SHOW|DESCRIBE|EXPLAIN|FROM|SUMMARIZE)\b",
    re.IGNORECASE,
)


def _strip_sql_comments(sql: str) -> str:
    # Remove /* ... */ block comments and -- line comments.
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _ensure_read_only(sql: str) -> None:
    stripped = _strip_sql_comments(sql).strip().rstrip(";")
    if ";" in stripped:
        raise ValueError("Multiple statements are not allowed in `query`.")
    if not _ALLOWED_START.match(stripped):
        raise ValueError(
            "Only SELECT / WITH / SHOW / DESCRIBE / EXPLAIN / SUMMARIZE "
            "statements are allowed."
        )
    if _FORBIDDEN.search(stripped):
        raise ValueError("Query contains a forbidden keyword for a read-only server.")


# ---------------------------------------------------------------------------
# Helpers: turn a DuckDB result into JSON-serialisable rows.
# ---------------------------------------------------------------------------
def _rows_to_dicts(rel: duckdb.DuckDBPyRelation) -> list[dict[str, Any]]:
    cols = rel.columns
    out: list[dict[str, Any]] = []
    for row in rel.fetchall():
        out.append({c: _to_jsonable(v) for c, v in zip(cols, row)})
    return out


def _to_jsonable(v: Any) -> Any:
    # DuckDB returns native Python types for most cases; coerce the rest.
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    # datetimes, Decimal, UUID, bytes, lists, dicts, ...
    try:
        import datetime
        import decimal
        import uuid

        if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
            return v.isoformat()
        if isinstance(v, decimal.Decimal):
            return str(v)
        if isinstance(v, uuid.UUID):
            return str(v)
        if isinstance(v, bytes):
            return v.hex()
    except Exception:  # pragma: no cover
        pass
    if isinstance(v, list):
        return [_to_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _to_jsonable(val) for k, val in v.items()}
    return str(v)


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "ori-ducklake-mcp",
    instructions=(
        "Read-only SQL access to a DuckLake catalog (DuckLake v1.0 spec) hosted "
        "on SURF Object Store. "
        "Start with `catalog_stats` to get a cheap overview of all tables (file counts, "
        "sizes in GB, descriptions) without scanning any data. "
        "Use `list_schemas` and `list_tables` to explore structure, "
        "`describe_table` for column metadata, and `query` to run SELECT SQL. "
        f"The catalog is attached as `{LAKE_ALIAS}`; fully-qualified table names "
        f"look like `{LAKE_ALIAS}.<schema>.<table>`."
    ),
)


@mcp.tool()
def ducklake_info() -> dict[str, Any]:
    """Return basic metadata about the attached DuckLake (URL, catalog version,
    extension version, data path, DuckDB version)."""
    con = get_con()
    info: dict[str, Any] = {
        "ducklake_url": DUCKLAKE_URL,
        "alias": LAKE_ALIAS,
        "duckdb_version": con.execute("SELECT version();").fetchone()[0],
    }
    # ducklake_settings() is part of the v1.0 extension and returns one row
    # per setting: (setting_name, value, scope).
    try:
        settings = _rows_to_dicts(
            con.query(f"FROM ducklake_settings('{LAKE_ALIAS}')")
        )
        info["settings"] = settings
    except duckdb.Error as e:
        info["settings_error"] = str(e)
    return info


@mcp.tool()
def list_schemas() -> list[dict[str, Any]]:
    """List schemas present in the DuckLake catalog."""
    con = get_con()
    rel = con.query(
        """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE catalog_name = ?
          AND schema_name NOT IN ('information_schema', 'pg_catalog')
        ORDER BY schema_name
        """,
        params=[LAKE_ALIAS],
    )
    return _rows_to_dicts(rel)


@mcp.tool()
def list_tables(schema: str | None = None) -> list[dict[str, Any]]:
    """List tables and views in the DuckLake. Optionally filter by schema."""
    con = get_con()
    sql = """
        SELECT table_schema AS schema,
               table_name   AS name,
               table_type   AS type
        FROM information_schema.tables
        WHERE table_catalog = ?
    """
    params: list[Any] = [LAKE_ALIAS]
    if schema:
        sql += " AND table_schema = ?"
        params.append(schema)
    sql += " ORDER BY table_schema, table_name"
    return _rows_to_dicts(con.query(sql, params=params))


@mcp.tool()
def describe_table(table: str, schema: str | None = None) -> dict[str, Any]:
    """Describe a table: columns, data types, nullability, comments.

    `table` may be a bare name (then `schema` is required or `main` is assumed)
    or a qualified `schema.table`.
    """
    con = get_con()
    if "." in table and schema is None:
        schema, table = table.split(".", 1)
    if schema is None:
        schema = "main"

    cols = _rows_to_dicts(
        con.query(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_catalog = ?
              AND table_schema = ?
              AND table_name = ?
            ORDER BY ordinal_position
            """,
            params=[LAKE_ALIAS, schema, table],
        )
    )
    if not cols:
        raise ValueError(f"Table {LAKE_ALIAS}.{schema}.{table} not found.")

    # Approximate row count from DuckLake's table stats (cheap, metadata-only).
    row_count: int | None = None
    try:
        r = con.execute(
            f'SELECT COUNT(*) FROM {LAKE_ALIAS}."{schema}"."{table}"'
        ).fetchone()
        row_count = int(r[0]) if r else None
    except duckdb.Error as e:
        log.warning("Could not count rows for %s.%s: %s", schema, table, e)

    return {
        "catalog": LAKE_ALIAS,
        "schema": schema,
        "table": table,
        "row_count": row_count,
        "columns": cols,
    }


@mcp.tool()
def preview_table(
    table: str, schema: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Return the first `limit` rows (default 20, max 200) of a table."""
    if "." in table and schema is None:
        schema, table = table.split(".", 1)
    if schema is None:
        schema = "main"
    limit = max(1, min(int(limit), 200))
    con = get_con()
    rel = con.query(f'FROM {LAKE_ALIAS}."{schema}"."{table}" LIMIT {limit}')
    return _rows_to_dicts(rel)


@mcp.tool()
def query(sql: str, limit: int | None = None) -> dict[str, Any]:
    """Run a read-only SQL query against the DuckLake.

    Only SELECT / WITH / SHOW / DESCRIBE / EXPLAIN / SUMMARIZE are accepted.
    If the statement is a SELECT/WITH and has no LIMIT clause, a safety LIMIT
    is wrapped around it. Use qualified names like `lake.schema.table` (the
    catalog alias is exposed via `ducklake_info`).
    """
    _ensure_read_only(sql)
    con = get_con()

    stripped = _strip_sql_comments(sql).strip().rstrip(";")
    effective_limit = (
        DEFAULT_ROW_LIMIT
        if limit is None
        else max(1, min(int(limit), MAX_ROW_LIMIT))
    )

    # Wrap SELECT/WITH in an outer LIMIT so an unbounded scan can't blow up
    # the client. EXPLAIN / SHOW / DESCRIBE / SUMMARIZE are left as-is.
    lead = stripped.split(None, 1)[0].upper()
    if lead in {"SELECT", "WITH", "FROM"} and not re.search(
        r"\blimit\b\s+\d", stripped, re.IGNORECASE
    ):
        wrapped = f"SELECT * FROM ({stripped}) AS _q LIMIT {effective_limit}"
    else:
        wrapped = stripped

    rel = con.query(wrapped)
    rows = _rows_to_dicts(rel)
    return {
        "columns": list(rel.columns),
        "row_count": len(rows),
        "limit_applied": effective_limit if lead in {"SELECT", "WITH", "FROM"} else None,
        "rows": rows,
    }


@mcp.tool()
def catalog_stats(schema: str | None = None) -> dict[str, Any]:
    """Return file-level statistics for every table in the DuckLake catalog.

    **No data files are scanned** — all figures come from catalog metadata
    (the .ducklake catalog file). This is the cheap first call to understand
    what is in the lake before issuing any SQL queries.

    Returns per-table:
    - ``file_count``     — number of Parquet files backing the table
    - ``size_bytes``     — total compressed size on object storage
    - ``size_gb``        — same, in GB (rounded to 3 dp)
    - ``description``    — table description from the catalog

    Also returns catalog-level totals (table_count, total_files, total_size_gb).

    Args:
        schema: Optional schema name to filter (e.g. 'openalex'). Omit for all.
    """
    con = get_con()

    # ---- table list + descriptions (catalog metadata, no data scan) ----------
    params: list[Any] = [LAKE_ALIAS]
    sql = """
        SELECT table_schema, table_name, COALESCE(TABLE_COMMENT, '') AS description
        FROM information_schema.tables
        WHERE table_catalog = ?
          AND table_schema NOT IN ('information_schema', 'pg_catalog', 'main')
    """
    if schema:
        sql += " AND table_schema = ?"
        params.append(schema)
    sql += " ORDER BY table_schema, table_name"
    tables = con.execute(sql, params).fetchall()

    # ---- file stats per table (ducklake_list_files = catalog metadata only) --
    rows: list[dict[str, Any]] = []
    total_bytes = 0
    total_files = 0

    for tbl_schema, tbl_name, description in tables:
        try:
            agg = con.execute(
                f"""
                SELECT COUNT(*)                          AS file_count,
                       COALESCE(SUM(data_file_size_bytes), 0) AS size_bytes
                FROM ducklake_list_files(
                    '{LAKE_ALIAS}', '{tbl_name}', schema => '{tbl_schema}'
                )
                """
            ).fetchone()
            fc = int(agg[0])
            sb = int(agg[1])
        except duckdb.Error as exc:
            log.warning("catalog_stats: could not get file stats for %s.%s: %s",
                        tbl_schema, tbl_name, exc)
            fc, sb = 0, 0

        total_files += fc
        total_bytes += sb
        rows.append({
            "schema":      tbl_schema,
            "table":       tbl_name,
            "description": description,
            "file_count":  fc,
            "size_bytes":  sb,
            "size_gb":     round(sb / 1e9, 3),
        })

    # Sort largest first
    rows.sort(key=lambda r: r["size_bytes"], reverse=True)

    return {
        "catalog_url":    DUCKLAKE_URL,
        "table_count":    len(rows),
        "total_files":    total_files,
        "total_size_bytes": total_bytes,
        "total_size_gb":  round(total_bytes / 1e9, 2),
        "tables":         rows,
    }


@mcp.tool()
def list_snapshots() -> list[dict[str, Any]]:
    """List DuckLake snapshots (for time-travel). Uses `ducklake_snapshots()`."""
    con = get_con()
    rel = con.query(f"FROM ducklake_snapshots('{LAKE_ALIAS}')")
    return _rows_to_dicts(rel)


@mcp.tool()
def table_files(
    table: str, schema: str | None = None
) -> list[dict[str, Any]]:
    """List the Parquet data files backing a DuckLake table (via
    `ducklake_list_files`). Useful for debugging and for understanding
    partitioning/compaction state."""
    if "." in table and schema is None:
        schema, table = table.split(".", 1)
    if schema is None:
        schema = "main"
    con = get_con()
    rel = con.query(
        f"FROM ducklake_list_files('{LAKE_ALIAS}', '{table}', schema => '{schema}')"
    )
    return _rows_to_dicts(rel)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    # Eager-attach so startup errors (bad URL, wrong catalog version, network
    # unreachable) surface on stderr immediately instead of on the first tool
    # call.
    try:
        get_con()
    except duckdb.Error as e:
        log.error("Failed to attach DuckLake: %s", e)
        # Don't hard-exit: some MCP clients still want to list tools even if
        # the backend is down. Tools will re-raise on use.
    transport = os.environ.get("DUCKLAKE_MCP_TRANSPORT", "stdio")
    log.info("Starting MCP server on transport=%s", transport)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
