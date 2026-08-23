# IA-006 — Recover and harmonize role bridges across retained and discovered papers

## Status

Derived post-processing correction. The preregistered discovery, screening, and `keep` decisions remain unchanged.

## Failure mode

IA-005 initially evaluated role proximity only among `papers_retained.csv`. Spot checking showed that this architecture systematically misses legitimate non-scientific-core role papers that were successfully discovered but rejected by the scientific retention gate.

Positive control: Semantic Scholar paper `17356a69dd1a1a0708e927aa8fc2279d399dcd76`, **CIRCUIT summer program: A computational neuroscience outreach experience for high-achieving undergraduates via sponsored research** (2018), was present in `papers_all.csv`, retrieved through one-hop citations, and had `people_development_hits = outreach;undergraduate`, but `keep = False`. Therefore it could not enter the original IA-005 retained-only bridge triage.

## Correction

Role-bridge analysis now starts from **all discovered papers**, while preserving the original retained/discarded origin. A paper enters the actionable role-bridge queue only when all of the following hold:

1. it was discovered by the frozen run;
2. it is not already in the IA-004 derived nanoscale core;
3. it has an original pipeline role hit for the role being considered;
4. its title contains a role-specific high-specificity expression; and
5. it has the required number of **directed citation relationships** with the IA-004 derived nanoscale core.

The identical gate is applied to both originally retained non-core papers and originally discarded papers. This replaces the earlier provisional IA-005 retained-only count, making retained and recovered bridge counts directly comparable.

Indirect relationships (bibliographic coupling and co-citation-like proximity) remain useful for ranking/review context but cannot establish bridge eligibility by themselves.

## Role-specific gates

The role source tags come from frozen pipeline fields:

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

The differing direct-link minima are queue-prioritization heuristics, not universal literature constants.

## Frozen-run calibration

Frozen artifact SHA-256: `6c1b7ea962fb1dd58e4e8c84c216d2d2d6999392949b598165016a2c205ee68c`.

The frozen discovered set contains 118,165 papers, with 3,768 retained and a 1,685-paper IA-004 derived nanoscale core.

A naive extension of IA-005 indirect proximity to all discarded role-bearing records produced 13,097 candidates and was rejected as too permissive.

Applying the final role-specific gate to originally discarded papers yields **391 recovered role bridges**:

- training/outreach: 32
- health: 59
- proofreading/annotation: 113
- infrastructure/methods: 144
- network science: 50

Role counts overlap.

Applying **the same gate** to the 2,083 retained non-core papers yields **15 retained role bridges**:

- training/outreach: 0
- health: 8
- proofreading/annotation: 2
- infrastructure/methods: 2
- network science: 4

Again, role counts overlap. The harmonized final union is therefore **406 unique role-bridge papers: 15 retained non-core + 391 originally discarded**.

Fourteen of the 406 carry an existing macroscale flag. They are not silently removed; they are labeled `macroscale_role_bridge_review` so the bridge relationship can be adjudicated separately from nanoscale-core status. The remaining 392 are non-macroscale role-bridge candidates.

The earlier provisional ~246 retained IA-005 priority count is superseded by this harmonized calculation because it used different eligibility rules.

The CIRCUIT positive-control paper is recovered as training/outreach: it has the original `outreach;undergraduate` evidence, explicit outreach/undergraduate title evidence, and one directed citation from the candidate to a derived-core paper.

## Interpretation

Role bridges remain distinct from nanoscale-core papers. Recovery/harmonization corrects a mismatch between a scientific-paper retention predicate and evidence-map roles such as education/outreach, health, proofreading, infrastructure, and network methods. Every original `keep` value and source record remains intact for auditability.
