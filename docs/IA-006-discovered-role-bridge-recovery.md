# IA-006 — Recover role bridges from the discovered set

## Status

Derived post-processing correction. The preregistered discovery, screening, and `keep` decisions remain unchanged.

## Failure mode

IA-005 initially evaluated role proximity only among `papers_retained.csv`. Spot checking showed that this architecture systematically misses legitimate non-scientific-core role papers that were successfully discovered but rejected by the scientific retention gate.

Positive control: Semantic Scholar paper `17356a69dd1a1a0708e927aa8fc2279d399dcd76`, **CIRCUIT summer program: A computational neuroscience outreach experience for high-achieving undergraduates via sponsored research** (2018), was present in `papers_all.csv`, retrieved through one-hop citations, and had `people_development_hits = outreach;undergraduate`, but `keep = False`. Therefore it could not enter the original IA-005 retained-only bridge triage.

## Correction

Role-bridge analysis now starts from **all discovered papers with an explicit role hit already recorded by the pipeline**, rather than from retained papers only.

This does **not** reopen all discovered papers. A discarded paper enters the actionable recovery queue only when all of the following hold:

1. it was discovered by the frozen run;
2. it has an original pipeline role hit for the role being considered;
3. its title contains a role-specific high-specificity expression; and
4. it has the required number of **directed citation relationships** with the IA-004 derived nanoscale core.

Indirect relationships (bibliographic coupling and co-citation-like proximity) are retained for ranking and review context but cannot recover a discarded record by themselves.

## Role-specific recovery gates

The role source tags come from the frozen pipeline fields:

- health -> `health_hits`
- training/outreach -> `people_development_hits`
- proofreading/annotation -> `qc_hits`
- infrastructure/methods -> `infrastructure_hits`
- network science -> `network_hits`

Title-level specificity and direct-core requirements are:

- **training/outreach:** outreach, undergraduate/student, education/curriculum, summer school, workforce, citizen science, or mentorship; >=1 direct core citation relationship.
- **health:** disease/disorder/pathology/clinical/patient/therapy/diagnosis/neurodegeneration/trauma/injury/stroke/cancer or named high-frequency neurological disease expressions; >=2 direct core relationships.
- **proofreading/annotation:** proofreading, annotation, error/merge/segmentation correction, human-in-the-loop, or quality control; >=1 direct core relationship.
- **infrastructure/methods:** connectomics/reconstruction/segmentation/alignment/registration/synapse-detection/volume-EM/data-service/visualization language; >=2 direct core relationships.
- **network science:** connectome/circuit/network-analysis/graph-analysis/motif/centrality/community/subgraph/query language; >=2 direct core relationships.

The differing direct-link minima are queue-prioritization heuristics: human-development and proofreading role language is comparatively specific, while health, infrastructure, and network-science vocabularies are much broader. They are not claimed as universal literature constants.

## Frozen-run calibration

Frozen artifact SHA-256: `6c1b7ea962fb1dd58e4e8c84c216d2d2d6999392949b598165016a2c205ee68c`.

The discovered set contains 118,165 papers, versus 3,768 retained papers. A naive extension of IA-005 proximity to every discarded role-bearing record would have produced 13,097 recovered candidates, demonstrating that indirect proximity alone is too permissive outside the retained set.

Applying the role-specific recovery gates above produces **391 unique actionable originally-discarded bridge candidates**:

- training/outreach: 32
- health: 59
- proofreading/annotation: 113
- infrastructure/methods: 144
- network science: 50

Role counts overlap, so they sum to more than 391.

The CIRCUIT positive-control paper is recovered as training/outreach: it has the original `outreach;undergraduate` role evidence, explicit outreach/undergraduate title evidence, and one directed citation from the candidate to a derived-core paper.

## Interpretation

Recovered papers remain **role bridges**, not nanoscale-core papers. Recovery corrects a mismatch between a scientific-paper retention predicate and evidence-map roles such as education/outreach. Every original `keep` value and source record remains intact for auditability.
