# Field-progression axes and milestones — preliminary draft

**Status: DRAFT for screener review — nothing frozen.** Companion to
`REGISTRY_DRAFT.md`, implementing v5 §7's field-progression view. Two layers,
kept distinct on purpose: the **axes and their metrics** are charted facts
(dates and numbers reported by the papers themselves); the **milestone
shortlist** below is mildly editorial (which events to headline) and is flagged
as review-leaning-view material. `needs_verification` entries require §12.3
identifier verification before use.

## 1. Progression axes (the metrics charting will record per work)

| Axis | What moves forward | Chartable metric |
|---|---|---|
| A1 Scale | Volume and circuit size reconstructed | µm³/mm³ imaged; neurons and synapses reconstructed |
| A2 Throughput & automation | Acquisition and reconstruction speed; human effort | Reported acquisition rate; human proofreading hours per mm of cable |
| A3 Segmentation quality | Automated reconstruction accuracy | Expected run length; split/merge error rates on named benchmarks (CREMI, SNEMI3D) |
| A4 Modality integration | Structure joined to other measurements | EM+function (co-registered activity); EM+molecular (CLEM, expansion, barcoding) |
| A5 Organism & lifespan coverage | Species, sexes, developmental stages, individuals | Registry organism/stage coverage; N individuals per species |
| A6 Structure → function | From wiring maps to predictive models | Connectome-constrained models; validated predictions |
| A7 Openness & community | From lab-internal data to public platforms and community proofreading | Platform releases; community/citizen-science participation |
| A8 Translation & people | Human tissue, health links, workforce | Human-sample datasets; training/outreach programs |

## 2. Milestone draft (dated events; axis-tagged)

| Year | Milestone | Axes | Anchor | Status |
|---|---|---|---|---|
| 1986 | Complete *C. elegans* hermaphrodite wiring diagram (White et al.) | A1 A5 | DS01 | corpus-anchored |
| 2004 | SBF-SEM makes automated volume EM routine (Denk & Horstmann) | A2 | DS-method | corpus-anchored |
| 2008 | FIB-SEM for connectomic volumes (Knott) | A2 | method | corpus-anchored |
| 2011 | Wiring specificity shown in retina at scale (Briggman; Bock functional ssTEM) | A1 A4 | DS09 | corpus-anchored |
| 2013 | Dense IPL reconstruction; crowd + algorithm workflow (Helmstaedter) | A1 A2 | DS10 | corpus-anchored |
| 2014 | EyeWire: citizen-science proofreading at scale (Kim et al.) | A7 A8 | DS09/EyeWire | corpus-anchored |
| 2015 | Saturated reconstruction of neocortex (Kasthuri); multibeam SEM | A1 A2 | DS11 | corpus-anchored |
| 2017 | Flood-filling networks: automation step-change (Januszewski); whole-brain larval zebrafish ssEM (Hildebrand) | A3 A1 | DS15 | corpus-anchored |
| 2018 | FAFB: full adult fly brain imaged (Zheng/Bock) | A1 | DS04 | corpus-anchored |
| 2020 | hemibrain: largest proofread connectome + neuPrint public release (Scheffer) | A1 A7 | DS05 | corpus-anchored |
| 2021 | H01 human cortex petascale volume (Shapson-Coe); MICrONS mm³ function+structure; *C. elegans* developmental series (Witvliet) | A1 A4 A5 A8 | DS14 DS13 DS02 | corpus-anchored |
| 2023 | Whole-larva brain connectome with full synaptic graph (Winding) | A1 A6 | DS03 | corpus-anchored |
| 2024 | FlyWire: whole adult fly brain, community-proofread, public (Dorkenwald); connectome-constrained models predicting activity (Lappalainen) | A1 A6 A7 | DS06 | corpus-anchored |
| 2024–25 | Male CNS / optic lobe releases; sexual dimorphism at connectome scale | A5 | DS08 | needs_verification |
| 2025 | MICrONS flagship analyses released; mouse whole-brain roadmaps (BRAIN CONNECTS) | A1 A8 | DS13 | needs_verification |

## 3. How this is used without re-adding machinery

- Charting simply records, per work: which axes it advances and any reported
  metric values. The progression figure (e.g., the canonical log-volume vs.
  year plot, plus per-axis timelines) is then **generated from charted data**,
  not curated by hand.
- The table in §2 is the reviewable seed for that figure and for an eventual
  curriculum "milestones" view; the *choice* of which milestones to headline in
  prose is editorial (v5 §10) and stays out of outputs A–D.
- Fairness note: milestone lists gravitate to the biggest consortia. The
  per-axis structure counters this — throughput (A2) surfaces Delft and EPFL;
  openness (A7) surfaces platform and community work (BossDB, EyeWire,
  FlyWire); translation (A8) surfaces human-tissue and training work — and the
  axis metrics are recorded for *every* charted work, not only famous ones.
