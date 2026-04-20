# Common query patterns — DuckLake

## Exploration workflow

```sql
-- 1. What schemas exist?
SELECT schema_name FROM information_schema.schemata
WHERE catalog_name = 'lake' AND schema_name NOT IN ('information_schema','pg_catalog');

-- 2. What tables in a schema?
SELECT table_name, table_type FROM information_schema.tables
WHERE table_catalog = 'lake' AND table_schema = 'openalex';

-- 3. Column types for a table
DESCRIBE lake.openalex.institutions;

-- 4. Quick data peek
FROM lake.openalex.institutions LIMIT 5;
```

## Aggregation patterns

```sql
-- Output by country (top 10)
SELECT country_code, COUNT(*) AS institutions
FROM lake.openalex.institutions
GROUP BY ALL ORDER BY institutions DESC LIMIT 10;

-- Publication trend by year
SELECT publication_year, COUNT(*) AS works
FROM lake.openalex.works
WHERE publication_year BETWEEN 2010 AND 2024
GROUP BY ALL ORDER BY publication_year;
```

## Filtering nested arrays

OpenAlex stores related IDs as arrays (e.g. `concept_ids`, `author_ids`).

```sql
-- Works tagged with a specific concept ID
SELECT title, publication_year
FROM lake.openalex.works
WHERE list_contains(concept_ids, 'C41008148')  -- Computer Science
LIMIT 50;
```

## Time travel

```sql
-- List available snapshots
FROM ducklake_snapshots('lake');

-- Query a specific snapshot (use the snapshot_id from above)
SELECT COUNT(*) FROM lake.openalex.institutions
AT (VERSION => 3);
```

## Safety limits

The MCP server wraps unbounded SELECTs in `LIMIT 1000`. To raise the limit:

```python
query("SELECT ...", limit=5000)   # up to DUCKLAKE_MAX_ROW_LIMIT (default 10 000)
```

For counts / aggregations that return a single row, limits don't matter.
