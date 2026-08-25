# IA-013 — Corpus graph views and emergent-core labeling

**Status:** Implemented (2026-08-24). Interpretation layer over IA-007-v3 **plus IA-014 overlays**; does not change screening JSON.  
**Depends on:** IA-007-v3 adjudication; human overlay and manual seeds (IA-014); citation roles (`analysis/analyze_citation_roles.py`); corpus views (`analysis/build_corpus_graph_views.py`); emergent (`analysis/build_emergent_core.py`).  
**Artifacts:** `postanalysis/llm_agent_v3/` — see `CORPUS_GRAPH_VIEW.md`, `EXPERIMENT_IA013_GRAPH_LAYERS.md`, `EMERGENT_CORE.md`. **Live counts:** `viz/corpus_graph_views_stats.json` (Layer A full is **1,806** after overlay/seeds, not the 1,853 in the worked example below).

---

## 1. Problem: keeping `no_graph` while dropping `weak_unlinked`

### What the current **prime** view does

| Class | Operational definition | Full | Current prime |
|---|---|---:|---|
| `weak_unlinked` | Graph-matched; **in-degree = 0** and **in+out ≤ 2** | 402 | **dropped** |
| `weak` | Graph-matched; total degree ≤ 2 but **in > 0** | 123 | kept |
| `moderate` / `strong` | Graph-matched; thicker attachment | 834 | kept |
| `no_graph` | Not present in the directed corpus citation graph | 494 | **kept** |

Prime = full − `weak_unlinked` → **1,451** works. Off-graph papers stay.

### Why that feels odd

Dropping papers we **measured** as thinly attached, while **keeping** papers we **could not measure at all**, mixes two different claims:

1. **Evidence of weak integration** (`weak_unlinked`): the paper is in the citation graph and has almost no reciprocal corpus links.
2. **Missing coverage** (`no_graph`): the paper never entered the graph build (identifier / OpenAlex / edge incompleteness), so link strength is undefined — not “strong,” not “weak.”

Treating (2) as automatically spine-eligible is epistemically inconsistent with a view marketed as “citation-integrated.” Conversely, treating (2) as automatically droppable would discard six **ultra_core** landmarks that are simply unmatched (e.g. Brenner 1985 touch circuit; MIB; VAST; FlyWire cell typing 2024).

So: **absence of graph evidence ≠ evidence of absence**, but **neither is it evidence of integration**.

---

## 2. Defensible adjudication (layer ladder)

Separate **semantic inclusion** (IA-007-v3) from **graph situability**. Do not use a single binary “prime” as “integrated.”

### Layer A — **Full** (semantic inclusive)

- **Rule:** `decision ∈ {core_relevant, adjacent_relevant, role_bridge}`.
- **n = 1,853** (current freeze).
- **Use:** high-recall audit, demotion review, periphery maps.

### Layer B — **Graph-matched**

- **Rule:** Full ∧ `citation_role ≠ no_graph`.
- **n = 1,359** (core 640, ultra 39).
- **CSV:** `corpus_graph_matched_works.csv`
- **Use:** any analysis that conditions on citation roles, in/out degree, k-core, link strength.
- **Rationale:** only here is “weak” meaningful.

### Layer C — **Integrated** (citation-integrated spine)

- **Rule:** Graph-matched ∧ `citation_link_strength ≠ weak_unlinked`.
- **n = 957** (core 538, ultra 39). Optional tightening: moderate ∪ strong only (≈834).
- **CSV:** `corpus_integrated_works.csv`
- **Use:** checkpoint / curriculum **when** the claim is “integrated in the corpus citation network.”
- **Rationale:** measured thin, one-way attachment is excluded; unmeasured papers are not smuggled in.

### Layer D — **Coverage rescue** (overlay on C)

For papers in `no_graph`, reinstate by **independent** evidence — not by pretending they are graph-integrated:

| Rescue path | Rule | Intent |
|---|---|---|
| R1 Ultra | `ultra_core` | Landmark impact already audited |
| R2 High external cites | `citation_count_work ≥ 100` | Global impact proxy when corpus edges missing |
| R3 Core floor | `core_relevant` ∧ cites ≥ 50 | Strict semantic + non-trivial impact |

**n = 101** rescued (22 core, **6 ultra**).  
**CSV:** `corpus_rescued_no_graph.csv`  
**C∪D:** `corpus_integrated_plus_rescue_works.csv` (**n = 1,058**; **all 45 ultra**). Flag `graph_status = rescued_no_graph`.

### Legacy prime (retained, demoted in language)

