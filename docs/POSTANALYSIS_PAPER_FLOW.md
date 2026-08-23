# Canonical post-analysis paper flow

Reference artifact SHA-256: `6c1b7ea962fb1dd58e4e8c84c216d2d2d6999392949b598165016a2c205ee68c`

This document fixes the denominator accounting used by the derived post-analysis. It does not modify the frozen source corpus.

```text
ALL DISCOVERED: 118,165
|
+-- ORIGINALLY RETAINED: 3,768
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

Invariant for the retained corpus:

`3,768 = 1,685 + 15 + 2,068`

The **391 recovered role bridges are outside the 3,768 originally-retained denominator**. Therefore strict role bridges across both origins total `15 + 391 = 406`, but `1,685 + 406` is not a retained-corpus partition.

## IA-007 semantic-screening denominator

The default LLM-first semantic pass includes:

- all 1,685 derived-core papers as a noise audit; and
- all 2,068 unresolved retained papers as the primary relevance-screening population.

Total LLM-first target: **3,753** papers.

The 15 strict retained bridges and 391 recovered bridges are outside the default IA-007 pass and retain their role-bridge provenance. They can be audited separately later.

On the frozen artifact, **242/3,753** IA-007 target papers lack abstracts and must therefore route to human/full-text review rather than semantic exclusion from title alone.
