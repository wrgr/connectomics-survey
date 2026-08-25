# IA-014 — Post-v3 membership overlays and decision provenance

**Status:** Implemented (2026-08-25). Does not rewrite frozen retrieval, IA-007 agent JSON, or IA-008 version rows.  
**Depends on:** IA-007-v3 ingest; IA-008 canonical works; human and seed CSVs below.  
**This document is the provenance index for the current working corpus.** Earlier IAs remain in force; where a headline count drifted, this file states which file is source of record.

---

## 1. What is frozen vs overlay vs derived

Nothing in this chain mutates the preregistered retrieval corpus or original `keep` values. Later steps either **label**, **overlay**, or **derive**.

| Layer | Kind | Mutates screening JSON? | Source of record |
|---|---|---|---|
| Frozen retrieval artifact | frozen | no | `source_artifact/connectomics_deterministic_pipeline/outputs/` (SHA in `docs/POSTANALYSIS_PAPER_FLOW.md`) |
| IA-004–006 core / bridges | derived labels on paper IDs | no | accounting + bridge CSVs under `postanalysis/` / `bridges/` |
| IA-008 works | reconciliation | no | `postanalysis/works/canonical_works.csv`, `work_versions.csv`, `work_link_evidence.csv` |
| IA-008 / IA-011 abstracts | enrichment | no | `postanalysis/enriched/`, `postanalysis/enriched2/` |
| IA-007-v2 agent screen | historical first pass | no | `postanalysis/llm_agent/` |
| IA-007-v3 agent screen | **current screening of record** | no | `postanalysis/llm_agent_v3/llm_relevance_results.csv` + `adjudication/decisions/` |
| IA-010 record types | labels | no | `postanalysis/record_types/work_record_types.csv` |
| IA-012 checkpoint | derived from **v2** | no | `postanalysis/checkpoint/` (historical; not the working corpus) |
| Manual same-work links | IA-008 overlay | no (rebuilds works) | `postanalysis/works/manual_work_links.csv` |
| Human screening overlay | membership overlay | **no** | `postanalysis/llm_agent_v3/human_review_decisions.csv` |
| Manual seeds | discovery-hole adds | no | `postanalysis/works/manual_seed_works.csv` |
| IA-013 graph layers | derived views | no | `postanalysis/llm_agent_v3/corpus_*_works.csv` + `viz/corpus_graph_views_stats.json` |
| Citation-tier overlay | derived view | no | `analysis/citation_tier_overlay.py` products |
| PDF catalog | artifact harvest | no | `postanalysis/pdfs/paper_links.csv` (binaries gitignored) |

**Working inclusive corpus** = IA-007-v3 decisions, after human overlay, plus manual seeds, with decision in `{core_relevant, adjacent_relevant, role_bridge}`. Snapshot: `postanalysis/llm_agent_v3/corpus_full_works.csv`.

---

## 2. Amendment index (chronological)

| IA | What it decided | Still source of record? |
|---|---|---|
| IA-002–003 | Observability / modular runner | yes (ops) |
| IA-004 | Provenance-derived nanoscale core; person candidates | yes on paper IDs |
| IA-005–006 | Role triage; recover `keep=False` bridges into analysis | yes |
| IA-007 | LLM-first screen schema; high-recall first pass | schema yes; **v2 labels superseded for membership** |
| IA-007-v3 | Strict-core / fair-placement criteria; full re-screen | **yes — current screen** |
| IA-008 | Work/version reconciliation; abstract rescue pass one | yes; counts updated after manual links |
| IA-009 | Offline agent execution path (v2 run + Addendum A) | yes for v2 path; v3 used the same path |
| IA-010 | Record-type triage (papers vs non-papers) | yes (labels; not exclusions) |
| IA-011 | Second-pass abstract recovery | yes (`enriched2/`) |
| IA-012 | Inclusive checkpoint + curriculum from **v2** | yes as v2 checkpoint; **not** working corpus |
| IA-013 | Graph situability layers; emergent-core | yes as views over v3+overlays |
| **IA-014** | **This file — overlays + which numbers to cite** | **yes for membership overlays** |

---

## 3. Counting chain (cite the named file, not this table, if they disagree)

Snapshot **2026-08-25**.

| Step | Count | File |
|---|---:|---|
| All discovered | 118,165 | frozen retrieval |
| Originally retained (`keep=True`) | 3,768 | frozen invariant |
| Recovered role bridges (`keep=False`, in analysis) | 391 | IA-006 |
| Raw semantic-analysis records | 4,159 | `3,768 + 391` |
| Canonical works at v2/v3 **screen ingest** | **4,136** | `llm_agent_v3/run_manifest.json` / `llm_relevance_summary.json` |
| Canonical works **after audited manual links** | **4,100** | `works/work_reconciliation_summary.json` |
| v3 screened / undecided | 4,136 / 0 | `llm_relevance_summary.json` |
| IA-010 research papers / non-papers (on the 4,136-work screen set) | 4,086 / 50 | `record_types/record_type_summary.json` |
| Human overlay rows | 68 | `human_review_decisions.csv` |
| of which `out_of_scope` | 57 | same |
| of which agent≠human | 35 | same |
| Manual seeds (not in frozen discovery) | 8 | `manual_seed_works.csv` |
| Working inclusive (**full**) | **1,806** | `corpus_full_works.csv` (core 694, adjacent 911, bridge 201) |
| Graph-matched | 1,314 | `viz/corpus_graph_views_stats.json` |
| Integrated | 931 | same |
| Integrated ∪ coverage rescue | **1,038** | same (`corpus_integrated_plus_rescue_works.csv`) |

