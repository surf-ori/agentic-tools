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

## Run without cloning

`uvx` (bundled with `uv`) can run the server straight from this GitHub repo — no
`git clone`, no local checkout:

```bash
uvx --from "git+https://github.com/surf-ori/agentic-tools.git#subdirectory=mcp-servers/ori-ducklake-mcp" ori-ducklake-mcp
```

The first run downloads and builds (~15-20s); `uv` caches it after that. Wire it
into Claude Desktop/Code the same way as the [sections below](#wire-up-to-claude-code),
just swap the `command`/`args` for:

```json
{
  "command": "uvx",
  "args": [
    "--from", "git+https://github.com/surf-ori/agentic-tools.git#subdirectory=mcp-servers/ori-ducklake-mcp",
    "ori-ducklake-mcp"
  ]
}
```

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
| `DUCKLAKE_MCP_HOST` | `0.0.0.0` | Bind address in `streamable-http` mode. Ignored for `stdio`. |
| `DUCKLAKE_MCP_PORT` | `8000` | Bind port in `streamable-http` mode. Ignored for `stdio`. |

## Wire up to Claude Code

Project settings (`.claude/settings.json` in this repo):

```json
{
  "mcpServers": {
    "ori-ducklake": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/agentic-tools/mcp-servers/ori-ducklake-mcp",
        "run", "ori-ducklake-mcp"
      ],
      "type": "stdio",
      "env": {
        "DUCKLAKE_URL": "https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake",
        "DUCKLAKE_ALIAS": "lake"
      }
    }
  }
}
```

> **Why `uv run`?** `uv` reads `uv.lock` in the project directory and runs the server in an isolated, reproducible virtual environment — no global `pip install` needed. Replace `/path/to/agentic-tools` with your actual checkout path.

## Wire up to Claude Desktop

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ori-ducklake": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/agentic-tools/mcp-servers/ori-ducklake-mcp",
        "run", "ori-ducklake-mcp"
      ],
      "env": {
        "DUCKLAKE_URL": "https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake",
        "DUCKLAKE_ALIAS": "lake"
      }
    }
  }
}
```

Restart Claude Desktop; `ori-ducklake` should appear in the tools list (🔨).

## Run with Docker

```bash
docker compose up -d --build
```

Builds the image from the included `Dockerfile` (which runs `uv sync --frozen` to
install the exact versions from `uv.lock`) and starts it listening on
`streamable-http` at `http://localhost:8000/mcp`. `restart: unless-stopped` in
`docker-compose.yml` means it survives reboots and crash-restarts.

Verify it's up:

```bash
curl -i http://localhost:8000/mcp
```

A `406` response confirms the server is running and speaking MCP (a full
handshake needs a real MCP client, not `curl`).

## Deploy — SURF VM (or any Docker host)

Same image as above, just on a machine other than your laptop:

```bash
git clone https://github.com/surf-ori/agentic-tools.git
cd agentic-tools/mcp-servers/ori-ducklake-mcp
docker compose up -d --build
```

The server listens on `http://<VM-IP>:8000/mcp`. Make sure the VM's
firewall/security group allows inbound traffic on port 8000 from wherever it
needs to be reached.

**Updating**, once the repo has new commits:

```bash
cd agentic-tools && git pull
cd mcp-servers/ori-ducklake-mcp && docker compose up -d --build
```

**Note**: this is plain HTTP (no TLS) at a bare IP. Fine for this server — it's
strictly read-only against a public dataset, so there's nothing sensitive in
transit — but don't reuse this setup for anything that isn't already public and
read-only.

## Deploy — public Render instance

This repo includes a `render.yaml` Blueprint at the repo root, so Render can
deploy it with no manual configuration:

1. In the Render dashboard: **New → Blueprint**, connect the `surf-ori/agentic-tools`
   GitHub repo.
2. Render finds `render.yaml`, shows the one service it defines — click **Apply**.
3. Render builds the `Dockerfile` and assigns an HTTPS URL, e.g.
   `https://ori-ducklake-mcp.onrender.com`.

Every push to `main` auto-redeploys from then on — that's Render's native GitHub
integration, nothing custom to maintain.

Verify: `curl -i https://<your-app>.onrender.com/mcp` — expect `406`, same as the
Docker check above.

**Free-tier caveats**:
- The service sleeps after ~15 min idle; the next request wakes it in ~30s.
- ~512MB RAM. Fine for `catalog_stats`, `list_*`, `describe_table`, and most
  `query` calls, but an aggregation across the full 552GB `openalex.works` table
  could exceed it. For heavier use, point clients at a self-hosted instance
  instead (see the SURF VM section above).

## Connecting from LibreChat / EduGenAI

LibreChat connects to remote MCP servers via `librechat.yaml`, no plugin needed:

```yaml
mcpServers:
  ori-ducklake:
    type: streamable-http
    url: http://<SURF-VM-IP>:8000/mcp
    chatMenu: true
```

`type: streamable-http` must be explicit — LibreChat defaults to the older `sse`
transport for a bare `http(s)://` URL, which this server doesn't speak, and the
connection will silently fail to work if left implicit. Swap the `url` for the
public Render instance's URL to use that one instead.

## Connecting from SURF AI Chat (aichat.surf.nl)

SURF AI Chat lets you register an MCP server as an **extension** through its
web UI — no config file to edit.

1. Go to **https://aichat.surf.nl/extensions** and click **Add extension**.
2. Fill in the form:
   | Field | Value |
   |---|---|
   | Name | `ori-ducklake` |
   | Description | Read-only SQL access to the SURF ORI DuckLake catalog (OpenAlex, OpenAIRE, CRIS, OpenAPC) |
   | URL of MCP server | `https://ori-ducklake-mcp.onrender.com/mcp` (public instance) or your own self-hosted URL, e.g. `http://<SURF-VM-IP>:8000/mcp` |
   | Transport type | `Streamable HTTP` |
   | Authentication type | `No authentication` |
3. Check **"I trust this source and confirm that I am allowed to use the
   content within SURF AI Chat"**.
4. Click **Create extension**.

**Domain whitelisting**: SURF AI Chat only allows outbound MCP connections to
whitelisted domains — the form says *"The domain must be whitelisted before it
can be used as an extension. Request access via email."* Before the extension
will actually connect, ask SURF AI Chat support to whitelist the domain you
entered (`ori-ducklake-mcp.onrender.com`, or your own VM's hostname/IP if
self-hosting). Until that's approved, the extension will save but calls to it
will fail.

Once added, the extension is available across all your chats (not just one
conversation) — no per-chat setup needed.

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

**`ModuleNotFoundError: No module named 'mcp.server.fastmcp'`**
The installed `mcp` package resolved to `2.0.0` or newer, which restructured its
internals. This project pins `mcp>=1.2.0,<2.0.0` in `pyproject.toml` — if you hit
this, you're installing from something that bypassed that pin. Re-run
`pip install .` / `uv sync` from a fresh checkout of this repo.

**Render health check keeps failing / service won't stay up**
Don't point Render's `healthCheckPath` at `/mcp` — it only accepts real MCP
protocol POSTs with a session, so a plain GET health check always fails there.
Leave `healthCheckPath` unset in `render.yaml` so Render falls back to its
TCP-level "is it listening" check.

## References

- DuckLake 1.0 release: https://ducklake.select/2026/04/13/ducklake-10/
- DuckLake connecting docs: https://ducklake.select/docs/stable/duckdb/usage/connecting
- Public DuckLake on object storage: https://ducklake.select/docs/stable/duckdb/guides/public_ducklake_on_object_storage
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
