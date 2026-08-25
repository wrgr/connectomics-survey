# IA-012 — Inclusive checkpoint corpus, curriculum labels, and person reconciliation

## Series context

IA numbers are chronological amendments. **IA-012 does not supersede IA-002–IA-011.**
Earlier scientific / post-analysis amendments remain in force:

| IA | Scope |
|---|---|
| IA-002–IA-003 | Observability / modular runner (operational) |
| IA-004–IA-006 | Provenance core, role triage, bridge recovery |
| IA-007 | LLM-first semantic screening criteria & schema |
| IA-008 | Work reconciliation + abstract rescue |
| IA-009 | Offline agent adjudication path (+ Addendum A run record) |
| IA-010 | Record-type triage |
| IA-011 | Second-pass abstract recovery |
| **IA-012** | **This document — post-decision checkpoint derived layers only (from v2)** |
| IA-013 | Corpus graph views / emergent-core (over v3 + overlays) |
| IA-014 | Post-v3 membership overlays + provenance index |

## Status

Derived post-processing amendment **after** completed IA-007-v2 agent adjudication. It does **not** alter:

- the preregistered retrieval corpus or original `keep` values;
- IA-004 / IA-006 derived labels on frozen paper IDs;
- IA-007 adjudication decisions, criteria, or caches;
- IA-008 work links or abstract-rescue baselines.

All products live under `postanalysis/checkpoint/` (plus scripts in `analysis/`). Prior-run membership lists are **not** inputs to current labeling rules.

## Why this amendment

IA-007 yields provisional work-level decisions. Survey writing and network exploration need additional **transparent, regenerable** derived layers:

1. an inclusive checkpoint corpus;
2. draft curriculum / criticality labels;
3. author-name reconciliation for coauthorship graphs.

These layers are exploratory heuristics for analysis and writing support. They are **not** a second scientific screening pass and do not rewrite IA-007 decisions.

## Inclusive checkpoint corpus

**Definition:** all IA-007 screened works with decision in

`{core_relevant, adjacent_relevant, role_bridge}`

**Excluded:** `out_of_scope`, `uncertain`, auto-`insufficient_abstract`.

**Script:** `analysis/build_corpus_checkpoint.py`  
**Primary outputs:** `corpus_inclusive.csv`, `corpus_inclusive_authors.csv`, `checkpoint_summary.json`

Frozen-run headline (IA-007-v2 ingest complete): **1,912 / 4,136** works (46.2%).

## Analysis tiers and curriculum labels

**Script:** `analysis/analyze_corpus_tiers.py`  
**Docs:** `postanalysis/checkpoint/TIER_AND_GRAPH.md`

### Analysis tiers (confidence-aware splits of the checkpoint)

| Tier | Rule |
|---|---|
| `core_high_confidence` | `core_relevant`, confidence ≥ 0.85, not human-review flagged |
| `core_review` | other `core_relevant` |
| `adjacent` | `adjacent_relevant` |
| `role_bridge` | `role_bridge` |

### Curriculum labels (overlapping heuristics)

Assigned from **IA-007 decision + current work metadata only** (citations, title landmark cues, publication types, returned roles).

| Label | Rule |
|---|---|
| `field_defining` | `core_relevant` and (citations ≥ 100 **or** landmark-title regex and citations ≥ 40) |
| `core_methods` | `core_relevant` and roles ∩ {acquisition_preparation, reconstruction_segmentation, synapse_inference, proofreading_qc, infrastructure} |
| `key_for_students` | training/outreach role, Review type, student/survey title cues, or accessible infrastructure with modest citation support |

**Proposed (not yet implemented):** `ultra_core` as a tighter nest under `field_defining` (e.g. citations ≥ 200 **or** landmark ∩ citations ≥ 100). Documented here so the intent is captured before code lands.

### Explicit non-influence of prior runs

An earlier exploratory draft of `field_defining` also admitted papers that were members of the IA-004 file `derived_high_priority_nanoscale_curriculum_view.csv` with citations ≥ 20. That soft path **inflated** the label (~343 → mostly legacy overlap) and **coupled** current protocol to a previous derived run.

**Deviation / correction under IA-012:** that membership path is **removed**. Checkpoint labeling no longer reads IA-004 curriculum files. Optional offline comparison against archived IA-004 views remains allowed for diagnostics only.

## Person reconciliation (checkpoint coauthorship)

Distinct from IA-004’s Semantic Scholar **author-ID** candidate review (manual merge via aliases). Checkpoint reconciliation operates on **byline name strings** within the inclusive corpus.

**Script:** `analysis/reconcile_corpus_people.py`

| Step | Policy |
|---|---|
| Blocking | Unicode-folded names; remove single-letter middle initials |
| Auto-merge | Variants in the same block merge unless they co-occur on the same work (collision → keep separate) |
| Extra merges | Matching first+last tokens with strong shared coauthor-neighborhood evidence (probable threshold: ≥3 shared coauthor blocks, Jaccard ≥ 0.20, year overlap) |
| Audit | `person_aliases.csv`, `person_reconciliation_log.csv`, `person_reconciliation_summary.json` |

Frozen-run outcome: **6,889** surname+initial norms → **6,824** canonical people (62 merged components). Coauthorship graphs and the D3 viz use reconciled person IDs.

**Caveat:** this does not resolve distinct people who share a surname, ORCID-linked identity across unrelated strings, or full IA-004-style S2 ID adjudication. It is a name-variant layer for graph readability and unique-author counts in the checkpoint.

## Visualization

`analysis/build_checkpoint_viz.py` + `postanalysis/checkpoint/viz/` are **exploratory tooling**, not scientific protocol. Defaults: top-100 reconciled authors; top-120 field-defining/core-methods papers.

## Regenerability

```bash
python analysis/build_corpus_checkpoint.py
python analysis/reconcile_corpus_people.py
python analysis/analyze_corpus_tiers.py
python analysis/build_checkpoint_viz.py --top-authors 100
```

## What remains unchanged

- IA-007 decisions remain the screening source of record.
- Human review queues from IA-007 are unaffected.
- Frozen retrieval / keep / IA-004–IA-011 scientific provenance rules are not rewritten by this amendment.
