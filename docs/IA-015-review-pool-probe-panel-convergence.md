# IA-015 — Review pool, probe/attestation panel, and panel convergence

**Status:** Implemented (2026-08-25). Nothing here mutates frozen retrieval, screening JSON, overlays, or corpus membership.
**Depends on:** IA-014 (provenance index); frozen retrieval outputs; IA-008 works; IA-007-v3 working corpus.
**Companion to:** the external execution spec *"Review Gap-Fill, Probe/Attestation Panel, and Convergence Enrichment"* (itself a companion to `connectomics_bibliography_methodology_v3.md`). Neither external document lives in this repo; this IA is the repo-side implementation record and the sync map between the two worlds.

Screener of record: William Gray Roncal (ORCID 0000-0002-7362-9665).

---

## 1. Sync map: spec references vs. repo reality

The execution spec was written against the external protocol document at an out-of-sync point. Every spec reference is mapped here before anything was executed; unmapped references were **not** guessed at.

| Spec reference | Status in this repo | Handling |
|---|---|---|
| `connectomics_bibliography_methodology_v3.md` §§3.1, 5, 9.1, 11, 12, 14, 17, 19, 24 | **Not in repo** (external protocol doc) | Section numbers treated as external pointers; repo-side equivalents named below. Splice-map rows 26–28 of its revision table must be applied in that document, not here. |
| `review_pool.json` working artifact | Did not exist | Created fresh: `postanalysis/review_pool/review_pool.json` (§3 below). |
| `COI_sets_WGR_frozen.json` (SHA-256 46f86882…) | **Not in repo** | COI tagging of pool/panel entries is **deferred**; author-ID lists are captured now so tagging is mechanical once the artifact is synced. G7 carries its COI-0 flag from the spec directly. |
| "Seven-paper held-out set" and "136-paper independent core" | **Not in repo** under those definitions (nearest repo analogues — `label_ultra_core.csv` 65 works, `label_field_defining.csv` 122 works — are *different objects*) | 3b mutual-exclusivity check cannot be evaluated here; 3b is gated off (§5). Do not map these names onto repo labels without the screener. |
| §5 lexicon freeze ("freeze panel alongside the lexicon, same OSF deposit") | No lexicon-freeze artifact in repo | Panel frozen now as a standalone artifact; OSF deposit target is an open item for the screener (§7). |
| Phase 2/3 completion + §14 stopping evaluated (timing precondition for Step 3) | Repo retrieval is frozen and complete (118,165 discovered; provenance invariant `3,768 = 1,685 + 15 + 2,068`) | Precondition satisfied in repo terms: convergence ran **after** all frozen retrieval and screening, so "convergence found it" is distinguishable from "anything would have found it". |
| Route-label vocabulary (`targeted-title-search (gap-fill)`, family (a); `panel-convergence (b)`; `WGR-nominated`) | Adopted verbatim | Recorded in artifact fields; does not alter the frozen pipeline's `retrieval_channels` vocabulary. |

---

## 2. New artifacts and code

| Artifact | What it is |
|---|---|
| `postanalysis/review_pool/review_pool.json` | Review corpus working artifact: 9 gap-fill additions (G1–G9) + 6 reconstructed pre-existing pool members (R1–R6), each with Crossref/S2/OpenAlex resolution, verification checks, retraction check, route label, rationale, and frozen-corpus cross-reference. |
| `postanalysis/review_pool/probe_panel_frozen.json` (+ `.sha256`) | **Frozen** probe/attestation panel P1–P9. SHA-256: `0029158eed5344c358e38d9780e2a86bda5ec04ce0f5eb065aebbb28bd3f3149`. Any post-freeze change is a logged deviation (`--refreeze` refuses by default). |
| `postanalysis/review_pool/resolution_log.json` | Per-entry resolution/verification log with timestamps. |
| `postanalysis/review_pool/convergence/` | Step 3a/3c outputs: `panel_convergence_candidates.csv`, `panel_reference_lists.json`, `convergence_diagnostics.json`, `PANEL_CONVERGENCE.md`. |
| `analysis/build_review_pool.py` | Builds/refreshes the pool; freezes the panel. |
| `analysis/panel_convergence.py` | Runs Step 3a + 3c; gates Step 3b. |

