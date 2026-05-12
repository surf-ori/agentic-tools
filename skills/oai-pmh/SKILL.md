---
name: oai-pmh
description: >
  Use this skill when the user wants to harvest, inspect, or work with OAI-PMH
  metadata from Dutch or OpenAIRE-compatible repositories. Trigger on phrases
  like "harvest metadata", "OAI-PMH endpoint", "ListRecords", "ListSets",
  "NARCIS", "DAREnet", "Datacite OAI", or "OpenAIRE aggregator". Also load
  when writing Python scripts that use the Sickle library or the requests library
  to call an OAI-PMH feed.
---

# OAI-PMH harvesting skill — SURF ORI

## Overview

OAI-PMH (Open Archives Initiative Protocol for Metadata Harvesting) is the standard protocol for bulk metadata export from repository systems. Most Dutch institutional repositories (DSpace, Pure, EPrints) expose an OAI-PMH endpoint.

## Standard verbs

| Verb | Purpose |
|---|---|
| `Identify` | Repository name, admin email, earliest datestamp |
| `ListSets` | Available sets (faculties, types, …) |
| `ListMetadataFormats` | Supported schemas (`oai_dc`, `oai_openaire`, `datacite`, …) |
| `ListIdentifiers` | Lightweight list of record IDs (use for incremental harvesting) |
| `ListRecords` | Full metadata records |
| `GetRecord` | Single record by identifier |

## List of OAI-PMH Endpoints
Most Dutch repositories expose an OAI-PMH endpoint at `/oai` or `/oai-pmh`. For example:
- VU Research portal: ["https://research.vu.nl/ws/oai"]
- Leiden University Scholarly Publications Repository: ["https://scholarlypublications.universiteitleiden.nl/oai2"]

The full list of active Dutch OAI-PMH endpoints is maintained in 
https://zenodo.org/api/records/19470205/files/nl_orgs_openaire_datasources_with_endpoint_public.xlsx/content  
to check for updates: see https://zenodo.org/records/19470205/export/json for a machine-readable list. 
when "is_latest": false, then check "latest": "https://zenodo.org/api/records/19470205/versions/latest" for the most recent version. under "files", "entries" with "key": "nl_orgs_openaire_datasources_with_endpoint_public.xlsx" will have the file download link, under link "links": "content": "https://zenodo.org/api/records/{record_id}/files/nl_orgs_openaire_datasources_with_endpoint_public.xlsx/content".
in column "oai_endpoint" contains a list of OAI-PMH endpoints for each repository, which can be used for harvesting metadata. e.g. ["https://pure.buas.nl/ws/oai"]

## Python with Sickle

```python
from sickle import Sickle

sickle = Sickle("https://repository.example.nl/oai")

# Inspect the repository
identify = sickle.Identify()
print(identify.repositoryName, identify.earliestDatestamp)

# List available sets
for s in sickle.ListSets():
    print(s.setSpec, s.setName)

# Harvest records (with resumption token handling built in)
records = sickle.ListRecords(
    metadataPrefix="oai_dc",
    set="col_20.500.12345_1",        # optional set filter
    from_="2024-01-01",              # incremental harvest
)
for rec in records:
    print(rec.header.identifier, rec.metadata.get("title"))
```

## Common Dutch endpoints

See `references/endpoints.md` for a list of active Dutch OAI-PMH endpoints.

## Error handling

```python
from sickle.oaiexceptions import NoRecordsMatch, BadArgument

try:
    records = sickle.ListRecords(metadataPrefix="oai_dc", set="nonexistent")
except NoRecordsMatch:
    print("No records for this filter")
```

Sickle handles `resumptionToken` pagination automatically — do not implement it yourself.
