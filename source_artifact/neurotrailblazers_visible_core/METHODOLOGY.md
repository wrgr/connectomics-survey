# Visible-core export — methodology

This is the methods note for the NeuroTrailblazers first drop. Use it as the audit spec: if the site, YAML, or a local PDF disagrees with this file, the file is wrong or the export is stale.

Audience copy can be shortened from this document. Do not shorten the rules.

## What this export is

One collection: the **visible core** of the pilot catalog.

| Object | N | Ships in first NTB drop? |
|---|---|---|
| Frozen Semantic Scholar discovery | 118,165 unique papers | No |
| Frozen retained (`keep=True`) | 3,768 | No |
| Canonical works screened (IA-007-v3 ingest) | 4,136 (later 4,100 after extra version collapse) | No |
| Working inclusive corpus / catalog of record | **1,806** | No |
| Named exploration working set | 1,544 (docs; some fill not in catalog) | No |
| Catalog-measurable analysis base | **1,488** (overlay prune + 4 unavailable PDFs dropped) | No |
| Earlier two-period union (history through 2023 + 2024–2026 SOTA) | 1,142 | No — superseded |
| **Visible core** | **1,074** (383 history · 571 contemporary · 120 SOTA) | **Yes** |

The old NTB 96 markdown pages and 191 journal-club YAML were two corpora. This drop **replaces both**. k-core, organism, dataset, method, axis, era, year, and reading paths are **views** over the same 1,074 rows. Views never add or drop papers. Protocol v5 §10: audience shelves do not feed back into inclusion.

**Do not copy PDF binaries into NeuroTrailblazers.** Records point at a public URL and, in this repo only, `postanalysis/pdfs/files/<stem>.pdf`.

## How the catalog was derived

The 1,806-work catalog is **Study A: the exploratory pilot**, not the protocol v5 registered search. Formal v5 strings, calibration, and full-text charting have not been executed (`docs/IA-016-provenance-reconciliation.md`). The NTB drop is an audience view on this frozen pilot. It does not become the review corpus.

Source-of-record chain: `docs/POSTANALYSIS_PAPER_FLOW.md` → `docs/IA-014-post-v3-overlays-and-decision-provenance.md`. If a blog post, canvas, or older IA disagrees with those files, the files win.

### 1. Frozen retrieval (2026-08-22)

Deterministic Semantic Scholar pipeline, SHA-pinned under `source_artifact/connectomics_deterministic_pipeline/outputs/` (artifact SHA `6c1b7ea9…`; config SHA `a11c830a…`; query-file SHA `65c0ee7b…`).

Architecture (`CODEX_TASK.md`, IA-003):

1. **Multi-axis lexical search** (positive scope; no `NOT MRI`-style destructive filters): direct connectomics, prep/acquisition, reconstruction, synapses, proofreading/QC, infrastructure, network science, organism applications, structure–function / NeuroAI, alternative modalities, training/outreach, health translation.
2. **Lexical scope screen** on those hits.
3. **One-hop only** from retained seeds: references + citing papers, then the same positive-scope gate. No second hop.
4. **Author saturation** as an extra discovery channel (also screened).
5. Dedup, Crossref verification, citation graph among retained papers (`paper_graph_edges.csv`, 8,065 edges).

`screening_log.csv` has 118,604 rows on **118,165 unique papers**. Channel *events* in the manifest (lexical 1,776 · 1-hop refs 40,271 · 1-hop cites 30,157 · author saturation 77,261) are not unique-paper counts.

**Frozen retained invariant:** 3,768 papers with original `keep=True` (`papers_retained.csv`). That `keep` is never rewritten.

Known retrieval bias, measured later: the lexical gate **underweights methods papers** that do not say “connectome” (FIB-SEM, staining, infrastructure). That is a discovery defect of the pilot, not a later overlay.

### 2. Record-level labels (do not change `keep`)

| Step | What it does | Frozen-run count |
|---|---|---|
| IA-004 | Derived nanoscale core: `direct_scope+resolution` **or** inherited provenance (≥2 citations to direct-resolution papers + connectome-analysis language, non-macro) | 1,534 direct + 151 inherited = **1,685** |
| IA-005/006 | Role-bridge triage; recover qualifying `keep=False` records into analysis | 15 retained + **391** recovered = 406 records |
| Accounting | Semantic-analysis universe | **4,159 records** = 3,768 + 391 |

Recovered bridges stay `keep=False` for provenance and **are included** in all later work-level analysis.

### 3. Works, not records (IA-008)

Preprint/journal and high-confidence metadata duplicates are linked; source versions stay in `work_versions.csv`.

- 4,159 records → **4,136 canonical works** at v3 screen ingest.
- Audited manual same-work links (`manual_work_links.csv`) later collapse that to **4,100**. The drop is version collapse, not exclusion.
- Abstracts rescued where possible (IA-008 / IA-011). Missing abstract ≠ exclude.

`work_id` (`work_…`) is the stable key from here on. `canonical_paper_id` is the Semantic Scholar paper id used to join the frozen graph.

### 4. Semantic screen of record (IA-007-v3)

Full re-screen of the 4,136-work ingest under frozen prompt `IA-007-v3-work-level`. v2 (`postanalysis/llm_agent/`) is historical: high-recall, **too-permissive core**. Agent JSON is never rewritten.

Decision ladder (best fit; do not use `out_of_scope` to mean “not core”):

