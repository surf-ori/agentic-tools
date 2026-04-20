# Query patterns & unnesting cookbook — Sprouts DuckLake

Verified against live data (DuckDB 1.5.2, 2026-04-20).

---

## 1  Exploration workflow

```sql
-- What schemas exist?
SELECT schema_name FROM information_schema.schemata
WHERE catalog_name = 'lake' AND schema_name NOT IN ('information_schema','pg_catalog');

-- Tables in a schema
SELECT table_name, table_type FROM information_schema.tables
WHERE table_catalog = 'lake' AND table_schema = 'openalex';

-- Column types for a table
DESCRIBE lake.openalex.works;

-- Quick row peek
FROM lake.openalex.works LIMIT 3;
```

---

## 2  Identifier look-ups

### 2.1  DOI

```sql
-- OpenAlex: top-level doi column (full URI)
SELECT id, title, publication_year
FROM lake.openalex.works
WHERE doi = 'https://doi.org/10.1038/s41586-021-03819-2';

-- OpenAIRE: pids is a STRUCT[] — unnest to filter by scheme
SELECT pub.id, pub.mainTitle, p.value AS doi
FROM lake.openaire.publications AS pub,
     UNNEST(pub.pids) AS p
WHERE p.scheme = 'doi'
  AND p.value  = '10.1038/s41586-021-03819-2';

-- CRIS: direct column (no URI prefix)
SELECT "cerif:DOI", "cerif:Title"[1]["#text"] AS title
FROM lake.cris.publications
WHERE "cerif:DOI" = '10.1038/s41586-021-03819-2';

-- OpenAPC: direct column
SELECT institution, period, euro
FROM lake.openapc.apc
WHERE doi = '10.1038/s41586-021-03819-2';
```

### 2.2  ORCID

```sql
-- OpenAlex authors table (full URI)
SELECT id, display_name, works_count, cited_by_count
FROM lake.openalex.authors
WHERE orcid = 'https://orcid.org/0000-0001-7284-3590';

-- OpenAlex works: unnest authorships to find works by ORCID
SELECT w.id, w.doi, w.title
FROM lake.openalex.works AS w, UNNEST(w.authorships) AS a
WHERE a.author.orcid = 'https://orcid.org/0000-0001-7284-3590';

-- OpenAIRE publications: author pid (scheme='orcid', bare id without URI)
SELECT pub.id, pub.mainTitle, a.fullName
FROM lake.openaire.publications AS pub, UNNEST(pub.authors) AS a
WHERE a.pid.id.scheme = 'orcid'
  AND a.pid.id.value  = '0000-0001-7284-3590';
```

### 2.3  ROR

```sql
-- OpenAlex institutions (full URI)
SELECT id, display_name, country_code, type, works_count
FROM lake.openalex.institutions
WHERE ror = 'https://ror.org/027m9bs27';

-- OpenAlex works: institutions via authorships → institutions
SELECT DISTINCT w.id, w.title, inst.display_name
FROM lake.openalex.works AS w,
     UNNEST(w.authorships) AS a,
     UNNEST(a.institutions) AS inst
WHERE inst.ror = 'https://ror.org/027m9bs27'
LIMIT 20;

-- OpenAIRE organizations (scheme='ROR', full URI)
SELECT id, legalName, p.value AS ror
FROM lake.openaire.organizations, UNNEST(pids) AS p
WHERE p.scheme = 'ROR'
  AND p.value  = 'https://ror.org/027m9bs27';

-- CRIS: repository-level ROR
SELECT DISTINCT repository, repository_info.ror, repository_info.institution
FROM lake.cris.publications
WHERE repository_info.ror IS NOT NULL
LIMIT 10;
```

---

## 3  Unnesting STRUCT arrays

### 3.1  Authorships in openalex.works

```sql
-- One row per author per work
SELECT
    w.id          AS work_id,
    w.doi,
    a.author.orcid,
    a.author.display_name,
    a.author_position,
    a.is_corresponding
FROM lake.openalex.works AS w,
     UNNEST(w.authorships) AS a
WHERE w.publication_year = 2023
LIMIT 50;
```

### 3.2  Author → institution (two-level unnest)

```sql
-- One row per author × institution per work
SELECT
    w.id   AS work_id,
    w.doi,
    a.author.orcid,
    inst.ror,
    inst.display_name   AS institution,
    inst.country_code
FROM lake.openalex.works AS w,
     UNNEST(w.authorships) AS a,
     UNNEST(a.institutions) AS inst
WHERE inst.country_code = 'NL'
LIMIT 20;
```

### 3.3  OpenAIRE publication PIDs

```sql
-- All identifier schemes for a publication
SELECT pub.id, pub.mainTitle, p.scheme, p.value
FROM lake.openaire.publications AS pub,
     UNNEST(pub.pids) AS p
WHERE pub.id = 'doi_dedup__::abc123'
LIMIT 20;

-- Publications that have a DOI
SELECT pub.id, pub.mainTitle, p.value AS doi
FROM lake.openaire.publications AS pub,
     UNNEST(pub.pids) AS p
WHERE p.scheme = 'doi'
LIMIT 10;
```

### 3.4  OpenAIRE organizations: ROR from pids

```sql
SELECT o.id, o.legalName, p.value AS ror
FROM lake.openaire.organizations AS o,
     UNNEST(o.pids) AS p
WHERE p.scheme = 'ROR'
LIMIT 10;
```

### 3.5  OpenAIRE publication → project (funders)

```sql
SELECT
    pub.id          AS pub_id,
    pub.mainTitle,
    proj.code       AS grant_code,
    proj.acronym,
    f.shortName     AS funder,
    f.jurisdiction
FROM lake.openaire.publications AS pub,
     UNNEST(pub.projects)  AS proj,
     UNNEST(proj.fundings) AS f
WHERE f.jurisdiction = 'NL'
LIMIT 20;
```

