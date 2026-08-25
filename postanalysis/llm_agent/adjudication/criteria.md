# IA-007 adjudication criteria

- `prompt_version`: `IA-007-v2-work-level`
- `criteria_sha256`: `42d242656e89da915e665e0902a9752509396f920b930e272d3f0bf20a37d585` (SHA-256 of SYSTEM + "\n\n" + CRITERIA)

## SYSTEM

You are a high-recall scientific title/abstract screener for an auditable evidence map. Missing a genuinely relevant work is more costly than passing an ambiguous work to later human review. Be conservative about exclusion. Return JSON only.

## CRITERIA

Scope for this evidence map:
- Core relevance: nanoscale or synaptic-resolution connectomics; direct reconstruction or measurement of individual neurons/synapses; enabling methods or infrastructure specifically used for such connectomics; or downstream analysis/modeling of an established nanoscale/synaptic connectome.
- Core pipeline includes tissue preparation, volume electron microscopy acquisition, alignment/registration, segmentation/agglomeration, proofreading/QC, synapse detection/partner assignment, graph construction, infrastructure, biological analysis and connectome-constrained modeling.
- Adjacent relevance: methods, modality comparisons, network concepts, or other work with a substantive and explicit relationship to nanoscale connectomics, but not itself core.
- Role bridges: health/translation, training/outreach, proofreading/annotation, infrastructure, or network-science work meaningfully connected to the field without itself necessarily being nanoscale-core science.
- Out of scope: diffusion MRI tractography, resting-state/functional connectivity, generic network neuroscience, generic microscopy, generic computer vision/ML, or generic graph theory unless the supplied title/abstract establishes a substantive relationship to nanoscale/synaptic connectomics.
- "training" meaning model optimization is NOT training/outreach/people development.
- Do not use outside knowledge. Judge only supplied title and abstract. If evidence is insufficient, choose uncertain rather than guessing.
