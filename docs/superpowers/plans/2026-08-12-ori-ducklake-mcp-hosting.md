# ori-ducklake-mcp Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ori-ducklake-mcp` reachable over the network (not just local stdio), with a self-hosted Docker path (SURF VM, used by EduGenAI/LibreChat), a public Render instance anyone can use immediately, and a zero-clone `uvx` quick-start for individual Claude Desktop/Code users — plus documentation updates across the repo so all three are discoverable.

**Architecture:** Same server code, three access modes distinguished only by transport (`stdio` vs `streamable-http`) and where the process runs. A dependency-pin bug (found during design validation) is fixed first since it blocks the zero-clone path and Docker builds alike. Docker packaging uses `uv sync --frozen` so the container always gets the exact `uv.lock` versions regardless of what's on PyPI.

**Tech Stack:** Python 3.10+, `uv`/`uvx`, `duckdb`, `mcp` (FastMCP), Docker, Render Blueprint (`render.yaml`), `docker-compose`.

## Global Constraints

- `mcp` dependency in `pyproject.toml`: `>=1.2.0,<2.0.0` — `mcp==2.0.0` restructured its package layout and breaks the `mcp.server.fastmcp` import `server.py` relies on; confirmed via live reproduction against the pushed repo.
- Python: `>=3.10` (existing, unchanged). Docker base image: `python:3.12-slim`.
- DuckDB: `>=1.5.2` (existing, unchanged).
- Default catalog URL is correct as-is (`https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake`) — verified via live local run, no change needed anywhere.
- Both hosted instances (SURF VM, Render) are fully open — no auth, no rate limiting. Explicit design decision; do not add access control.
- SURF VM updates are manual (`git pull` + `docker compose up -d --build`) — explicit design decision; do not add GitHub-Actions-driven auto-deploy to the VM.
- Public PaaS is Render, not Fly.io (Fly.io requires a credit card even on its free tier).
- `render.yaml` must NOT set `healthCheckPath: /mcp` — verified live that `GET /mcp` never returns 2xx (406 without proper headers, 400 with them but no session), so a path-based health check would flap a healthy service. Leave `healthCheckPath` unset.

---

## File Structure

```
mcp-servers/ori-ducklake-mcp/
├── pyproject.toml              # MODIFY: tighten mcp dependency pin
├── uv.lock                     # MODIFY: regenerated (expected: no diff)
├── src/ori_ducklake_mcp/
│   └── server.py                # MODIFY: add DUCKLAKE_MCP_HOST/PORT config
├── tests/
│   └── test_server_config.py   # CREATE: unit test for host/port env wiring
├── Dockerfile                   # CREATE
├── .dockerignore                 # CREATE
├── docker-compose.yml            # CREATE
└── README.md                    # MODIFY: config table + 5 new sections + troubleshooting

render.yaml                       # CREATE (repo root)
README.md                         # MODIFY (repo root): "three ways to connect" summary
skills/ori-ducklake/references/connection.md  # MODIFY: pointer to zero-clone/hosted options
```

---

### Task 1: Fix the `mcp` dependency pin

**Files:**
- Modify: `mcp-servers/ori-ducklake-mcp/pyproject.toml:9-17`
- Modify: `mcp-servers/ori-ducklake-mcp/uv.lock` (regenerated, not hand-edited)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: a `pyproject.toml` constraint that every later task (Docker build, zero-clone `uvx`, `uv sync`) relies on to resolve `mcp` to a working `1.x` version instead of the breaking `2.0.0`.

- [ ] **Step 1: Edit the dependency constraint**

In `mcp-servers/ori-ducklake-mcp/pyproject.toml`, change:

```toml
dependencies = [
    # DuckLake v1.0 ships in DuckDB 1.5.2 (released 2026-04-13).
    "duckdb>=1.5.2",
    # FastMCP lives inside the official MCP Python SDK.
    "mcp>=1.2.0",
    # DuckDB needs pytz to materialise TIMESTAMPTZ columns returned by
    # ducklake_snapshots() into Python objects.
    "pytz",
]
```

