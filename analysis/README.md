# Post-processing and reconciliation

This directory contains **derived-analysis tooling** for completed deterministic connectomics runs. It does not alter the preregistered retrieval corpus, source `keep` decisions, or first-discovery provenance.

## Core post-analysis sequence

1. `reconcile_cleanup.py` — IA-004 nanoscale-core derivation and author-reconciliation candidates.
2. `triage_paper_categories.py` / `consolidate_role_bridges.py` — IA-005/006 role-bridge triage and recovery.
3. `build_paper_accounting.py` — canonical record-level accounting.
4. `reconcile_paper_works.py` — IA-008 preprint/final and metadata-version reconciliation.
5. `rescue_missing_abstracts.py` — best-effort abstract enrichment.
6. `llm_relevance_screen.py` — IA-007 LLM-first semantic screening at canonical-work level.
7. `compare_screening_runs.py` — IA-009 comparison of two screening runs (e.g. offline agent adjudication vs API).
8. `triage_record_types.py` / `apply_record_type_partition.py` — IA-010 deterministic record-type triage and post-hoc paper/non-paper partition.
9. IA-007-v3 full agent ingest (`postanalysis/llm_agent_v3/`) — current screening of record.
10. `human_review.py` / `manual_seeds.py` — IA-014 membership overlays (CSV sources of record; agent JSON untouched).
11. `analyze_citation_roles.py` / `build_corpus_graph_views.py` / `build_emergent_core.py` — IA-013 derived views.
12. human person aliases and `triage_people.py`.

## `postprocess_run.py`

Reproduces the QC tables and visualization panels used for the first fresh full run.

## `reconcile_cleanup.py` — IA-004

Creates the derived nanoscale paper core and person-reconciliation candidate queue. On the frozen reference run this yields 1,534 direct papers + 151 inherited-provenance papers = **1,685 derived nanoscale-core records**.

Person reconciliation uses normalized-name blocking, including a conservative form that removes only single-letter middle initials. Name matching only generates candidates. Coauthor-neighborhood and temporal evidence prioritize review; no person is automatically merged.

## `triage_paper_categories.py` / `consolidate_role_bridges.py` — IA-005/006

Role evidence plus directed proximity identifies health, training/outreach, proofreading/annotation, infrastructure/method and network-science bridges. IA-006 additionally recovers qualifying papers from `papers_all.csv` even when original `keep=False`; source `keep` provenance is unchanged.

Frozen-run final strict bridge records: **15 retained + 391 recovered = 406 records**.

## `build_paper_accounting.py`

Reports two denominators explicitly:

- frozen retrieval provenance: **3,768 retained records = 1,685 core + 15 strict retained bridges + 2,068 unresolved**;
- raw semantic-analysis universe: **4,159 records = 3,768 retained + 391 recovered role bridges**.

Recovered bridges remain `keep=False` for provenance but **are included in all later semantic/work-level analysis**.

## `reconcile_paper_works.py` — IA-008

Reconciles multiple records representing the same scholarly work while preserving all versions. It links exact DOI/PMID/arXiv identifiers first and then applies conservative title/author/year/preprint-publication similarity rules. Optional audited manual links live in `postanalysis/works/manual_work_links.csv` (columns `a`, `b`; optional `reason`, `notes`) and are applied on each run. After reconciliation changes `work_id`s, remap frozen screening with `analysis/remap_screening_work_ids.py`. Outputs:

- `canonical_works.csv`
- `work_versions.csv`
- `work_link_evidence.csv`
- `work_reconciliation_summary.json`

Frozen-run dry run: **4,159 records → 4,136 canonical works**, with 22 multi-version works and 23 redundant version records collapsed.

Citation counts are not blindly summed: the maximum version count is the conservative work-level metric; the sum is retained as an explicitly labelled upper bound because citing sets may overlap.

## `rescue_missing_abstracts.py` — IA-008

For canonical works still lacking abstracts after linked-version aggregation, best-effort rescue tries:

1. Semantic Scholar (`SEMANTIC_SCHOLAR_API_KEY` when available);
2. Europe PMC by PMID/DOI;
3. OpenAlex when `OPENALEX_API_KEY` is configured;
4. Crossref DOI metadata.

