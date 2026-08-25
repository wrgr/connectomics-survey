# IA-007-v3 pilot sample

Draft screening criteria: `docs/IA-007-v3-screening-criteria-draft.md`

## Files

| File | Description |
|---|---|
| `pilot_v3_sample.csv` | Stratified **200 works** (30 golden boundary cases + 170 stratified random) |
| `pilot_v3_golden_reference.csv` | Human reference v3 labels for golden 30 (prompt calibration) |
| `pilot_v3_golden_comparison.csv` | Golden set v2 vs v3 side-by-side |
| `pilot_v3_manifest.json` | Headline counts |
| `pilot_v3_sample_summary.json` | Sample composition |

## Sample composition (200)

- **30 golden** — hand-picked boundary cases (false-positive cores, true cores, macro, multi-scale)
- **40** v2 `core_relevant` (random)
- **35** v2 `adjacent_relevant`
- **35** v2 `out_of_scope`
- **25** v2 `role_bridge`
- **15** v2 `uncertain`
- **20** fill to reach 200

## Golden set preview (v2 → v3)

**9 / 30** change tier under v3 reference labels. Core count **24 → 17**.

Notable demotions from v2 `core_relevant`:
- Microglia sculpt circuits → `out_of_scope`
- unc-25 GAD → `out_of_scope`
- IMOD → `adjacent_relevant`
- Sporns Comparative Connectomics → `adjacent_relevant`
- Alzheimer macro connectome → `out_of_scope`
- Volume EM review (Bock) → `adjacent_relevant`
- Annotation standards → `role_bridge`

Unchanged true cores: Hemibrain, FlyWire, TrakEM2, petavoxel human cortex, C. elegans wiring papers, Turaga segmentation, DotMotif/CONFIRMS/images-to-graphs, etc.

## Next step

Export v3 prompts for full 200 (`--prompt-version v3` when implemented) and adjudicate, or adjudicate golden 30 first against reference labels.
