"""
describe_table_detailed.py

Combines live DESCRIBE output from DuckLake with curated human-readable
column documentation, then prints an enriched data dictionary.

Usage:
    python scripts/describe_table_detailed.py <schema> <table>
    python scripts/describe_table_detailed.py openalex works
    python scripts/describe_table_detailed.py openaire publications
    python scripts/describe_table_detailed.py cris publications
    python scripts/describe_table_detailed.py openapc apc
"""

from __future__ import annotations

import json
import os
import sys

import duckdb

# ---------------------------------------------------------------------------
# Connection helpers (reuse connect_ducklake pattern)
# ---------------------------------------------------------------------------
DEFAULT_URL = (
    "https://objectstore.surf.nl/"
    "cea01a7216d64348b7e51e5f3fc1901d:sprouts/catalog.ducklake"
)


def get_con(url: str | None = None, alias: str = "lake") -> duckdb.DuckDBPyConnection:
    url = url or os.environ.get("DUCKLAKE_URL", DEFAULT_URL)
    con = duckdb.connect(":memory:")
    con.execute("INSTALL ducklake; LOAD ducklake;")
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(
        f"ATTACH 'ducklake:{url}' AS {alias} "
        f"(READ_ONLY, CREATE_IF_NOT_EXISTS false);"
    )
    con.execute(f"USE {alias};")
    return con


