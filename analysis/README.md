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

```bash
python analysis/triage_paper_categories.py \
  --outputs-dir extracted/connectomics_deterministic_pipeline/outputs \
  --cleanup-dir reconciliation \
  --out role_triage
```

Reference-run calibration produces **391 unique originally-discarded actionable bridge candidates**: 32 training/outreach, 59 health, 113 proofreading/annotation, 144 infrastructure/methods, and 50 network-science candidates (roles overlap).

## `triage_people.py`

Builds a multidimensional descriptive evidence matrix for people touching the derived nanoscale core. It reports productivity, fractional contribution, active years, axis breadth, coauthor structure, and hyperauthorship sensitivity. It deliberately does **not** assign an importance score or A/B/C/D tier before the empirical distributions are inspected.

For the final people map, run this after reviewed author aliases have been applied.

## Reproducibility principles

- Never mutate the preregistered broad corpus; derived views are separate outputs.
- Never reinterpret an original `keep=False` as a core-paper inclusion. IA-006 recovered records are role bridges only.
- Never merge people from name equality alone.
- Preserve raw paper IDs, author IDs, and discovery provenance.
- Keep empirical thresholds documented as local calibration choices rather than universal literature constants.
- Use explicit review/alias decisions for identity reconciliation.

See `docs/IA-004-provenance-and-author-reconciliation.md`, `docs/IA-005-proximity-aware-role-triage.md`, and `docs/IA-006-discovered-role-bridge-recovery.md` for the methodological rationale and frozen-run calibration.
