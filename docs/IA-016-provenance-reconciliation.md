# IA-016 — Provenance reconciliation and registration decision

**Status:** Drafted 2026-08-25 for the screener's decision. Nothing here mutates artifacts; this document consolidates *who knew what when* into one auditable place and frames the registration options.
**Depends on:** IA-014 (provenance index), IA-015 (protocol sync), `docs/protocol/connectomics_bibliography_methodology_v3.md`.

---

## 1. The two-study framing

There are two distinguishable studies in this repository's history:

- **Study A — exploratory pilot corpus** (the "reasonable destination"): the deterministic Semantic Scholar pipeline (118,165 discovered → 3,768 retained → IA-004…014 chain → working corpus of 1,806). Executed 2026-08-22; frozen; SHA-pinned; fully documented in the IA chain.
- **Study B — protocol-driven corpus** under `connectomics_bibliography_methodology_v3.md`: Phase 0 partially complete; **its formal searches (Phase 2) have not been executed**. The bootstrap bundle's own manifest labels its state "EXPLORATORY run, pre-registration."

The defensible relationship: Study A is the pilot that motivated and calibrated the protocol for Study B. Study A is disclosed, frozen, and becomes a §21 comparison set; it never seeds Study B's discovery. Study B's remaining phases can still be genuinely prospective. This framing requires no retroactive claims about anything.

---

## 2. Verified timeline (git history + artifact timestamps)

| Date (2026) | Event | Evidence |
|---|---|---|
| 08-21 | Repository initialized; Codex handoff bundle committed | commits `8018d56`…`8e720b9` |
| 08-21 18:12/18:15 UTC | **COI distance-1 set frozen** (WGR; 94 works, 349 d1 coauthors) — before any retrieval | `COI_sets_WGR_frozen.json` internal timestamps |
| 08-22 15:59–18:22 UTC | **Pilot retrieval executed** (deterministic pipeline, 1-hop; config SHA `a11c830a…`, queries SHA `65c0ee7b…`) | `outputs/manifest.json` |
| 08-22 | Full pilot analysis chain: IA-004…013 (bridges, works, screens, graph views) — 87 commits | git log |
| 08-25 | IA-014 provenance index committed | `ab9bd1f` |
| ≤08-25 | Protocol v2 → v3 consolidated (external); v3 records the 08-21 COI freeze in §24 item 2 | protocol text |
| 08-25 | v3 §5.2 bootstrap passes run (OA/PubMed anchor searches; ~6,506-record candidate review pool); D-001, D-002 logged | `bootstrap_2026-08-25/MANIFEST.md` |
| 08-25 | Gap-fill executed (9 works); **probe panel frozen** (SHA `0029158e…`); panel convergence 3a/3c run (112 candidates; 0 unique finds; 0 lexicon-gap alarms) | commit `7cc9a0b`; IA-015 |
| 08-25 | IA-014 §6 seed-provenance wording corrected (logged amendment) | `d399308` |
| 08-25 | Protocol v3 synced into repo with splice (revisions 26–28); COI artifact + bootstrap bundle synced; COI tags computed (G7 COI-0; P3, P6 COI-1) | `c8efdc9` |

**Not yet executed** (and therefore still available for genuine pre-registration): lexicon freeze; search-string freeze; parameter freeze; OSF deposit; Phase 1 calibration; Phase 2 formal searches; Phase 3 expansion; §3.1 Core derivation at registered thresholds; §12.2 reliability screening; investigator map; **§21 held-out comparisons (7-paper, 136-core, bespoke bibliography — never run against anything)**.

---

## 3. §24 execution checklist vs. reality

