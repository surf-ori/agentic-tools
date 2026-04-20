# Schemas, tables and columns — Sprouts DuckLake

Last verified: 2026-04-20.  Run `list_schemas` / `list_tables` / `describe_table` for the live picture.

---

## openalex

OpenAlex global research catalog — works, authors, institutions and more.
Source: https://openalex.org

### openalex.works — 364 M rows

Core publication/output record. Heavily nested.

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | OpenAlex URI, e.g. `https://openalex.org/W2741809807` |
| `doi` | VARCHAR | Full DOI URI, e.g. `https://doi.org/10.1038/…` |
| `title` / `display_name` | VARCHAR | Title text |
| `publication_date` | DATE | |
| `publication_year` | BIGINT | |
| `type` | VARCHAR | `article`, `book-chapter`, `dataset`, … |
| `language` | VARCHAR | BCP-47 code |
| `ids` | STRUCT | `.openalex`, `.doi`, `.mag`, `.pmid`, `.pmcid` |
| `authorships` | STRUCT[] | See below — authors + institutions per work |
| `primary_location` | STRUCT | `.source.display_name`, `.license`, `.is_oa`, `.pdf_url` |
| `locations` | STRUCT[] | All locations (repositories, journals) |
| `best_oa_location` | STRUCT | Best open-access copy |
| `open_access` | STRUCT | `.is_oa`, `.oa_status`, `.oa_url` |
| `primary_topic` | STRUCT | `.id`, `.display_name`, `.subfield`, `.field`, `.domain` |
| `topics` | STRUCT[] | All assigned topics |
| `concepts` | STRUCT[] | `.id`, `.display_name`, `.level`, `.score` |
| `keywords` | STRUCT[] | `.id`, `.display_name`, `.score` |
| `funders` | STRUCT[] | `.id`, `.display_name`, `.ror` |
| `awards` | STRUCT[] | `.funder_id`, `.funder_display_name`, `.funder_award_id` |
| `sustainable_development_goals` | STRUCT[] | `.id`, `.display_name`, `.score` |
| `cited_by_count` | BIGINT | |
| `fwci` | DOUBLE | Field-weighted citation impact |
| `apc_list` / `apc_paid` | STRUCT | `.value`, `.currency`, `.value_usd` |
| `biblio` | STRUCT | `.volume`, `.issue`, `.first_page`, `.last_page` |
| `mesh` | STRUCT[] | MeSH descriptors |
| `abstract_inverted_index` | MAP | Inverted index of abstract — use `list_value` to decode |
| `referenced_works` | VARCHAR[] | OpenAlex IDs of references |
| `is_retracted` / `is_paratext` | BOOLEAN | |

**`authorships` STRUCT layout:**
```
authorships[]
  .author.id           -- OpenAlex author URI
  .author.display_name
  .author.orcid        -- full ORCID URI
  .author_position     -- 'first', 'middle', 'last'
  .is_corresponding    -- BOOLEAN
  .raw_author_name
  .institutions[]
    .id                -- OpenAlex institution URI
    .display_name
    .ror               -- full ROR URI
    .country_code
    .type
  .affiliations[]
    .institution_ids[] -- list of OpenAlex institution URIs
    .raw_affiliation_string
```

### openalex.authors — 110 M rows

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | OpenAlex URI |
| `display_name` | VARCHAR | |
| `orcid` | VARCHAR | Full ORCID URI |
| `works_count` | BIGINT | |
| `cited_by_count` | BIGINT | |
| `ids` | STRUCT | `.openalex`, `.orcid`, `.scopus`, `.twitter`, `.wikipedia` |
| `affiliations` | STRUCT[] | `.institution.ror`, `.institution.display_name`, `.years[]` |
| `last_known_institutions` | STRUCT[] | `.id`, `.ror`, `.display_name`, `.country_code`, `.type` |
| `summary_stats` | STRUCT | `.h_index`, `.i10_index`, `.2yr_mean_citedness` |
| `topics` | STRUCT[] | Research topics |
| `counts_by_year` | STRUCT[] | `.year`, `.works_count`, `.cited_by_count` |

