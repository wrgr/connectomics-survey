# IA-007 inclusive corpus checkpoint

Generated from the completed IA-007-v2 agent adjudication run (`agent:cursor/claude-opus-5-thinking`).

**Protocol capture:** post-adjudication derived layers (inclusive corpus, curriculum labels, checkpoint person reconciliation) are recorded as **IA-012** — see `docs/IA-012-checkpoint-corpus-curriculum-and-person-recon.md`. That amendment does not alter IA-007 decisions.

## Definition

**Checkpoint corpus** = all screened works with decision in:

- `core_relevant`
- `adjacent_relevant`
- `role_bridge`

Excluded: `out_of_scope`, `uncertain`, and auto-`insufficient_abstract` (no abstract after rescue).

## Headline numbers

| Metric | Value |
|---|---:|
| Screened works (full IA-008 universe) | 4,136 |
| **Checkpoint corpus works** | **1,912** |
| Share of screened | 46.2% |
| Unique authors (raw strings) | 7,818 |
| Unique authors (normalized surname + initials) | 6,889 |
| **Unique authors (IA-012 reconciled people)** | **6,824** |
| Author mentions | 14,346 |
| Mean authors / work | 7.5 |
| Median publication year | 2021 |
| Median citations / work | 12 |

### Decision mix

| Decision | Works |
|---|---:|
| core_relevant | 1,075 |
| adjacent_relevant | 613 |
| role_bridge | 224 |

### Provenance mix

| source_group | Works in corpus |
|---|---:|
| core_audit | 1,422 |
| role_bridge | 224 |
| unresolved | 266 |

The corpus is dominated by the pre-audit nanoscale core pool (`core_audit`), with a substantial adjacent tail and a preserved role-bridge slice.

## Author count caveats

Two author counts are reported:

1. **Raw unique strings (7,818)** — counts distinct author field tokens after splitting on `;`/`|`. Inflated by formatting variants (`J. Lichtman` vs `Jeff Lichtman`).
2. **Normalized unique (6,889)** — conservative blocking key: lowercase surname + given-name initials. This is the best current automated estimate without person reconciliation.

For publication-grade author statistics, run person reconciliation (`postanalysis/cleanup/person_reconciliation_candidates.csv` → reviewed aliases → `apply_person_aliases.py`) before counting people.

## Exploratory findings

**Temporal concentration.** ~61% of corpus works are from 2020–2029 (1,167 / 1,912). The field’s literature mass in this checkpoint is heavily recent.

**Venue shape.** Top venues are `bioRxiv` (467), `arXiv.org` (64), then `eLife`, `Nature`, `Neuron`. Preprint-heavy corpus — expect version duplicates and citation lag.

**Role composition (multi-label).** Top adjudicated roles: biological_application (1,043), reconstruction_segmentation (461), network_science (438), structure_function_modeling (331), infrastructure (292). Pipeline + analysis + application are all well represented.

**Highly connected authors (normalized, top 5).**

| Author | Works in corpus |
|---|---:|
| J. Lichtman | 76 |
| H. Pfister | 55 |
| G. Jefferis | 42 |
| Kisuk Lee | 40 |
| Albert Cardona | 38 |

These are connectomics infrastructure/methods hubs, not surprising given FlyWire/FAFB/C.elegans density.

**Quality flags inside corpus.** 785 / 1,912 works (41%) still carry `human_review_priority=True`, all tagged `low_confidence`. Treat confidence < 0.85 as soft labels until spot-checked.

**Citation skew.** Mean 69 vs median 12 citations; 275 works have zero citations (often preprints or very recent).

## Artifacts

| File | Description |
|---|---|
| `corpus_inclusive.csv` | One row per corpus work with adjudication + metadata |
| `corpus_inclusive_authors.csv` | Exploded author rows (work × author) |
| `checkpoint_summary.json` | Machine-readable statistics |
| `CHECKPOINT.md` | This note |

Regenerate:

```bash
python analysis/build_corpus_checkpoint.py
```

## Suggested next steps

### 1. Stabilize the checkpoint boundary (high priority)

- **Human-review pass** on the 785 flagged corpus works, especially the 266 `unresolved` inclusions (44 core + 172 adjacent + 50 role_bridge) — highest false-positive risk.
- **Decide policy for `uncertain` (43 screened)** — currently excluded. Review whether any should graduate into the corpus after manual read.
- **Record-type triage** (IA-010) on corpus rows — filter editorials, corrections, peer-review reports inherited from preprint/version merges.

### 2. Author / institution analysis (medium priority)

- Run IA-012 person reconciliation (done for checkpoint graphs) before citing a unique-author number in a paper; S2-ID review (IA-004) remains a separate, stronger identity layer if needed.
- Compute coauthorship graph on normalized authors; identify communities (FlyWire, MICrONS, FIB-SEM segmentation, C. elegans, Drosophila olfactory, etc.).
- Add affiliation extraction (OpenAlex / Semantic Scholar) for geographic and institutional concentration.

### 3. Corpus refinement views (medium priority)

Split checkpoint into analytic tiers without losing the inclusive checkpoint:

| Tier | Rule | Approx. size |
|---|---|---:|
| Core | `decision == core_relevant` | 1,075 |
| Adjacent | `decision == adjacent_relevant` | 613 |
| Role bridge | `decision == role_bridge` | 224 |
| High-confidence core | core + confidence ≥ 0.85 + not human_review | 1,032 |

Compare these tiers to legacy derived views in `postanalysis/cleanup/derived_nanoscale_core.csv` to quantify how LLM screening shifted the boundary vs rule-based IA-004.

### 4. Bibliometric / map readiness (lower priority)

- DOI/venue/year completeness audit on the 1,912 works.
- Deduplicate preprint/journal pairs at work level (already partially done in IA-008; verify no double-count in author stats).
- Topic clustering on titles/abstracts (pipeline stage, species, modality) for the survey map layout.

### 5. Validation loop (when API key available)

- Run API replicate on overlap set (120 works in manifest) and compare with `compare_screening_runs.py`.
- Use tier-5 disagreements to prioritize human adjudication and tighten the checkpoint.
