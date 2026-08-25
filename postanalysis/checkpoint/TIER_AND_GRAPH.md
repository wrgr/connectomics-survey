# Tier splits, curriculum labels, and coauthorship graph

Protocol: **IA-012** (`docs/IA-012-checkpoint-corpus-curriculum-and-person-recon.md`).

Checkpoint base: **1,912 works** (`core_relevant` + `adjacent_relevant` + `role_bridge`).

Regenerate:

```bash
python analysis/build_corpus_checkpoint.py
python analysis/reconcile_corpus_people.py
python analysis/analyze_corpus_tiers.py
python analysis/build_checkpoint_viz.py --top-authors 100
```

## Analysis tiers (confidence-aware)

| Tier | Works | Meaning |
|---|---:|---|
| `core_high_confidence` | 1,032 | core_relevant, confidence ≥ 0.85, not human-review flagged |
| `core_review` | 43 | core_relevant but low confidence or flagged |
| `adjacent` | 613 | adjacent_relevant |
| `role_bridge` | 224 | role_bridge |

Files: `tier_core_high_confidence.csv`, `tier_core_review.csv`, `tier_adjacent.csv`, `tier_role_bridge.csv`

## Curriculum labels (overlapping, draft heuristics)

These are **not mutually exclusive** — a paper can be both field-defining and core-methods.

| Label | Works | Rule sketch |
|---|---:|---|
| **field_defining** | 115 | Core + high impact only: citations ≥100, or ≥40 with landmark title. No prior-run membership rules. |
| **core_methods** | 628 | Core + pipeline/infrastructure roles (EM acquisition, segmentation, synapses, proofreading, platforms) |
| **key_for_students** | 504 | Reviews/surveys/tutorials, training/outreach role, or accessible infrastructure tools |

225 works carry **2+ labels**. Curriculum labels are assigned from IA-007 decisions + current metadata only.

Files: `label_field_defining.csv`, `label_core_methods.csv`, `label_key_for_students.csv`, full annotated `corpus_inclusive_labeled.csv`.

## Coauthorship graph

Built from co-listed authors on corpus works (edge weight = shared papers).

| Metric | Value |
|---|---:|
| Unique authors | 6,895 |
| Coauthor edges | 121,134 |
| Connected components | 281 |
| Largest component | 5,694 authors (83%) |
| Modularity communities | 338 |

### Interpretable communities (largest)

1. **Lichtman / Pfister / Harvard EM** (~1,119 authors) — serial EM, human/mouse cortex, segmentation tooling
2. **Peng / China EM pipeline** (~761) — high-throughput EM, brain mapping centers
3. **Seung / FlyWire / MICrONS** (~493) — Drosophila whole-brain, petascale proofreading stack
4. **Jefferis / Cambridge / Drosophila** (~461) — hemibrain, navigation, comparative connectomics
5. **Helmstaedter / Max Planck** (~441) — dense mammalian cortex connectomics, inhibition circuits
6. **Ellisman / UCSD / RC1** (~390) — retinal connectome, neuroinformatics infrastructure

Note: community 6 in the raw output (Sporns / Mišić) is mostly **macro network neuroscience** authors who coappear on adjacent papers — worth filtering when building a nanoscale-only author map.

### Top authors by works in corpus

| Author | Works |
|---|---:|
| J. Lichtman | 76 |
| H. Pfister | 55 |
| G. Jefferis | 42 |
| Kisuk Lee | 40 |
| S. Dorkenwald | 38 |

Files: `coauthorship_nodes.csv`, `coauthorship_edges.csv`

## Suggested next steps

1. **Tune curriculum labels** — review `label_field_defining.csv` for false positives (high cites on adjacent biology); add manual overrides file.
2. **Split author graph by tier** — rebuild coauthorship using only `core_high_confidence` (~1,032 works) to drop adjacent macro-network clusters.
3. **Person reconciliation** — replace string-based author nodes with reconciled person IDs before citing unique-author counts.
4. **Reading-list export** — intersect `key_for_students` ∩ `core_high_confidence` for a short starter syllabus (~50–100 works).
5. **Optional historical compare** — if needed, manually diff `label_field_defining` against archived IA-004 views; do not feed those views back into labeling.

Open the interactive summary canvas: **Connectomics checkpoint corpus** (`.canvas.tsx` in Cursor canvases).