API keys are read from `SEMANTIC_SCHOLAR_API_KEY` only and never logged or serialized, per the repo's standing rule.

---

## 3. Step 1 — gap-fill (executed)

All 9 works resolved, verified (identifier resolves; title/year/venue consistent across Crossref and S2; no retraction notices via Crossref `updates:` filter and OpenAlex `is_retracted`), and added with route `targeted-title-search (gap-fill)`, family (a).

Identifier resolutions performed (spec-permitted, logged):

- **G1 Ware & LoPresti 1975**: spec-marked UNRESOLVED. Resolved via Crossref `query.bibliographic` (title + container) to **doi:10.1016/s0074-7696(08)60956-0** (Elsevier backfile; pages 325–440 and author set match). The works-without-DOI path was not needed.
- **G9 Beyer et al. 2022**: DOI **10.1111/cgf.14574** taken from the frozen corpus record (exact title match), verified against Crossref.
- **G7 Vogelstein et al. 2018** carries **COI-0 (screener is author)** and the `self-tagged` flag; role-tag evidence third-party only; always in the human reliability sample.

Known-absent by decision (spec, logged verbatim): the "Collinson et al. 2023 community-standards piece" could not be verified to exist (likely conflation with Peddie et al. 2022). Not searched further; this retraction of the claim is itself the log entry.

Declared standing gap (do not patch): **alignment/registration has no review**; stratum reported thin; Saalfeld/Cardona enter later as primary literature.

**Repo cross-reference finding.** All 9 gap-fill works were already present in the frozen discovery log by title; only G9 (Beyer) was retained (`keep=True`). In repo terms these are **screening drops, not discovery holes**. This does not change their role here — the review pool is a separate artifact serving lexicon extraction and attestation, not corpus membership — but any prose claiming the frozen searches "missed" these works would be wrong and must not be written.

---

## 4. Step 2 — probe/attestation panel (frozen)

Panel P1–P9 frozen per the spec's table: clusters, probe/attestation flags, P9 (Abbott 2020) **confirmation-only** (never counts toward discovery convergence). Resolved IDs (DOI, S2 paper ID, OpenAlex ID) and full author lists from three sources are in the freeze artifact.

- **Title correction (logged):** P7 is published as *"Constraining computational models using electron microscopy wiring diagrams"* (Litwin-Kumar & Turaga, Curr. Opin. Neurobiol. 2019, doi:10.1016/j.conb.2019.07.007), not the spec's *"Constraining computation with connectomics"*. Author set, venue, and year uniquely match; resolved from the frozen corpus record as the spec directs.
- **Explicit exclusion (logged verbatim):** Kornfeld & Denk 2018 — in the corpus, NOT on the panel: same intellectual lineage as P1 (Denk trained Helmstaedter); its reference list is a second draw from the MPI distribution, not an independent probe.
- **Declared panel gaps (logged, not patched):** proofreading/QC and alignment strata have no probe (no comprehensive review exists). Plaza et al. 2014 remains corpus-member and attestation-eligible but is a perspective, not a systematic probe.
- **Attestation-source COI:** panel members' author sets must be COI-tagged relative to any work they attest; panel membership does not exempt them from with/without-COI-1 Core sensitivity reporting. Tagging deferred until `COI_sets_WGR_frozen.json` is synced (§1).

---

## 5. Step 3 — convergence (3a/3c executed; 3b gated)

**Deviation from spec, logged:** the spec designates OpenAlex `referenced_works` as the reference-list source. Some publishers **elide reference lists from Semantic Scholar**, and OpenAlex was intermittently unavailable (shared daily API budget). Retrieval therefore used a per-member fallback chain — S2 (preferred: S2 IDs join the frozen discovery log exactly) → OpenAlex → Crossref deposited references — with the source used recorded per member in `panel_reference_lists.json` and the diagnostics. Sources actually used: P2/P3/P5/P8 via S2; P1/P4/P6/P7/P9 via Crossref. Candidate DOIs from Crossref-sourced lists were re-resolved through S2 (batch + single) and Crossref titles before any novelty claim, so no candidate is called "new" on the strength of a malformed reference string.