| Decision | Meaning |
|---|---|
| `core_relevant` | Strict: synaptic-resolution / nanoscale wiring science or pipeline |
| `adjacent_relevant` | Substantive link (multi-scale, comparative, wiring-graph methods, field reviews) |
| `role_bridge` | Infrastructure, training, health translation, cross-field tools |
| `uncertain` | Plausible but insufficient text |
| `out_of_scope` | No fair link |

**Working inclusive membership** = `{core_relevant, adjacent_relevant, role_bridge}`.

### 5. Membership overlays (IA-014)

Small, CSV-auditable exceptions. Not a silent re-screen.

- **Human overlay** (`human_review_decisions.csv`): 68 rows; 57 `out_of_scope` drops from inclusive views. Overlay at corpus-build time; agent JSON untouched.
- **Manual seeds** (`manual_seed_works.csv`): 8 landmarks (White 1986 through Januszewski 2017). All eight were **discovered then `keep=False`**; recovered as screening false-negatives, not discovery holes. Human `core_relevant`. They appear in `paper_links.csv` with empty `source_group`.

**Working inclusive corpus = 1,806** (`postanalysis/llm_agent_v3/corpus_full_works.csv`): 694 core · 911 adjacent · 201 bridge.

`postanalysis/pdfs/paper_links.csv` is the **same 1,806 work_ids**. That identity is the catalog of record for this export. Do not rerun `python analysis/collect_corpus_pdfs.py` with the default v2∪v3 union: that harvest set is larger and would rewrite the catalog.

IA-013 graph layers (matched / integrated / rescue) are **views** over these 1,806, not a second corpus. About 492 works have `citation_role=no_graph` (identifier/edge coverage gap, not “unimportant”).

### 6. Analysis base vs catalog (exploration overlays)

Placeholder views over the 1,806 (`postanalysis/registry/EXPLORATION_SET.md`). They do not mutate screening JSON.

- **Prune / disconnect / stray / odd-type / OA-ref adjudication** drops in-catalog works from the *working set* (macro/generic network papers, verified isolates, etc.).
- **Fill** (53): convergence-rescue + methods-registry papers the lexical screen dropped. Only fill DOIs already in `paper_links.csv` can re-enter; the rest stay outside the catalog.
- **Named working set = 1,544** (1,491 retained + 53 fill) in that note.
- **Catalog-measurable analysis base = 1,488** = in-catalog retained ∪ in-catalog fill rescues, minus **4 confirmed-unavailable PDFs** (IEEE/CUP/World Scientific proceedings; none a unique milestone).

Visible-core **inclusion is applied only to this 1,488**. Overlay drops and the four unavailable PDFs cannot enter the 1,074. Graph In/Out/k-core are still computed on the **1,806-catalog** citation subgraph.

### 7. Citation graph used for In / Out / k-core

Not global OpenAlex rank.

1. Take frozen `paper_graph_edges.csv` (S2 paper ids, `edge_type=citation`).
2. Map `canonical_paper_id` → `work_id` for catalog rows.
3. Keep edges where **both ends are in the 1,806**.
4. **In** = catalog papers that cite this work; **Out** = this work’s references that are in the catalog; **k-core** = undirected k-core of that graph.
5. **global cites** = catalog `citation_count_work` (OpenAlex/S2-style), independent of In/Out.

Papers with no mapped edges still have In = Out = 0. That is missing graph coverage, not a measured zero in the field.

## Visible-core inclusion (locked)

Source catalog: `postanalysis/pdfs/paper_links.csv` (1,806 works). Core table: `postanalysis/registry/sota_history_core_labeled.csv`, `in_core=1`.

Inclusion is computed on the **intra-catalog citation graph** (edges among the 1,806), then applied only to the 1,488 analysis base — not on global citation rank alone.

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

1. **This catalog is the pilot, not the v5 review.** Lexical discovery underweights methods/infrastructure papers; 1-hop only; no PRESS-frozen strings. Overlay fill is an interim patch, not a completed search.
2. **PDF identity** is not reliable for the whole core. 117 files were known mismatches; only a subset have verified replacements. Quarantine + `paywall` on unresolved rows is intentional so they stop looking like downloads.
3. **urllib PDF retrieval is not a working OA pipeline** for remaining closed/HTML-walled publishers. Crossref often has the right URL; the fetcher does not get the article PDF.
4. **Related lists were capped at 8** in the first builder (`RELATED_CAP`). That is removed. If an older YAML or site copy still shows 8 neighbors, it is stale.
5. **In/Out ≠ related list length.** Display both; do not substitute one for the other. ~492 of 1,806 works are graph-unmatched (`no_graph`).
6. Collection `pdf.status` / `annotation_status` can lag the catalog if cards were not re-merged after a later download.
7. Pedagogical text is generated, not author-approved. Treat as journal-club draft copy.

## Counts to check against a build

- Frozen discovery 118,165 · retained `keep=True` 3,768 · working inclusive / catalog 1,806  
- Analysis base 1,488 · collection N = 1,074  
- History 383 · contemporary 571 · SOTA 120  
- UUID = DOI else work_id  
- Related: every core–core catalog edge, uncapped  
- First NTB export: this collection only  
- Deeper provenance: `docs/POSTANALYSIS_PAPER_FLOW.md`, `docs/IA-014-post-v3-overlays-and-decision-provenance.md`, `docs/IA-016-provenance-reconciliation.md`