Existing abstracts are never overwritten. Remaining missing abstracts stay reviewable and cannot be excluded from title alone.

One JSON line per canonical work is appended and flushed to `<out>/abstract_rescue_progress.jsonl` as each work is resolved, so the run is tailable against the 4,136-work denominator. Rescued abstract text is carried in that record, so a rerun into the same `--out` reuses it instead of re-hitting the network; `--skip-attempted` additionally skips works already recorded as `still_missing`.

## `llm_relevance_screen.py` — IA-007

Runs **after IA-008** on canonical enriched works. All source groups are included:

- `core_audit`
- `unresolved`
- `role_bridge`

The frozen work-reconciliation dry run yields an expected LLM universe of **4,136 canonical works**: 1,678 core-audit, 2,062 unresolved, and 396 role-bridge works. The exact denominator after abstract rescue is written at runtime.

The LLM is a high-recall first-pass reviewer only. It returns structured relevance/role/confidence/evidence/noise labels and creates a later human-review queue. It never mutates source `keep`, core, bridge or work-link status.

**Current screen:** IA-007-v3 (`--prompt-version v3`, `postanalysis/llm_agent_v3/`). v2 under `postanalysis/llm_agent/` is historical.

Human exclusions after the queue live in `postanalysis/llm_agent_v3/human_review_decisions.csv` (IA-014). They overlay agent decisions at corpus-build time (`out_of_scope` drops the work from inclusive views and PDF collection) and do not rewrite frozen agent JSON. Landmark works missing from frozen discovery are added from `postanalysis/works/manual_seed_works.csv` the same way.

One JSON line per screened work is appended and flushed to `<out>/llm_screen_progress.jsonl` as each decision lands, including whether the result came from the per-work cache. Every 25 works the partial `llm_relevance_results.csv` is rewritten with the final schema, so an interrupted run is still usable, and the running decision tally is printed.

```bash
python analysis/reconcile_paper_works.py \
  --outputs-dir extracted/connectomics_deterministic_pipeline/outputs \
  --bridges-dir bridges \
  --accounting-csv accounting/retained_paper_accounting.csv \
  --out works

python analysis/rescue_missing_abstracts.py \
  --works-csv works/canonical_works.csv \
  --versions-csv works/work_versions.csv \
  --out enriched

python analysis/llm_relevance_screen.py \
  --works-csv enriched/canonical_works_enriched.csv \
  --out llm_screen \
  --prepare-only
```

## `watch_progress.py`

Strictly read-only per-paper viewer for either progress stream. It prints one line per canonical work plus a running summary — counts by rescue source, or counts by decision and source group — and never writes, truncates or moves anything, so it is safe against an in-flight run.

```bash
python analysis/watch_progress.py postanalysis/enriched/abstract_rescue_progress.jsonl --follow
python analysis/watch_progress.py postanalysis/llm_screen/llm_screen_progress.jsonl --follow
python analysis/watch_progress.py postanalysis/pdfs/pdf_progress.jsonl --follow
python analysis/watch_progress.py postanalysis/enriched/abstract_rescue_progress.jsonl --summary-only
```

`--tail N` limits the initial backlog, `--summary-every N` sets the follow-mode summary cadence, and repeated records for the same work (from a resumed run) collapse to the latest.

## `compare_screening_runs.py` — IA-009

Compares two IA-007 `llm_relevance_results.csv` runs at canonical-work level, joining on `work_id`. Built for the IA-009 agent-adjudicated versus API comparison and for measuring internal consistency across replicate adjudications of the same overlap set. Strictly read-only with respect to both runs; it refuses to write into an input directory.

Coverage may differ between runs, so only the intersection is scored and the gaps are listed separately. It reports coverage, decision agreement and Cohen's kappa overall and per source group, the full decision confusion matrix, role and noise-flag set agreement (Jaccard), confidence calibration per decision, and human-review-queue overlap.

Because IA-007 is explicitly high recall, disagreements are ranked by cost rather than counted flat: an `out_of_scope` in one run against `core_relevant`/`adjacent_relevant`/`role_bridge` in the other is the top tier, ahead of exclusion-versus-deferral, benign uncertain-versus-decided churn, and relevance-class swaps.

