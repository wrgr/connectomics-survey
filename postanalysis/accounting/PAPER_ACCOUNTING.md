# Canonical post-analysis paper accounting

## Frozen retrieval provenance

- **Originally retained (`keep=True`): 3,768**
  - Derived nanoscale core: **1,685**
  - Strict retained role bridges: **15**
  - Unresolved retained non-core: **2,068**

This is the immutable retrieval provenance denominator: `3,768 = 1,685 + 15 + 2,068`.

## Semantic-analysis record universe

IA-006 additionally recovered **391** role-bridge records whose original `keep` value remains false. These records are included in all subsequent semantic/work-level analysis.

**Raw semantic-analysis universe: 4,159 records = 3,768 retained + 391 recovered bridge records.**

IA-008 reconciles preprint/final and metadata-duplicate versions within those 4,159 records before LLM screening. Therefore the LLM denominator is the resulting number of canonical works, not 4,159 raw records.
