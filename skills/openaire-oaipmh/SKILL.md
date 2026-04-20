---
name: openaire-oaipmh
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