```bash
python analysis/compare_screening_runs.py \
  --run-a postanalysis/llm_agent/llm_relevance_results.csv \
  --run-b postanalysis/llm_api/llm_relevance_results.csv \
  --label-a agent --label-b api \
  --out postanalysis/screen_comparison \
  --expected-works 4136
```

Outputs `screening_comparison_summary.json`, `screening_decision_disagreements.csv` (highest stake first) and `screening_comparison_report.md`. Optional `--queue-a`/`--queue-b` compare explicit `human_review_queue.csv` files instead of the `human_review_priority` column. Neither run is treated as a gold standard.

`test_compare_screening_runs.py` covers it with synthetic fixtures in a temp dir and runs without a test runner:

```bash
python analysis/test_compare_screening_runs.py
```

## `triage_record_types.py` / `apply_record_type_partition.py` — IA-010

Some canonical works are not research papers: referee reports, `Author response:` items, errata, editorials, replies, meeting-abstract stubs, a proceedings volume. IA-007 routes every abstract-less work to `insufficient_abstract`, which spends human adjudication on the "relevance" of a correction notice and inflates the paper denominator.

`triage_record_types.py` assigns one record type per work from `publication_types` plus **anchored** title patterns, writes the firing signal and matched substring per record, and routes the ambiguous middle to `record_type_review_queue.csv`. It is high precision in the non-paper direction: a `Review;JournalArticle` work is a review ARTICLE and stays `research_paper`; only `^Review for "…"` is a peer-review report; `correction` unanchored matches fifteen ordinary methods papers and is therefore never matched unanchored. `LettersAndComments` never classifies alone and an unsupported `Editorial` is vetoed by a research article type in the same string, because both misfire on real papers here. Empty `publication_types` (661 works) lets title evidence stand alone, one confidence level lower.

Frozen-run result: **4,136 canonical works = 4,086 research papers + 50 non-paper records** — 24 editorial/commentary, 10 peer-review reports, 9 errata/corrections, 4 conference abstracts, 3 book/proceedings. 18 of the 321 abstract-less works are non-papers; 66 rows go to the review queue.

`apply_record_type_partition.py` applies that label to a finished IA-007 run *after the fact*, so the screening script, its prompt and its 4,136-work denominator are untouched. It emits paper and non-paper result views, both denominators, and a reduced human queue with non-paper rows lifted into their own file rather than dropped. Every input row lands in exactly one partition, and a work with no record-type row stays a paper.

```bash
python analysis/triage_record_types.py \
  --works-csv postanalysis/works/canonical_works.csv \
  --out postanalysis/record_types \
  --expected-works 4136

python analysis/apply_record_type_partition.py \
  --results-csv postanalysis/llm_agent/llm_relevance_results.csv \
  --record-types-csv postanalysis/record_types/work_record_types.csv \
  --queue-csv postanalysis/llm_agent/human_review_queue.csv \
  --out postanalysis/record_types/partition_agent --label agent
```

Both tools refuse to write into an input directory, the triage hashes its input before and after, and both are byte-identical on rerun. `test_triage_record_types.py` covers both with synthetic fixtures in a temp dir and needs no test runner:

```bash
python analysis/test_triage_record_types.py
```

## `collect_corpus_pdfs.py` — frozen-corpus paper links and OA PDFs

Records a landing URL for every IA-012 inclusive-corpus work and downloads an open-access PDF when one is locatable. It does not mutate checkpoint or work-reconciliation files. Paywalled works keep their DOI / PubMed / arXiv / Semantic Scholar links for later iteration.

Filenames prefer a DOI stem (`doi_10.1038_s41586-026-10735-w.pdf`), then `arxiv_<id>`, `pmid_<id>`, and `work_<id>`. Progress is append-only JSONL; a rerun skips valid local PDFs and retries the rest.

