---
name: zenodo-github-release-sync
description: >
  Use this skill when a project needs its GitHub release and Zenodo archival
  deposition kept in sync — creating or updating a Zenodo version via the
  REST API, writing a .zenodo.json, or attaching a project's primary output
  files alongside the code snapshot. Trigger on "publish to Zenodo", "new
  Zenodo version", "sync the release to Zenodo", "get a DOI", "update
  .zenodo.json", or "CITATION.cff".
---

# Zenodo / GitHub Release Sync — SURF ORI

Keeps a project's Zenodo deposition version, files, and metadata in lockstep with
its GitHub releases, using the Zenodo REST API directly (not the passive
GitHub-Zenodo webhook integration, which most projects don't have enabled and
which this skill's API-driven flow supersedes).

## Standing rule: always ask first

Creating a GitHub release, pushing tags, creating a Zenodo deposition, and
publishing a Zenodo version are all public and either hard or impossible to
undo (a published Zenodo record cannot be deleted, only superseded by a new
version). **Before taking any of these actions, confirm with the user**: which
repo, what version, what changed, what files get attached. This applies even
when the user's request sounds like a standing instruction ("keep these in
sync going forward") — confirm the specific action each time you're about to
publish something new, not just the general policy once.

Never guess at credentials. If a project doesn't already have a
`ZENODO_API_TOKEN` (or equivalent) available, ask the user for one and store
it in the project's gitignored `.env` — never commit it, never paste it into
a file that gets uploaded to Zenodo.

## The two version identifiers

Every Zenodo "concept" (the thing with a stable identity across versions) has:

- a **concept DOI** (e.g. `10.5281/zenodo.21416468`) — always resolves to the
  *latest* version. Use this for badges, citations, and permanent links.
- a **version DOI** (e.g. `10.5281/zenodo.21419893`) — one per published
  version, immutable.

Badges/links using the concept DOI need no updates when you publish a new
version — they resolve automatically.

## .zenodo.json structure

Keep a `.zenodo.json` at the repo root — it documents the intended metadata
even if the passive GitHub-Zenodo integration isn't enabled, and is exactly
what to mirror in each API publish call's metadata payload.

```json
{
  "title": "Project Name",
  "description": "<p>HTML allowed. Keep the actual description here, plus a link to any live/published view. For a data-producing project, consider embedding an HTML &lt;table&gt; describing each output column and its upstream source — see \"Documenting output columns\" below.</p>",
  "upload_type": "dataset",
  "access_right": "open",
  "license": "eupl-1.2",
  "creators": [
    {"name": "Family, Given", "orcid": "0000-0000-0000-0000", "affiliation": "Org"}
  ],
  "keywords": ["..."],
  "related_identifiers": [
    {"identifier": "https://example.org/live-view/", "relation": "isSupplementedBy", "resource_type": "software-computationalnotebook", "scheme": "url"},
    {"identifier": "https://some-upstream-data-source.org", "relation": "isDerivedFrom", "resource_type": "dataset", "scheme": "url"}
  ],
  "communities": [{"identifier": "your-community"}],
  "custom": {
    "code:codeRepository": "https://github.com/org/repo",
    "code:programmingLanguage": [{"id": "python", "title": {"en": "Python"}}],
    "code:developmentStatus": {"id": "active", "title": {"en": "Active"}}
  }
}
```

Key points learned the hard way:

- **License IDs are lowercase Zenodo vocabulary slugs**, not SPDX casing —
  `eupl-1.2`, not `EUPL-1.2`. Verify any license before trusting a guess:
  `curl -s "https://zenodo.org/api/vocabularies/licenses?q=<name>"`.
- **The GitHub repo URL goes in `custom.code:codeRepository`, not in
  `related_identifiers`.** Zenodo's current UI shows a dedicated "Software"
  metadata section for this, separate from "Related works" — if a
  `related_identifiers` entry links to the repo, that duplicates the
  "Software" section and reads as noise. Use `isSupplementTo`/
  `isSupplementedBy` in `related_identifiers` only for genuinely different
  resources (a live dashboard, a companion paper), not the repo itself.
- **Add one `related_identifiers` entry per upstream data source** the
  project derives from, `relation: "isDerivedFrom"`, pointing at each
  source's own root/docs URL — this is what makes the deposition's
  provenance legible on Zenodo's page, not just in your own README.
- Do **not** hardcode a `version` field in `.zenodo.json` — it goes stale the
  moment you publish the next release. Set `version` explicitly in the API
  payload at publish time instead (see below), matching the current GitHub
  release tag.

## Documenting output columns

If the project produces a structured dataset (a table with many columns each
sourced from a different upstream API), don't make a Zenodo visitor go dig
through the README to understand it — embed the column-to-source mapping
directly in the metadata, in two places:

1. **`.zenodo.json`'s `description`** — an HTML `<table>` (Zenodo's allowed
   tag list includes `table`, `thead`, `tbody`, `tr`, `th`, `td`, `caption`),
   one row per output column: column name, upstream source, and type. Keep
   the README's own copy as the source of truth and regenerate this table
   from it rather than maintaining two independent copies by hand.