to:

```toml
dependencies = [
    # DuckLake v1.0 ships in DuckDB 1.5.2 (released 2026-04-13).
    "duckdb>=1.5.2",
    # FastMCP lives inside the official MCP Python SDK. Upper-bounded below
    # 2.0.0: that release restructured mcp's package layout and no longer
    # exposes mcp.server.fastmcp where server.py imports it from. This
    # matters even though uv.lock pins an exact version, because uvx and
    # `pip install` from a git URL both bypass the lockfile and re-resolve
    # fresh against this constraint.
    "mcp>=1.2.0,<2.0.0",
    # DuckDB needs pytz to materialise TIMESTAMPTZ columns returned by
    # ducklake_snapshots() into Python objects.
    "pytz",
]
```

- [ ] **Step 2: Regenerate the lock file**

Run: `cd mcp-servers/ori-ducklake-mcp && uv lock`

- [ ] **Step 3: Verify the lock file didn't need to change**

Run: `git diff --stat uv.lock`
Expected: no output (empty diff) — the currently-locked `mcp==1.27.1` already satisfies the new tighter constraint, so this step just proves that.

- [ ] **Step 4: Commit**

```bash
git add mcp-servers/ori-ducklake-mcp/pyproject.toml mcp-servers/ori-ducklake-mcp/uv.lock
git commit -m "fix: pin mcp dependency below 2.0.0 to avoid breaking import"
```

---

### Task 2: Add `DUCKLAKE_MCP_HOST` / `DUCKLAKE_MCP_PORT` config

**Files:**
- Modify: `mcp-servers/ori-ducklake-mcp/src/ori_ducklake_mcp/server.py:41-44` (config constants)
- Modify: `mcp-servers/ori-ducklake-mcp/src/ori_ducklake_mcp/server.py:167-179` (`FastMCP(...)` construction)
- Test: `mcp-servers/ori-ducklake-mcp/tests/test_server_config.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `server.MCP_HOST` (str), `server.MCP_PORT` (int) module constants, and `server.mcp` (the `FastMCP` instance) constructed with those values as `host=`/`port=` — Task 3's Docker `CMD` relies on `DUCKLAKE_MCP_PORT` actually reaching the bound server for the `${PORT}` passthrough to work.

- [ ] **Step 1: Write the failing test**

Create `mcp-servers/ori-ducklake-mcp/tests/test_server_config.py`:

```python
"""Tests for DUCKLAKE_MCP_HOST / DUCKLAKE_MCP_PORT wiring into FastMCP.

Importing ori_ducklake_mcp.server never opens a network connection (the
DuckLake ATTACH happens lazily on first tool call, not at import time), so
these tests are safe to run offline.
"""

from __future__ import annotations

import importlib
import os
import unittest


