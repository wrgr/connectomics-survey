# Emergent core

Formal definition: [docs/IA-013-corpus-graph-views-and-emergent-core.md](../../docs/IA-013-corpus-graph-views-and-emergent-core.md) (§3)  
Experiment context: [EXPERIMENT_IA013_GRAPH_LAYERS.md](EXPERIMENT_IA013_GRAPH_LAYERS.md)

**Build:** `python analysis/build_emergent_core.py`  
**List:** `label_emergent_core.csv` (n=69)  
**Summary:** `emergent_core_summary.json`

**Rule:** `core_relevant` ∧ ¬ultra ∧ year≥2019 ∧ (cites/year ≥ p90 among recent non-ultra core ∨ within-year cite percentile ≥ 0.9 ∨ (year≥2023 ∧ cites≥20)).

**Policy:** stays in core; never auto-promoted to `ultra_core`. Graph layer is annotated (`graph_status`, `in_integrated_plus_rescue`) but not used as an eligibility gate.
