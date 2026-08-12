# ori-ducklake-mcp hosting design

Date: 2026-08-12
Status: Approved, ready for implementation planning

## Problem

`ori-ducklake-mcp` currently has exactly one way to run: clone the repo and start it
locally over stdio via `uv run`. That's fine for an individual developer, but it
doesn't serve two real needs:

1. SURF wants an EduGenAI instance of LibreChat to call this MCP server so chat
   users can pull research information (OpenAlex, OpenAIRE, CRIS, OpenAPC) into
   conversations. LibreChat is itself a running service — it needs a stable network
   URL to connect to, not a command it spawns locally.
2. Beyond that one deployment, there should be an already-running public instance
   so anyone can point an MCP client at it immediately, without cloning or deploying
   anything themselves ("an active one to use right from the start").

GitHub Pages (static-only) and GitHub Actions (ephemeral CI runners, capped runtime)
were considered and ruled out — neither can host a persistent backend process, which
is what both needs above actually require.

## Approach

Keep one codebase, add two things:

- A **persistent HTTP mode**, deployed to two targets:
  - A **SURF VM** (Docker), reachable at `http://<VM-IP>:8000/mcp` — this is what
    LibreChat/EduGenAI connects to. Plain HTTP/IP, no TLS, per available infra.
  - A **public Render instance** (Docker, deployed from this GitHub repo via
    Render's native Blueprint integration), reachable at
    `https://ori-ducklake-mcp.onrender.com/mcp` — the "ready to use immediately"
    instance for anyone.
- A **zero-clone quick-start** for individual Claude Desktop/Code users: run
  straight from the GitHub repo via `uvx --from git+https://github.com/...`,
  no local checkout needed. This is a separate, lower-effort convenience path —
  it doesn't require deploying or hosting anything, since the MCP client spawns
  the process locally on demand.

All three modes run the same server code; only the transport (`stdio` vs
`streamable-http`) and where the process runs differ. The DuckLake catalog, tools,
and read-only safety model are untouched.

**Default catalog confirmed correct**: the hardcoded default in `server.py`
(`https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake`)
matches what's documented everywhere else in the repo, and a live local run
confirmed it attaches successfully (`DuckLake 'lake' attached read-only`). No change
needed there.

## Decisions made during design

- **Access control**: both hosted instances are fully open, no auth. The server is
  already read-only (keyword filtering + `READ_ONLY` ATTACH); the only risk of
  being open is availability (someone running expensive queries), not data
  integrity. A gate would work against "ready to use right from the start."
- **SURF VM updates**: manual redeploy (`git pull` + `docker compose up -d --build`),
  not GitHub-Actions-driven auto-deploy. Simpler, no secrets to manage, matches a
  non-technical operator's comfort level. Can be revisited later if it becomes a
  burden.
- **Public PaaS**: Render, not Fly.io — Fly.io requires a credit card even for its
  free tier, Render doesn't. Render's native GitHub Blueprint integration gives
  push-to-deploy for free.

## Components

### 1. Server config: listen on a network port

`FastMCP` is constructed once in `server.py` with no `host`/`port`, so in HTTP mode
it defaults to `127.0.0.1:8000` — unreachable from outside a container. Add two env
vars, read at module load and passed into the `FastMCP(...)` constructor:

- `DUCKLAKE_MCP_HOST` — default `0.0.0.0`
- `DUCKLAKE_MCP_PORT` — default `8000`

These are inert when `DUCKLAKE_MCP_TRANSPORT=stdio` (the existing default), so
nothing changes for current users.

Confirmed live (local run, `DUCKLAKE_MCP_TRANSPORT=streamable-http`):
- `GET /` → 404
- `GET /mcp` (no `Accept` headers) → 406
- `GET /mcp` (proper `Accept` headers, no session) → 400
- `POST /mcp` with a real MCP `initialize` request → **200**, correct
  `serverInfo`/`instructions`, catalog attached successfully

This matters for the Render health check (see Component 3): a GET-based path check
against `/mcp` would never see a 2xx and would flap the service.

### 2. Dependency pin fix (found via testing, required for everything below)

`pyproject.toml` currently declares `"mcp>=1.2.0"` with no upper bound. `uv.lock`
pins it to `mcp==1.27.1` (which is what `uv run` inside the project always uses),
but **`uvx`/`uv tool run` and plain `pip install` do not consult `uv.lock`** — they
re-resolve fresh against the `pyproject.toml` constraint. That currently resolves to
`mcp==2.0.0`, which restructured its package layout and no longer exposes
`mcp.server.fastmcp` where `server.py` imports it from — an immediate
`ModuleNotFoundError` on startup.

Confirmed via live reproduction against the real GitHub repo:
- `uv tool run --from git+https://github.com/surf-ori/agentic-tools.git#subdirectory=mcp-servers/ori-ducklake-mcp ori-ducklake-mcp` → crashes with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`
- Same command with `--with "mcp<2.0.0"` → starts cleanly, attaches to the correct catalog

**Fix**: tighten `pyproject.toml` to `"mcp>=1.2.0,<2.0.0"`. This is required for the
zero-clone quick-start (Component 4) to work at all, and also protects any
lockfile-free install path (e.g. a naive `pip install .` in a Dockerfile).

### 3. Docker packaging

New `mcp-servers/ori-ducklake-mcp/Dockerfile`. Uses `uv sync --frozen` rather than
`pip install .`, so the container always gets the exact versions from `uv.lock`
regardless of what's on PyPI — belt-and-suspenders on top of the pin fix above:

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
EXPOSE 8000
CMD ["sh", "-c", "DUCKLAKE_MCP_PORT=${PORT:-${DUCKLAKE_MCP_PORT:-8000}} DUCKLAKE_MCP_TRANSPORT=streamable-http uv run ori-ducklake-mcp"]
```

The `${PORT:-...}` fallback lets the same image work unmodified on Render (which
injects `PORT`) and the SURF VM (which doesn't).

New `mcp-servers/ori-ducklake-mcp/docker-compose.yml`, for the SURF VM:

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

### 4. Deploy target A — SURF VM

Setup (once):
```bash
git clone https://github.com/surf-ori/agentic-tools.git
cd agentic-tools/mcp-servers/ori-ducklake-mcp
docker compose up -d --build
```

Update (manual redeploy, per decision above):
```bash
cd agentic-tools && git pull
cd mcp-servers/ori-ducklake-mcp && docker compose up -d --build
```

Verify: `curl -i http://<VM-IP>:8000/mcp` — expect 406 (proves the process is up and
speaking MCP; a full handshake needs a real MCP client).

`restart: unless-stopped` means the container survives VM reboots and crash-restarts
without manual intervention.

Security note (documented, not solved): plaintext HTTP, no auth, on an IP the
operator controls. No secrets flow through it since the catalog is public and
read-only. Optional future hardening: firewall port 8000 to just the LibreChat
host.

### 5. Deploy target B — public Render instance

New `render.yaml` at repo root (Render's Blueprint auto-detects this):

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
    # No healthCheckPath: /mcp only accepts real MCP protocol POSTs, not plain
    # GETs (see Component 1's probe results) — a path health check would flap
    # a healthy service. Omitting it falls back to Render's TCP-level check.
```

Setup (once, in the Render dashboard — no CLI, no credit card on the free tier):
1. New → Blueprint → connect the `surf-ori/agentic-tools` GitHub repo.
2. Render reads `render.yaml`, click Apply.
3. Render builds the Dockerfile, assigns an HTTPS URL
   (`https://ori-ducklake-mcp.onrender.com`).

Every push to `main` auto-redeploys from then on — Render's native GitHub
integration, no custom CI needed.

Verify: `curl -i https://<app>.onrender.com/mcp` — expect 406, same as the VM.

Documented caveats:
- **Cold start**: free tier sleeps after ~15 min idle, ~30s to wake on next request.
- **Memory**: free tier has ~512MB RAM. A query aggregating across the full 552GB
  `openalex.works` table could plausibly OOM there even though it runs fine locally
  or on the SURF VM. Guidance: the public Render instance is for light/exploratory
  use; point LibreChat at the SURF VM for anything heavier.

### 6. Zero-clone quick-start (individual users)

Claude Code (`~/.claude/settings.json` or project `.claude/settings.json`):
```json
{
  "mcpServers": {
    "ori-ducklake": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/surf-ori/agentic-tools.git#subdirectory=mcp-servers/ori-ducklake-mcp",
        "ori-ducklake-mcp"
      ]
    }
  }
}
```

Claude Desktop: same shape under `mcpServers`, no `type` field, matching the
existing local-run examples already in the README.

Confirmed working live (post dependency-pin-fix) against the real repo: first run
downloads and builds in ~15-20s, subsequent runs are fast from `uv`'s cache.
`DUCKLAKE_URL` and other env vars still override via the `env` block as before.

### 7. LibreChat / EduGenAI wiring

Verified against current LibreChat docs (`librechat.yaml` MCP server config):

```yaml
mcpServers:
  ori-ducklake:
    type: streamable-http
    url: http://<SURF-VM-IP>:8000/mcp
    chatMenu: true
```

`type: streamable-http` must be explicit — LibreChat auto-detects plain `sse` for a
bare `http(s)://` URL, which is a different transport than what this server speaks;
getting this wrong silently fails to connect. Same block works against the Render
URL instead if EduGenAI ever wants the public instance as a fallback.

### 8. Documentation updates

Technical detail lives once, in `mcp-servers/ori-ducklake-mcp/README.md`; other
docs link to it rather than duplicating.

- **`mcp-servers/ori-ducklake-mcp/README.md`**: add `DUCKLAKE_MCP_HOST`/
  `DUCKLAKE_MCP_PORT` to the config table; new sections "Run without cloning",
  "Run with Docker", "Deploy — SURF VM", "Deploy — public Render instance",
  "Connecting from LibreChat / EduGenAI"; troubleshooting entries for the
  `mcp.server.fastmcp` import error and the Render health-check gotcha.
- **Top-level `README.md`**: short "three ways to connect" summary (run-it-yourself
  / zero-clone / already-running instance) linking down to the MCP README; add the
  public Render URL once live.
- **`skills/ori-ducklake/references/connection.md`**: light-touch addition noting
  the zero-clone command and the public Render URL exist, pointing to the MCP
  README for full deployment details — this skill's job is SQL patterns, not ops.

## Testing / verification plan

Verifiable without external credentials (done during implementation):
- Host/port env vars: start locally with `DUCKLAKE_MCP_TRANSPORT=streamable-http`
  and custom host/port, confirm the same 406/400/200 response pattern already
  measured.
- `Dockerfile` builds and runs locally (`docker build` + `docker run`), same curl
  probe against the container.
- Dependency pin: re-run the `uv tool run --from git+https://...` reproduction
  against the pushed branch, confirm clean startup.
- Docs cross-check: every URL/command in the new doc sections matches the shipped
  config (port numbers, env var names, file paths).

Requires the user (no Render/SURF VM credentials available here):
- Actual Render Blueprint connect and first deploy.
- Actual `docker compose up -d --build` on the SURF VM.
- Actual `librechat.yaml` change taking effect in the EduGenAI instance.

Each of the above has an exact copy-paste command and expected output already
specified in Components 4/5/7, so it's "run this, see this" rather than
open-ended debugging.

## Out of scope (explicitly deferred, not forgotten)

- TLS on the SURF VM (plain HTTP/IP was the operator's explicit choice).
- Auth/rate limiting on either hosted instance (explicitly chosen open).
- GitHub-Actions-driven auto-deploy to the SURF VM (manual redeploy chosen).
- Query-cost limits beyond the existing row-count caps (pre-existing limitation,
  not newly introduced — now more exposed since the server is reachable by anyone,
  but fixing it is a separate piece of work if abuse becomes a real problem).