| Name | Rule | Prefer |
|---|---|---|
| **Prime** | full − weak_unlinked (keeps no_graph) | Call **audit cut**; do not say “integrated” |
| **Integrated / C∪D** | as above | Checkpoint / curriculum default |

### Recommended practice

1. **Report always:** Full / Graph-matched / Integrated / C∪D (and legacy prime if comparing older notes).
2. **Checkpoint default:** C∪D with `graph_status ∈ {integrated, rescued_no_graph}`.
3. **Human review queues (disjoint):**
   - `review_queue_weak_unlinked_core.csv` (102)
   - `review_queue_no_graph_core_unrescued.csv` (39)
4. **Do not** promote `no_graph` into “strong” by fiat.

Experiment write-up: `postanalysis/llm_agent_v3/EXPERIMENT_IA013_GRAPH_LAYERS.md`.

---

## 3. Emergent-core process (documented)

### Motivation

**ultra_core** requires proven citation mass (`cites ≥ 200`, or landmark title ∧ `cites ≥ 100`) on top of `core_relevant`. Young papers can be field-shaping but fail that bar because of **citation lag**. They must **not** be labeled ultra early; they stay in core with an explicit **emergent** watch-list until windows mature.

### Definition (implemented rule)

Script: `analysis/build_emergent_core.py` → `label_emergent_core.csv` + `emergent_core_summary.json` (n = **69**).

**Eligibility**

1. `decision == core_relevant`
2. **Not** `ultra_core`
3. Publication year **≥ 2019** (reference year for rates: **2026**)

**Impact signal** (any one of):

| Clause | Threshold | Notes |
|---|---|---|
| Age-normalized rate | `cites_per_year ≥` 90th percentile among recent (year≥2019) non-ultra core | Age = `max(0.5, 2026 − year)`; rate = cites / age; freeze p90 ≈ **12.27** |
| Within-year rank | `cites_pct_in_year ≥ 0.90` among **all core** in that calendar year | Percentile rank of `citation_count_work` |
| Very recent floor | year ≥ 2023 **and** cites ≥ 20 | Catches newest wave before percentiles stabilize |

**Explicit non-goals**

- Emergent is **not** a path into ultra_core without meeting the ultra rule later.
- Emergent is **not** a semantic tier (still `core_relevant`).
- Emergent does **not** require integrated membership (3 of 69 are `weak_unlinked`; 3 `no_graph`; **66** in C∪D).

### Bibliometric stance

| Label | Claim | Time scale |
|---|---|---|
| `ultra_core` | Proven high-impact core | Long window; absolute cites |
| `emergent_core` | High relative impact **for age / cohort** | Short window; rate + within-year percentile |
| plain `core` | Semantically core under IA-007-v3 | Independent of cites |

Promotion rule (policy): re-evaluate emergent set annually; move to ultra only when the **ultra** predicate becomes true; demote from emergent if rate/percentile fall below thresholds for two consecutive freezes.

### Regeneration

```bash
python analysis/build_corpus_graph_views.py   # annotates graph_status on full works
python analysis/build_emergent_core.py
```

Columns in `label_emergent_core.csv`:  
`work_id`, `title`, `year_n`, `citation_count_work`, `cites_per_year`, `cites_pct_in_year`, `citation_link_strength`, `corpus_in_degree`, `k_core`, `primary_community_label`, `confidence`, `graph_status`, `in_integrated_plus_rescue`.

### Relation to graph layers

Report emergent counts on **Full** and on **C∪D** separately. Do not silently drop emergent `weak_unlinked` from the watch-list; flag for periphery review.

---

## 4. Landing snapshot (2026-08-24 freeze)

| Set | n | Core | Ultra |
|---:|---:|---:|---:|
| Full | 1,853 | 701 | 45 |
| Prime legacy (full − weak_unlinked) | 1,451 | 599 | 45 |
| Graph-matched | 1,359 | 640 | 39 |
| Integrated | 957 | 538 | 39 |
| no_graph rescue (R1∨R2∨R3) | 101 | 22 | 6 |
| Integrated ∪ rescue | 1,058 | 560 | 45 |
| Emergent core (watch-list) | 69 | 69 | 0 |

Review queues: weak_unlinked∩core = **102**; no_graph∩core unrescued = **39**.

---

## 5. Decisions locked

1. Legacy prime remains generated but is an **audit cut**, not “integrated.”
2. Layers B/C/D (+ C∪D) are implemented in `build_corpus_graph_views.py` with the CSV names above.
3. Checkpoint default: **integrated ∪ rescue**.
4. Emergent is scripted and documented; **no** auto-promote to ultra.
5. Experiment record: `EXPERIMENT_IA013_GRAPH_LAYERS.md`.
