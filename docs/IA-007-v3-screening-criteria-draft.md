# IA-007-v3 — Screening criteria (fair placement, strict core)

Filename kept (`…-draft.md`) so existing links do not break. **Status is no longer draft.**

## Status

**Accepted and executed (2026-08-24).** Full re-screen under `prompt_version` `IA-007-v3-work-level`. v3 agent decisions are the **current screening of record**. v2 remains a comparable historical run under `postanalysis/llm_agent/`. Membership overlays after ingest are **IA-014**, not a silent rewrite of this criteria text.

See Addendum A below.

## Motivation

IA-007-v2 is high-recall but **`core_relevant` is too permissive**, producing noise in checkpoint and ultra-core layers (e.g. developmental biology, molecular genetics, macro HCP-style imaging, general-purpose tools cited heavily by the field).

v3 keeps **fair inclusion** (adjacent / role_bridge / uncertain) while **strictening core** and using **confidence for triage sweeps**, not hard auto-exclusion.

## Design principles

1. Assign the **best-fitting tier** — do not default to `out_of_scope`.
2. **`uncertain` is a valid outcome** for human review when abstracts are ambiguous.
3. **`core_relevant` is strict** — synaptic-resolution / nanoscale wiring science or pipeline only.
4. **`adjacent_relevant` holds multi-scale bridging** — work that relates nanoscale EM to broader brain organization, comparative connectomics, network methods on wiring graphs, field reviews.
5. **`out_of_scope` is last resort** — only when clearly unrelated with no fair link to nanoscale connectomics.

## Decision ladder (apply in order; stop at best fit)

If two tiers fit, prefer the **less specific** tier (adjacent over core; uncertain over out_of_scope).

1. **CORE_RELEVANT** — nanoscale/synaptic wiring science or pipeline (strict gate)
2. **ADJACENT_RELEVANT** — explicit substantive link, including multi-scale bridging
3. **ROLE_BRIDGE** — infrastructure, training, health translation, cross-field tools
4. **UNCERTAIN** — plausible link but insufficient text to place fairly
5. **OUT_OF_SCOPE** — clearly unrelated; no fair case for tiers 1–4

**Do not use out_of_scope as a shortcut for “not core.”**

## SYSTEM

```
You are a title/abstract screener for a nanoscale connectomics evidence map.

Classify each work into the tier that BEST FITS the supplied title and abstract.
Do not force unrelated work into the map, but also do not exclude generously —
when a fair link to nanoscale connectomics exists, place it in adjacent_relevant or
role_bridge rather than out_of_scope.

core_relevant is STRICT: reserve it for synaptic-resolution / nanoscale wiring
connectomics (reconstruction, pipeline, or analysis explicitly on wiring graphs).

When placement is ambiguous, prefer uncertain (for human review) over
out_of_scope or core_relevant.

Judge ONLY the supplied title and abstract. Return JSON only.
```

## CRITERIA

```
TIER DEFINITIONS

CORE_RELEVANT (strict)
Requires explicit title/abstract evidence of at least one:
- EM or synaptic-resolution reconstruction, segmentation, proofreading, synapse
  assignment, or release/analysis of a neuronal/synaptic wiring diagram.
- Methods/software whose stated primary purpose is the connectomics reconstruction
  pipeline or wiring-graph construction/query.
- Analysis explicitly performed ON a reconstructed nanoscale/synaptic wiring graph.

NOT core: general tools "also used by connectomics labs"; macro network studies;
developmental/cellular biology about synapses unless wiring-graph work is central;
high citation or field importance alone.

ADJACENT_RELEVANT (broad, fair home for related science)
Work with a substantive explicit relationship to nanoscale connectomics, including:
- Multi-scale and cross-level analysis: relating nanoscale EM wiring to mesoscale or
  macro brain organization; comparative connectomics; integrative reviews that
  connect EM connectomes to broader circuit/architecture context.
- Network/graph analysis, topology, classification, or comparative methods clearly
  motivated by wiring graphs or connectome datasets (including influential
  network-science work on connectome structure).
- EM/segmentation/microscopy methods linked to circuit reconstruction but not
  exclusively connectomics pipeline tools.
- General-purpose EM visualization or infrastructure widely used by connectomics
  labs when not framed as connectomics pipeline science.

ROLE_BRIDGE
Training/outreach, health translation, annotation/metadata standards, infrastructure
platforms, or cross-field bridges where connectomics is one meaningful application.

UNCERTAIN
Plausible relevance but insufficient detail to choose fairly among tiers — e.g.
"connectome", "connectivity", or "circuit" language without clear modality, scale,
or wiring-graph evidence. Prefer uncertain over guessing core or excluding.

OUT_OF_SCOPE (narrow — last resort)
Use only when the abstract clearly concerns unrelated domains with no fair link to
nanoscale connectomics, even as context, e.g.:
- Macro in vivo imaging connectomes (DTI, fMRI, BOLD, HCP-style cohort studies) with
  no stated link to synaptic wiring or EM connectomics.
- Generic neuroscience (genetics, immunity, development, physiology) where connectivity
  is background, not wiring-map science.
- Generic ML/CV/graph theory/microscopy with no connectomics relationship.

If macroscale work discusses methods or concepts that could inform how wiring graphs
relate to larger brain organization, use adjacent_relevant or uncertain — not
out_of_scope.

DISAMBIGUATION
- "Connectome" from macro imaging alone → usually out_of_scope OR uncertain if vague;
  NOT core.
- Multi-scale / integrative framing of EM connectomes → adjacent_relevant.
- Network methods on wiring graphs → adjacent_relevant (network_science role).
- General-purpose tools → adjacent or role_bridge, not core.
- Biology papers (microglia, GAD genes, etc.) without wiring reconstruction →
  out_of_scope if clearly unrelated; uncertain if abstract is ambiguous.

CONFIDENCE (for triage sweeps)
- 0.90+: unambiguous tier from explicit wording.
- 0.75–0.89: clear with one reasonable inference.
- 0.55–0.74: borderline; prefer uncertain or adjacent over core.
- <0.55: weak; uncertain unless clearly out_of_scope.

When choosing between adjacent and uncertain, pick uncertain if a human could
reasonably disagree. When choosing between out_of_scope and uncertain, pick
uncertain if any connectomics-relevant phrase exists without clear modality.

"training" meaning model optimization is NOT training_outreach.
```