```bash
# Identifier-derived links only (no network). Writes postanalysis/pdfs/paper_links.csv.
python analysis/collect_corpus_pdfs.py --local-ids-only --resolve-only --expected-works 1996

# Resolve OA PDF URLs (Unpaywall / OpenAlex / Europe PMC) and download where possible.
# Default work set = v2 checkpoint inclusive ∪ v3 full inclusive, minus human exclusions.
python analysis/collect_corpus_pdfs.py --email you@institution.edu --expected-works 1996

python analysis/watch_progress.py postanalysis/pdfs/pdf_progress.jsonl --follow
```

`--skip-attempted` leaves previous failures untouched. `--force` re-downloads even when a valid local PDF exists. Binary PDFs live in `postanalysis/pdfs/files/` and are gitignored; the catalog and progress log are the versioned record.

Works that still lack a PDF are retried with a title-and-DOI bibliographic search (OpenAlex, Crossref, Europe PMC). A match is always flagged `pdf_source=direct_search` with `match_method` `doi` or `title`, and written to `postanalysis/pdfs/direct_search_audit.csv` for review. Title matches use the same 0.92 similarity floor as IA-011 abstract rescue.

```bash
python analysis/collect_corpus_pdfs.py --email you@institution.edu --search-unresolved --expected-works 1996
```

Remaining gaps can be retried against NCBI PubMed/PMC (DOI idconv, PMID→PMC elink, title/DOI esearch). Hits are tagged `pdf_source=pubmed` and existing local PDFs are left untouched:

```bash
python analysis/collect_corpus_pdfs.py --email you@institution.edu --pubmed-unresolved --expected-works 1996
```

NCBI serves NIHMS PDFs only after a browser JavaScript proof-of-work cookie. urllib therefore gets HTML on `pdf/nihms….pdf` even when Chrome does not. The Chrome pass visits the PMC article page, scrapes the named PDF href, and downloads with that cookie jar:

```bash
python3 -m pip install playwright
python analysis/collect_pmc_browser_pdfs.py --email you@institution.edu --unresolved-only --expected-works 1996 --workers 4
```

Hand-retrieved PDFs go in `postanalysis/pdfs/manual_OA/` (open access) or `postanalysis/pdfs/manual_closed/` (paywall). `--ingest-manual` copies them to `files/` under the corpus stem (`doi_…` / `arxiv_…` / `pmid_…` / `work_…`), logs `pdf_source=manual_oa` or `manual_closed`, and rewrites the catalog. Matching uses the corpus stem, an embedded DOI, an MDPI article id (`photonics-06-00066`), a truncated publisher title, or a DOI found inside the PDF (raw bytes, then `pdftotext` on the first pages when available). Unmatched files fail the run after the rest are ingested. Drop-folder originals are left in place.

```bash
python analysis/collect_corpus_pdfs.py --ingest-manual --expected-works 1996
```

`test_collect_corpus_pdfs.py` covers naming, landing URLs, resume, HTML-paywall rejection, and manual ingest with synthetic fixtures and no sockets:

```bash
python analysis/test_collect_corpus_pdfs.py
```

## Person tools

- `prepare_person_review.py` creates a human-review table for probable/possible identity pairs.
- `apply_person_aliases.py` applies explicit reviewed aliases only and preserves source author IDs.
- `triage_people.py` builds a multidimensional evidence matrix for reconciled people touching the cleaned field corpus; it deliberately does not impose an arbitrary universal importance score.

## Reproducibility principles

- Never mutate the preregistered broad corpus; derived views are separate outputs.
- Include IA-006 recovered bridges in semantic analysis while preserving their original `keep=False` provenance.
- Reconcile paper versions before LLM screening and person-level counting.
- Preserve every paper version and every author source ID.
- Never merge people from name equality alone.
- Treat empirical thresholds as local calibration choices, not universal literature constants.
- Route ambiguous LLM and identity decisions to later human review.
- Label non-research record types deterministically and retain them; report the paper denominator alongside the frozen **4,136-work screen-ingest** provenance rather than in place of it. Current canonical works after audited manual links: **4,100** (IA-014).

See `docs/IA-004-provenance-and-author-reconciliation.md` through `docs/IA-014-post-v3-overlays-and-decision-provenance.md` for methodology and frozen-run calibration. **IA-014 is the provenance index** for which file is source of record after v3.
