# NeuroTrailblazers visible-core source

One collection. Multiple views. Export this directory into NeuroTrailblazers so `/content-library/journal-papers/` and `/technical-training/journal-club/` stop being two corpora.

**First export = visible core only (1,074 papers).** Methods: `METHODOLOGY.md`. Do not copy the 1,806 catalog or the 1,488 working set.

Related-neighbor refresh (does not wipe cards):

```bash
python analysis/build_ntb_visible_core.py --related-only
```

Full collection rebuild **wipes pedagogical text** — do not run after summaries exist:

```bash
python analysis/build_ntb_visible_core.py
```

| File | Role |
|---|---|
| `METHODOLOGY.md` | Methods spec / audit note (inclusion, graph, PDFs, cards, rebuild traps) |
| `meta.json` | Counts, rules, coverage |
| `collection.json` | Full core records (uuid, PDF, graph, streams, OCAR, related) |
| `collection.jsonl` | Same, one paper per line |
| `views/manifest.json` | View catalog |
| `views/*.json` | uuid lists / grouped streams |
| `ntb_export/journal_papers.yml` | Drop-in for `_data/journal_papers.yml` |
| `SCHEMA.md` | Record and view fields |

Do not commit PDFs. `pdf.local_path` is relative to `postanalysis/pdfs/`.
