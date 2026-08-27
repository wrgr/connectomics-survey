# What to copy into NeuroTrailblazers

First drop is the **visible core only (1,074 papers)**. Not the 1,806 catalog, not the 1,488 working set, not the old 96 markdown + 191 YAML as two corpora.

**Methods spec:** `METHODOLOGY.md` in this directory. If a number, related list, or PDF disagrees with that file, trust the methods note and treat the data as stale or defective.

## Copy

| From this repo | Into NTB |
|---|---|
| `ntb_export/journal_papers.yml` | `_data/journal_papers.yml` (replace the 191-paper file) |
| `views/` | `_data/paper_views/` (or equivalent) — filters, not a second set |
| `METHODOLOGY.md` | methods / about copy for the library |
| `collection.json` | optional if the site can load JSON instead of YAML |

Do **not** copy PDF binaries. Do **not** keep the old 96 teaching pages and 191 journal-club YAML as two libraries.

## What each card has

- year, dimension, title, authors, venue, DOI/`uuid`
- Opportunity / Challenge / Action / Resolution / Future Work
- beginner / intermediate / advanced
- tags
- In, Out, k-core, global cites (catalog graph; In/Out are not capped)
- related core works: **all** cites / cited-by uuids inside the core (not a top-8 list)
- PDF / DOI / landing links — local files are not verified for every row; see METHODOLOGY.md
