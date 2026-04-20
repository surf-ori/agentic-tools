"""
Standalone helper to open a DuckDB connection to the DuckLake catalog.

Usage:
    python scripts/connect_ducklake.py
    python -c "from scripts.connect_ducklake import get_con; print(get_con().execute('SHOW TABLES').fetchall())"
"""

from __future__ import annotations

import os

import duckdb

DEFAULT_URL = (
    "https://objectstore.surf.nl/"
    "cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake"
)


def get_con(url: str | None = None, alias: str = "lake") -> duckdb.DuckDBPyConnection:
    url = url or os.environ.get("DUCKLAKE_URL", DEFAULT_URL)
    con = duckdb.connect(":memory:")
    con.execute("INSTALL ducklake; LOAD ducklake;")
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(
        f"ATTACH 'ducklake:{url}' AS {alias} "
        f"(READ_ONLY, CREATE_IF_NOT_EXISTS false);"
    )
    con.execute(f"USE {alias};")
    return con


if __name__ == "__main__":
    con = get_con()
    schemas = con.execute(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE catalog_name = 'lake' AND schema_name NOT IN ('information_schema','pg_catalog')"
    ).fetchall()
    print("Schemas:", [r[0] for r in schemas])
