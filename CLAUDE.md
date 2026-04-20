# SURF ORI Agentic Tools

This repository contains Claude agent skills and MCP servers for the SURF Open Research Information (ORI) stack.

## Repository layout

```
agentic-tools/
├── skills/                  # Claude skill packages (Markdown instructions)
│   ├── ducklake/            # Query the DuckLake catalog on SURF Object Store
│   ├── openaire-oaipmh/     # OAI-PMH harvesting from Dutch repositories
│   └── urn-nbn/             # URN:NBN resolution via Nationale Resolver
├── mcp-servers/             # MCP server source code
│   └── ori-ducklake-mcp/    # Read-only SQL access to DuckLake via DuckDB
└── scripts/                 # Shared Python utilities
```

## MCP servers

### ori-ducklake-mcp

Exposes the SURF "Sprouts" DuckLake catalog as read-only MCP tools:

| Tool | Purpose |
|---|---|
| `catalog_stats` | **Free overview** — file counts, sizes (GB), descriptions for all tables. No data scanning. |
| `ducklake_info` | Catalog metadata and DuckDB version |
| `list_schemas` | List schemas in the catalog |
| `list_tables` | List tables, optionally filtered by schema |
| `describe_table` | Column types, nullability, row count |
| `preview_table` | First N rows of a table |
| `query` | Run read-only SQL (SELECT/WITH/SHOW/DESCRIBE/EXPLAIN/SUMMARIZE) |
| `list_snapshots` | Time-travel snapshots |
| `table_files` | Parquet data files backing a table |

Install and run:

```bash
cd mcp-servers/ori-ducklake-mcp
pip install -e .
ducklake-mcp          # stdio transport (default)
```

Configure via env vars: `DUCKLAKE_URL`, `DUCKLAKE_ALIAS`, `DUCKLAKE_ROW_LIMIT`, `DUCKLAKE_MCP_LOG_LEVEL`.

## Skills

Install a skill into Claude Code:

```bash
npx skills add surf-ori/agentic-tools@ducklake
```

Skills live in `skills/<name>/SKILL.md`. Claude loads the description automatically; the full body is injected when triggered.

## License

EUPL-1.2 — see [LICENSE](LICENSE).