class TestHostPortConfig(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            key: os.environ.pop(key, None)
            for key in ("DUCKLAKE_MCP_HOST", "DUCKLAKE_MCP_PORT")
        }

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_defaults_bind_all_interfaces_on_port_8000(self) -> None:
        from ori_ducklake_mcp import server

        importlib.reload(server)
        self.assertEqual(server.MCP_HOST, "0.0.0.0")
        self.assertEqual(server.MCP_PORT, 8000)
        self.assertEqual(server.mcp.settings.host, "0.0.0.0")
        self.assertEqual(server.mcp.settings.port, 8000)

    def test_env_vars_override_host_and_port(self) -> None:
        os.environ["DUCKLAKE_MCP_HOST"] = "192.168.1.5"
        os.environ["DUCKLAKE_MCP_PORT"] = "9001"

        from ori_ducklake_mcp import server

        importlib.reload(server)
        self.assertEqual(server.MCP_HOST, "192.168.1.5")
        self.assertEqual(server.MCP_PORT, 9001)
        self.assertEqual(server.mcp.settings.host, "192.168.1.5")
        self.assertEqual(server.mcp.settings.port, 9001)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd mcp-servers/ori-ducklake-mcp && uv run python -m unittest tests.test_server_config -v`
Expected: FAIL — `AttributeError: module 'ori_ducklake_mcp.server' has no attribute 'MCP_HOST'`

- [ ] **Step 3: Add the config constants**

In `mcp-servers/ori-ducklake-mcp/src/ori_ducklake_mcp/server.py`, change:

```python
DUCKLAKE_URL = os.environ.get("DUCKLAKE_URL", DEFAULT_DUCKLAKE_URL)
LAKE_ALIAS = os.environ.get("DUCKLAKE_ALIAS", "lake")
DEFAULT_ROW_LIMIT = int(os.environ.get("DUCKLAKE_ROW_LIMIT", "1000"))
MAX_ROW_LIMIT = int(os.environ.get("DUCKLAKE_MAX_ROW_LIMIT", "10000"))
```

to:

```python
DUCKLAKE_URL = os.environ.get("DUCKLAKE_URL", DEFAULT_DUCKLAKE_URL)
LAKE_ALIAS = os.environ.get("DUCKLAKE_ALIAS", "lake")
DEFAULT_ROW_LIMIT = int(os.environ.get("DUCKLAKE_ROW_LIMIT", "1000"))
MAX_ROW_LIMIT = int(os.environ.get("DUCKLAKE_MAX_ROW_LIMIT", "10000"))
# Only used in streamable-http mode; harmless when transport=stdio (the default).
MCP_HOST = os.environ.get("DUCKLAKE_MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("DUCKLAKE_MCP_PORT", "8000"))
```

- [ ] **Step 4: Pass host/port into the FastMCP constructor**

In the same file, change:

```python
mcp = FastMCP(
    "ori-ducklake-mcp",
    instructions=(
```

to:

```python
mcp = FastMCP(
    "ori-ducklake-mcp",
    host=MCP_HOST,
    port=MCP_PORT,
    instructions=(
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd mcp-servers/ori-ducklake-mcp && uv run python -m unittest tests.test_server_config -v`
Expected: `OK` (2 tests passed)

- [ ] **Step 6: Commit**

```bash
git add mcp-servers/ori-ducklake-mcp/src/ori_ducklake_mcp/server.py mcp-servers/ori-ducklake-mcp/tests/test_server_config.py
git commit -m "feat: add DUCKLAKE_MCP_HOST/PORT config for streamable-http mode"
```

---

### Task 3: Docker packaging

**Files:**
- Create: `mcp-servers/ori-ducklake-mcp/Dockerfile`
- Create: `mcp-servers/ori-ducklake-mcp/.dockerignore`
- Create: `mcp-servers/ori-ducklake-mcp/docker-compose.yml`

**Interfaces:**
- Consumes: `DUCKLAKE_MCP_PORT`/`DUCKLAKE_MCP_HOST` from Task 2 (the `CMD`'s `${PORT:-${DUCKLAKE_MCP_PORT:-8000}}` fallback only works because Task 2 made the server actually honor `DUCKLAKE_MCP_PORT`).
- Produces: a `Dockerfile` at `mcp-servers/ori-ducklake-mcp/Dockerfile` that Task 4's `render.yaml` references via `dockerfilePath`/`dockerContext`.

- [ ] **Step 1: Create the Dockerfile**

Create `mcp-servers/ori-ducklake-mcp/Dockerfile`:

```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# --frozen: install exactly what's in uv.lock, ignore whatever pyproject.toml
# would otherwise re-resolve to. Keeps the image immune to future PyPI
# releases regardless of the version pin in pyproject.toml.
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Render injects $PORT; the SURF VM / docker-compose don't, so fall back to
# DUCKLAKE_MCP_PORT (or 8000) when it's unset.
CMD ["sh", "-c", "DUCKLAKE_MCP_PORT=${PORT:-${DUCKLAKE_MCP_PORT:-8000}} DUCKLAKE_MCP_TRANSPORT=streamable-http uv run ori-ducklake-mcp"]
```

- [ ] **Step 2: Create .dockerignore**

Create `mcp-servers/ori-ducklake-mcp/.dockerignore`:

```
.venv
__pycache__
*.pyc
tests
.git
```

- [ ] **Step 3: Create docker-compose.yml**

Create `mcp-servers/ori-ducklake-mcp/docker-compose.yml`:

```yaml
services:
  ori-ducklake-mcp:
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      DUCKLAKE_MCP_TRANSPORT: streamable-http
```

- [ ] **Step 4: Build and run the image locally**

Run:
```bash
cd mcp-servers/ori-ducklake-mcp
docker compose up -d --build
```
Expected: build succeeds, container starts (`docker compose ps` shows it `running`/`healthy`).

- [ ] **Step 5: Verify it responds correctly**

The container needs a moment to attach to the catalog and start listening before
it'll answer — retry briefly instead of curling immediately:

```bash
for i in $(seq 1 10); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/mcp)
  [ "$code" = "406" ] && echo "OK: $code" && break
  sleep 2
done
echo "final: $code"
```
Expected: `OK: 406` — matches the local (non-Docker) probe from design validation; confirms the containerized server is up and speaking MCP on the expected port.

- [ ] **Step 6: Tear down the test container**

Run: `docker compose down`

- [ ] **Step 7: Commit**

```bash
git add mcp-servers/ori-ducklake-mcp/Dockerfile mcp-servers/ori-ducklake-mcp/.dockerignore mcp-servers/ori-ducklake-mcp/docker-compose.yml
git commit -m "feat: add Docker packaging for streamable-http deployment"
```

---

### Task 4: Render Blueprint

**Files:**
- Create: `render.yaml` (repo root)

**Interfaces:**
- Consumes: `mcp-servers/ori-ducklake-mcp/Dockerfile` from Task 3 (referenced by path).
- Produces: nothing consumed by later tasks in this plan — this is the artifact Render's dashboard reads when the user connects the repo (a manual step outside this plan's automated scope).

- [ ] **Step 1: Create render.yaml**

Create `render.yaml` at the repo root:

```yaml
services:
  - type: web
    name: ori-ducklake-mcp
    runtime: docker
    dockerfilePath: ./mcp-servers/ori-ducklake-mcp/Dockerfile
    dockerContext: ./mcp-servers/ori-ducklake-mcp
    plan: free
    envVars:
      - key: DUCKLAKE_MCP_TRANSPORT
        value: streamable-http
    # Deliberately no healthCheckPath: /mcp only accepts real MCP protocol
    # POSTs with a session, never a plain GET, so a path-based health check
    # would flap a healthy service (verified: GET /mcp -> 406/400, never
    # 2xx). Omitting it falls back to Render's TCP-level "is it listening"
    # check, which this server always satisfies once started.
```

- [ ] **Step 2: Validate the YAML syntax**

Run:
```bash
uv run --with pyyaml python3 -c "import yaml; yaml.safe_load(open('render.yaml')); print('valid')"
```
Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add render.yaml
git commit -m "feat: add Render Blueprint for public MCP instance"
```

---

### Task 5: Update the MCP server's README

**Files:**
- Modify: `mcp-servers/ori-ducklake-mcp/README.md`

**Interfaces:**
- Consumes: exact commands/config from Tasks 1-4 (must match what was actually built, not the design-time sketch, in case anything changed during implementation).
- Produces: the canonical deployment documentation that the top-level README (Task 6) and the skill (Task 7) link to instead of duplicating.

- [ ] **Step 1: Add host/port rows to the Configuration table**

In `mcp-servers/ori-ducklake-mcp/README.md`, find the Configuration table:

```markdown
| `DUCKLAKE_MCP_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING`. Logs go to stderr. |
| `DUCKLAKE_MCP_TRANSPORT` | `stdio` | Set to `streamable-http` for HTTP mode. |
```

Change to:

```markdown
| `DUCKLAKE_MCP_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING`. Logs go to stderr. |
| `DUCKLAKE_MCP_TRANSPORT` | `stdio` | Set to `streamable-http` for HTTP mode. |
| `DUCKLAKE_MCP_HOST` | `0.0.0.0` | Bind address in `streamable-http` mode. Ignored for `stdio`. |
| `DUCKLAKE_MCP_PORT` | `8000` | Bind port in `streamable-http` mode. Ignored for `stdio`. |
```

- [ ] **Step 2: Add a "Run without cloning" section**

Insert immediately after the existing `## Run` section (right before `## Configuration`):

```markdown
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

```

- [ ] **Step 3: Add deployment sections**

Insert after the existing `## Wire up to Claude Desktop` section (right before `## Quick sanity check`):

```markdown
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

```

- [ ] **Step 4: Add troubleshooting entries**

In the existing `## Troubleshooting` section, after the last entry (`**Catalog version mismatch**` block), add:

```markdown

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
```

- [ ] **Step 5: Commit**

```bash
git add mcp-servers/ori-ducklake-mcp/README.md
git commit -m "docs: document Docker, Render, zero-clone, and LibreChat setup"
```

---

### Task 6: Update the top-level README

**Files:**
- Modify: `README.md` (repo root)

**Interfaces:**
- Consumes: the section headings created in Task 5 (links must resolve).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add a "three ways to connect" summary**

In `README.md`, find:

```markdown
## Quick start: ori-ducklake-mcp

No `pip install` needed — [uv](https://docs.astral.sh/uv/) manages the isolated environment from `uv.lock`.

Add to Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`):
```

Change to:

```markdown
## Quick start: ori-ducklake-mcp

No `pip install` needed — [uv](https://docs.astral.sh/uv/) manages the isolated environment from `uv.lock`.

There are three ways to connect, depending on what you need:

| Option | Best for | Details |
|---|---|---|
| **Run it yourself** | Local dev, a custom catalog URL | Clone this repo, point Claude at it via `uv run` — walkthrough below |
| **Zero-clone** | Individual Claude Desktop/Code use, no upkeep | `uvx --from git+https://github.com/surf-ori/agentic-tools...` — no checkout needed |
| **Already-running instance** | Trying it immediately, or wiring into another app (e.g. LibreChat) | Public instance at `https://ori-ducklake-mcp.onrender.com/mcp`, or a self-hosted one |

Full instructions for all three — plus Docker deployment and LibreChat/EduGenAI
wiring — live in [`mcp-servers/ori-ducklake-mcp/README.md`](mcp-servers/ori-ducklake-mcp/README.md).

Add to Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`):
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: summarize the three ways to connect to ori-ducklake-mcp"
```

---

### Task 7: Update the skill's connection reference

**Files:**
- Modify: `skills/ori-ducklake/references/connection.md`

**Interfaces:**
- Consumes: the section headings/URLs from Task 5.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Append a pointer section**

At the end of `skills/ori-ducklake/references/connection.md` (after the existing `## Troubleshooting` section), add:

```markdown

## Other ways to connect

Besides running this locally, the MCP server can also be reached without any
setup:

- **Zero-clone**: `uvx --from "git+https://github.com/surf-ori/agentic-tools.git#subdirectory=mcp-servers/ori-ducklake-mcp" ori-ducklake-mcp` — no checkout needed, `uv` builds and caches it on first run.
- **Public instance**: `https://ori-ducklake-mcp.onrender.com/mcp` (streamable-http) — already running, useful for a quick try without configuring anything.

Full deployment details (Docker, a self-hosted instance, LibreChat wiring) are in
[`mcp-servers/ori-ducklake-mcp/README.md`](../../../mcp-servers/ori-ducklake-mcp/README.md).
```

- [ ] **Step 2: Commit**

```bash
git add skills/ori-ducklake/references/connection.md
git commit -m "docs: point the ori-ducklake skill at zero-clone and hosted MCP options"
```

---

### Task 8: End-to-end verification against the pushed repo

**Files:** none created/modified — verification only.

**Interfaces:**
- Consumes: all commits from Tasks 1-7 (this task requires them to be on GitHub, since the zero-clone check pulls from the remote).
- Produces: confirmation that the whole plan works together, not just task-by-task in isolation.

- [ ] **Step 1: Confirm with the user before pushing**

This is the point where local commits from Tasks 1-7 go to `origin/main`. Per this
repo's working pattern, don't push without the user explicitly asking — check in
before running `git push`.

- [ ] **Step 2: Push**

```bash
git push origin main
```

- [ ] **Step 3: Re-verify the zero-clone path against the pushed code**

```bash
uv tool run --from "git+https://github.com/surf-ori/agentic-tools.git#subdirectory=mcp-servers/ori-ducklake-mcp" ori-ducklake-mcp
```

Expected (in stderr logs before it blocks waiting for stdio input — Ctrl-C or let
it hit EOF to exit): `DuckLake 'lake' attached read-only.` and
`Starting MCP server on transport=stdio`, no `ModuleNotFoundError`.

- [ ] **Step 4: Cross-check docs for consistency**

```bash
grep -rn "DUCKLAKE_MCP_HOST\|DUCKLAKE_MCP_PORT" mcp-servers/ori-ducklake-mcp/README.md mcp-servers/ori-ducklake-mcp/src/ori_ducklake_mcp/server.py
grep -rln "onrender.com" README.md mcp-servers/ori-ducklake-mcp/README.md skills/ori-ducklake/references/connection.md
grep -rln "uvx --from" README.md mcp-servers/ori-ducklake-mcp/README.md skills/ori-ducklake/references/connection.md
```

Expected: the env var names appear in both the README table and the source; the
Render URL and the `uvx --from` command each appear in all three files listed
(confirms no file was missed or left with stale/inconsistent wording).

- [ ] **Step 5: Report remaining manual steps to the user**

These require credentials this environment doesn't have — hand off with the exact
commands already documented in `mcp-servers/ori-ducklake-mcp/README.md`:
- Connecting the Render Blueprint (dashboard step, Task 5's "Deploy — public
  Render instance" section has the walkthrough).
- Running `docker compose up -d --build` on the actual SURF VM (Task 5's "Deploy —
  SURF VM" section).
- Adding the `librechat.yaml` block to the actual EduGenAI config (Task 5's
  "Connecting from LibreChat / EduGenAI" section).

No commit for this task — it's verification and handoff only.

---

## Self-Review Notes

**Spec coverage**: every component in the design spec (host/port config, dependency
pin fix, Dockerfile/compose, render.yaml, SURF VM guide, Render guide, zero-clone
quick-start, LibreChat wiring, and all three doc-file updates) maps to a task above.
The spec's "Out of scope" list (TLS, auth, CI-driven VM deploy, query-cost limits)
has deliberately no corresponding task.

**Placeholder scan**: no TBD/TODO; every step has literal file content or an exact
command with expected output.

**Type/name consistency**: `MCP_HOST`/`MCP_PORT` (Task 2) match the names used in
Task 3's Dockerfile comment and Task 5's README table. `DUCKLAKE_MCP_HOST`/
`DUCKLAKE_MCP_PORT` (the env var names, as opposed to the Python constants) are
consistent across Task 2's code, Task 3's Dockerfile, and Task 5's docs.