The 4,136 → 4,100 drop is **version collapse**, not exclusion. Every collapsed record remains in `work_versions.csv`. v3 agent JSON is keyed to the 4,136-work IDs from ingest; `analysis/remap_screening_work_ids.py` exists for remapping after reconciliation changes.

IA-013 prose that still says full **n = 1,853** was written before the human overlay and seeds. Prefer `corpus_graph_views_stats.json`.

---

## 4. Human screening overlay

**CSV:** `postanalysis/llm_agent_v3/human_review_decisions.csv`  
**Code:** `analysis/human_review.py`

Rules:

1. Agent batch JSON is never rewritten.
2. `human_decision` overlays `decision` at corpus-build and PDF-collection time.
3. `human_decision=out_of_scope` drops the work from inclusive views and from the PDF harvest set.
4. Confirmations (`agent_decision == human_decision`) are kept so the audit trail is complete.

This is a **membership** overlay, not a second model run. It covers targeted noise (molecular/macro false includes), duplicate-pair exclusions that were not merged, and a small number of promotions.

---

## 5. Manual same-work links

**CSV:** `postanalysis/works/manual_work_links.csv` (41 pairs; 36 applied on the last reconciliation, per `work_reconciliation_summary.json`)  
**Log:** `postanalysis/works/DUPLICATE_REVIEW_APPLIED.md`  
**Code:** `analysis/reconcile_paper_works.py` step 5

Audited preprint/journal and near-duplicate pairs that automatic title similarity missed. Applied on rebuild; source versions retained. Some duplicate *pairs* were instead **both excluded** via the human overlay (unc-4/Hox; neuropeptide male *C. elegans*) rather than merged — see the duplicate-review log.

---

## 6. Manual seeds (discovery-set holes)

**CSV:** `postanalysis/works/manual_seed_works.csv`  
**Code:** `analysis/manual_seeds.py`  
**`source_group`:** `manual_seed`  
**`prompt_version`:** `IA-007-v3-manual-seed`

Eight landmark works cited from Helmstaedter 2025 *Nature Reviews Neuroscience* coverage holes and **absent from frozen Semantic Scholar discovery**. Human-assigned `core_relevant`. Concatenated into citation-role / corpus views only; they do not alter `keep` on the retrieval artifact.

| Year | Work |
|---:|---|
| 1986 | White et al., *C. elegans* nervous system structure |
| 2004 | Denk & Horstmann, SBF-SEM |
| 2011 | Briggman et al., retinal direction-selectivity wiring |
| 2011 | Helmstaedter et al., KNOSSOS / RESCOP |
| 2013 | Helmstaedter et al., mouse IPL connectome |
| 2014 | Kim / EyeWire, space-time wiring specificity |
| 2015 | Kasthuri et al., saturated neocortex volume |
| 2017 | Januszewski et al., flood-filling networks |

---

## 7. PDF harvest universe (not a scientific denominator)

`analysis/collect_corpus_pdfs.py` unions **IA-012 v2 inclusive** with **v3 working inclusive**, then subtracts human `out_of_scope`. That union is for **open-access file capture**, not for reporting corpus size. Paywalled works keep landing URLs. Binary PDFs under `postanalysis/pdfs/files/` are gitignored; `paper_links.csv` is the versioned catalog.

---

## 8. Derived views that must not be cited as screening decisions

- **IA-012 checkpoint** (`postanalysis/checkpoint/`): built from **v2**. Core was too permissive; keep as historical comparison.
- **IA-013 layers:** semantic inclusion vs graph situability. Default checkpoint-when-coverage-matters view is **integrated ∪ rescue**.
- **Ultra-core / emergent-core:** heuristics on v3 core + citations/title landmarks (`analyze_citation_roles.py`, `build_emergent_core.py`). Not a human gold set.
- **Citation-tier overlay** (`citation_tier_overlay.py`): exploratory ultra / connected-core / contextual-ring / hidden-gem / drop. Does not rewrite agent JSON.
- **Record types:** non-papers stay in the 4,136-work provenance; report the paper denominator *alongside*, not instead of, that count.

---

## 9. Stale text to ignore if it conflicts

| Location | Stale claim | Replace with |
|---|---|---|
| `docs/IA-007-v3-screening-criteria-draft.md` title (filename kept) | “draft; v2 remains source of record” | Addendum A in that file; this IA-014 |
| `postanalysis/llm_agent_v3/RUN.md` queue tables | in-progress 3,783/3,983 | ingest complete; `run_manifest.json` |
| IA-013 §2 Layer A **n = 1,853** | pre-overlay | `corpus_graph_views_stats.json` |
| IA-012 frozen **1,912** inclusive | **v2** checkpoint | working corpus = v3 full 1,806 |
| LLM denominator **4,136** as *current* canonical | screen ingest | current canonical **4,100** after manual links |

---

## 10. Honesty

Human overlay and seeds are **small, explicit, CSV-auditable** exceptions on top of a complete v3 agent pass. They are the right place to put “we looked at this paper” decisions. They are the wrong place to hide a silent re-screen. If a future pass changes criteria, fork `prompt_version` and compare with `compare_screening_runs.py` rather than growing the overlay.
