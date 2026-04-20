---
name: ducklake
description: >
  Use this skill when the user asks to query, explore, or analyse research data
  in the SURF DuckLake catalog — including OpenAlex (works, authors, institutions,
  funders, topics), OpenAIRE (publications, organizations, projects, datasets,
  software), CRIS (institutional repository publications), or OpenAPC (article
  processing charges). Trigger on phrases like "query the lake", "list tables
  in DuckLake", "how many Dutch universities", "find publications by ORCID",
  "show me the APC costs", "resolve a DOI in the lake", or any question about
  research information stored on SURF Object Store. Also load when the user asks
  about connecting to DuckLake, unnesting nested STRUCT or LIST columns, or
  writing DuckDB SQL against the catalog.
---

# DuckLake skill — SURF ORI

## Available MCP tools

The `ducklake-sprouts` MCP server is connected. Use these tools:

| Tool | When to use |
|---|---|
| `ducklake_info` | First call — confirm catalog URL, DuckDB version, alias (`lake`) |
| `list_schemas` | Discover schemas: `cris`, `openaire`, `openalex`, `openapc` |
| `list_tables` | List tables in a schema |
| `describe_table` | Get column names, types, nullability, row count |
| `preview_table` | Peek at first rows before writing SQL |
| `query` | Run read-only SQL against the lake |
| `list_snapshots` | Enumerate time-travel snapshots |
| `table_files` | Parquet files backing a table |

## Approach every question in this order

1. `describe_table` first — column names and types before writing any SQL.
2. Use **fully-qualified names**: `lake.<schema>.<table>`.
3. For struct/array columns, use the unnesting patterns below.
4. Wrap unbounded SELECTs with an explicit `LIMIT`; the server auto-applies 1 000.

## Schemas at a glance

| Schema | Tables | Key identifiers |
|---|---|---|
| `openalex` | works, authors, institutions, sources, topics, concepts, funders, … | DOI, ORCID, ROR (all as full URIs) |
| `openaire` | publications, organizations, projects, datasets, software, relations, … | pids[{scheme,value}] array — scheme = `doi`, `orcid`, `ROR`, `pmid`, … |
| `cris` | publications | `cerif:DOI`, `repository_info.ror` |
| `openapc` | apc, bpc, transformative_agreements, apc_additional_costs | doi (plain string) |

## Identifier cheat-sheet

### DOI

```sql
-- OpenAlex: top-level field (full URI)
SELECT doi FROM lake.openalex.works WHERE doi = 'https://doi.org/10.1038/s41586-021-03819-2';

-- OpenAIRE: unnest pids array
SELECT id, p.value AS doi
FROM lake.openaire.publications,
     UNNEST(pids) AS p
WHERE p.scheme = 'doi' AND p.value = '10.1038/s41586-021-03819-2';

-- CRIS: direct column
SELECT "cerif:DOI" FROM lake.cris.publications WHERE "cerif:DOI" = '10.1038/s41586-021-03819-2';

-- OpenAPC: direct column
SELECT * FROM lake.openapc.apc WHERE doi = '10.1038/s41586-021-03819-2';
```

### ORCID

```sql
-- OpenAlex authors table (full URI)
SELECT id, display_name, orcid FROM lake.openalex.authors WHERE orcid = 'https://orcid.org/0000-0001-7284-3590';

-- OpenAlex works — first author's ORCID
SELECT id, authorships[1].author.orcid FROM lake.openalex.works WHERE authorships[1].author.orcid IS NOT NULL LIMIT 5;

-- OpenAlex works — all authors ORCID via UNNEST
SELECT w.id, a.author.orcid
FROM lake.openalex.works w, UNNEST(w.authorships) AS a
WHERE a.author.orcid IS NOT NULL LIMIT 10;

-- OpenAIRE publications — author pid
SELECT id, a.fullName, a.pid.id.value AS orcid
FROM lake.openaire.publications, UNNEST(authors) AS a
WHERE a.pid.id.scheme = 'orcid' LIMIT 5;
```

### ROR

```sql
-- OpenAlex institutions (full URI)
SELECT id, display_name, ror FROM lake.openalex.institutions WHERE ror = 'https://ror.org/027m9bs27';

-- OpenAlex works — institution ROR via UNNEST
SELECT w.id, inst.ror, inst.display_name
FROM lake.openalex.works w,
     UNNEST(w.authorships) AS a,
     UNNEST(a.institutions) AS inst
WHERE inst.ror IS NOT NULL LIMIT 10;

-- OpenAIRE organizations
SELECT id, legalName, p.value AS ror
FROM lake.openaire.organizations, UNNEST(pids) AS p
WHERE p.scheme = 'ROR' LIMIT 5;

-- CRIS: repository ROR
SELECT repository, repository_info.ror FROM lake.cris.publications WHERE repository_info.ror IS NOT NULL LIMIT 5;
```

## Unnesting STRUCT arrays — general pattern

```sql
-- UNNEST turns STRUCT[] into rows; dot-notation accesses nested fields
SELECT w.id, auth.author.display_name, auth.author.orcid, auth.author_position
FROM lake.openalex.works w, UNNEST(w.authorships) AS auth
LIMIT 20;

-- Nested STRUCT within array (institution inside authorship)
SELECT w.id, auth.author.orcid, inst.ror, inst.display_name
FROM lake.openalex.works w,
     UNNEST(w.authorships) AS auth,
     UNNEST(auth.institutions) AS inst
LIMIT 10;

-- OpenAIRE pids (scheme/value pattern)
SELECT id, p.scheme, p.value
FROM lake.openaire.publications, UNNEST(pids) AS p
LIMIT 10;
```

## Scalar STRUCT field access (no UNNEST)

```sql
-- primary_location is a single STRUCT, not an array — use dot notation
SELECT id, primary_location.source.display_name, primary_location.license
FROM lake.openalex.works LIMIT 5;

-- open_access struct
SELECT id, open_access.oa_status, open_access.oa_url
FROM lake.openalex.works WHERE open_access.is_oa = true LIMIT 5;

-- geo struct on institutions
SELECT display_name, geo.city, geo.country, geo.latitude, geo.longitude
FROM lake.openalex.institutions LIMIT 5;
```

## describe_table_detailed helper

For enriched column documentation run:

```bash
python scripts/describe_table_detailed.py openalex works
```

This combines live `DESCRIBE` output with curated human-readable descriptions.

## References

- [Connection details & auth patterns](references/connection.md)
- [All schemas, tables, and columns](references/schemas.md)
- [Query patterns and unnesting cookbook](references/patterns.md)