### openalex.institutions — 120 K rows

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | OpenAlex URI |
| `ror` | VARCHAR | Full ROR URI, e.g. `https://ror.org/027m9bs27` |
| `display_name` | VARCHAR | |
| `country_code` | VARCHAR | ISO 3166-1 alpha-2 |
| `type` | VARCHAR | `education`, `company`, `government`, `nonprofit`, … |
| `ids` | STRUCT | `.openalex`, `.ror`, `.grid`, `.wikipedia`, `.wikidata` |
| `geo` | STRUCT | `.city`, `.country`, `.latitude`, `.longitude` |
| `associated_institutions` | STRUCT[] | `.ror`, `.display_name`, `.relationship` |
| `summary_stats` | STRUCT | `.h_index`, `.i10_index` |
| `repositories` | STRUCT[] | Institutional repositories |
| `lineage` | VARCHAR[] | Parent institution IDs |

### openalex other tables

| Table | Rows | Key columns |
|---|---|---|
| `sources` | ~250 K | Journal/repository. `issn_l`, `is_in_doaj`, `is_core`, `type` |
| `funders` | ~33 K | `ror`, `ids.ror`, `ids.crossref` |
| `topics` | ~4 600 | `id`, `display_name`, `subfield.id`, `field.id`, `domain.id` |
| `concepts` | ~65 K | `id`, `wikidata`, `level`, `works_count` |
| `domains` / `fields` / `subfields` | — | Taxonomy hierarchy |
| `publishers` | ~10 K | `ids.ror`, `ids.wikidata` |
| `sdgs` | 17 | UN Sustainable Development Goals |
| `countries` / `continents` | — | Geographic lookup |
| `awards` | — | Grant award metadata |

---

## openaire

OpenAIRE Graph — aggregated European open science outputs.
Source: https://graph.openaire.eu

### openaire.publications — 206 M rows

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | OpenAIRE internal ID |
| `mainTitle` | VARCHAR | |
| `publicationDate` | DATE | |
| `type` | VARCHAR | `publication`, `dataset`, … |
| `pids` | STRUCT[] | `{scheme, value}` — scheme = `doi`, `pmid`, `pmc`, `handle`, `arxiv`, … |
| `authors` | STRUCT[] | See below |
| `language` | STRUCT | `.code`, `.label` |
| `bestAccessRight` | STRUCT | `.code` (`OPEN`, `RESTRICTED`, …), `.label` |
| `container` | STRUCT | `.name`, `.issnPrinted`, `.issnOnline`, `.vol`, `.iss` |
| `instances` | STRUCT[] | `.urls[]`, `.license`, `.accessRight.openAccessRoute` |
| `projects` | STRUCT[] | Linked funding projects — `.code`, `.acronym`, `.fundings[].shortName` |
| `organizations` | STRUCT[] | Linked orgs — `.legalName`, `.pids[{scheme,value}]` |
| `indicators` | STRUCT | `.citationImpact.citationCount`, `.usageCounts.downloads` |
| `isGreen` | BOOLEAN | Green OA |
| `isInDiamondJournal` | BOOLEAN | |
| `openAccessColor` | VARCHAR | `gold`, `green`, `bronze`, `closed` |
| `collectedfrom` | STRUCT[] | Source datasource `{key, value}` |

**`authors` STRUCT layout:**
```
authors[]
  .fullName
  .name / .surname / .rank
  .pid
    .id.scheme    -- 'orcid', 'mag', …
    .id.value     -- e.g. '0000-0001-7284-3590'
    .provenance.provenance
    .provenance.trust
```

### openaire.organizations — 448 K rows

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | OpenAIRE internal ID |
| `legalName` | VARCHAR | |
| `legalShortName` | VARCHAR | |
| `country` | STRUCT | `.code`, `.label` |
| `pids` | STRUCT[] | `{scheme, value}` — scheme = `ROR`, `FundRef`, `ISNI`, `GRID`, `Wikidata` |
| `websiteUrl` | VARCHAR | |
| `alternativeNames` | VARCHAR[] | |

### openaire.projects — 3.7 M rows

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | |
| `code` | VARCHAR | Grant number |
| `acronym` | VARCHAR | |
| `title` | VARCHAR | |
| `startDate` / `endDate` | DATE | |
| `fundings` | STRUCT[] | `.shortName`, `.name`, `.jurisdiction`, `.fundingStream.id` |
| `granted` | STRUCT | `.totalCost`, `.fundedAmount`, `.currency` |
| `h2020Programmes` | STRUCT[] | `.code`, `.description` |
| `openAccessMandateForPublications` | BOOLEAN | |
| `subjects` | VARCHAR[] | |

### openaire other tables

| Table | Rows | Description |
|---|---|---|
| `datasets` | — | Research datasets (same pids pattern as publications) |
| `software` | — | Software outputs |
| `otherresearchproducts` | — | Other outputs (preprints, reports, …) |
| `relations` | — | Links between graph entities |
| `datasources` | — | Data sources / repositories |
| `communities_infrastructures` | — | OpenAIRE communities |

