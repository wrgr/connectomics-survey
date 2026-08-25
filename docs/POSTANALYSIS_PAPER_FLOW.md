# Canonical post-analysis paper flow

Reference artifact SHA-256: `6c1b7ea962fb1dd58e4e8c84c216d2d2d6999392949b598165016a2c205ee68c`

This document fixes both provenance accounting and the later semantic-analysis universe. It does not modify the frozen source corpus.

```text
ALL DISCOVERED: 118,165
|
+-- ORIGINALLY RETAINED (keep=True): 3,768
|   |
|   +-- Derived nanoscale core .................... 1,685
|   |   +-- direct scope + resolution ............. 1,534
|   |   +-- inherited connectome provenance .......   151
|   |
|   +-- Strict retained role bridges ..............    15
|   |
|   +-- Unresolved retained non-core .............. 2,068
|       +-- macroscale review ...................... 1,018
|       +-- role signal, not strict bridge .........   841
|       +-- graph-supported adjacent review ........   149
|       +-- low-specificity review .................    60
|
+-- ORIGINALLY keep=False
    +-- strict recovered role bridges ..............   391
```

Frozen retained-provenance invariant:

`3,768 = 1,685 + 15 + 2,068`

The 391 recovered records remain `keep=False` for provenance, **but they are included in all later semantic/work-level analysis**.

## Raw semantic-analysis universe

`4,159 records = 3,768 originally retained + 391 recovered role-bridge records`

This is the correct record-level input to work reconciliation.

## IA-008 work reconciliation

Preprint/final versions and high-confidence metadata duplicates are linked without deleting source records. On the frozen-run dry run:

`4,159 records -> 4,136 canonical works`

- 22 canonical works have multiple source-version records;
- 23 redundant version records are collapsed for work-level counting/screening;
- source-version provenance remains in `work_versions.csv`.

Work-level source groups after reconciliation:

- **core audit:** 1,678 works;
- **unresolved:** 2,062 works;
- **role bridge:** 396 works.

The role-bridge work count is lower than the 406 bridge-record count because some bridge records are alternate versions of the same work or link into a work whose retained-version category has precedence. No source bridge record is discarded.

## Abstract rescue

Before network rescue, 321/4,136 canonical works still lack an abstract. IA-008 attempts best-effort rescue from Semantic Scholar, Europe PMC, optional OpenAlex and Crossref. Remaining missing abstracts cannot be excluded from title alone.

## IA-007 LLM denominator

IA-007 runs after work reconciliation and abstract rescue on **all canonical works**:

- core-audit works for a noise/false-positive check;
- unresolved works as the primary relevance-classification population;
- role-bridge works, including IA-006 recovered bridges.

Therefore the LLM **screen ingest** denominator was **4,136 canonical works**, subject only to later reviewed corrections to work-version links. It is no longer 3,753 papers.

Audited manual same-work links (IA-008 / IA-014) later collapsed additional versions. **Current canonical-work count is 4,100** (`postanalysis/works/work_reconciliation_summary.json`). Collapsed records remain in `work_versions.csv`.

## IA-007-v3 screening of record

v2 agent adjudication (`postanalysis/llm_agent/`) is the historical high-recall pass. The **current screening of record** is IA-007-v3 (`prompt_version` `IA-007-v3-work-level`, complete ingest under `postanalysis/llm_agent_v3/`). Criteria: `docs/IA-007-v3-screening-criteria-draft.md` (filename retained; status is accepted). Agent JSON is not rewritten afterward.

## IA-012 checkpoint derived layers (v2, historical)

After IA-007-v2 adjudication completed, **IA-012** defined regenerable derived views under `postanalysis/checkpoint/`:

- inclusive corpus = `{core_relevant, adjacent_relevant, role_bridge}`;
- analysis tiers and curriculum labels from IA-007 decisions + current metadata only;
- checkpoint person-name reconciliation for coauthorship graphs.

These layers do **not** rewrite IA-007 decisions and do **not** use prior-run membership lists as labeling inputs. They are the **v2 checkpoint**, not the working v3 corpus. See `docs/IA-012-checkpoint-corpus-curriculum-and-person-recon.md`.

## IA-014 overlays (working membership)

Working inclusive membership applies, in order, on top of v3 agent decisions:

1. human screening overlay — `human_review_decisions.csv` (`analysis/human_review.py`);
2. manual seeds for frozen-discovery holes — `manual_seed_works.csv` (`analysis/manual_seeds.py`).

Snapshot inclusive **full** corpus: `postanalysis/llm_agent_v3/corpus_full_works.csv`. Provenance index: `docs/IA-014-post-v3-overlays-and-decision-provenance.md`.

## IA-013 graph situability

Semantic inclusion (v3 + IA-014) is separate from citation-graph situability. Default “citation-integrated, with coverage rescue” view is `corpus_integrated_plus_rescue_works.csv`. Counts: `postanalysis/llm_agent_v3/viz/corpus_graph_views_stats.json`. See `docs/IA-013-corpus-graph-views-and-emergent-core.md`.
