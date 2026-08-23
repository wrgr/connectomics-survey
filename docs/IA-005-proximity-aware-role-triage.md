# IA-005 — Proximity-aware role triage

## Purpose

Triage non-core retained papers by combining role-specific textual evidence with measured proximity to the IA-004 derived nanoscale core. The frozen broad corpus remains unchanged.

## Methodological basis

Bibliometric science mapping treats direct citation, bibliographic coupling, and co-citation as complementary indicators of publication relatedness. Large-scale comparisons show that no single citation relation is universally optimal and that hybrid citation/text approaches can improve coherence. Citation-context research further shows that citations differ in function: method use, extension, comparison, support, and background do not imply equal substantive relatedness. Therefore IA-005 preserves multiple proximity channels separately and uses them to prioritize review rather than treating citation adjacency as proof of inclusion.

References include Boyack & Klavans (2010), JASIST, doi:10.1002/asi.21419; Small (2018), Journal of Informetrics, doi:10.1016/j.joi.2018.03.007; and the citation-classification literature summarized in Quantitative Science Studies (2021), 2(4):1170-1218.

## Role channels

The first implementation nominates five role families:

- health/translation;
- training, outreach, workforce, and citizen science;
- proofreading/annotation/human-in-the-loop;
- infrastructure/methods;
- network science/graph analysis.

Existing protocol lexical hits are preserved as discovery evidence. Additional conservative phrase patterns are added for role nomination. A role hit does not establish nanoscale scope.

## Proximity channels

For every retained paper, compute relative to the 1,685-paper IA-004 core:

1. number of core papers cited by the candidate;
2. number of core papers that cite the candidate;
3. number of core papers bibliographically coupled to the candidate (at least one shared reference in the retrieved graph);
4. number of core papers with a shared citing neighborhood (co-citation-like proxy in the retrieved graph).

These channels remain separate in outputs. A summed hybrid proximity is used only for queue ordering.

## Review strata

Initial queue-prioritization heuristics:

- strong: >=2 direct core links OR >=5 hybrid links;
- moderate: >=1 direct core link OR >=2 hybrid links;
- weak/none: otherwise.

These numbers are **not literature-standard inclusion thresholds**. They are review-queue heuristics and must be calibrated/audited on the frozen run before any automatic retain/exclude rule is adopted.

Triage actions are therefore deliberately non-final:

- `retain_core` — already IA-004 core;
- `priority_adjacent_review` — strong proximity plus at least one nominated role;
- `adjacent_review` — moderate/strong proximity without a role nomination;
- `role_bridge_review` — role nomination but weak measured proximity;
- `low_priority_review` — neither.

## Why this matters

This structure lets health, outreach/training, proofreading, infrastructure, and network-science papers earn field relevance from demonstrable proximity to the nanoscale corpus without making generic terms such as `health`, `training`, or `network` sufficient for inclusion. It also avoids a single undirected-distance rule and leaves room for later Semantic Scholar citation-intent evidence (`Uses`, `Methods`, influential citations, contexts) where available.
