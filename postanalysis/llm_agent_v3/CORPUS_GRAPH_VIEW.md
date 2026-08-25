# Corpus graph views — full, prime, and IA-013 layers

**Protocol:** IA-007-v3 screening + citation-graph / authorship readout  
**Decision record:** [docs/IA-013-corpus-graph-views-and-emergent-core.md](../../docs/IA-013-corpus-graph-views-and-emergent-core.md)  
**Experiment log:** [EXPERIMENT_IA013_GRAPH_LAYERS.md](EXPERIMENT_IA013_GRAPH_LAYERS.md)  
**Emergent:** [EMERGENT_CORE.md](EMERGENT_CORE.md)  
**Stats JSON:** `corpus_graph_views.json`  
**Figures:** `viz/00_ia013_layer_ladder.svg`, `viz/00_full_vs_prime_ladder.svg`, `viz/{full,prime,matched,integrated,integrated_rescue}_*.svg`

```bash
python analysis/build_corpus_graph_views.py
python analysis/build_emergent_core.py
python analysis/compare_v2_v3_quick.py
python analysis/build_people_tables.py
python analysis/build_paper_lists_and_figures.py
```

---

## Layer ladder (preferred)

| Layer | Definition | Works | Core | Ultra | Use |
|---|---|---:|---:|---:|---|
| **A Full** | v3 inclusive | 1,853 | 701 | 45 | High-recall audit |
| **Prime (legacy)** | Full − `weak_unlinked` (**keeps `no_graph`**) | 1,451 | 599 | 45 | Audit continuity only |
| **B Graph-matched** | Full − `no_graph` | 1,359 | 640 | 39 | Analyses needing degrees/roles |
| **C Integrated** | B − `weak_unlinked` | 957 | 538 | 39 | True citation-integrated spine |
| **D Rescue** | `no_graph` ∧ (ultra ∨ cites≥100 ∨ core∧cites≥50) | 101 | 22 | 6 | Coverage repair (flagged) |
| **C∪D** | Integrated ∪ rescue | **1,058** | **560** | **45** | **Default checkpoint / curriculum** |

Shared rules:

1. **Semantic tiers** from IA-007-v3 agent adjudication.
2. **Citation roles** on the directed corpus graph (asymmetric; high out/in is normal).
3. **Link strength:** `weak_unlinked` / `weak` / `moderate` / `strong` (total degree ≤ 2 ⇒ weak family; weak_unlinked if also in = 0). Undefined for `no_graph`.
4. **Authorship trim (`trim_middle`):** exclude sole middle-only credit; consortium middles kept if they have other credit.
5. **ultra_core:** `core_relevant` ∧ (cites ≥ 200 ∨ landmark title ∧ cites ≥ 100).
6. **`graph_status`:** `integrated` | `weak_unlinked` | `no_graph` | `rescued_no_graph` on full works.

**Why not call legacy prime “integrated”?** It drops measured thin links but keeps 494 unmeasured (`no_graph`) papers. Missing coverage ≠ integration. See IA-013.

---

## Review queues (disjoint)

| Queue | File | n |
|---|---|---:|
| Measured thin core | `review_queue_weak_unlinked_core.csv` | 102 |
| Off-graph core, not rescued | `review_queue_no_graph_core_unrescued.csv` | 39 |

Do not merge these queues — different failure modes.

---

## Emergent core

Young non-ultra core with high relative impact (citation lag). **n=69**; 66 sit in C∪D. Stays in core; never auto-promotes to ultra. Rule + CSV: `EMERGENT_CORE.md`, `label_emergent_core.csv`.

---

## People (trim_middle)

| View | Persons | Top-100 floor (works) |
|---|---:|---:|
| Full | 3,281 | ≥14 |
| Prime (legacy) | 2,649 | ≥13 |
| Integrated | 1,806 | ≥11 |
| Integrated ∪ rescue | 2,004 | ≥12 |

Files: `people_{view}.csv`, `people_{view}_top100.csv`, `people_{view}_top100_by_last.csv`.

---

## Outputs

| File | Contents |
|---|---|
| `corpus_full_works.csv` | Full + layer flags |
| `corpus_prime_works.csv` | Legacy prime |
| `corpus_graph_matched_works.csv` | B |
| `corpus_integrated_works.csv` | C |
| `corpus_rescued_no_graph.csv` | D |
| `corpus_integrated_plus_rescue_works.csv` | C∪D |
| `corpus_prime_dropped_weak_unlinked.csv` | Dropped for legacy prime |
| `corpus_dropped_no_graph.csv` / `corpus_no_graph_not_rescued.csv` | Off-graph splits |
| `*_communities.csv` | Per-view community aggregates |
| `corpus_graph_views.json` | Combined stats + `layer_ladder` |
| `label_ultra_core_ranked.csv` / `label_core_ranked.csv` | Explicit paper lists |
| `label_emergent_core.csv` | Emergent watch-list |

---

## Recommended use

1. **Checkpoint / curriculum** → `corpus_integrated_plus_rescue_works.csv` (filter core ∩ moderate∪strong∪ultra or keep rescued flag visible).
2. **Strict graph analyses** → integrated (C) only.
3. **Periphery / demotion audit** → full; prioritize the two review queues.
4. **ultra_core / emergent** → lists under `label_*.csv`; ultra identical on full and C∪D (n=45).
