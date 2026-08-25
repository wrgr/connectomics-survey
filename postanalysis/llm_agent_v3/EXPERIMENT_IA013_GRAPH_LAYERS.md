# Experiment log — IA-013 graph-layer ladder (2026-08-24)

**Question.** Is legacy **prime** (full − `weak_unlinked`, keeping `no_graph`) a defensible “citation-integrated” corpus?

**Motivation.** Dropping papers with *measured* thin attachment while keeping papers with *missing* citation-graph coverage mixes two claims. See [IA-013](../../docs/IA-013-corpus-graph-views-and-emergent-core.md).

---

## Design

| Layer | Operational rule | Intended claim |
|---|---|---|
| **A Full** | v3 inclusive | Semantic field map |
| **Prime (legacy)** | Full − `weak_unlinked` | Audit cut only (keeps `no_graph`) |
| **B Graph-matched** | Full − `no_graph` | Situable in directed corpus citation graph |
| **C Integrated** | B − `weak_unlinked` | Citation-integrated spine |
| **D Rescue** | `no_graph` ∧ (ultra ∨ cites≥100 ∨ (core ∧ cites≥50)) | Coverage repair; **not** claimed integrated |
| **C∪D** | Integrated ∪ Rescue | Preferred checkpoint when gaps matter |

**Disjoint review queues**

1. `weak_unlinked ∩ core` — measured periphery  
2. `no_graph ∩ core` not rescued — coverage / identity repair  

**Emergent core** (parallel watch-list): young non-ultra core with high relative impact; never auto-promotes to ultra (`analysis/build_emergent_core.py`).

---

## Implementation

```bash
python analysis/build_corpus_graph_views.py
python analysis/build_emergent_core.py
python analysis/build_people_tables.py
python analysis/build_paper_lists_and_figures.py
```

Key outputs under `postanalysis/llm_agent_v3/`:

| Artifact | Role |
|---|---|
| `corpus_full_works.csv` | A + `graph_status` / layer flags |
| `corpus_prime_works.csv` | Legacy prime |
| `corpus_graph_matched_works.csv` | B |
| `corpus_integrated_works.csv` | C |
| `corpus_rescued_no_graph.csv` | D only |
| `corpus_integrated_plus_rescue_works.csv` | C∪D |
| `review_queue_weak_unlinked_core.csv` | Queue 1 |
| `review_queue_no_graph_core_unrescued.csv` | Queue 2 |
| `label_emergent_core.csv` / `emergent_core_summary.json` | Emergent watch-list |
| `viz/00_ia013_layer_ladder.svg` | Layer comparison figure |
| `corpus_graph_views.json` → `layer_ladder` | Machine-readable counts |
| `people_{full,prime,graph_matched,integrated,integrated_plus_rescue}*.csv` | People per layer |

`graph_status` values on full works: `integrated` | `weak_unlinked` | `no_graph` | `rescued_no_graph`.

---

## Results (this freeze)

| Layer | Works | Core | Ultra |
|---|---:|---:|---:|
| Full | 1,853 | 701 | 45 |
| Prime (legacy) | 1,451 | 599 | 45 |
| Graph-matched | 1,359 | 640 | 39 |
| Integrated | 957 | 538 | 39 |
| Rescued no_graph | 101 | 22 | 6 |
| **Integrated ∪ rescue** | **1,058** | **560** | **45** |

| Queue | n |
|---|---:|
| weak_unlinked ∩ core | 102 |
| no_graph ∩ core, unrescued | 39 |

**Emergent:** n=69; 66 in C∪D; 3 `weak_unlinked`; 3 `no_graph`. p90 cites/year (recent non-ultra core) = 12.27.

**People (trim_middle):** full 3,281 → prime 2,649 → matched (via people tables) → integrated 1,806 → C∪D **2,004**.

---

## Interpretation

1. Legacy prime (**1,451**) is larger than true integrated (**957**) because it retains **494** `no_graph` papers without an integration claim.
2. Pure integrated drops **6 ultra** that are off-graph; rescue restores them (and 95 other high-evidence no_graph works) → **all 45 ultra** in C∪D.
3. “Citation-integrated spine” should mean **C** (or **C∪D** with an explicit `rescued_no_graph` flag) — not legacy prime.
4. Emergent stays a **core watch-list**; graph layer membership is reported, not used as an eligibility gate.

---

## Decisions locked by this experiment

1. Keep generating legacy prime for continuity; label it **audit cut**, not integrated.
2. Default checkpoint / curriculum starting set: **`corpus_integrated_plus_rescue_works.csv`**.
3. Maintain the two disjoint core review queues.
4. Emergent regeneration is scripted (`build_emergent_core.py`); no auto ultra promotion.

---

## Follow-ups (not in this run)

- Tighten C further to moderate∪strong only (n≈834) as an optional “dense spine.”
- Repair OpenAlex / edge coverage for the 39 unrescued no_graph core papers.
- Fold layer ladder + emergent into the offline PDF on next review rebuild.
