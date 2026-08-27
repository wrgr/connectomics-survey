# Visible-core export — methodology

This is the methods note for the NeuroTrailblazers first drop. Use it as the audit spec: if the site, YAML, or a local PDF disagrees with this file, the file is wrong or the export is stale.

Audience copy can be shortened from this document. Do not shorten the rules.

## What this export is

One collection: the **visible core** of the v3 catalog.

| Object | N | Ships in first NTB drop? |
|---|---|---|
| Catalog of record (`postanalysis/pdfs/paper_links.csv`) | 1,806 | No |
| Named working set / analysis base | 1,488 after dropping 4 unavailable PDFs | No |
| Earlier two-period union (history through 2023 + 2024–2026 SOTA) | 1,142 | No — superseded |
| **Visible core** | **1,074** (383 history · 571 contemporary · 120 SOTA) | **Yes** |

The old NTB 96 markdown pages and 191 journal-club YAML were two corpora. This drop **replaces both**. k-core, organism, dataset, method, axis, era, year, and reading paths are **views** over the same 1,074 rows. Views never add or drop papers. Protocol v5 §10: audience shelves do not feed back into inclusion.

**Do not copy PDF binaries into NeuroTrailblazers.** Records point at a public URL and, in this repo only, `postanalysis/pdfs/files/<stem>.pdf`.

## Catalog and inclusion (locked)

Source catalog: `postanalysis/pdfs/paper_links.csv` (1,806 works). Do not run `python analysis/collect_corpus_pdfs.py --ingest-manual` with default union: that rebuilds a larger work set and rewrites the catalog.

Core table: `postanalysis/registry/sota_history_core_labeled.csv`, `in_core=1`.

Inclusion is computed on the **intra-catalog citation graph** (edges among the 1,806), not on global citation rank alone.

| Period | Years | Bar |
|---|---|---|
| Historical | ≤2018 | year-cohort citation percentile ≥ 50 **or** undirected corpus k-core ≥ 3 |
| Contemporary | 2019–2024 | that bar **or** Out ≥ 3 |
| SOTA | 2025–2026 | 2026: Out ≥ 3 **or** In ≥ 1. 2025: Out ≥ 3 **and** In ≥ 2 |

Era bins for display: pre-2005, 2005–2009, 2010–2015, 2016–2018, then yearly 2019–2026.

Rebuild the labeled core (does not write NTB YAML):

```bash
python analysis/label_from_title_abstract.py
```

## Graph quantities — In, Out, related

These are easy to mix up. They are not the same list.

**In** (`graph.in` / YAML `in_degree`): number of **1,806-catalog** papers that cite this work.

**Out** (`graph.out` / YAML `out_degree`): number of this work’s references that are **in the 1,806 catalog**.

**k-core**: undirected k-core on that catalog graph.

**global cites**: OpenAlex/S2-style citation count from the catalog row (`graph.cites`). Independent of In/Out.

**related.cites / related.cited_by**: uuids of **other visible-core papers** this one cites or is cited by. Ordered by k-core (then `work_id`). **No cap.** An earlier export truncated these lists at 8; that truncation is a defect and has been removed. Rebuild related without touching card text:

```bash
python analysis/build_ntb_visible_core.py --related-only
```

In/Out can be larger than the related lists. That is expected: In/Out count the whole catalog; related lists only neighbors that are also in the 1,074. Example: a paper with Out = 20 may have 17 related cites if three of its catalog-internal references are outside the core.

Related links are currently 6,130 directed core→core edges (same count in each direction). Max related cites ≈ 48; max related cited-by ≈ 138.

Site UI should show **all** related uuids, not a top-8 shelf, unless the UI itself paginates. Do not re-introduce a data cap.

## Identity

- **uuid**: DOI lowercased when present; else catalog `work_id`. About 46 core papers have no DOI.
- **id**: slug `{first-author}-{year}-{doi-tail}` for NTB routes.
- **work_id**: catalog key (`work_…`).

Journal club, content-library pages, graphs, and related-work links must share uuid. Do not mint a second id per page.

## PDFs (intended vs current)

### Intended

- One file `postanalysis/pdfs/files/<stem>.pdf` **is** the catalog paper (title/DOI on the first pages).
- `pdf.status=downloaded` only when that file exists and has been verified.
- Public `pdf.url` is an OA or publisher PDF URL, not a mismatched Europe PMC render.
- NTB does not host the binary.

### What went wrong

A large fraction of “downloaded” files were **the wrong paper**. Typical causes:

1. Europe PMC `?pdf=render` attached an unrelated PMC article to the catalog DOI.
2. Truncated arXiv ids (e.g. `2208.0479` vs `2208.04790`).
3. Shared-word false matches (“connectome”, “brain”) in a weak verifier.

Writers flagged **117** core files as mismatches (`postanalysis/registry/pdf_extract_mismatches.csv`). urllib/Unpaywall/Crossref **find** many article URLs but often get HTML, HTTP 403, Cell redirect loops, or Springer **supplementary** PDFs that share the title/DOI. A Chrome pass can retrieve some articles urllib cannot; it is not finished and is not the source of truth until a file is title/DOI-checked.

