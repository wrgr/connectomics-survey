# NeuroTrailblazers visible-core source

One collection. Multiple views. Export this directory into NeuroTrailblazers so `/content-library/journal-papers/` and `/technical-training/journal-club/` stop being two corpora.

**First export = visible core only (1,074 papers).** Do not copy the 1,806 catalog or the 1,488 working set. The 1,142 figure was the pre-split SOTA+history union; it is not this drop.

Rebuild:

```bash
python analysis/build_ntb_visible_core.py
```

| File | Role |
|---|---|
| `METHODOLOGY.md` | Audience-facing note (site copy) |
| `meta.json` | Counts, rules, coverage |
| `collection.json` | Full core records (uuid, PDF, graph, streams, OCAR, related) |
| `collection.jsonl` | Same, one paper per line |
| `views/manifest.json` | View catalog |
| `views/*.json` | uuid lists / grouped streams |
| `ntb_export/journal_papers.yml` | Drop-in for `_data/journal_papers.yml` |
| `SCHEMA.md` | Record and view fields |

Do not commit PDFs. `pdf.local_path` is relative to `postanalysis/pdfs/`.