### 3.6  CRIS authors (deeply nested CERIF)

```sql
-- Author names from CRIS
SELECT
    p.repository,
    p."cerif:DOI",
    a["cerif:Person"]["cerif:PersonName"]["cerif:FamilyNames"] AS family,
    a["cerif:Person"]["cerif:PersonName"]["cerif:FirstNames"]  AS given
FROM lake.cris.publications AS p,
     UNNEST(p."cerif:Authors"["cerif:Author"]) AS a
LIMIT 20;

-- Multilingual title (take first element, English preferred)
SELECT
    "cerif:DOI",
    "cerif:Title"[1]["#text"] AS title
FROM lake.cris.publications
WHERE "cerif:DOI" IS NOT NULL
LIMIT 10;
```

---

## 4  Scalar STRUCT access (no UNNEST)

```sql
-- open_access is a single STRUCT field (not an array)
SELECT id, open_access.is_oa, open_access.oa_status, open_access.oa_url
FROM lake.openalex.works
WHERE open_access.oa_status = 'gold'
LIMIT 10;

-- primary_location (single STRUCT)
SELECT id, primary_location.source.display_name, primary_location.license
FROM lake.openalex.works
WHERE primary_location.source.is_oa = true
LIMIT 10;

-- biblio
SELECT id, biblio.volume, biblio.issue, biblio.first_page
FROM lake.openalex.works
WHERE biblio.volume IS NOT NULL
LIMIT 5;

-- institution geo
SELECT display_name, geo.city, geo.country, geo.latitude, geo.longitude
FROM lake.openalex.institutions
WHERE country_code = 'NL'
ORDER BY works_count DESC LIMIT 10;

-- openaire indicators
SELECT id, mainTitle,
       indicators.citationImpact.citationCount,
       indicators.usageCounts.downloads
FROM lake.openaire.publications
WHERE indicators.citationImpact.citationCount > 100
LIMIT 10;
```

---

## 5  Aggregations

```sql
-- Dutch NL institutions by type
SELECT type, COUNT(*) AS n
FROM lake.openalex.institutions
WHERE country_code = 'NL'
GROUP BY type ORDER BY n DESC;

-- OpenAPC: average APC by publisher (top 10)
SELECT publisher, ROUND(AVG(euro),2) AS avg_eur, COUNT(*) AS n
FROM lake.openapc.apc
GROUP BY publisher ORDER BY n DESC LIMIT 10;

-- OpenAPC: Dutch institutional APC spend by year
SELECT institution, period, SUM(euro) AS total_eur, COUNT(*) AS articles
FROM lake.openapc.apc
WHERE institution LIKE '%Netherlands%' OR institution LIKE '%Utrecht%'
   OR institution LIKE '%Amsterdam%'  OR institution LIKE '%Delft%'
GROUP BY institution, period ORDER BY institution, period;

-- OA status breakdown in OpenAIRE
SELECT openAccessColor, COUNT(*) AS n
FROM lake.openaire.publications
GROUP BY openAccessColor ORDER BY n DESC;

-- Publication types in CRIS
SELECT "pubt:Type"["#text"] AS pub_type, COUNT(*) AS n
FROM lake.cris.publications
GROUP BY 1 ORDER BY n DESC LIMIT 10;
```

---

## 6  Cross-schema joins via DOI

```sql
-- Enrich OpenAPC APC record with OpenAlex citation data
SELECT
    apc.doi,
    apc.institution,
    apc.euro,
    apc.period,
    w.cited_by_count,
    w.open_access.oa_status
FROM lake.openapc.apc AS apc
JOIN lake.openalex.works AS w
  ON 'https://doi.org/' || apc.doi = w.doi
WHERE apc.institution LIKE '%Utrecht%'
LIMIT 20;

-- CRIS publication enriched with OpenAIRE OA colour
SELECT
    c."cerif:DOI" AS doi,
    c."cerif:Title"[1]["#text"] AS title,
    c.repository_info.institution,
    p.value AS oa_pid,
    pub.openAccessColor
FROM lake.cris.publications AS c
JOIN lake.openaire.publications AS pub
  ON pub.id LIKE '%' || c."cerif:DOI" || '%'   -- approximate; prefer pids join below
LEFT JOIN LATERAL (
    SELECT value FROM UNNEST(pub.pids) WHERE scheme = 'doi' LIMIT 1
) AS p ON true
WHERE c."cerif:DOI" IS NOT NULL
LIMIT 10;

-- Proper cross-schema DOI join (openapc ↔ openaire)
SELECT
    apc.doi, apc.euro, apc.institution,
    pub.openAccessColor, pub.isGreen
FROM lake.openapc.apc AS apc
JOIN (
    SELECT pub.id, pub.openAccessColor, pub.isGreen, p.value AS doi
    FROM lake.openaire.publications AS pub, UNNEST(pub.pids) AS p
    WHERE p.scheme = 'doi'
) AS pub ON pub.doi = apc.doi
LIMIT 20;
```

---

## 7  Full-text search on abstract (openalex inverted index)

```sql
-- Decode abstract from inverted index for specific works
SELECT id, title,
       MAP_KEYS(abstract_inverted_index) AS words
FROM lake.openalex.works
WHERE id = 'https://openalex.org/W2741809807';
```

---

## 8  Time travel

```sql
-- Available snapshots
FROM ducklake_snapshots('lake');

-- Query at a specific snapshot version
SELECT COUNT(*) FROM lake.openalex.works AT (VERSION => 2);
```
