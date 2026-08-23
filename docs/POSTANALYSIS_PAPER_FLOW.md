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

Therefore the current expected LLM denominator is **4,136 canonical works**, subject only to later reviewed corrections to work-version links. It is no longer 3,753 papers.
