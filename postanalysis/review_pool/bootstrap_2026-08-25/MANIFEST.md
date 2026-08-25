# Exploratory bootstrap working state — 2026-08-25
Companion to connectomics_bibliography_methodology_v3.md and gapfill_panel_convergence_spec.md.
Status: EXPLORATORY run, pre-registration. Nothing here is a frozen protocol artifact except as noted.

| File | What it is |
|---|---|
| review_pool.json | ~5,700 candidate review records; merged OA/PubMed passes 1-4 + WGR-nominated additions; routes per record |
| oa_reviews_pass1.json | OpenAlex anchor-term review searches (A1-A4), raw results |
| pm_reviews_pass1.json | PubMed anchor-term searches (A1-A4): queries, counts, PMIDs |
| pm_reviews_recs.json | PubMed record summaries for pass-1 PMIDs |
| review_candidates.json | Prescreen-passing candidate identifiers (regex prescreen; not screening decisions) |
| coi_d1.json | Screener works (94) + distance-1 coauthors (349), intermediate |
| coi_d2.json | Distance-2 expansion (86,742 authors; retained for completeness, NOT used for tagging per D-001) |

Frozen artifact (separate): COI_sets_WGR_frozen.json, SHA-256 46f8688242f00b4e3c162d3958ca062b898f748f4e16461d27b268ae0aaf9d08, frozen 2026-08-21T18:15Z.
Deviations logged so far: D-001 (COI-2 dropped from tagging), D-002 (review-type filters under-retrieve; venue/citation supplement passes).
Known open items: 9 gap-fill additions not yet executed; lexicon not yet extracted or frozen; panel not yet frozen.
