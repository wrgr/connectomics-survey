# IA-004 — Provenance-derived scope and author reconciliation

## Status

Derived post-processing amendment. The preregistered broad corpus and first-discovery provenance remain unchanged.

## Rationale from methodological literature

### Citation/provenance scope

Citation searching is an established supplementary method for difficult-to-search evidence domains. TARCiS distinguishes backward citation searching (references cited by an eligible/seed paper) from forward and indirect citation searching, recommends citation searching as a supplement rather than a replacement for primary searching, and emphasizes explicit reporting of direction, seeds, iterations, indexes, and deduplication. This supports using directed citation relationships as evidence of topical/provenance connection after the primary corpus has already been retrieved.

The literature does **not** establish a universal rule that two citations to direct-resolution papers proves nanoscale scope. The `>=2` threshold used here is therefore explicitly an empirical calibration on the frozen run, selected because the trial sharply reduced macroscale/peripheral leakage while retaining known downstream connectome-analysis papers. It is a derived classifier threshold, not a literature-derived constant.

Reference: Hirt J, Nordhausen T, Fuerst T, Ewald H, Appenzeller-Herzog C; TARCiS study group. Guidance on terminology, application, and reporting of citation searching: the TARCiS statement. BMJ. 2024;385:e078384. doi:10.1136/bmj-2023-078384.

## IA-004 paper rule

A retained paper enters the derived nanoscale core by either route:

1. `direct_scope+resolution`; or
2. inherited connectome provenance:
   - the paper is not already direct;
   - title/abstract contains specific connectome-analysis language (`connectome`, `wiring diagram`, `synaptic graph/network/connectivity`, `connectome-constrained`, or graph/subgraph query language);
   - the paper **cites at least two** papers already established as `direct_scope+resolution`; and
   - the paper has no existing macroscale flag.

The citation direction is important: candidate source -> cited direct-resolution target. Undirected graph adjacency is retained only as a diagnostic and does not establish inherited provenance.

### Frozen-run calibration

On artifact SHA-256 `6c1b7ea962fb1dd58e4e8c84c216d2d2d6999392949b598165016a2c205ee68c`:

- direct-resolution papers: 1,534;
- specific language + >=1 directed direct-resolution citation: 335 (27 peripheral; 15.2% macroscale flagged);
- specific language + >=2 directed direct-resolution citations: 161 (0 peripheral; 6.2% macroscale flagged);
- **specific language + >=2 directed direct-resolution citations + non-macroscale: 151** (83 core-candidate, 68 supported, 0 peripheral);
- resulting derived nanoscale core: **1,685** papers.

The known downstream paper `Circuit motifs and graph properties of connectome development in C. elegans` satisfies the rule independently of its identity: it contains specific connectome-analysis language, is non-macroscale, and cites six direct-resolution papers in the frozen corpus.

## Author-name reconciliation rationale

Author-name disambiguation (AND) literature treats names as insufficient identifiers and commonly combines blocking/name variants with relational and bibliographic evidence such as coauthors, topics, affiliations, publication years, citations, and persistent identifiers. Coauthor relationships are particularly established features. ORCID-linked records are used as authority/gold-standard data for evaluation. Practical systems also preserve uncertainty because automatic AND still requires validation/correction.

Relevant examples:

- Boukhers Z, Asundi NB. Deep author name disambiguation using DBLP data. International Journal on Digital Libraries. 2024;25:431-441. Uses name grouping plus coauthor and research-domain information.
- Mihaljević H, Santamaría L. Disambiguation of author entities in ADS using supervised learning and graph theory methods. Scientometrics. 2021;126:3893-3917. Uses authorship-pair features and graph clustering, including coauthor/content/location evidence.
- Kim J, Owen-Smith J. ORCID-linked labeled data for evaluating author name disambiguation at scale. Scientometrics. 2021;126:2057-2083. Supports ORCID as an authority source for evaluation.
- Schulz C, Mazloumian A, Petersen AM, Penner O, Helbing D. Exploiting citation networks for large-scale author name disambiguation. Uses common coauthors, citations, and shared references in publication similarity.

## Applied author procedure

1. Preserve every source Semantic Scholar author ID.
2. Generate candidate blocks from either:
   - exact normalized name; or
   - the same normalization after removing only single-letter **middle** initials while preserving first and last name tokens.
3. Within blocks, compute shared normalized coauthor names, coauthor-neighborhood Jaccard, topical-axis overlap, and relevant-year compatibility.
4. Label candidate pairs with conservative local heuristics:
   - probable: >=3 shared coauthor names, coauthor Jaccard >=0.20, compatible years;
   - possible: >=1 shared coauthor name, coauthor Jaccard >=0.10, compatible years;
   - otherwise ambiguous.
5. **Do not automatically merge any pair.** Review probable/possible candidates against S2 profiles, publication overlap, ORCID where available, affiliation/other external evidence, and record an explicit decision.
6. Apply approved merges only through the separate alias table; never rewrite raw author IDs.
7. Recompute person-paper and network metrics from canonical aliases after adjudication.

The numerical coauthor/Jaccard cutoffs are local conservative heuristics, not literature-standard thresholds. Their role is prioritization of manual review, not autonomous identity resolution.

## Frozen-run blocking comparison

Exact normalized-name blocking produced 1,231 pairs. Middle-initial-insensitive blocking produced 1,435 pairs, adding 204 comparisons. Of the newly exposed pairs, 15 met the local probable heuristic, 12 possible, and 177 remained ambiguous. Thus the broader blocking rule improves recall while preserving the rule that name normalization alone never causes a merge.
