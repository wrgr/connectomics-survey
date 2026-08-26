# What's left — working checklist (2026-08-26)

Status snapshot after the exploration phase. Three lists: exploration
leftovers (optional, nothing locks in), the formal-run gate (the v5 critical
path), and standing rules. Source docs: protocol v5 (`docs/protocol/`),
IA-016 (registration decision), `postanalysis/registry/EXPLORATION_SET.md`.

## A. Exploration leftovers (optional; all lock-free)

1. **Screener review of the registry package** — the main human input still
   needed: mark up `dataset_registry_draft.csv`, `MILESTONES_DRAFT.md`,
   `methods_registry_draft.csv` (40 entries), and the fill/prune lists.
   Everything is provisional until this pass.
2. **7 DOI-less works** → manual identity resolution
   (`exploration_doi_resolution.csv`, status `unresolved`).
3. **135 protected unmatched works** (107 reference-lists elided from S2, 21
   not in S2, 7 no-DOI) → optionally re-resolve via OpenAlex
   `referenced_works` now that a keyed budget exists; otherwise they resolve
   at the formal run.
4. **~65 no-axis strays** → per-work adjudication (the residual after the
   biology/conceptual axes were added).
5. **Version links**: apply the LICONN preprint/published link and review the
   rest of `suspected_unmerged_duplicates.csv` into
   `manual_work_links.csv`.
6. **25 deferred recent works** (reference lists not yet served) → recheck as
   S2/OpenAlex coverage catches up; they are protected until verified.
7. Optionally refresh the field-map artifact with the 1,595-work view.

## B. The formal-run gate (v5 critical path; order matters)

1. **Lexicon**: select top reviews per 5-year window + per stratum from
   `review_pool_v2.json` (in-scope adjudication at selection); extract terms
   (each traceable to its source review); **FREEZE**.
2. **Search strings** per family × era × source; PRESS-guided review with
   recorded accept/reject dispositions; **FREEZE**.
3. **Parameters**: thresholds, windows, batch and reliability-sample sizes,
   emergent-rule numbers, ablation list, **calibration papers list**;
   **FREEZE**. *(Two genuine screener decisions live here.)*
4. **Registry seed**: apply the screener's review-pass edits; **FREEZE**
   (it grows during charting, growth logged).
5. **COI re-freeze** with byte-stream hash + sidecar (cures D-004).
6. **DEPOSIT** (OSF registration = option A, Zenodo DOI = option B floor;
   IA-016 §5) referencing the git tag; record the DOI. *After this,
   "deviation" is a defined term and prospectivity is secured.*
7. Then, in order: 50-record calibration → frozen searches (families a/c/d)
   → citation expansion to saturation (+ §9.1a convergence at 16b) →
   screening + verification → charting (dataset × stage × era × axes) →
   **FREEZE corpus v1.0** → §21 corroboration vs. the pilot (gap diagnosis,
   never "validation") → limitations → audience views built editorially.

## C. Standing rules (do not relax during exploration)

- **No §21 pilot comparison and no tier derivation before the deposit** —
  the ordering is the entire value of registration.
- Corpus membership changes only via v5 charting or logged nominations;
  exploration fill/prune lists are views.
- Post-freeze change only through the typed adjudication log (errata /
  nominations / removals / wholesale recomputation; no item-wise tier edits).
- Every human-judgment act stays an enumerated, dated artifact; every LLM
  act is logged with recorded dispositions.

## API keys (operational note)

Semantic Scholar and OpenAlex keys live in the **session scratchpad only**
(environment variables at call time; never committed, logged, or hashed —
repo scanned before every push). Scratchpad is session-scoped: **re-supply
both keys at the start of any new session** that needs API work.
