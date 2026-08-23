# Post-processing and reconciliation

This directory contains **derived-analysis tooling** for completed deterministic connectomics runs. It does not alter the preregistered retrieval corpus, source `keep` decisions, or first-discovery provenance.

## `postprocess_run.py`

Reproduces the QC tables and visualization panels used for the first fresh full run.

```bash
python analysis/postprocess_run.py \
  --artifact connectomics-fresh-outputs.zip \
  --expected-sha256 6c1b7ea962fb1dd58e4e8c84c216d2d2d6999392949b598165016a2c205ee68c \
  --out postprocessed
```

## `reconcile_cleanup.py` — IA-004

Creates the derived nanoscale paper core and person-reconciliation candidate queue.

Paper scope has two routes:

- direct nanoscale: explicit `direct_scope+resolution` evidence;
- inherited connectome provenance: specific connectome-analysis language + at least two directed citations to direct-resolution papers + no macroscale flag.

On the frozen reference run this yields 1,534 direct papers + 151 inherited-provenance papers = **1,685 derived nanoscale-core papers**.

Person reconciliation uses normalized-name blocking, including a conservative form that removes only single-letter middle initials. Name matching only generates candidates. Coauthor-neighborhood and temporal evidence prioritize review; no person is automatically merged.

```bash
python analysis/reconcile_cleanup.py \
  --outputs-dir extracted/connectomics_deterministic_pipeline/outputs \
  --out reconciliation
```

## `prepare_person_review.py`

Creates a human-review table for probable/possible identity pairs, including Semantic Scholar profile links and adjudication fields.

## `apply_person_aliases.py`

Applies **explicit reviewed merge decisions only** through a canonical alias table. Source Semantic Scholar author IDs are preserved. Reconciled person-paper counts are recomputed from canonical aliases.

## `triage_paper_categories.py` — IA-005 / IA-006

Triages health, training/outreach, proofreading/annotation, infrastructure/methods, and network-science bridge papers using role evidence plus proximity to the 1,685-paper derived nanoscale core.

IA-006 corrects an important retained-only failure mode: legitimate role papers can be discovered by the frozen run but rejected by the scientific-core `keep` predicate. The script therefore reads `papers_all.csv`, but only considers papers with an **original role hit recorded by the pipeline**.

Originally discarded records enter the actionable recovery queue only when they additionally have role-specific high-specificity title evidence and directed citation proximity to the derived core. Indirect bibliographic-coupling/co-citation proximity is reported for ranking but cannot recover a discarded paper by itself.

Reference-run calibration produces **391 unique originally-discarded actionable bridge candidates**.

## `consolidate_role_bridges.py`

Applies the final harmonized IA-006 bridge rules to both retained non-core and originally `keep=False` records. On the frozen reference run this produces:

- **15** strict role bridges inside the originally retained corpus;
- **391** recovered `keep=False` role bridges;
- **406** strict role bridges across both origins.

The two origins remain explicit in every output.

## `build_paper_accounting.py`

Freezes the canonical mutually exclusive accounting of the **3,768 originally retained papers** and asserts the partition in code:

- **1,685** derived nanoscale core;
- **15** strict retained role bridges;
- **2,068** unresolved retained non-core.

The 391 recovered `keep=False` role bridges are reported separately and are never added to the 3,768 retained denominator.

```bash
python analysis/build_paper_accounting.py \
  --outputs-dir extracted/connectomics_deterministic_pipeline/outputs \
  --cleanup-dir reconciliation \
  --bridges-dir bridges \
  --out accounting
```

## `llm_relevance_screen.py` — IA-007

Runs an **LLM-first high-recall title/abstract relevance pass** on the 2,068 unresolved retained papers and audits all 1,685 core papers for false-positive/noise signals. It does not change deterministic paper status.

Default target: **3,753 papers**. Records without abstracts are routed directly to `insufficient_abstract` for later human/full-text review rather than being excluded from title alone.

The LLM returns provisional semantic classes (`core_relevant`, `adjacent_relevant`, `role_bridge`, `out_of_scope`, `uncertain`), role labels, confidence, evidence, and noise flags. A later human-review queue includes uncertain/low-confidence cases, every core paper flagged as possible noise, and a deterministic audit sample of high-confidence exclusions.

```bash
# Prepare the exact screening set without calling a model
python analysis/llm_relevance_screen.py \
  --accounting-csv accounting/retained_paper_accounting.csv \
  --out llm_screen \
  --prepare-only

# Run with an OpenAI-compatible endpoint
export LLM_API_KEY=...
export LLM_API_BASE=https://api.openai.com/v1
export LLM_MODEL=gpt-5.6
python analysis/llm_relevance_screen.py \
  --accounting-csv accounting/retained_paper_accounting.csv \
  --out llm_screen
```

The model is deliberately a first-pass screener, not an autonomous inclusion/exclusion authority. See `docs/IA-007-llm-first-semantic-screening.md`.

## `triage_people.py`

Builds a multidimensional descriptive evidence matrix for people touching the derived nanoscale core. It reports productivity, fractional contribution, active years, axis breadth, coauthor structure, and hyperauthorship sensitivity. It deliberately does **not** assign an importance score or A/B/C/D tier before the empirical distributions are inspected.

For the final people map, run this after reviewed author aliases have been applied and after the paper universe is sufficiently stabilized.

## Reproducibility principles

- Never mutate the preregistered broad corpus; derived views are separate outputs.
- Never reinterpret an original `keep=False` as a core-paper inclusion. IA-006 recovered records are role bridges only.
- Keep retained-corpus and recovered-bridge denominators separate.
- LLM labels are provisional semantic review aids, never silent mutations of deterministic status.
- Never merge people from name equality alone.
- Preserve raw paper IDs, author IDs, and discovery provenance.
- Keep empirical thresholds documented as local calibration choices rather than universal literature constants.
- Use explicit review/alias decisions for identity reconciliation.

See `docs/IA-004-provenance-and-author-reconciliation.md`, `docs/IA-005-proximity-aware-role-triage.md`, `docs/IA-006-discovered-role-bridge-recovery.md`, and `docs/IA-007-llm-first-semantic-screening.md` for methodological rationale and frozen-run calibration.
