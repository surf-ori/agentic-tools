---
name: ducklake
description: >
  Use this skill when the user asks to query, explore, or analyse research data
  in the SURF DuckLake catalog — including OpenAlex institutions, works, authors,
  concepts, or any other table in the Sprouts lake. Trigger on phrases like
  "query the lake", "list tables in DuckLake", "how many Dutch universities",
  "show me the OpenAlex data", or any question about research information stored
  on SURF Object Store. Also load when the user asks about connecting to DuckLake,
  writing DuckDB SQL against the catalog, or time-travel snapshots.
---

# DuckLake skill — SURF ORI

## What you have access to

The `ori-ducklake-mcp` MCP server is available. It exposes these tools:

| Tool | When to use |
|---|---|
| `ducklake_info` | First call — get the catalog URL, DuckDB version, extension settings |
| `list_schemas` | Discover what schemas exist (e.g. `openalex`, `narcis`) |
| `list_tables` | List tables in a schema |
| `describe_table` | Get column names, types, nullability, and row count for a table |
| `preview_table` | Peek at the first rows before writing a full query |
| `query` | Run a read-only SQL SELECT against the lake |
| `list_snapshots` | Enumerate time-travel snapshots |
| `table_files` | See the Parquet files backing a table (useful for debugging) |

## How to approach a question

1. Call `ducklake_info` once per session to confirm the catalog is reachable and get the alias (default: `lake`).
2. Call `list_schemas` if you don't know which schema holds the data.
3. Call `list_tables(schema=...)` to narrow down.
4. Call `describe_table` before writing SQL — saves you from guessing column names.
5. Call `preview_table` for a sanity check on actual values.
6. Write your SELECT using fully-qualified names: `lake.<schema>.<table>`.

## SQL conventions

- Always use `lake.<schema>.<table>` fully-qualified names.
- Use column aliases for readability in results returned to the user.
- The server wraps unbounded SELECTs in `LIMIT 1000` automatically. Pass an explicit `limit` arg to `query` to raise or lower it (max 10 000).
- DuckDB SQL syntax applies — window functions, `LIST_AGG`, `STRUCT`, `UNNEST`, etc. all work.

## Example queries

```sql
-- Count institutions by country
SELECT country_code, COUNT(*) AS n
FROM lake.openalex.institutions
GROUP BY country_code
ORDER BY n DESC
LIMIT 20

-- Find Dutch universities
SELECT display_name, ror, cited_by_count
FROM lake.openalex.institutions
WHERE country_code = 'NL'
  AND type = 'education'
ORDER BY cited_by_count DESC
```

## References

- [Connection details & auth patterns](references/connection.md)
- [Known schemas and tables](references/schemas.md)
- [Common query patterns](references/patterns.md)
