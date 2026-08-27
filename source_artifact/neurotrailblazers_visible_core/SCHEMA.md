# Visible-core record schema

## Collection record (`collection.json`)

| Field | Meaning |
|---|---|
| `uuid` | DOI lowercase, else `work_id` |
| `id` | Slug for NTB (`{author}-{year}-{doi-tail}`) |
| `work_id` | Catalog work id |
| `title`, `authors`, `year`, `journal` | Bibliographic |
| `doi`, `landing_url` | Identity / resolver |
| `pdf.status` | `downloaded` / `linked` / `download_failed` / `paywall` |
| `pdf.url` | Public PDF or landing URL |
| `pdf.local_path` | `files/<stem>.pdf` when the file exists |
| `graph.in`, `.out`, `.k_core`, `.cites`, `.year_cites_percentile` | Place in the 1,806 catalog graph |
| `graph.citation_role`, `.link_strength` | From citation-role overlay, when present |
| `role` | `history` / `contemporary` / `sota` |
| `era` | Display bin (e.g. `2016–2018`, `2024`) |
| `why` | Inclusion rule fired |
| `streams.axis`, `.stages`, `.datasets`, `.organism`, `.method` | Charting tags |
| `streams.training_outreach`, `.health_translation`, … | Axis flags (`yes` or empty) |
| `related.cites`, `.cited_by` | Core uuids, capped, ordered by k-core |
| `dimension` | NTB journal-club dimension (derived view, not a second corpus) |
| `reading_phase` | `1_foundations` / `2_contemporary` / `3_sota` |
| `annotation_status` | `generated_from_abstract` or `extracted_from_ntb` |
| `ocar` | opportunity, challenge, action, resolution, future_work |
| `plain_language_summary` | Beginner-facing |
| `summaries` | beginner / intermediate / advanced |
| `discussion_prompts` | List of strings |
| `tags` | Flattened stream tags |

## Views (`views/*.json`)

Each view is `{ "id", "title", "description", "kind": "rank"|"group", ... }`.

- rank views: `{ "uuids": ["10.1038/…", …] }`
- group views: `{ "groups": [{ "key", "label", "uuids" }] }`

Papers never appear only in a view. Membership is always the collection.

First NeuroTrailblazers export is this collection only (the visible core). The 1,806 catalog is not exported yet.
