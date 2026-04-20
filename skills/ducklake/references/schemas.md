# Known schemas and tables — Sprouts DuckLake

Run `list_schemas` / `list_tables` to get the live picture. This file documents what was present at the time of writing (2026-04-20). Confirmed schemas: `cris`, `main`, `openaire`, `openalex`, `openapc`.

## openalex

OpenAlex is an open catalog of global research (works, authors, institutions, venues, concepts). Derived from the OpenAlex data dump.

| Table | Description | Key columns |
|---|---|---|
| `institutions` | Research organisations | `id`, `display_name`, `ror`, `country_code`, `type`, `cited_by_count` |
| `works` | Publications (articles, books, datasets, …) | `id`, `doi`, `title`, `publication_year`, `type`, `cited_by_count` |
| `authors` | Researcher profiles | `id`, `display_name`, `orcid`, `works_count`, `cited_by_count` |
| `concepts` | Subject/field taxonomy | `id`, `display_name`, `level`, `works_count` |
| `venues` | Journals and repositories | `id`, `display_name`, `issn`, `type` |

Fully-qualified example: `lake.openalex.institutions`

## Useful joins

```sql
-- Works with their primary institution (via authorships array)
SELECT w.title, w.publication_year,
       inst.display_name AS institution
FROM lake.openalex.works w,
     UNNEST(w.authorships) AS a(authorship),
     UNNEST(authorship.institutions) AS i(inst_id)
JOIN lake.openalex.institutions inst ON inst.id = i.inst_id
WHERE inst.country_code = 'NL'
LIMIT 100
```

> Note: `authorships` and similar columns are DuckDB `STRUCT[]` / `LIST` types. Use `UNNEST` to expand them.
