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
      "command": "ducklake-mcp",
      "env": {
        "DUCKLAKE_URL": "https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake"
      }
    }
  }
}
```

Add to Claude Code (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "ducklake-sprouts": {
      "command": "ducklake-mcp",
      "type": "stdio"
    }
  }
}
```

## Quick start: skills

```bash
npx skills add surf-ori/agentic-tools@ducklake
```

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
