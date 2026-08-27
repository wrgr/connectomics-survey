# Visible core — one collection, many views

This is the audience note for the NeuroTrailblazers paper library. It replaces the split between the 96-paper teaching collection and the 191-paper journal-club corpus. Those were two corpora built for different jobs. The job is now one collection: every paper in the **visible core**, with filters (views) on top.

## First export is the core only

The v3 catalog is 1,806 works. The analysis working set is 1,488. **Neither ships in the first NeuroTrailblazers export.** The first drop is the visible core only — currently **1,074** papers (383 historical · 571 contemporary · 120 SOTA).

The figure **1,142** was the earlier two-period SOTA+history union (history through 2023, plus a 2024–2026 proving window) before contemporary was split out as 2019–2024 and four unavailable PDFs were dropped from the analysis base. Do not restore that count for this export.

## What you are looking at

The **collection** is the SOTA + history + contemporary core of the 1,806-work v3 catalog (`postanalysis/pdfs/paper_links.csv`). A paper is in the visible core if it meets the era bar below. It is not a second screening of the field, and it is not a ranked canon. The rest of the catalog stays in this repo for audit; it is not copied to the site yet.

| Period | Years | Bar |
|---|---|---|
| Historical | ≤2018 | year-cohort citation percentile ≥ 50 **or** corpus k-core ≥ 3 |
| Contemporary | 2019–2024 | that bar **or** Out ≥ 3 |
| SOTA | 2025–2026 | 2026: Out ≥ 3 **or** In ≥ 1; 2025: Out ≥ 3 **and** In ≥ 2 |

**In** = citations from other papers in the 1,806 catalog. **Out** = how many of this paper’s references are in that catalog. Both are independent of global citation counts.

Protocol v5 treats curricula and “start here” shelves as **editorial audience views** (§10): they may be opinionated, carry no evidentiary weight, and never feed back into inclusion. Highest k-core, a pipeline stage, an organism, a dataset, training/outreach, and health translation are all views over the same rows.

## Identity

Every record has a stable **uuid**:

- DOI, lowercased, when the catalog has one
- otherwise the catalog `work_id`

That uuid is what journal club, the content-library paper pages, graphs, and related-work links share. Do not mint a second id per page.

## What each paper card carries

The card shape is the journal-club example (OCAR, three-level summaries, discussion prompts, tags) applied to **every** core paper, plus the fields the two old collections were missing when they lived apart:

- bibliographic identity (title, authors, year, venue, uuid/DOI)
- PDF: public URL, and a local `files/<stem>.pdf` path when the catalog file exists
- graph place: In, Out, k-core, global cites, year-cohort percentile
- streams: pipeline stage(s), registry dataset(s), organism, method, charting axis
- related works: other **core** papers this one cites or is cited by, inside the catalog graph
- OCAR + summaries + discussion prompts (journal-club shape)

Pedagogical text is generated from title and abstract unless a later editorial pass replaces it. Generated copy is labeled `annotation_status: generated_from_abstract`. Hand-written journal-club or teaching-dimension prose, when merged, is `extracted_from_ntb`.

## Views (not corpora)

Views are ordered lists of uuids. Adding a view does not add papers. Dropping a view does not drop papers.

Shipped with this artifact:

- **Highest k-core** — corpus k-core descending
- **Era** — historical / contemporary / SOTA
- **Pipeline stage** — preparation → analysis
- **Organism**
- **Dataset** (registry volumes)
- **Method**
- **Charting axis** — including training/outreach and health translation
- **Year**
- **Suggested reading paths** — editorial sequences (historical arc, methods, analysis), resolved onto core uuids

The 11 teaching dimensions on the old journal-paper pages remain a view (map from pipeline stage / axis), not a second collection.

## What comes after export

This artifact is the source to copy into NeuroTrailblazers (`_data/journal_papers.yml` plus view sidecars). After that, the site work is: one library route with view switchers; paper and stream pages that show related works, graph place, and descriptions; links from modules and the content library into the same uuids. That UI is deliberately not this commit.
