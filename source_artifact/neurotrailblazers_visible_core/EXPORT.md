# What to copy into NeuroTrailblazers

First drop is the **visible core only (1,074 papers)**. Not the 1,806 catalog, not the 1,488 working set, not the old 96 markdown pages plus 191 YAML as two corpora.

## Copy

| From this repo | Into NTB |
|---|---|
| `ntb_export/journal_papers.yml` | `_data/journal_papers.yml` (replace the 191-paper file) |
| `views/` | `_data/paper_views/` (or equivalent) — filters, not a second set |
| `METHODOLOGY.md` | methods / about copy for the library |
| `collection.json` | optional if the site can load JSON instead of YAML |

Do **not** copy PDF binaries. Each record already has a public `pdf_url` (YAML) or `pdf.url` plus `pdf.local_path` (`collection.json`).

Do **not** keep the old 96 teaching pages and 191 journal-club YAML as two libraries. Both routes should read this one collection; k-core, organism, dataset, method, axis, era, and year are views.

## What each card has

- year, dimension, title, authors, venue, DOI/`uuid`
- Opportunity / Challenge / Action / Resolution / Future Work
- beginner / intermediate / advanced
- tags
- In, Out, k-core, global cites
- related core works (cites / cited-by)
- PDF / DOI / landing links

## Status of the prose

Cards are journal-club shaped for all 1,074. A PDF-grounded pass is in progress (intro + discussion, not the whole file). Where the file on disk is the wrong paper, the card follows the catalog abstract. Those mismatches are being replaced or quarantined; do not treat every local `files/<stem>.pdf` as verified until that repair finishes.
