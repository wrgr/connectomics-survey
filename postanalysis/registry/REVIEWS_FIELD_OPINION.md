# Diverse review set and field-opinion capture — placeholder companion

**PLACEHOLDER (2026-08-26), provisional like the rest of the registry package.**
This file assembles the previously-resolved diverse review set and the
citation-derived field-opinion signal into the registry package. In v5 terms
everything here is **descriptive**: cross-cluster citation counts are facts
about what the field's own syntheses cite, not an importance criterion or an
attestation apparatus (that machinery was withdrawn in v5 §12).

## 1. The review roster (15 works, all identifier-verified, COI-tagged)

Nine-review panel spanning eight institutional/intellectual clusters, plus the
gap-fill reviews. Full resolution record:
`postanalysis/review_pool/gapfill_panel_resolution.json`; freeze artifact
`probe_panel_frozen.json` (SHA `0029158e…`); COI tags
`coi/coi_tags_gapfill_panel.json`.

| Review | Cluster / stratum voice | COI |
|---|---|---|
| Helmstaedter 2025, *Nat Rev Neurosci* | MPI-Frankfurt / mammalian cortex | none |
| Peddie et al. 2022, *Nat Rev Methods Primers* | Crick–EMBL / cell-biology vEM | none |
| Lee et al. 2019, *Curr Opin Neurobiol* | Princeton–Seung / reconstruction | **COI-1** (first author in d1) |
| Scheffer & Meinertzhagen 2019, *Annu Rev Cell Dev Biol* | Janelia–FlyEM / fly datasets | none |
| Galili et al. 2022, *Curr Opin Insect Sci* | Cambridge–natverse / fly analysis | none |
| Beyer et al. 2022, *Comput Graph Forum* | Harvard–Pfister / visualization & infrastructure | **COI-1** (last author in d1) |
| Litwin-Kumar & Turaga 2019, *Curr Opin Neurobiol* | Columbia–Janelia / theory & NeuroAI | none |
| Collins et al. 2025, *Cell Rep Methods* | Outside-field / emulation & alt. modalities | none |
| Abbott et al. 2020, *Cell* (Mind of a Mouse) | Cross-cluster consensus (25 authors) | 5 d1 middle authors (recorded) |
| + gap-fill: Ware 1975; Fiala 2005; Wassie 2019; Kebschull 2018; Vogelstein 2018 (**COI-0**); Kievits 2022 | era-1 anchor; tooling; alt-modality vocabulary; infrastructure; throughput | as tagged |

## 2. Field-opinion capture via reference-list convergence

The panel's reference lists were retrieved in full and cross-cluster citation
counts computed (`convergence/panel_convergence_candidates.csv`, 112 works
cited by ≥2 clusters). Cross-cluster count = how many independent corners of
the field's synthesis literature cite a work — a descriptive endorsement
signal. Registry entries as seen by the field's own reviews:

| Registry entry | Cited by clusters (of 8) |
|---|---:|
| DS04 FAFB producing paper | **8** |
| DS01 White 1986 | 6 |
| DS11 Kasthuri 2015 · SBF-SEM (Denk 2004) | 5 |
| DS05 hemibrain · FFN · EyeWire/Kim 2014 | 4 |
| DS02 Witvliet · DS09 Briggman · DS10 Helmstaedter 2013 · DS12 Motta L4 · DS15 zebrafish · DS20 Ciona | 3 |
| DS03 larva · DS06 FlyWire · DS13 MICrONS · DS14 H01 | 2 |
| DS16 Spirou · DS19 songbird · DS21 octopus | <2 |

Interpretation, honestly bounded:

- High counts corroborate the registry's dataset selection from eight
  independent editorial vantage points — the field's reviews converge on the
  same volumes the registry names.
- **Low counts are not evidence against an entry.** FlyWire/MICrONS/H01 sit at
  2 because most panel reviews predate or barely postdate them (citation lag);
  Spirou/songbird/octopus sit below threshold because the panel's clusters
  skew to the large lineages — which is a *panel-composition limitation*,
  recorded here, not a fact about those datasets. This asymmetry (presence
  means something; absence means little) is stated wherever these counts
  appear.
- P9 (Abbott 2020) corroboration marks are descriptive only, per the panel
  freeze rules.

## 3. Role in v5

The review roster serves v5 as: (a) vocabulary sources for the lexicon (§5.2
selection draws on them); (b) the one-time supplementary saturation check
already run (zero convergence candidates outside the frozen discovery); and
(c) this descriptive field-opinion layer for the registry. None of this
re-creates the withdrawn attestation machinery: no count here is an inclusion
or tier criterion.
