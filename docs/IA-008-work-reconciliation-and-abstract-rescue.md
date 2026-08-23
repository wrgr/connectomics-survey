# IA-008 — Work reconciliation and abstract rescue before semantic screening

## Status

Derived post-processing amendment. Original paper records, Semantic Scholar IDs, original `keep` values, IA-004 core labels, and IA-006 bridge labels remain immutable.

## Why this is necessary

The semantic-analysis universe contains records from multiple scholarly versions. Preprints and later journal publications may represent the same underlying work, and bibliographic databases may also contain near-duplicate metadata records. Sending every version independently to an LLM would inflate paper counts, duplicate screening effort, and distort author/citation summaries.

The evidence-synthesis deduplication literature supports multistep metadata normalization and matching across identifiers, titles, authors, years, journals and other fields rather than exact-string matching alone. However, systematic-review literature also distinguishes duplicate *citations* from multiple reports/versions of the same study or work. IA-008 therefore performs **work/version reconciliation**, not destructive citation deletion: every source version remains traceable.

Preprint-publication linkage literature specifically supports combining title and author similarity, publication timing and persistent identifiers. Crossref's own preprint-linking work scores title, authors and years, while Europe PMC links preprints to journal articles using deposited DOI relationships or normalized title plus first-author similarity. PreprintMatch likewise combines title/abstract similarity with author-set similarity.

References:

- Borissov N et al. Reducing systematic review burden using Deduklick: a novel, automated, reliable, and explainable deduplication algorithm to foster medical research. *Systematic Reviews*. 2022;11:172. Uses normalized title, author, journal, DOI, year and other metadata in a multistep duplicate-detection process.
- Forbes C et al. Automation of duplicate record detection for systematic reviews: Deduplicator. *Systematic Reviews*. 2024;13:206. doi:10.1186/s13643-024-02619-9.
- Cabanac G et al. Day-to-day discovery of preprint-publication links. *Scientometrics*. 2021;126:5285-5304. Uses title/byline similarity and publication timing.
- Eckmann P, Bandrowski A. PreprintMatch: A tool for preprint to publication detection. *PLOS ONE*. 2023;18:e0281659. Uses title, abstract and author similarity.
- Europe PMC preprint infrastructure documentation: links preprints to journal versions using deposited relationships and, when needed, title plus first-author matching.
- Crossref. Discovering relationships between preprints and journal articles. Crossref matching combines fuzzy title, author and year evidence.

The exact similarity thresholds in `analysis/reconcile_paper_works.py` are conservative local heuristics, not universal literature constants. Link evidence is written explicitly for auditing.

## Analysis universe

The frozen retrieval provenance remains:

- 3,768 originally retained (`keep=True`) records.

IA-006 additionally recovered:

- 391 role-bridge records whose original `keep=False` provenance is preserved.

Therefore the **raw semantic-analysis universe is 4,159 records**. The recovered bridges are included in the semantic analysis; they are no longer described as being outside its denominator.

## Work reconciliation

`analysis/reconcile_paper_works.py`:

1. links exact DOI, PMID or arXiv identifiers;
2. normalizes titles and author surnames;
3. generates conservative candidate pairs using exact-title and author-surname blocking;
4. links strong version pairs using title similarity, author overlap, publication timing and preprint/publication status;
5. preserves every source record in `work_versions.csv`;
6. chooses a canonical display version, preferring a DOI-bearing non-preprint/journal version and richer metadata;
7. carries the longest available abstract across linked versions;
8. emits all link evidence in `work_link_evidence.csv`.

### Frozen-run dry-run

On artifact SHA-256 `6c1b7ea962fb1dd58e4e8c84c216d2d2d6999392949b598165016a2c205ee68c`:

- raw semantic-analysis records: **4,159**;
- canonical works: **4,136**;
- multi-version works: **22**;
- records collapsed into existing works: **23**;
- work-level source groups before LLM screening: **1,678 core-audit, 2,062 unresolved, 396 role-bridge**.

These counts may change if later manual review approves or rejects work-link candidates; raw records never disappear.

## Citation aggregation

Citation counts reported on multiple versions are not known to be disjoint. Summing them can double-count the same citing publication. IA-008 therefore stores both:

- `citation_count_work`: **maximum** citation count among linked versions, used as the conservative default work-level metric;
- `citation_count_sum_versions`: sum across versions, retained only as an explicitly labelled upper bound.

A future source that exposes citing-work IDs can replace this with an exact union of unique citing works.

## Best-effort abstract rescue

After version reconciliation, `analysis/rescue_missing_abstracts.py` attempts to recover abstracts for canonical works still missing them. It never overwrites an existing abstract and never makes a missing-abstract paper ineligible.

Order:

1. abstract from any linked version (already handled during work reconciliation);
2. Semantic Scholar paper metadata using repository secret `SEMANTIC_SCHOLAR_API_KEY` when available;
3. Europe PMC core metadata by PMID/DOI;
4. OpenAlex `abstract_inverted_index` when `OPENALEX_API_KEY` is configured;
5. Crossref DOI metadata when an abstract was deposited.

Semantic Scholar's Academic Graph API documents `abstract` as a paper field. Europe PMC's `core` result type includes abstracts. OpenAlex exposes abstracts as an inverted index, and Crossref sometimes carries deposited abstracts.

The dry-run work reconciliation leaves **321/4,136 works** without an abstract before network rescue. The actual rescue count is recorded when the networked rescue step is executed. Any remaining missing works are routed to `insufficient_abstract` during LLM screening and cannot be excluded from title alone.

## LLM sequencing

IA-007 now runs **after IA-008** on canonical enriched works, not raw paper records. All three work-level source groups are screened:

- `core_audit` — noise/false-positive audit;
- `unresolved` — primary relevance classification target;
- `role_bridge` — includes retained and recovered bridge versions after work reconciliation.

Thus the LLM denominator is the canonical-work count after reconciliation and abstract rescue, not 3,753 retained records and not 4,159 raw records.