# ---------------------------------------------------------------------------
# Curated documentation dictionary
# Format: DOCS[schema][table][column] = description string
# ---------------------------------------------------------------------------
DOCS: dict[str, dict[str, dict[str, str]]] = {
    "openalex": {
        "works": {
            "id": "OpenAlex work URI, e.g. https://openalex.org/W2741809807",
            "doi": "Full DOI URI, e.g. https://doi.org/10.1038/…  Use this for cross-schema joins.",
            "title": "Primary title text",
            "display_name": "Display title (same as title for most records)",
            "ids": "STRUCT with .openalex, .doi, .mag, .pmid, .pmcid — alternative identifiers",
            "publication_date": "ISO date of first publication",
            "publication_year": "Year of first publication (integer)",
            "language": "BCP-47 language code, e.g. 'en', 'de'",
            "type": "Output type: article, book-chapter, dataset, preprint, …",
            "authorships": (
                "STRUCT[] — one element per author. "
                "Key paths: .author.orcid (full ORCID URI), .author.display_name, "
                ".author_position ('first'/'middle'/'last'), .is_corresponding, "
                ".institutions[].ror (full ROR URI). "
                "Use UNNEST(authorships) to expand into rows."
            ),
            "authors_count": "Number of authors",
            "primary_location": (
                "STRUCT (not array). "
                ".source.display_name = journal/repo name, "
                ".source.issn_l = linking ISSN, "
                ".license = SPDX licence string, "
                ".is_oa = open-access flag, "
                ".pdf_url = direct PDF link."
            ),
            "best_oa_location": "STRUCT — same shape as primary_location; best OA copy available",
            "open_access": ".is_oa BOOLEAN, .oa_status ('gold','green','bronze','closed'), .oa_url",
            "primary_topic": "STRUCT — top topic with .subfield, .field, .domain nested structs",
            "topics": "STRUCT[] — all assigned topics; UNNEST to expand",
            "concepts": "STRUCT[] — legacy concept tags with .level and .score",
            "keywords": "STRUCT[] — keyword tags with .score",
            "funders": "STRUCT[] — .id (OpenAlex), .display_name, .ror (full ROR URI)",
            "awards": "STRUCT[] — grant awards linked to this work",
            "sustainable_development_goals": "STRUCT[] — linked UN SDGs",
            "cited_by_count": "Total citations (OpenAlex count)",
            "fwci": "Field-Weighted Citation Impact (Elsevier metric)",
            "apc_list": "STRUCT — list-price APC: .value (int), .currency, .value_usd",
            "apc_paid": "STRUCT — actually-paid APC (from OpenAPC data)",
            "biblio": "STRUCT — .volume, .issue, .first_page, .last_page",
            "abstract_inverted_index": "MAP(word → position[]) — inverted index of abstract words",
            "referenced_works": "VARCHAR[] — list of OpenAlex work IDs cited by this work",
            "referenced_works_count": "Number of references",
            "mesh": "STRUCT[] — MeSH medical subject headings",
            "is_retracted": "TRUE if work has been retracted",
            "is_paratext": "TRUE if this is a front matter / table-of-contents entry",
            "counts_by_year": "STRUCT[] — .year, .cited_by_count — citation history",
            "locations": "STRUCT[] — all hosting locations (journal, repo, …)",
            "locations_count": "Number of locations",
        },
        "authors": {
            "id": "OpenAlex author URI",
            "display_name": "Author's primary name",
            "orcid": "Full ORCID URI, e.g. https://orcid.org/0000-0001-7284-3590",
            "works_count": "Number of works indexed in OpenAlex",
            "cited_by_count": "Total citations received",
            "ids": "STRUCT — .orcid, .scopus, .twitter, .wikipedia",
            "affiliations": (
                "STRUCT[] — institutional affiliations over time. "
                ".institution.ror (full ROR URI), .institution.display_name, .years[]"
            ),
            "last_known_institutions": "STRUCT[] — most recent institutions: .ror, .display_name, .country_code",
            "summary_stats": "STRUCT — .h_index, .i10_index, .2yr_mean_citedness",
            "topics": "STRUCT[] — research topics by activity",
            "counts_by_year": "STRUCT[] — .year, .works_count, .cited_by_count",
        },
        "institutions": {
            "id": "OpenAlex institution URI",
            "ror": "Full ROR URI, e.g. https://ror.org/027m9bs27 — primary persistent identifier",
            "display_name": "Institution name",
            "country_code": "ISO 3166-1 alpha-2, e.g. 'NL'",
            "type": "education, company, government, nonprofit, healthcare, facility, archive, other",
            "lineage": "VARCHAR[] — parent institution OpenAlex IDs",
            "geo": "STRUCT — .city, .country, .latitude, .longitude",
            "ids": "STRUCT — .ror, .grid, .wikipedia, .wikidata",
            "associated_institutions": "STRUCT[] — related organisations with .relationship type",
            "summary_stats": "STRUCT — .h_index, .i10_index",
            "works_count": "Number of associated works",
            "cited_by_count": "Total citations",
            "repositories": "STRUCT[] — institutional repositories",
        },
    },
    "openaire": {
        "publications": {
            "id": "OpenAIRE deduplication ID, e.g. doi_dedup__::abc123",
            "mainTitle": "Primary title",
            "publicationDate": "Date of publication (DATE type)",
            "type": "Publication type string",
            "pids": (
                "STRUCT[] — persistent identifiers. "
                "Use UNNEST(pids) to expand. "
                "Common schemes: doi, pmid, pmc, handle, arxiv, mag_id. "
                "Example: UNNEST(pids) AS p WHERE p.scheme = 'doi'"
            ),
            "authors": (
                "STRUCT[] — author list. "
                ".fullName, .name, .surname, .rank (position). "
                ".pid.id.scheme / .pid.id.value — author PID (scheme='orcid' → bare ORCID). "
                "Use UNNEST(authors) to expand."
            ),
            "bestAccessRight": "STRUCT — .code (OPEN/RESTRICTED/CLOSED), .label, .scheme",
            "openAccessColor": "gold, green, bronze, diamond, closed",
            "isGreen": "TRUE if green OA (repository copy available)",
            "isInDiamondJournal": "TRUE if published in a diamond OA journal",
            "container": "STRUCT — journal/book container: .name, .issnPrinted, .issnOnline, .vol, .iss",
            "instances": (
                "STRUCT[] — concrete access instances. "
                ".urls[] = landing/download URLs, "
                ".license = licence string, "
                ".accessRight.openAccessRoute = 'gold','green','hybrid','bronze'"
            ),
            "projects": (
                "STRUCT[] — linked funding projects. "
                ".code = grant number, .acronym, "
                ".fundings[].shortName = funder short name, "
                ".fundings[].jurisdiction = country/region"
            ),
            "organizations": "STRUCT[] — linked organisations: .legalName, .pids[{scheme,value}]",
            "indicators": "STRUCT — .citationImpact.citationCount, .usageCounts.downloads/.views",
            "language": "STRUCT — .code (ISO 639), .label",
            "subjects": "STRUCT[] — subject classifications",
            "collectedfrom": "STRUCT[] — source datasources {key, value}",
        },
        "organizations": {
            "id": "OpenAIRE internal organisation ID",
            "legalName": "Full legal name",
            "legalShortName": "Abbreviated name / acronym",
            "country": "STRUCT — .code (ISO 3166-1), .label",
            "pids": (
                "STRUCT[] — organisation identifiers. "
                "Use UNNEST(pids) AS p WHERE p.scheme = 'ROR' to get ROR. "
                "Known schemes: ROR (full URI), FundRef, ISNI, GRID, Wikidata"
            ),
            "alternativeNames": "VARCHAR[] — alternative organisation names",
        },
        "projects": {
            "id": "OpenAIRE project ID",
            "code": "Grant/project number assigned by funder",
            "acronym": "Project acronym",
            "title": "Project title",
            "startDate": "DATE",
            "endDate": "DATE",
            "fundings": (
                "STRUCT[] — funder info. "
                ".shortName = funder acronym (e.g. 'NWO', 'EC'), "
                ".jurisdiction = 'NL', 'EU', …, "
                ".fundingStream.id = programme identifier"
            ),
            "granted": "STRUCT — .totalCost, .fundedAmount, .currency",
            "openAccessMandateForPublications": "BOOLEAN — funder OA mandate applies",
            "h2020Programmes": "STRUCT[] — Horizon 2020 programme codes",
        },
    },
    "cris": {
        "publications": {
            "repository": "Source repository short identifier",
            "repository_info": "STRUCT — .url, .name, .type, .institution (name), .ror (full ROR URI)",
            "header": "STRUCT — .identifier (OAI-PMH handle), .datestamp (TIMESTAMP), .setSpec",
            "cerif:DOI": "DOI string without URI prefix, e.g. '10.1016/j.respo.2021.100082'",
            "cerif:Handle": "Handle URI, e.g. 'https://hdl.handle.net/…'",
            "cerif:URL": "Landing page URL",
            "cerif:Title": (
                "STRUCT[] — multilingual titles. "
                "Each element: {\"@xml:lang\": \"en\", \"#text\": \"The title\"}. "
                "Access first element with \"cerif:Title\"[1][\"#text\"]"
            ),
            "cerif:Abstract": "STRUCT[] — multilingual abstracts, same shape as cerif:Title",
            "cerif:PublicationDate": "Publication date as free-text string (not always a valid DATE)",
            "cerif:Authors": (
                "Nested CERIF author structure. "
                "Path to family name: "
                "[\"cerif:Author\"][n][\"cerif:Person\"][\"cerif:PersonName\"][\"cerif:FamilyNames\"]. "
                "Person UUID: [\"cerif:Author\"][n][\"cerif:Person\"][\"@id\"]. "
                "Use UNNEST(\"cerif:Authors\"[\"cerif:Author\"]) to expand."
            ),
            "cerif:DOI": "Plain DOI string (no https://doi.org/ prefix)",
            "cerif:ISSN": "STRUCT[] — {\"@medium\": \"print\"|\"electronic\", \"#text\": \"ISSN\"}",
            "pubt:Type": "STRUCT — [\"#text\"] = publication type string",
            "ar:Access": "Access rights string from the source CRIS",
            "cerif:Keyword": "STRUCT[] — keywords: {\"@xml:lang\", \"#text\"}",
            "cerif:PresentedAt": "STRUCT[] — conference event info",
        },
    },
    "openapc": {
        "apc": {
            "doi": "Plain DOI string, e.g. '10.1371/journal.pone.0000001'. Join to other schemas with 'https://doi.org/' || doi",
            "institution": "Name of the institution that paid the APC",
            "period": "Year the APC was paid (integer)",
            "euro": "APC amount in EUR (DOUBLE)",
            "is_hybrid": "TRUE if published in a hybrid journal (subscription + OA)",
            "publisher": "Publisher name",
            "journal_full_title": "Full journal title",
            "issn": "Primary ISSN",
            "issn_l": "Linking ISSN",
            "license_ref": "SPDX licence identifier, e.g. 'CC BY 4.0'",
            "indexed_in_crossref": "TRUE if DOI is registered in Crossref",
            "pmid": "PubMed ID (string)",
            "pmcid": "PubMed Central ID (string)",
            "doaj": "TRUE if journal is in DOAJ",
        },
        "bpc": {
            "doi": "Plain DOI string for the book",
            "institution": "Paying institution",
            "period": "Year of payment",
            "euro": "BPC amount in EUR",
            "book_title": "Book title",
            "isbn": "Primary ISBN",
            "license_ref": "SPDX licence identifier",
            "backlist_oa": "TRUE if this is a backlist open-access conversion",
            "doab": "TRUE if book is in DOAB (Directory of Open Access Books)",
        },
        "transformative_agreements": {
            "doi": "Plain DOI string",
            "institution": "Participating institution",
            "period": "Year",
            "euro": "APC equivalent amount in EUR",
            "agreement": "Name/code of the transformative agreement",
            "publisher": "Publisher",
            "journal_full_title": "Journal title",
        },
    },
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def describe_table_detailed(schema: str, table: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {schema}.{table}")
    print(f"{'='*70}\n")

    con = get_con()

    # Live column metadata from DuckDB
    rows = con.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_catalog = 'lake'
          AND table_schema  = ?
          AND table_name    = ?
        ORDER BY ordinal_position
        """,
        [schema, table],
    ).fetchall()

    if not rows:
        print(f"ERROR: table lake.{schema}.{table} not found.")
        return

    # Row count
    try:
        count = con.execute(
            f'SELECT COUNT(*) FROM lake."{schema}"."{table}"'
        ).fetchone()[0]
        print(f"  Row count : {count:,}")
    except Exception:
        count = None

    table_docs = DOCS.get(schema, {}).get(table, {})

    print(f"\n  {'Column':<45} {'Type':<50} N? Description")
    print(f"  {'-'*45} {'-'*50} -- {'-'*40}")

    for col_name, data_type, is_nullable in rows:
        nullable = "Y" if is_nullable == "YES" else "N"
        description = table_docs.get(col_name, "")
        # Truncate type for display
        short_type = data_type if len(data_type) <= 50 else data_type[:47] + "…"
        print(f"  {col_name:<45} {short_type:<50} {nullable}  {description}")

    # Full type details for complex columns
    complex_cols = [(n, t) for n, t, _ in rows if "STRUCT" in t or "MAP" in t or "[]" in t]
    if complex_cols:
        print(f"\n  {'─'*70}")
        print("  Complex column types (full definitions):\n")
        for col_name, data_type in complex_cols:
            print(f"  [{col_name}]")
            print(f"    {data_type}")
            print()

    print()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        print("\nAvailable schema.table combinations:")
        for s, tables in DOCS.items():
            for t in tables:
                print(f"  {s}  {t}")
        sys.exit(1)

    schema_arg = sys.argv[1]
    table_arg = sys.argv[2]
    describe_table_detailed(schema_arg, table_arg)