2. **`CITATION.cff`'s `references` array** — one entry per *upstream data
   source* (not per column) so each gets its own citable `url`:
   ```yaml
   references:
     - type: data
       title: "ROR — Research Organization Registry"
       url: "https://api.ror.org/v2/organizations"
     - type: data
       title: "OpenAlex institutions API"
       url: "https://api.openalex.org/institutions"
   ```
   CFF's `references` is the format-native way to cite what a dataset was
   derived from — `abstract` stays short prose, `references` carries the
   itemized source list.

## Publishing a new version

1. **Confirm with the user first** (see Standing rule above) — which repo,
   what's changed, what version tag.
2. **Create the GitHub release first** (or confirm it already exists) so you
   know the exact tag string to mirror, e.g. `v1.1.0`:
   ```bash
   gh release create v1.1.0 --title "..." --generate-notes
   ```
3. **Start a new Zenodo version** from the *latest existing* deposition id
   (not the concept id — using the concept id here will fail):
   ```bash
   curl -s -X POST "https://zenodo.org/api/deposit/depositions/<latest_id>/actions/newversion" \
     -H "Authorization: Bearer $ZENODO_API_TOKEN"
   ```
   The response's own body is the *old* record; the new draft's id is at
   `links.latest_draft` (the trailing number) or read `links.latest_draft`.
4. **Delete the carried-over files.** A "new version" draft starts as a copy
   of the previous version's files — remove them before adding the new set,
   or old and new files will both end up attached:
   ```bash
   curl -s -X DELETE "https://zenodo.org/api/deposit/depositions/<new_id>/files/<file_id>" \
     -H "Authorization: Bearer $ZENODO_API_TOKEN"
   ```
5. **Build and upload the repo snapshot.** `git archive` only includes
   committed/tracked files, so a gitignored `.env` is never at risk — but
   spot-check the listing before uploading regardless:
   ```bash
   git archive --format=zip --prefix=<repo-name>/ -o /tmp/<repo-name>-<version>.zip HEAD
   unzip -l /tmp/<repo-name>-<version>.zip | grep -i "\.env\|secret\|token"   # expect nothing but .env.example
   ```
   Upload to the new draft's bucket (from the newversion response, or GET the
   draft to find `links.bucket`):
   ```bash
   curl -s -X PUT "<bucket_url>/<repo-name>-<version>.zip" \
     -H "Authorization: Bearer $ZENODO_API_TOKEN" --upload-file /tmp/<repo-name>-<version>.zip
   ```
