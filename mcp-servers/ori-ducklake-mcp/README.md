# ducklake-mcp

A small **Model Context Protocol** server that exposes a **DuckLake v1.0** catalog as read-only SQL tools for LLM clients like Claude Desktop, Claude Code, or the MCP Inspector.

Built against:

- DuckLake spec **v1.0** ([announcement](https://ducklake.select/2026/04/13/ducklake-10/))
- DuckDB **1.5.2** (ships the `ducklake` extension for spec 1.0)
- MCP Python SDK **≥ 1.2** (FastMCP)

Default target catalog (overridable):

```
https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake
```

This is the SURF "Frozen DuckLake" / [public DuckLake on object storage](https://ducklake.select/docs/stable/duckdb/guides/public_ducklake_on_object_storage.html) pattern — a `.ducklake` file (a DuckDB database acting as the catalog) served over HTTPS, pointing at Parquet data files in the same bucket. No credentials required.

## What the server exposes

| Tool | Purpose |
|---|---|
| `ducklake_info` | Catalog URL, DuckDB version, `ducklake_settings()` (catalog type, extension version, data path). |
| `list_schemas` | Schemas present in the catalog. |
| `list_tables` | Tables & views, optionally filtered by schema. |
| `describe_table` | Columns, types, nullability, plus a row count. |
| `preview_table` | First N rows (default 20, max 200). |
| `query` | Run read-only SQL (`SELECT` / `WITH` / `SHOW` / `DESCRIBE` / `EXPLAIN` / `SUMMARIZE`). Blocks writes and multi-statement SQL; wraps unlimited SELECTs in a safety `LIMIT`. |
| `list_snapshots` | Enumerate DuckLake time-travel snapshots (`ducklake_snapshots`). |
| `table_files` | Parquet data files backing a table (`ducklake_list_files`). |

## Install

```bash
# From the project root
uv venv
. .venv/bin/activate            # on Windows: .venv\Scripts\activate
uv pip install -e .
```

Or with plain pip:

```bash
pip install -e .
```

## Run

As a stdio MCP server (what Claude Desktop / Code / Cowork expect):

```bash
ducklake-mcp
# or
python -m ducklake_mcp
```

## Configuration

All via environment variables:

| Env var | Default | Notes |
|---|---|---|
| `DUCKLAKE_URL` | SURF sprouts catalog (above) | The `.ducklake` URL, `s3://...`, or a local path. |
| `DUCKLAKE_ALIAS` | `lake` | Alias used in `ATTACH`. Shows up in fully-qualified names, e.g. `lake.openalex.works`. |
| `DUCKLAKE_ROW_LIMIT` | `1000` | Default safety LIMIT when a SELECT is unbounded. |
| `DUCKLAKE_MAX_ROW_LIMIT` | `10000` | Cap on what a caller can pass via the `limit` argument. |
| `DUCKLAKE_MCP_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING`. Logs go to stderr. |
| `DUCKLAKE_MCP_TRANSPORT` | `stdio` | Set to `streamable-http` for HTTP mode. |

## Wire it up to Claude Desktop

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ducklake-sprouts": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ducklake-mcp", "run", "ducklake-mcp"],
      "env": {
        "DUCKLAKE_URL": "https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake",
        "DUCKLAKE_ALIAS": "lake"
      }
    }
  }
}
```

Restart Claude Desktop and the `ducklake-sprouts` server should appear in the tools list.

### Windows note

The execution-policy issue that blocks `npx`/`npm` in PowerShell doesn't affect this server — it's pure Python. If you're using `cmd` as a workaround, the above `uv` invocation works fine there.

## Quick sanity check

```bash
python -c "
from ducklake_mcp.server import list_schemas, query
print(list_schemas())
print(query('SELECT country_code, COUNT(*) FROM lake.openalex.institutions GROUP BY 1 ORDER BY 2 DESC', limit=5))
"
```

## Safety model

`query` enforces:

1. **Single statement only** — no `;`-separated batches.
2. **Allowed leading keywords**: `WITH`, `SELECT`, `SHOW`, `DESCRIBE`, `EXPLAIN`, `FROM`, `SUMMARIZE`.
3. **Forbidden keywords** anywhere: any DDL/DML (`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`, `ATTACH`, `DETACH`, `COPY`, `IMPORT`, `EXPORT`, `CHECKPOINT`, `VACUUM`, `PRAGMA`, `SET`, `CALL`, `INSTALL`, `LOAD`, `GRANT`, `REVOKE`, …).
4. **`READ_ONLY` attach** — even if the keyword check were bypassed, DuckDB would refuse mutations at the storage layer.

Comments (`--` and `/* */`) are stripped before these checks so you can't hide keywords behind them.

## Troubleshooting

**`Required module 'pytz' failed to import`**
DuckDB needs `pytz` to return `TIMESTAMPTZ` values (used by `ducklake_snapshots`). `pytz` is in the dependencies; `pip install -e .` should pick it up.

**`Cannot open database "..." in read-only mode: database does not exist`**
The URL is wrong or the catalog isn't publicly accessible. Try fetching it with `curl -I` first.

**`Catalog version mismatch`**
You're on a pre-1.0 DuckLake extension. Upgrade: `pip install -U "duckdb>=1.5.2"`.

## References

- DuckLake 1.0 release: https://ducklake.select/2026/04/13/ducklake-10/
- DuckLake connecting docs: https://ducklake.select/docs/stable/duckdb/usage/connecting
- Public DuckLake on object storage: https://ducklake.select/docs/stable/duckdb/guides/public_ducklake_on_object_storage
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