## JSON output (extends v2)

```json
{
  "decision": "adjacent_relevant",
  "roles": ["network_science"],
  "confidence": 0.82,
  "evidence": "phrase from title/abstract",
  "reason": "one sentence",
  "noise_flags": [],
  "scale_relationship": "multi_scale_bridging",
  "core_gate": "not_applicable"
}
```

### `scale_relationship` (required)

One of: `nanoscale_only` | `multi_scale_bridging` | `macro_only` | `unclear`

### `core_gate` (required)

If `decision` is `core_relevant`, one of:

- `em_or_synaptic_reconstruction`
- `connectomics_pipeline_tool`
- `analysis_on_wiring_graph`

Else: `not_applicable`

### Extended `noise_flags` (additive)

- `macro_connectome_imaging`
- `human_connectome_project_style`
- `unrelated_developmental_or_cell_biology`
- `molecular_genetics_not_wiring`
- `general_purpose_tool_only`
- `connectome_word_only`
- `analysis_without_wiring_graph`

(v2 flags retained.)

## Triage sweeps (post-screen)

| Layer | Rule |
|---|---|
| Exploratory map | `core ∪ adjacent ∪ role_bridge`, confidence ≥ 0.55 |
| Trusted core | `core_relevant` + confidence ≥ 0.85 + valid `core_gate` |
| Ultra-core candidacy | trusted core only; no citation threshold |
| Human review | `uncertain` OR confidence < 0.75 OR `scale_relationship = unclear` |

## Pilot plan

1. Stratified sample of **200 works** — see `postanalysis/llm_agent/pilot_v3/`
2. Golden subset (**30**) with human v3 reference labels (`pilot_v3_golden_reference.csv`)
3. Full v3 re-screen only after pilot acceptance → new `prompt_version` + `compare_screening_runs.py`

**Outcome:** the pilot was accepted and the full re-screen ran (Addendum A). This subsection is retained as the plan of record, not as a still-open gate.

### Golden preview (reference labels applied)

- **9/30** tier changes vs v2; **core 24 → 17**
- Demotions: Microglia, unc-25 GAD, IMOD, Sporns comparative, Alzheimer macro connectome, Bock vEM review, annotation standards
- Unchanged cores: Hemibrain, FlyWire, TrakEM2, petavoxel cortex, C. elegans wiring graph papers, pipeline tools (DotMotif, CONFIRMS, images-to-graphs)

## Relation to IA-012

IA-012 checkpoint/curriculum layers were built from **IA-007-v2**. They remain the v2 checkpoint. Working corpus membership after v3 is IA-014 (human overlay + seeds) feeding IA-013 views. Ultra-core must not use citation-only heuristics on v2 noisy core labels.

## Addendum A — Full v3 re-screen executed (2026-08-24)

The pilot in `postanalysis/llm_agent/pilot_v3/` was accepted. The full agent-offline re-screen used this document’s SYSTEM/CRITERIA, `run_mode=agent_offline`, model `agent:cursor/claude-opus-5-thinking@2026-08-24`.

| | |
|---|---|
| Ingest | `postanalysis/llm_agent_v3/` |
| `criteria_sha256` | `7fb4cab60b9426966bf43edf4e02e5c1b19b5ddf3ddd43cfb8292902f4b8b04a` (`run_manifest.json`) |
| Works screened | **4,136** (IA-008 denominator at ingest) |
| Undecided | **0** |
| Batch JSON | `adjudication/decisions/` — never rewritten by later overlays |

Post-ingest membership changes (human overlay, manual seeds, manual work links) are **IA-014**. They do not change this criteria text or the frozen agent JSON.