6. **Attach the project's primary output file(s) as separate files**, if the
   project produces one (a dataset CSV/Parquet, a report PDF, etc.) — don't
   make people unzip the whole repo snapshot just to get the data:
   ```bash
   curl -s -X PUT "<bucket_url>/<output-file>" \
     -H "Authorization: Bearer $ZENODO_API_TOKEN" --upload-file <path>
   ```
   **File order controls Zenodo's default preview** — the first-listed file
   previews by default. Upload the most human-readable format first (CSV
   before Parquet, before the zip), or explicitly set order after all
   uploads via the deposition files sort endpoint:
   ```bash
   curl -s -X PUT "https://zenodo.org/api/deposit/depositions/<new_id>/files" \
     -H "Authorization: Bearer $ZENODO_API_TOKEN" -H "Content-Type: application/json" \
     -d '[{"id": "<csv_file_id>"}, {"id": "<parquet_file_id>"}, {"id": "<zip_file_id>"}]'
   ```
7. **Set metadata**, mirroring `.zenodo.json` plus an explicit `version` field
   matching the GitHub tag (strip any leading `v` or keep it — just be
   consistent and explicit; **never omit `version`**, Zenodo will otherwise
   assign something arbitrary that has no relationship to your actual
   release):
   ```bash
   curl -s -X PUT "https://zenodo.org/api/deposit/depositions/<new_id>" \
     -H "Authorization: Bearer $ZENODO_API_TOKEN" -H "Content-Type: application/json" \
     -d '{"metadata": { ...same shape as .zenodo.json..., "version": "1.1.0" }}'
   ```
8. **Publish**:
   ```bash
   curl -s -X POST "https://zenodo.org/api/deposit/depositions/<new_id>/actions/publish" \
     -H "Authorization: Bearer $ZENODO_API_TOKEN"
   ```
9. **Verify**: both DOIs resolve, and the concept DOI now points at the new
   record:
   ```bash
   curl -sI "https://doi.org/10.5281/zenodo.<new_id>"
   curl -sIL "https://doi.org/<concept_doi>" | grep -i location
   ```

## Metadata-only fixes to an already-published record

If you need to fix/add metadata (a typo, a missing related identifier) on a
record that's already published and you do **not** want to mint a new
version/DOI for it, use the edit action instead of newversion — this updates
the *same* version in place:

```bash
curl -s -X POST "https://zenodo.org/api/deposit/depositions/<id>/actions/edit" \
  -H "Authorization: Bearer $ZENODO_API_TOKEN"
# ...PUT updated metadata to the same id...
curl -s -X POST "https://zenodo.org/api/deposit/depositions/<id>/actions/publish" \
  -H "Authorization: Bearer $ZENODO_API_TOKEN"
```

Reserve this for genuine metadata corrections. Any change to what the
files/data actually contain belongs in a new version (step-by-step above),
since that's what gives readers a distinct, citable DOI for what they read.

## Auth token gotcha

`source .env` alone only sets shell variables, not environment variables —
child processes (like `curl` invoked from a script, or `python3 -c`) won't
see them. Use `set -a; source .env; set +a` (or explicit `export`) so the
token is actually exported.

## CITATION.cff

Add a `CITATION.cff` (Citation File Format v1.2.0) at the repo root alongside
`.zenodo.json` — GitHub renders a native "Cite this repository" button from
it, and Zenodo displays it as a citation format option. Minimal shape:

```yaml
cff-version: 1.2.0
message: "If you use this software, please cite it as below."
title: "Project Name"
type: software   # or "dataset"
authors:
  - family-names: Family
    given-names: Given
    orcid: "https://orcid.org/0000-0000-0000-0000"
    affiliation: Org
version: 1.0.0
date-released: "2026-01-01"
doi: 10.5281/zenodo.<concept_id>
url: "https://github.com/org/repo"
repository-code: "https://github.com/org/repo"
license: EUPL-1.2   # CFF's `license` uses SPDX casing, unlike Zenodo's own API vocab
keywords: ["..."]
abstract: >-
  Short prose description.
```

Note the license-casing split: `CITATION.cff`'s `license` field follows SPDX
identifiers (`EUPL-1.2`), while `.zenodo.json`'s `license` field uses
Zenodo's own lowercase vocabulary slug (`eupl-1.2`) — same license, two
different casings depending on which file you're editing.
