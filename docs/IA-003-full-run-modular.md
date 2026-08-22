# IA-003 — Checkpointed modular full-run orchestration

**Classification:** implementation/orchestration amendment with explicit scientific-output equivalence testing.

This amendment adds a second runner, `full-run-modular`, while retaining the reference monolithic `run_pipeline.py` workflow.

## Purpose

The monolithic full run is difficult to inspect operationally because discovery, graph expansion, contributor derivation, enrichment, and final output generation execute inside one long process. The modular runner exposes those boundaries as separate GitHub Actions steps and persists trusted local checkpoints between them.

## Phases

1. **Discovery** — optional locked seeds, lexical retrieval, lexical scope screening.
2. **Graph** — one-hop citations/references, one-hop scope screening, deduplication, graph metrics, ranking.
3. **People** — contributor map and deterministic author saturation.
4. **Enrichment** — Crossref verification, NIH enrichment, health bridge, training/outreach branch.
5. **Finalize** — graph files, tables/logs, coverage diagnostics, output manifest.

## Scientific invariants

This amendment does not change:

- query families or search strings;
- Semantic Scholar endpoints or requested fields;
- positive scope rules;
- one-hop citation depth;
- deduplication rules;
- graph/ranking algorithms or thresholds;
- contributor/author saturation criteria;
- NIH, health, or people-development logic;
- stopping criteria.

The reference monolithic runner remains available.

## Checkpoints

Each completed phase writes an atomic Python checkpoint plus a human-readable JSON summary outside the scientific output directory. Checkpoints contain pipeline state but no Semantic Scholar API key. A later phase refuses to load a checkpoint when the package version, checkpoint schema, configuration hash, or query-file hash differs.

Checkpoint files are trusted execution artifacts and should not be loaded from untrusted sources because they use Python pickle serialization.

## Equivalence test

CI includes a synthetic, network-free fixture that runs both the monolithic and modular orchestration paths with identical mocked retrieval. It requires:

- identical coverage counts; and
- byte-identical scientific output files other than `manifest.json`, whose modular form intentionally adds orchestration metadata.

The modular manifest explicitly records `orchestration: modular_checkpointed` and the five modular phases.

## Preregistration relation

The scientific protocol freeze remains `38b01f40f8a5727fe51420f8c1febd2a1d5a757c`. IA-003 is prospective and does not use results from the canceled full run to alter scientific rules.