### Current handling (do not treat as done)

- **Resolved** mismatch rows: verified replacement on disk; catalog `pdf_status=downloaded`; card may be PDF-grounded. Do not retry these.
- **Unresolved** mismatch rows: wrong file moved to `postanalysis/pdfs/mismatch_quarantine/`; catalog row `pdf_status=paywall`, empty `local_path`; card follows the **catalog abstract** and says so in `summaries.advanced`.
- `pdf.status=downloaded` on a collection record still does **not** guarantee the file matches if the row was never in the 117-list. Trust the mismatch table + verifier, not the filename.

Do not use `europepmc.org/articles/…?pdf=render` as a verified PDF. Skip `/esm/` and Springer supplementary PDFs.

Targeted catalog patches only (those stems). Never rewrite the 1,806 union to ingest files.

## Cards (OCAR and summaries)

Shape matches the live journal-club example: Opportunity, Challenge, Action, Resolution, Future Work; beginner / intermediate / advanced; tags; In, Out, k-core, cites; PDF/DOI links.

Two generation passes:

1. **Title + abstract** for all 1,074 (`annotation_status: generated_from_title_abstract`).
2. **Selected PDF text** (intro + last discussion/conclusions block, capped ~12k characters via `analysis/extract_pdf_summary_inputs.py`) overlaid when the on-disk file was trusted (`generated_from_pdf`).

If the extract is a different paper, the card must use the catalog abstract only. Do not invent numbers that are not in the supplied text.

**Do not** run a bare `python analysis/build_ntb_visible_core.py` after summaries exist: that rebuilds stub OCAR and wipes pedagogical text. Merge overlays instead:

```bash
python analysis/merge_ntb_summaries.py
```

`annotation_status` values in the live collection are `generated_from_pdf` or `generated_from_title_abstract`. Hand-written NTB prose, if ever merged, would be `extracted_from_ntb`.

## Streams and dimension

Tags (pipeline stage, dataset, organism, method, axis) come from title/abstract rules in `analysis/label_from_title_abstract.py`, not from the PDF. NTB `dimension` is a **derived view** from stage/axis (e.g. segmentation, proofreading, review). It is not a second corpus and not an inclusion axis.

## Views

`views/*.json`: uuid lists or groups. Membership is always the collection. Shipped: k-core rank, era, pipeline stage, organism, dataset, method, axis, year, suggested reading paths (editorial, not evidence).

## Files to copy into NTB

| This repo | NTB |
|---|---|
| `ntb_export/journal_papers.yml` | `_data/journal_papers.yml` (replace the 191-paper file) |
| `views/` | view sidecars |
| this `METHODOLOGY.md` | methods / about |
| `collection.json` | optional if the site loads JSON |

YAML now includes `in_degree`, `out_degree`, `k_core`, and `related.cites` / `related.cited_by` (full uuid lists). Compact browse JSON (`compact_papers.json`) `rc` / `rb` are those list lengths, not the catalog In/Out.

## Rebuild map (what each command is allowed to do)

| Command | Writes | Must not |
|---|---|---|
| `label_from_title_abstract.py` | labeled CSVs + core JSON | paper_links.csv, NTB cards |
| `build_ntb_visible_core.py` | collection shell, views, stub OCAR | run after real summaries |
| `build_ntb_visible_core.py --related-only` | related lists, YAML, compact rc/rb | OCAR / summaries |
| `merge_ntb_summaries.py` | overlay shards onto collection + YAML | catalog, PDFs |
| `extract_pdf_summary_inputs.py` | summary input jsonl | catalog union |
| `repair_mismatched_pdfs.py` | only listed mismatch catalog rows + files | 1,806 union |
| `collect_corpus_pdfs.py --ingest-manual` | **forbidden** for this export (default union) | — |

## Known defects (audit these first)

1. **PDF identity** is not reliable for the whole core. 117 files were known mismatches; only a subset have verified replacements. Quarantine + `paywall` on unresolved rows is intentional so they stop looking like downloads.
2. **urllib PDF retrieval is not a working OA pipeline** for remaining closed/HTML-walled publishers. Crossref often has the right URL; the fetcher does not get the article PDF.
3. **Related lists were capped at 8** in the first builder (`RELATED_CAP`). That is removed. If an older YAML or site copy still shows 8 neighbors, it is stale.
4. **In/Out ≠ related list length.** Display both; do not substitute one for the other.
5. Collection `pdf.status` / `annotation_status` can lag the catalog if cards were not re-merged after a later download.
6. Pedagogical text is generated, not author-approved. Treat as journal-club draft copy.

## Counts to check against a build

- Collection N = 1,074  
- History 383 · contemporary 571 · SOTA 120  
- UUID = DOI else work_id  
- Related: every core–core catalog edge, uncapped  
- First NTB export: this collection only
