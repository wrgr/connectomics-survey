# Post-processing and reconciliation

This directory contains **derived-analysis tooling** for completed deterministic connectomics runs. It does not alter the preregistered retrieval corpus or scientific protocol.

## `postprocess_run.py`

Reproduces the QC tables and ten visualization panels used for the first fresh full run. It can consume either a GitHub Actions artifact ZIP or an extracted `outputs/` directory.

Example:

```bash
python analysis/postprocess_run.py \
  --artifact connectomics-fresh-outputs.zip \
  --expected-sha256 6c1b7ea962fb1dd58e4e8c84c216d2d2d6999392949b598165016a2c205ee68c \
  --out postprocessed
```

## `reconcile_cleanup.py`

Creates conservative derived corpus views and review queues. It never deletes papers or merges people automatically.

```bash
python analysis/reconcile_cleanup.py \
  --outputs-dir extracted/connectomics_deterministic_pipeline/outputs \
  --out reconciliation
```

### Paper cleanup

The broad retained corpus is preserved. The script derives:

- `direct_nanoscale_view`: explicit `direct_scope+resolution` evidence;
- `high_priority_direct_nanoscale_curriculum_view`: direct view plus `core_candidate`/`supported` tier;
- `graph_supported_adjacent_view`: non-direct papers with at least two corpus citation links to direct nanoscale papers;
- `paper_cleanup_review_queue`: every retained paper assigned to a transparent review bucket.

No paper is automatically excluded.

### Person reconciliation

The first pass blocks only on exact normalized names, then scores each pair with coauthor-neighborhood overlap, axis overlap, and relevant-year overlap. It outputs `probable_same_person`, `possible_same_person`, and `ambiguous_name_collision` candidates.

**No candidate is automatically merged.** A reviewed alias table should be the only mechanism for reconciliation: source Semantic Scholar author IDs remain immutable, while approved aliases map to a separate canonical person ID. Strong candidates should be confirmed using Semantic Scholar author profiles, ORCID, institutional pages, or publication rosters before the alias is accepted.

This conservative architecture distinguishes *candidate generation* from *identity adjudication* and makes every manual merge auditable.