---

## cris

CRIS (Current Research Information System) publications harvested via OAI-PMH from Dutch institutional repositories (Pure/DSpace). CERIF-XML schema flattened to DuckDB.

### cris.publications — 2.4 M rows

| Column | Type | Notes |
|---|---|---|
| `repository` | VARCHAR | Source repository identifier |
| `repository_info` | STRUCT | `.url`, `.name`, `.type`, `.institution`, `.ror` |
| `header` | STRUCT | `.identifier` (OAI handle), `.datestamp`, `.setSpec` |
| `cerif:DOI` | VARCHAR | DOI string (no `https://doi.org/` prefix) |
| `cerif:Handle` | VARCHAR | Handle URI |
| `cerif:URL` | VARCHAR | Landing page URL |
| `cerif:Title` | STRUCT[] | `{@xml:lang, #text}` — multilingual |
| `cerif:Abstract` | STRUCT[] | `{@xml:lang, #text}` — multilingual |
| `cerif:PublicationDate` | VARCHAR | Free text, not always parseable as DATE |
| `cerif:Authors` | STRUCT | Nested CERIF author list — see below |
| `cerif:ISSN` | STRUCT[] | `{@medium, #text}` |
| `cerif:ISBN` | STRUCT[] | `{@medium, #text}` |
| `ar:Access` | VARCHAR | Access rights string |
| `pubt:Type` | STRUCT | `.#text` = publication type |
| `cerif:Keyword` | STRUCT[] | `{@xml:lang, #text}` |
| `cerif:PresentedAt` | STRUCT[] | Conference info — `.cerif:Event.cerif:Name[0].#text` |

**`cerif:Authors` STRUCT layout:**
```
cerif:Authors
  .cerif:Author[]
    .cerif:Person
      .@id               -- UUID (internal CRIS person ID)
      .cerif:PersonName
        .cerif:FamilyNames
        .cerif:FirstNames
    .cerif:Affiliation[]
      .cerif:OrgUnit
        .@id             -- UUID
        .cerif:Acronym
        .cerif:Name[]    -- {#text}
```

> Note: CRIS does not expose ORCID — use `cerif:Person.@id` (UUID) as the person identifier within this dataset. Cross-link to OpenAlex/OpenAIRE via DOI.

---

## openapc

OpenAPC — article and book processing charges paid by institutions for open access.
Source: https://openapc.net

### openapc.apc — 261 K rows

Article Processing Charges for journal articles.

| Column | Type | Notes |
|---|---|---|
| `doi` | VARCHAR | Plain DOI string, e.g. `10.1371/journal.pone.0000001` |
| `institution` | VARCHAR | Paying institution name |
| `period` | BIGINT | Year of payment |
| `euro` | DOUBLE | APC amount in EUR |
| `is_hybrid` | BOOLEAN | Hybrid journal? |
| `publisher` | VARCHAR | |
| `journal_full_title` | VARCHAR | |
| `issn` / `issn_print` / `issn_electronic` / `issn_l` | VARCHAR | |
| `license_ref` | VARCHAR | e.g. `CC BY 4.0` |
| `indexed_in_crossref` | BOOLEAN | |
| `pmid` / `pmcid` / `ut` | VARCHAR | Other identifiers |
| `url` | VARCHAR | Landing page |
| `doaj` | BOOLEAN | In DOAJ? |

### openapc.bpc — 2 355 rows

Book Processing Charges.

| Column | Type | Notes |
|---|---|---|
| `doi` | VARCHAR | |
| `institution` | VARCHAR | |
| `period` | BIGINT | |
| `euro` | DOUBLE | |
| `publisher` | VARCHAR | |
| `book_title` | VARCHAR | |
| `isbn` / `isbn_print` / `isbn_electronic` | VARCHAR | |
| `license_ref` | VARCHAR | |
| `backlist_oa` | BOOLEAN | |
| `doab` | BOOLEAN | In DOAB? |

### openapc.transformative_agreements — rows vary

Transformative agreements (read-and-publish deals).

| Column | Type | Notes |
|---|---|---|
| `doi` | VARCHAR | |
| `institution` | VARCHAR | |
| `period` | BIGINT | |
| `euro` | DOUBLE | |
| `agreement` | VARCHAR | Agreement name/code |
| `publisher` | VARCHAR | |
| `journal_full_title` | VARCHAR | |

### openapc.apc_additional_costs

Additional costs beyond the APC (colour charges, page charges, etc.).
