# Corpus cleanup and person reconciliation process

This is a **derived post-processing layer**. The preregistered broad corpus remains immutable.

## 1. Paper scope cleanup

`reconcile_cleanup.py` assigns every retained paper to one transparent bucket:

1. `direct_nanoscale` — `scope_reasons` contains `direct_scope+resolution`.
2. `graph_supported_adjacent` — not direct, but at least two corpus citation links connect it to direct-nanoscale papers.
3. `macroscale_review` — explicit macroscale trigger terms remain and the paper did not meet either rule above.
4. `bridge_term_review` — retained through health or training/outreach lexical evidence but without the two stronger rules above.
5. `low_specificity_review` — everything else.

These are **review categories, not exclusion decisions**. In particular, macroscale comparison papers and generic network-science methods can still be valuable if their relationship to nanoscale connectomics is demonstrable.

The script also emits two convenient positive views:

- `derived_direct_nanoscale_view.csv`
- `derived_high_priority_direct_nanoscale_curriculum_view.csv` (`direct_nanoscale` plus `core_candidate` or `supported` tier)

Any later human exclusion should be recorded in a separate adjudication table with paper ID, decision, reason, reviewer, and date. The original retained table is never rewritten.

## 2. Person candidate generation

Name equality is not identity. `reconcile_cleanup.py` therefore uses exact normalized names **only to generate candidate pairs**.

For each pair it computes:

- number of shared normalized coauthor names;
- coauthor-neighborhood Jaccard similarity;
- lexical-axis Jaccard similarity;
- overlap of first/latest relevant publication years.

The v1 triage rules are:

- `probable_same_person`: exact normalized name, at least 3 shared coauthor names, coauthor Jaccard >= 0.20, and overlapping relevant-year intervals;
- `possible_same_person`: exact normalized name, at least 1 shared coauthor name, coauthor Jaccard >= 0.10, and overlapping relevant-year intervals;
- `ambiguous_name_collision`: same normalized name but insufficient relational evidence.

These thresholds prioritize review efficiency; they are not identity proof.

## 3. Manual identity verification

Before any merge, inspect independent identity evidence. Preferred evidence, roughly strongest first:

1. ORCID or another stable researcher identifier linking both records;
2. Semantic Scholar author profiles/aliases and overlapping publication rosters;
3. institutional or laboratory profile showing matching publication history;
4. multiple shared coauthors plus consistent subject area and chronology;
5. publication pages that demonstrate both S2 IDs refer to the same author.

A reviewed candidate file must add a `decision` column. Supported decisions are:

- `merge` — sufficient evidence that the source author IDs represent one person;
- `separate` — evidence supports distinct people;
- `unresolved` — insufficient evidence; do not merge.

Optional audit columns are `canonical_person_id`, `evidence_url_or_identifier`, `reviewer`, `review_date`, and `notes`.

## 4. Applying approved merges

`apply_person_aliases.py` consumes the reviewed candidate table and uses **only** rows whose decision is exactly `merge`.

It creates:

- `person_aliases.csv`: immutable source S2 author ID → canonical person ID;
- `paper_canonical_person_edges.csv`: unique paper-person relationships after aliasing;
- `people_reconciled.csv`: recomputed unique retained-paper counts, core-candidate counts, year span, and axis breadth;
- `applied_merge_decisions.csv`: the exact reviewed rows that affected identity;
- `person_reconciliation_applied_summary.json`.

If no canonical person ID is supplied manually, a stable `s2:<root_author_id>` identifier is generated. Conflicting manual canonical IDs inside one merged component cause a hard failure.

## 5. What remains intentionally unresolved

The first version does **not** automatically discover name variants such as initials versus full given names, transliteration variants, married-name changes, or completely different aliases. Those require a broader blocking strategy and stronger external identifiers. This is deliberate: false merges damage the investigator map more than leaving some duplicate identities unresolved.

A sensible second reconciliation layer is to expand candidate blocking only after the exact-name queue has been reviewed, using ORCID/S2 aliases and coauthor neighborhoods as the primary anchors.
