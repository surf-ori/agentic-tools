# SURF ORI Agentic Tools

Claude agent skills and MCP servers for the [SURF](https://www.surf.nl/) Open Research Information (ORI) stack.

## What's in here

| Path | Type | Purpose |
|---|---|---|
| `skills/ducklake/` | Skill | Teaches Claude to query the DuckLake catalog on SURF Object Store |
| `skills/openaire-oaipmh/` | Skill | OAI-PMH harvesting patterns for Dutch repositories |
| `skills/urn-nbn/` | Skill | URN:NBN resolution via the Nationale Resolver |
| `mcp-servers/ori-ducklake-mcp/` | MCP server | Live read-only SQL access to the DuckLake via DuckDB |
| `scripts/` | Utilities | Shared Python helpers |

## Quick start: ori-ducklake-mcp

```bash
cd mcp-servers/ori-ducklake-mcp
pip install -e .
ducklake-mcp
```

Add to Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ducklake-sprouts": {
      "command": "python",
      "args": ["-m", "ducklake_mcp"],
      "env": {
        "DUCKLAKE_URL": "https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake"
      }
    }
  }
}
```

Add to Claude Code (`~/.claude/settings.json`) — or use the project `.claude/settings.json` already in this repo:

```json
{
  "mcpServers": {
    "ducklake-sprouts": {
      "command": "python",
      "args": ["-m", "ducklake_mcp"],
      "type": "stdio"
    }
  }
}
```

> **Windows note:** `python -m ducklake_mcp` is preferred over the `ori-ducklake-mcp` script command because pip installs scripts to `%APPDATA%\Python\PythonXXX\Scripts` which may not be on `PATH`. The `python -m` form always works.

## Quick start: skills

Skills teach Claude *how* to think about DuckLake — which tables exist, how to unnest structs, identifier cross-walk patterns, etc. They work alongside the MCP server.

### Install into Claude Code

```bash
# Install the ducklake skill (reads from skills/ducklake/SKILL.md)
npx skills add surf-ori/agentic-tools@ducklake

# Install all skills in this repo
npx skills add surf-ori/agentic-tools@openaire-oaipmh
npx skills add surf-ori/agentic-tools@urn-nbn
```

Skills are stored in `~/.claude/skills/` (user-global) or `.claude/skills/` (project-local). Claude loads the short `description:` from each `SKILL.md` at startup; the full body is injected only when a conversation triggers it — keeping token cost low.

### Install into Claude Desktop

Claude Desktop doesn't have a skill CLI yet. Instead, copy the skill content directly into a **Project** instruction:

1. Open **Claude Desktop** → **Projects** → your project → **Instructions**.
2. Copy the contents of `skills/ducklake/SKILL.md` (everything after the YAML front-matter `---` block) into the instructions box.
3. Attach the reference files as **Project Knowledge** files (drag `references/schemas.md`, `references/patterns.md`, `references/connection.md` into the Knowledge panel).

### Skill file structure

```
skills/ducklake/
├── SKILL.md              ← Trigger description + core instructions
└── references/
    ├── connection.md     ← Loaded on demand: SURF endpoints, auth, troubleshooting
    ├── schemas.md        ← All 4 schemas, tables, column docs, struct layouts
    └── patterns.md       ← SQL cookbook: unnesting, joins, identifier look-ups
```

Three-level progressive disclosure keeps context lean:
- Only the `description:` frontmatter (~50 words) is always loaded.
- `SKILL.md` body loads when a conversation triggers the skill.
- `references/` files are loaded only when the task needs them.

## Architecture

```
┌─────────────────────────────────────────────┐
│              Claude Agent                   │
├──────────────┬──────────────────────────────┤
│   Skills     │  MCPs (live tool calls)      │
│  (prompts +  │                              │
│   guidance)  │  ori-ducklake-mcp ──► DuckDB │
│              │      └──► SURF Object Store  │
├──────────────┴──────────────────────────────┤
│   CLAUDE.md (rules & context)               │
└─────────────────────────────────────────────┘
```

The **skill** teaches Claude *when* and *how* to use the DuckLake; the **MCP server** gives Claude the actual callable tools at runtime. They're complementary: deploy both for the full experience.

## Default catalog

The default DuckLake URL points at the public SURF "Sprouts" research dataset catalog:

```
https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake
```

No credentials required. Override via `DUCKLAKE_URL` env var.

## Contributing

PRs welcome. All contributions are licensed under EUPL-1.2.

## License

[EUPL-1.2](LICENSE) © SURF / Maurice Vanderfeesten
