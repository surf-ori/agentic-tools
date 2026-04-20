# DuckLake connection reference

## Default catalog (public, no auth)

```
https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake
```

This is the "Frozen DuckLake" pattern: a `.ducklake` file (DuckDB catalog) served over HTTPS, with Parquet data files in the same object-store bucket. No credentials needed for read access.

## Override via env var

```bash
export DUCKLAKE_URL="https://objectstore.surf.nl/<bucket>/<path>/catalog.ducklake"
ducklake-mcp
```

Or for a local catalog during development:

```bash
export DUCKLAKE_URL="/path/to/local/catalog.ducklake"
```

## Attach manually in DuckDB (no MCP)

```sql
INSTALL ducklake;
LOAD ducklake;
INSTALL httpfs;
LOAD httpfs;

ATTACH 'ducklake:https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake'
  AS lake (READ_ONLY, CREATE_IF_NOT_EXISTS false);

USE lake;
SHOW TABLES;
```

Requires DuckDB >= 1.5.2 (ships the `ducklake` extension for spec v1.0).

## SURF Object Store endpoints

| Environment | Base URL |
|---|---|
| Production | `https://objectstore.surf.nl/` |
| S3-compatible API | `https://objectstore.surf.nl/` (path-style) |

For private buckets, set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` or use the SURF SURFdrive token flow. The Sprouts catalog is public and needs no credentials.

## Troubleshooting

**`Cannot open database in read-only mode: database does not exist`**
The URL is wrong or not publicly accessible. Test with:
```bash
curl -I "https://objectstore.surf.nl/cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake"
```

**`Catalog version mismatch`**
You need DuckDB >= 1.5.2. Upgrade: `pip install -U "duckdb>=1.5.2"`.

**`Required module 'pytz' failed to import`**
Run `pip install pytz` (it's in the package dependencies but may be missing in a bare env).