Results (2026-08-25; full tables in `convergence/`):

| Metric | Value |
|---|---:|
| Distinct works cited across P1–P8 | 903 |
| Convergence candidates, ≥2 clusters (k=2) | 112 |
| Candidates, ≥3 clusters (k=3) | 39 |
| P9-corroborated among k=2 (descriptive only) | 5 |
| **Unique finds (retrieved by no frozen route)** | **0** |
| **Lexicon-gap alarms (≥4 clusters, undiscovered)** | **0** |
| Discovered but absent from the working corpus | 47 (43 `keep=False`, 4 retained-then-screened-out) |

**Interpretation.** Zero unique finds and zero lexicon-gap alarms: every work that ≥2 independent panel clusters converge on was already retrieved by the frozen term/institutional/citation routes. This is the designed test of whether retrieval saturation was real, and it passed. The operators' marginal value here is entirely **diagnostic of screening**, not discovery: 47 convergence candidates were discovered and then dropped, including five cited by ≥4 distinct clusters (Knott et al. 2008 FIB-SEM; GCIB-SEM 2019; Ohyama et al. 2015; Eberle et al. 2015 multibeam SEM; Buhmann et al. 2021 synaptic-partner detection). These form a natural screening-review queue (route `panel-convergence (b)`, discovery-only; normal screening/verification/inclusion applies; no convergence statistic is ever attestational or structural evidence).

**Reopening rule (spec 3d / external §14):** the reopening trigger is convergence surfacing a **new qualifying work** in a saturated stratum. With zero unique finds, no stratum reopens on discovery grounds. Whether the 47 screened-out candidates warrant a screening-overlay review round is a **screener decision**, and per IA-014 §10 belongs in the human overlay (or a forked `prompt_version`), never in a silent re-screen.

**3b (ultracore seed-neighborhood expansion): NOT RUN.** No seed artifact has been designated (`ultracore_seeds_frozen.json` absent). The gate additionally requires the mutual-exclusivity check against the held-out sets, which are not in this repo (§1). Personalized PageRank remains excluded; adopting it would be a protocol amendment.

---

## 6. Findings routed to the screener (not applied)

1. **IA-014 §6 wording is imprecise.** The eight manual seeds are described as "absent from frozen Semantic Scholar discovery." Seven of them appear in the frozen `screening_log.csv` via the 1-hop citation-expansion stage with `keep=False` (e.g., White et al. 1986, paper `62d36f23…`, the same canonical paper ID the seed CSV uses). The defensible statement is: *discovered by 1-hop expansion, dropped by lexical screening, later recovered as manual seeds.* Recommend amending IA-014 §6 (a wording amendment, not a membership change). Not applied here because IA-014 is the provenance index of record.
2. **The 47-candidate screening-review queue** (§5), sorted by cluster count in `panel_convergence_candidates.csv`.
3. **Open items** (§7).

---

## 7. Open items requiring the screener

1. Whether an ultracore seed list will be designated; if so, supply `ultracore_seeds_frozen.json` (identifiers + per-paper rationale + COI tag), disjoint from the held-out sets or explicitly traded against them. Default remains: consume no held-out papers.
2. OSF deposit target for `probe_panel_frozen.json` (and the lexicon, which lives in the external protocol world).
3. Sync `COI_sets_WGR_frozen.json` into (or alongside) this repo so pool/panel COI tagging can run.
4. Decide whether the 47 screened-out convergence candidates get a human-overlay review round (§5).
5. Apply splice-map rows 26–28 in the external `connectomics_bibliography_methodology_v3.md` revision table, pointing its new §5.5/§9.1/§14-amendment text at the artifacts recorded here.

---

## 8. Reproduction

```
# resolve + verify pool, freeze panel (refuses to overwrite an existing freeze)
python3 analysis/build_review_pool.py

# panel backward-convergence + diagnostics (3b gated on seed artifact)
SEMANTIC_SCHOLAR_API_KEY=... python3 analysis/panel_convergence.py
```

Both scripts are stdlib-only, rate-limited (≥1.1–1.5 s between calls), and write timestamped logs. `IA015_CACHE_DIR` may point at a scratch directory to cache reference-list responses between runs; the cache is never committed.