| §24 item | Protocol requirement | Actual state | Assessment |
|---|---|---|---|
| 0.1 roster | Screener roster with ORCID/OpenAlex IDs | WGR enumerated in COI artifact; agents operate under WGR per §12.5 | done (roster of one; agents inherit WGR's COI tags) |
| 0.2 COI freeze | Freeze d1 coauthor sets | Done 08-21, **before all retrieval** | done, in order; hash-verifiability defect → **D-004** |
| 0.3 lexicon | §5.2 bootstrap → FREEZE lexicon | Bootstrap passes done (08-25); extraction/freeze pending | in progress, in order |
| 0.3b gap-fill (rev. 26) | 9 additions before lexicon freeze | Done 08-25 | done, in order (spec-timed "before lexicon") |
| 0.3c panel (rev. 27) | FREEZE panel *alongside lexicon, same OSF deposit* | Panel frozen 08-25 standalone; lexicon not yet frozen | done **out of order** → **D-003** |
| 0.4 strings | FREEZE search strings | Pending | — |
| 0.5 parameters | FREEZE thresholds/windows/batch/reliability params | Stated in §24; deposit pending | — |
| 0.6 deposit | Deposit protocol + artifacts to OSF; record DOI | **Pending — the registration decision (§5)** | — |
| 1 (7) calibration | 50 dual-screened records | Pending | — |
| 2 (8–13) primary retrieval | Frozen searches; funding/platform; date sweep; screening; seed-corpus FREEZE | **Not executed under v3.** Pilot (Study A) ran its own retrieval 08-22 under the Codex spec | pilot ≠ protocol run; disclosed, §1 framing |
| 3 (14–16) citation expansion | Iterative b-family; §14 stopping | Not executed under v3 (pilot did 1-hop only) | — |
| 3 (16b) convergence (rev. 28) | §9.1 after Phases 2–3 | **Run 08-25 against the pilot corpus** as a saturation probe of Study A (0 unique finds) | early relative to Study B → **D-005**; valid as Study-A diagnostic; re-run against Study B corpus at its 16b point |
| 4 (17–26) derivation | Graph, cells, role tags, Core, reliability, Absolute Core, COI sensitivity, investigator map, diagnostics, QC | Not executed under v3. Pilot analogues exist (IA-012/013 tiers) and are explicitly labeled non-gold heuristics in IA-014 §8 | pilot analogues stay out of the paper's Core claims |
| 5 (27–29) freeze & validate | FREEZE outputs; §21 held-out comparison; limitations | Not executed. **§21 comparisons never run** | prospectivity intact — protect it |

---

## 4. Consolidated deviations register

D-001 and D-002 were logged in the bootstrap manifest; numbering continues here. Every row is dated and already documented at the pointed location; this table is the single index.

| # | Date | Deviation | Disposition |
|---|---|---|---|
| D-001 | 08-25 | COI-2 dropped from tagging (86,742 authors via non-field hubs; tag uninformative) | Pre-registration decision; protocol §12.5 (v3 rev. 25) |
| D-002 | 08-25 | Review-type filters under-retrieve; venue/citation supplement passes added | Bootstrap manifest |
| D-003 | 08-25 | Panel frozen standalone, before the lexicon it was to be co-deposited with | IA-015 §1; cure: include panel in the §24-item-6 deposit unchanged (SHA already pinned) |
| D-004 | 08-25 | COI freeze artifact's internal content hash (`46f86882…`) not independently reproducible; file edited after hashing (two freeze timestamps) | `coi/COI_SYNC_NOTE.md`; cure: re-freeze with byte-stream hash + sidecar, retaining the original |
| D-005 | 08-25 | §9.1 panel convergence run before Study B's Phases 2–3 (against the pilot corpus) | IA-015 §5; interpreted as Study-A saturation diagnostic only; §9.1 runs again at Study B's 16b |
| D-006 | 08-25 | Reference-list source fallback (S2 → OpenAlex → Crossref) where publishers elide S2 reference lists, vs. the spec's OpenAlex designation | IA-015 §5; per-member source recorded |
| D-007 | 08-25 | P7 citation-title correction (published title differs from spec citation) | IA-015 §4; panel carries the published title |
| D-008 | 08-25 | IA-014 §6 seed-provenance wording corrected (seeds were discovered-then-screened-out, not undiscovered) | commit `d399308`; IA-014 amendment index |
| D-009 | 08-25 | "Collinson et al. 2023 community-standards piece" could not be verified to exist; claim retracted, not searched further | protocol rev. 26; `gapfill_panel_resolution.json` |

---

## 5. The registration decision

### Is registration required? No.

Nothing obliges registration of a scoping/evidence-mapping review. PROSPERO does not accept scoping reviews at all; PRISMA-ScR and PRISMA 2020 ask only that you **report** whether a protocol existed and where (PRISMA 2020 item 24: "state that the review was not registered" / "no protocol was prepared" are acceptable answers). Journals publish unregistered evidence maps routinely. Registration is a credibility instrument, not a gate.

### What it actually buys *this* project

The protocol's hardest-to-defend claims are exactly the ones a frozen timestamp protects:

1. **Core membership** at pre-registered thresholds (5/10/20%, cell size 30) — without a timestamp, a referee may say thresholds were tuned until the Core looked right;
2. **COI handling** — the screener is a field member; disclosure-not-recusal (§12.5) is defensible *because* the COI sets and sensitivity plan were frozen before derivation;
3. **Held-out validation** (§21) — meaningful only if demonstrably not consulted first;
4. **Investigator map** — categorizes living colleagues; the evidence rules being fixed in advance is the ethical backstop.

None of these have run yet, so the timestamp is still obtainable for all four.

### Three options, honestly priced

| Option | What it is | Cost | What you can claim | Residual exposure |
|---|---|---|---|---|
| **A. OSF registration** | Formal, frozen, DOI'd registration of protocol + freeze artifacts, referencing the git tag | ~1 hour once artifacts are ready (deposit manifest: §6) | "Registered protocol; deviations logged" — the strongest sentence available | Only the disclosed pilot-knowledge limitation (§4 of protocol) |
| **B. Timestamped public deposit** | Zenodo/OSF-project DOI of the same package, or even a signed git tag on the public repo — immutable timestamp without the registration formalism | ~30 min | "Protocol publicly archived (DOI, date) before Core derivation and validation" | A pedant can note it isn't a *registration*; substantively equivalent for timestamp purposes |
| **C. No deposit** | Rely on transparent reporting + this repo's git history | 0 | "No registration; full audit trail public" (PRISMA-compliant) | Referee may treat all thresholds as post hoc; the COI architecture loses its strongest external witness; **and protocol §1 must be amended**, since it currently *promises* an OSF deposit — leaving that sentence while not depositing would be a false statement in the methods |

**Recommendation:** A, with B as the floor. The package is already assembled (§6); the marginal cost over C is under an hour, and options A/B are the difference between the COI and Core sections being *self-attested* versus *externally witnessed*. If C is chosen anyway, amend protocol §1 and §24 item 6 as a logged deviation **before** Core derivation, and rely on git commit `c8efdc9`'s ancestry as the de facto timestamp.

**One hard rule under every option:** do not run §21 comparisons or derive the §3.1 Core until the chosen option is executed. That ordering is the entire value.

### The paper's registration statement (drafted for each option)

- **A:** "The protocol was registered on OSF (DOI …) on [date], after an exploratory pilot corpus (archived at [DOI/commit]) had been constructed and disclosed, and before the protocol's formal searches, Core derivation, or held-out comparisons were executed. Deviations are logged in the audit record (D-001…)."
- **B:** as A, with "publicly archived (Zenodo DOI …)" for "registered on OSF (DOI …)".
- **C:** "The review was not registered. The protocol, all frozen artifacts, and a dated deviations register are public in the project repository, whose version history timestamps each decision; the pilot corpus that informed protocol development is archived and disclosed, and Core derivation and held-out comparisons were executed only after the protocol text was finalized (commit …)."

---

## 6. Deposit package (ready for §24 item 6)

Upload set for OSF/Zenodo, with byte-stream SHA-256 recorded at deposit time (compute fresh with `sha256sum`; the values pinned in git at commit `c8efdc9`+ are authoritative until then):

| Artifact | Path |
|---|---|
| Protocol v3 + amendments 26–28 | `docs/protocol/connectomics_bibliography_methodology_v3.md` |
| COI freeze + sync note (+ planned byte-hash re-freeze, D-004) | `postanalysis/review_pool/coi/` |
| Probe panel freeze + sidecar | `postanalysis/review_pool/probe_panel_frozen.{json,sha256}` |
| Working review pool + gap-fill resolution record | `postanalysis/review_pool/{review_pool.json,gapfill_panel_resolution.json}` |
| Bootstrap working state (pristine) | `postanalysis/review_pool/bootstrap_2026-08-25/` |
| Lexicon (**pending — blocks deposit**) | to be produced by §5.2 extraction |
| Search strings (**pending — blocks deposit**) | §24 item 4 |
| Parameters | §24 item 5 (text already fixed in protocol) |
| Deviations register | this document, §4 |
| Pilot-corpus pointer (Study A) | repo snapshot/tag + `outputs/manifest.json` SHAs |

Add to §23 bias register at deposit (per IA-016 §1): row "Pilot-corpus knowledge — direction: toward reproducing the pilot; mitigation: externally derived era-stratified lexicon, frozen strings, pilot never seeds discovery; residual: §21 comparison against the pilot corpus, misses diagnosed by route family."

---

## 7. Actions this document requests from the screener

1. Choose option A / B / C (§5). Default recommendation: **A**.
2. Approve the D-004 cure (COI re-freeze with byte-stream hash).
3. Produce/approve the lexicon and search-string freezes — the only items blocking the deposit.
4. Confirm the standing hard rule: no §21 comparison, no Core derivation, until the deposit (or amended §1 under option C) is done.
