# Post-processing and reconciliation

This directory contains **derived-analysis tooling** for completed deterministic connectomics runs. It does not alter the preregistered retrieval corpus, source `keep` decisions, or first-discovery provenance.

## Core post-analysis sequence

1. `reconcile_cleanup.py` — IA-004 nanoscale-core derivation and author-reconciliation candidates.
2. `triage_paper_categories.py` / `consolidate_role_bridges.py` — IA-005/006 role-bridge triage and recovery.
3. `build_paper_accounting.py` — canonical record-level accounting.
4. `reconcile_paper_works.py` — IA-008 preprint/final and metadata-version reconciliation.
5. `rescue_missing_abstracts.py` — best-effort abstract enrichment.
6. `llm_relevance_screen.py` — IA-007 LLM-first semantic screening at canonical-work level.
7. human adjudication later, followed by author aliases and `triage_people.py`.

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

Reconciles multiple records representing the same scholarly work while preserving all versions. It links exact DOI/PMID/arXiv identifiers first and then applies conservative title/author/year/preprint-publication similarity rules. Outputs:

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

## `llm_relevance_screen.py` — IA-007

Runs **after IA-008** on canonical enriched works. All source groups are included:

- `core_audit`
- `unresolved`
- `role_bridge`

The frozen work-reconciliation dry run yields an expected LLM universe of **4,136 canonical works**: 1,678 core-audit, 2,062 unresolved, and 396 role-bridge works. The exact denominator after abstract rescue is written at runtime.

The LLM is a high-recall first-pass reviewer only. It returns structured relevance/role/confidence/evidence/noise labels and creates a later human-review queue. It never mutates source `keep`, core, bridge or work-link status.

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

See `docs/IA-004-provenance-and-author-reconciliation.md` through `docs/IA-008-work-reconciliation-and-abstract-rescue.md` for methodology and frozen-run calibration.
