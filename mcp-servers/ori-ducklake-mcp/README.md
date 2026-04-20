# ori-ducklake-mcp

A **Model Context Protocol** server that exposes a **DuckLake v1.0** catalog as read-only SQL tools for LLM clients like Claude Desktop, Claude Code, or the MCP Inspector.

Built against:

- DuckLake spec **v1.0** ([announcement](https://ducklake.select/2026/04/13/ducklake-10/))
- DuckDB **≥ 1.5.2** (ships the `ducklake` extension for spec 1.0)
- MCP Python SDK **≥ 1.2** (FastMCP)

Default target catalog (overridable via `DUCKLAKE_URL`):

```
https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake
```

This is the SURF "Frozen DuckLake" / [public DuckLake on object storage](https://ducklake.select/docs/stable/duckdb/guides/public_ducklake_on_object_storage.html) pattern — a `.ducklake` file (a DuckDB database acting as the catalog) served over HTTPS, with Parquet data files in the same bucket. No credentials required for read access.

## Tools

| Tool | Data scanned | Purpose |
|---|---|---|
| `catalog_stats` | 🟢 none | **Start here.** File counts, sizes (GB), descriptions for every table — pure catalog metadata. |
| `ducklake_info` | 🟢 none | Catalog URL, DuckDB version, `ducklake_settings()` (extension version, data path). |
| `list_schemas` | 🟢 none | Schemas present in the catalog. |
| `list_tables` | 🟢 none | Tables & views, optionally filtered by schema. |
| `describe_table` | 🟡 row count | Columns, types, nullability, plus a `COUNT(*)` row count (slow on large tables). |
| `preview_table` | 🟡 one file | First N rows (default 20, max 200). |
| `query` | 🟡–🔴 varies | Read-only SQL (`SELECT` / `WITH` / `SHOW` / `DESCRIBE` / `EXPLAIN` / `SUMMARIZE`). |
| `list_snapshots` | 🟢 none | Enumerate DuckLake time-travel snapshots. |
| `table_files` | 🟢 none | Parquet data files backing a table (`ducklake_list_files`). |

## Install

```bash
cd mcp-servers/ori-ducklake-mcp
pip install -e .
```

## Run

```bash
python -m ori_ducklake_mcp
# or using the installed script:
ori-ducklake-mcp
```

> **Windows note:** `python -m ori_ducklake_mcp` is preferred over the script command because pip installs scripts to `%APPDATA%\Python\PythonXXX\Scripts` which may not be on `PATH`. The `python -m` form always works.

## Configuration

All via environment variables:

| Env var | Default | Notes |
|---|---|---|
| `DUCKLAKE_URL` | SURF Sprouts catalog (above) | The `.ducklake` URL, `s3://…`, or a local path. |
| `DUCKLAKE_ALIAS` | `lake` | SQL alias used in `ATTACH`. Shows up in fully-qualified names like `lake.openalex.works`. |
| `DUCKLAKE_ROW_LIMIT` | `1000` | Default safety `LIMIT` for unbounded SELECT statements. |
| `DUCKLAKE_MAX_ROW_LIMIT` | `10000` | Cap on the `limit` argument callers can pass to `query`. |
| `DUCKLAKE_MCP_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING`. Logs go to stderr. |
| `DUCKLAKE_MCP_TRANSPORT` | `stdio` | Set to `streamable-http` for HTTP mode. |

## Wire up to Claude Code

Project settings (`.claude/settings.json` in this repo):

```json
{
  "mcpServers": {
    "ori-ducklake-sprouts": {
      "command": "python",
      "args": ["-m", "ori_ducklake_mcp"],
      "type": "stdio",
      "env": {
        "DUCKLAKE_URL": "https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake",
        "DUCKLAKE_ALIAS": "lake"
      }
    }
  }
}
```

## Wire up to Claude Desktop

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ori-ducklake-sprouts": {
      "command": "python",
      "args": ["-m", "ori_ducklake_mcp"],
      "env": {
        "DUCKLAKE_URL": "https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake",
        "DUCKLAKE_ALIAS": "lake"
      }
    }
  }
}
```

Restart Claude Desktop; `ori-ducklake-sprouts` should appear in the tools list (🔨).

## Quick sanity check

```bash
python -c "
from ori_ducklake_mcp.server import catalog_stats, list_schemas, query
import json

# Free catalog overview — no data scanning
stats = catalog_stats()
print(f'Catalog: {stats[\"table_count\"]} tables, {stats[\"total_size_gb\"]} GB')
for t in stats['tables'][:5]:
    print(f'  {t[\"schema\"]}.{t[\"table\"]:<35} {t[\"size_gb\"]:>8} GB  ({t[\"file_count\"]} files)')

# Schema listing
print(list_schemas())

# SQL query
print(query('SELECT country_code, COUNT(*) FROM lake.openalex.institutions GROUP BY 1 ORDER BY 2 DESC', limit=5))
"
```

## Safety model

`query` enforces:

1. **Single statement only** — no `;`-separated batches.
2. **Allowed leading keywords**: `WITH`, `SELECT`, `SHOW`, `DESCRIBE`, `EXPLAIN`, `FROM`, `SUMMARIZE`.
3. **Forbidden keywords** anywhere: any DDL/DML (`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`, `ATTACH`, `DETACH`, `COPY`, `IMPORT`, `EXPORT`, `CHECKPOINT`, `VACUUM`, `PRAGMA`, `SET`, `CALL`, `INSTALL`, `LOAD`, `GRANT`, `REVOKE`, …).
4. **`READ_ONLY` attach** — even if the keyword check were bypassed, DuckDB would refuse mutations at the storage layer.

Comments (`--` and `/* */`) are stripped before these checks so keywords cannot be hidden inside them.

## Troubleshooting

**`ModuleNotFoundError: No module named 'ori_ducklake_mcp'`**
Run `pip install -e .` from the `mcp-servers/ori-ducklake-mcp` directory first.

**`Required module 'pytz' failed to import`**
`pytz` is in the dependencies; `pip install -e .` should pick it up. Run `pip install pytz` if missing.

**`Cannot open database "…" in read-only mode: database does not exist`**
The URL is wrong or not publicly accessible. Test with `curl -I <DUCKLAKE_URL>`.

**`Catalog version mismatch`**
You need DuckDB ≥ 1.5.2. Upgrade: `pip install -U "duckdb>=1.5.2"`.

## References

- DuckLake 1.0 release: https://ducklake.select/2026/04/13/ducklake-10/
- DuckLake connecting docs: https://ducklake.select/docs/stable/duckdb/usage/connecting
- Public DuckLake on object storage: https://ducklake.select/docs/stable/duckdb/guides/public_ducklake_on_object_storage
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
