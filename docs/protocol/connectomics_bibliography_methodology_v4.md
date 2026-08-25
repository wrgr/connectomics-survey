# Methodology for Building the Nanoscale Connectomics Training Bibliography (v4)

**Status: DRAFT — not yet frozen or deposited.** This version supersedes v3 (`connectomics_bibliography_methodology_v3.md`, retained unchanged as the historical record). Because no version has been deposited, the changes below are **draft revisions**, not amendments or deviations; "deviation" becomes a defined term only after the §24 deposit. Upon deposit, this document is the protocol of record.

## Summary of revisions from v3

Rows 26–28 were applied to the repo copy of v3 during execution on 2026-08-25 and are carried here; rows 29+ are the v4 consolidation.

| # | Issue in v3 | Change in v4 |
|---|---|---|
| 26 | Review corpus had stratum/era gaps | Gap-fill executed: 9 works, route `targeted-title-search (gap-fill)`; Ware 1975 DOI resolved via Crossref bibliographic query; unverifiable "Collinson 2023" claim retracted and logged |
| 27 | No fixed probe/attestation panel | §5.5: panel P1–P9 defined and **frozen** (SHA `0029158e…`), with role separation, the Kornfeld & Denk exclusion, and declared gaps |
| 28 | No convergence operators; stopping rule untestable | §9.1 panel/seed convergence; §14 saturation-reopening rule; §24 items 3b/3c/16b |
| 29 | Protocol read as accumulated machinery; design intent implicit | §1 opens with the screener's design statement; the machinery is presented as its implementation. Two-study framing made explicit: the pilot corpus is Study A (exploratory, frozen, disclosed); this protocol governs Study B |
| 30 | §4/§21 named three held-out sets that cannot bear weight (seven-paper set: no artifact exists; "136-paper core": actually the 126-row backbone, screener-stated as not thoughtfully curated; "bespoke bibliography": same object) | Held-out apparatus replaced. §21 renamed **corroboration and gap diagnosis**, run against the **pilot corpus** (primary) plus convergence diagnostics. Backbone-126 reclassified historical-artifact-only; seven-paper set struck |
| 31 | Tier membership rules scattered; graph connectivity's role ambiguous | §3.0 tier logic: corpus needs scope; tiers need scope + **situability** + evidence; graph disconnection deprioritizes tiers, never excludes from corpus; infrastructure situability may run through the platform route |
| 32 | Emergent compensation could waive connectivity | **Emerging work must cite the core**: the citation-lag compensation relaxes inbound evidence only; outbound situability is never waived. Measurement guard: out-degree 0 triggers reference-list verification before any failure (pilot test: 56/68 pass; 12 flags were data-completeness artifacts) |
| 33 | Threshold choice reads as a dial | Dial-invariance elevated: strong Core claims only for members invariant across all three thresholds × both evidence types × with/without COI-1; everything else labeled sensitive-to-analytic-choice |
| 34 | §9.1b seed expansion had no qualified seed list | §9.1b **indefinitely gated**: no genuinely curated seed artifact exists (backbone unsuitable per screener statement); per-paper nomination is the channel for individual convictions. Personalized PageRank remains excluded |
| 35 | Screener design-path bias addressed only via COI (proximity channel) | Ablation clause (§18): every human-judgment overlay is reported **with and without** (nominations, human screening overlay, screener-nominated panel member). COI covers proximity; ablations cover tweaks |
| 36 | Investigator map categorized living people into tiers | §15/§22 flipped **evidence-first**: published output indexes contributions by works/datasets/tools/programs with role evidence; person-level category tiers become an internal working table and are not published |
| 37 | Freeze hashes under-specified (COI artifact's internal hash proved irreproducible) | Freeze discipline: every frozen artifact is hashed over its **byte stream** with a sidecar file; the repository is the single source of truth; external copies are exports. COI artifact to be re-frozen under this convention (cures D-004) |
| 38 | Executed Phase-0 items read as future steps | §24 records already-executed items in past tense with artifact SHAs and dates |
| 39 | No governance for changes after the run | **New §25: post-freeze adjudication** — typed change classes (errata / nomination / removal / tier recomputation), a single adjudication log, versioned releases, and a prohibition on item-wise tier edits |
| 40 | Steps not tied to their published standards; no independent search-string review | **New §1.1 methodological grounding table** citing the standard each component follows (PRISMA-ScR/-S, TARCiS, JBI, PRESS, ROSES, living-review guidance, percentile-indicator literature), with extensions beyond standard practice named as such; §24 item 4 gains a **PRESS-style search-string review** before the strings freeze |
| 41 | Draft criteria could be shaped around specific papers without a trace | **Calibration disclosure** (§24 item 5): the touchstone papers used to sanity-check draft criteria are listed and frozen with the parameters; criteria are justified in field terms, never by which papers they admit |
| 42 | LLM involvement in vocabulary/criteria under-specified | **New §5.6**: LLMs may *extract* terms (each adopted term traceable to a source review) and *audit* criteria adversarially (logged); they never author criteria; §1 execution-context logging applies to every use |
| 43 | Many steps; execution risk of drowning in machinery | §24 opens with a **critical path** — the twelve steps that constitute the study; everything else is marked supporting and cannot block them |
| 44 | Audience-facing views (curriculum lists, reading paths) could be mistaken for protocol outputs | §22.1: **audience views are a different thing** — downstream editorial products built *from* a released corpus version, allowed to be opinionated, carrying no evidentiary weight, never feeding back into tiers |

---

## 1. Purpose and study design

This project constructs a broad, verified evidence map of nanoscale connectomics research for use as the reading corpus behind a training curriculum, and derives from it an evidence-first map of the field's datasets, methods, infrastructure, and programs and the works underpinning them.

**Design statement (governing).** The corpus should make sure the field's major ideas, datasets, and labs are well represented; its most important tiers are scoped strictly to nanoscale (synaptic-resolution) work; missing links are inferred with citation graphs; and importance claims respect a two-sided filter — work that accumulates no citations *and* neither cites, is cited by, nor substantively discusses single-synapse-resolution connectomics is unlikely to matter to field definition — with named exceptions for infrastructure (systematically under-cited; protected by the institutional route) and emerging work (protected by citation-lag compensation, §3.0). Everything below implements this statement.

The objective is not a fixed number of papers or a citation ranking. It is to retrieve, verify, and organize the literature a working nanoscale-connectomics researcher would expect a trainee to encounter.

This is a scoping/evidence-mapping review with bibliometric augmentation. Search reporting follows PRISMA-S. Citation searching follows TARCiS terminology; citation searching supplements, and does not replace, primary subject searching. There is no target corpus size and no cap. Corpus size is an outcome.

**Two studies.** An exploratory pilot corpus (**Study A**) was constructed first: a deterministic Semantic Scholar pipeline (118,165 discovered → 3,768 retained → 1,806-work working corpus), executed 2026-08-22, frozen and SHA-pinned, fully documented in the repository's IA-001…015 chain. Study A informed this protocol and is disclosed as such. It never seeds Study B's discovery, and it serves as the primary §21 comparison set. **Study B** is the corpus built under this protocol; only Study B's outputs carry the protocol's claims.

**Protocol registration.** This protocol, the frozen lexicon (§5), the frozen search strings (§6), the screener roster (§12.5), the frozen probe panel (§5.5), and the pre-registered thresholds (§3.1, §14) will be deposited with a timestamp (OSF or equivalent DOI-issuing archive) referencing the repository commit, **before Phase 1 of §24 executes**. Deviations after deposit are logged with dates and reasons. The pilot corpus and every artifact frozen during protocol development are deposited alongside, in past tense, with their hashes.

**Execution context.** If any part of retrieval, screening, or metadata extraction is performed by an LLM-based agent, this is stated in the audit record, and the verification standard (§12) applies without exception. Confabulated references are the dominant failure mode of LLM-assisted bibliography work; this project's own development history includes three instances caught by verification (a nonexistent "community-standards" citation, a mis-titled review, a phantom validation set), which is the operational argument for §12.

**Positionality.** The investigators designing and executing this protocol are active researchers in the field and will appear, with their coauthors, among the authors of candidate works. This is handled by disclosure (§12.5) and ablation (§18), not by exclusion or recusal.

### 1.1 Methodological grounding

Each component of this protocol follows a published standard where one exists; the table is the citation map. Components with no published standard are listed separately as extensions, with their rationale — the claim is never that everything here is conventional, only that departures are named.

All DOIs below were verified to resolve via Crossref on 2026-08-25, per this protocol's own §12.3 standard.

| Component | Standard followed | Citation |
|---|---|---|
| Study type: scoping/evidence map with no importance-based inclusion | Scoping-review framework; evidence-map methodology | Arksey & O'Malley, *Int J Soc Res Methodol* 2005;8:19–32 (doi:10.1080/1364557032000119616); Miake-Lye et al., *Syst Rev* 2016;5:28 (doi:10.1186/s13643-016-0204-x) |
| Conduct and charting (§11–§12) | JBI scoping-review guidance; PRISMA-ScR reporting | Peters et al., *JBI Evid Synth* 2020;18:2119–26 (doi:10.11124/JBIES-20-00167); Tricco et al., *Ann Intern Med* 2018;169:467–73 (doi:10.7326/M18-0850) |
| Search documentation (§19) | PRISMA-S (exact strings, dates, counts, per source) | Rethlefsen et al., *Syst Rev* 2021;10:39 (doi:10.1186/s13643-020-01542-z); Page et al., *BMJ* 2021;372:n71 (doi:10.1136/bmj.n71) |
| Search-string review before freeze (§24.4) | PRESS peer review of electronic search strategies | McGowan et al., *J Clin Epidemiol* 2016;75:40–46 (doi:10.1016/j.jclinepi.2016.01.021) |
| Citation searching: terminology, seeds, iterations, stopping (§9) | TARCiS statement | Hirt et al., *BMJ* 2024;385:e078384 (doi:10.1136/bmj-2023-078384) |
| Co-citation and bibliographic coupling (§9.1, §10) | Classical bibliometric operators | Small, *JASIS* 1973;24:265–69 (doi:10.1002/asi.4630240406); Kessler, *Am Doc* 1963;14:10–25 (doi:10.1002/asi.5090140103) |
| Percentile-within-cell Core thresholds (§3.1) | Percentile-based indicators; field/era normalization | Waltman & Schreiber, *JASIST* 2013;64:372–79 (doi:10.1002/asi.22775); Hicks et al. (Leiden Manifesto), *Nature* 2015;520:429–31 (doi:10.1038/520429a) |
| Authorship-role evidence (§15.1) | CRediT contributor taxonomy | Brand et al., *Learned Publishing* 2015;28:151–55 (doi:10.1087/20150211) |
| Retraction checking (§12.3, §25-R) | Crossref/Retraction Watch practice per systematic-review guidance | Cochrane Handbook (Higgins et al., eds.), current version |
| Versioned post-freeze updating (§25) | Living systematic review model | Elliott et al., *PLoS Med* 2014;11:e1001603 (doi:10.1371/journal.pmed.1001603) |
| Reporting completeness for map-type syntheses | ROSES forms as a checklist cross-check | Haddaway et al., *Environ Evid* 2018;7:7 (doi:10.1186/s13750-018-0121-7) |

**Extensions beyond standard practice** (no published standard exists; each is pre-specified here so it can be evaluated as method, not improvisation): the frozen probe/attestation panel and its convergence-based saturation audit (§5.5, §9.1a, §14); dial-invariance labeling of Core membership (§3.1); the design-path ablation clause (§18), which generalizes self-citation-exclusion practice from citations to editorial decisions; screener COI tagging by frozen coauthorship distance (§12.5); and the typed adjudication classes of §25, which specialize the living-review model with an explicit prohibition on item-wise tier edits.

---

## 2. Field boundary

*(Unchanged from v3.)* The corpus covers nanoscale (synaptic-resolution) connectomics: reconstruction or direct measurement of individual neurons and the synapses between them at resolution sufficient to establish synaptic connectivity. The core technological lineage is volume electron microscopy (ssTEM, ssSEM, SBEM, FIB-SEM, automated tape/grid collection, multibeam acquisition) and associated preparation and reconstruction technologies. The field is defined functionally by the pipeline:

tissue preparation and staining → sectioning or block-face milling → EM acquisition → image alignment → segmentation → agglomeration → proofreading and QC → synapse detection and partner assignment → graph construction → analysis and modeling

Infrastructure needed to execute this pipeline at scale is part of the field.

### 2.1 Included adjacent work

*(Unchanged from v3.)* Adjacent literature is in scope iff at least one in-scope primary work cites it and substantively uses the method, result, or data for which it is being included. For each adjacent inclusion the record stores the citing work's identifier, the location of use, and a one-line statement of what was used. Adjacent work failing the test is excluded regardless of general influence.

### 2.2 Explicit boundary rulings

*(Unchanged from v3: CLEM, array tomography, cryo-ET, functional+EM, super-resolution LM, pre-2005 serial-section, and macroscale-exclusion rulings carry forward verbatim; borderline cases recorded with the ruling applied. The MRI/macroscale retrieval proportion is monitored as a boundary diagnostic; aggressive `NOT MRI` filters are not used.)*

---

## 3. Corpus architecture

A single broad training corpus with derived tiers.

### 3.0 Tier logic (new)

Three gates, applied in order; each strictly contains the next:

1. **Corpus membership needs scope only**: in scope under §2 (boundary test or §2.1 substantive-use link), verified under §12.3, eligible work type under §11. Graph status, citation counts, and importance judgments **never** exclude a work from the corpus.
2. **Field-defining tier membership needs scope + situability + evidence**:
   - *scope*: strictly nanoscale under §2 (no adjacent-only entries in field-defining tiers);
   - *situability*: situated in the nanoscale citation neighborhood — it cites corpus works, is cited by corpus works, or is substantively attested in a corpus review. Disconnection **deprioritizes** a tier claim; it never removes the work from the corpus. For the data-infrastructure stratum, where citation capture is known-poor, situability may instead be established through the institutional route (§8.2: datasets released through it, publications depending on it);
   - *evidence*: era-normalized dual evidence per §3.1.
3. **Emergent tier: the compensation is one-sided.** Work too recent for citation accumulation may enter the emergent tier with the inbound requirement replaced by the citation-lag rule (within-era rate percentile or recency floor, pre-registered). The **outbound situability requirement is never waived: emerging work must cite the core.** A reference list exists on day one; an uncited paper can be emerging, an unciting paper is disconnected. *Measurement guard*: an observed corpus-out-degree of 0 is a trigger for reference-list verification (fetch and check the actual reference list, which may be elided from any single index), never an automatic failure; a work fails the rule only when a verified reference list contains no corpus work. (Pilot test of this rule: 56 of 68 emergent candidates passed; all 12 flags traced to reference-list capture artifacts, none to genuine disconnection.)

### 3.1 Field-Defining Core

*(v3 criteria and machinery carry forward: the five qualifying contributions; dual structural + attestational evidence with reported Spearman correlation; three pre-registered percentile thresholds (5/10/20%) within stratum×era cells; minimum cell size 30 with the merge rule; the Absolute Core via three-of-four route families and attestation-distance ≥ 2; COI sensitivity reporting. Additions in v4:)*

**Dial-invariance (elevated).** The membership dial is published, not hidden: the Core is reported at all three thresholds with membership deltas. **Strong Core claims are made only for works whose membership is invariant** across all three thresholds, both evidence types, and the with/without-COI-1 variants. All other members are reported as Core with an explicit `sensitive-to-analytic-choice` flag naming which choice moves them. No prose in the paper states unqualified Core membership for a flagged work.

**Situability gate.** Core candidacy additionally requires §3.0 gate 2. Citation count alone is never sufficient; disconnection alone is never disqualifying from the corpus, only from tiers.

### 3.2 Broader Training Corpus

*(Unchanged from v3: enabling methods, refinements, benchmarks, QC, infrastructure, applications, comparative/developmental work, frontier work, reviews/tutorials. Reviews are first-class corpus members. Role tags: Field-defining core · Major enabling · Important application · Teaching/reference · Specialized/frontier.)*

---

## 4. Independence and provenance

**Comparison sets.** The single held-out comparison object is the **pilot corpus (Study A)**: frozen, SHA-pinned, and verifiably never a seed for Study B (the pilot itself ran `mode: fresh, seed_csv: null`; config hash matches its run manifest). The v3-era "seven-paper held-out set" is struck (no artifact of it exists); the "136-paper independent core"/"bespoke bibliography" is the 126-row backbone `stage1_backbone_126.csv`, preserved as a **historical artifact only** — by the screener's own statement it was not thoughtfully curated and holds no validation or seed role. Any genuine conviction embedded in it enters, one paper at a time, through the nomination route below.

**Limits of independence.** The screener designed both studies and has seen every list named above. Independence is procedural, not epistemic: enforced by (a) deriving the lexicon from external sources with recorded provenance (§5), (b) freezing and timestamping the lexicon, strings, panel, and parameters before Study B executes, (c) not consulting Study A outputs during Study B screening, and (d) the ablation reporting of §18. The §21 comparison is a gap diagnosis, not a validation of completeness.

**Provenance.** Every included work records *every* route that retrieved it, with route family (§3.1 of v3, unchanged): subject search (a) · canonical review reference list (b) · funding award (c) · public data platform (c) · backward citation (b) · forward citation (b) · co-citation/co-citing (b) · citation-network analysis (b) · author-derived supplementary search (a) · date-driven sweep (d) · **nomination (a; named nominator + one-line rationale)** · panel-convergence (b) · seed-convergence (b; gated). Each route record carries the date and expansion iteration.

No person enters because they are presumed important.

---

## 5. Search vocabulary development

*(§5.1–§5.4 unchanged from v3: controlled vocabulary; the §5.2 canonical-review bootstrap — pass-1 anchor searches executed 2026-08-25, candidate pool of ~6,506 review records frozen in the repository; retrieved-paper vocabulary with logged additions; era stratification with the three anchor-term sets. The lexicon remains a frozen, timestamped, reproducible artifact — extraction and freeze are the remaining §24 Phase-0 steps.)*

### 5.5 Probe/attestation panel *(executed and frozen 2026-08-25)*

A fixed panel of reviews serves two separable roles: **reference-list probe** (discovery, family b) and/or **attestation source** (§3.1 evidence). Discovery is never evidence.

The panel — P1–P8 probes spanning eight institutional/intellectual clusters (MPI-Frankfurt, Crick–EMBL, Princeton–Seung, Janelia–FlyEM, Cambridge–natverse, Harvard–Pfister, Columbia–Janelia, outside-field), plus P9 (Abbott et al. 2020) as confirmation-only — is frozen as `probe_panel_frozen.json`, byte-stream SHA-256 `0029158eed5344c358e38d9780e2a86bda5ec04ce0f5eb065aebbb28bd3f3149`, with resolved identifiers, tri-source author lists, cluster labels, and flags. Post-freeze changes are logged deviations.

Logged with the freeze: the Kornfeld & Denk 2018 exclusion (same lineage as P1; a second draw from the MPI distribution, not an independent probe); declared gaps (proofreading/QC and alignment have no probe; Plaza et al. 2014 is attestation-eligible but not a systematic probe); and screener-COI tags per member (P3 and P6 are COI-1 to the screener — their attestations fall under the §12.5 sensitivity reporting; P9 carries five distance-1 middle authors, recorded, not tag-raising).

### 5.6 LLM roles in vocabulary and criteria *(new)*

LLM-based agents may hold exactly two roles in vocabulary and criteria development; both are logged per §1's execution-context clause (model, prompt, date, input, output, human adjudication).

1. **Extractor.** A model may extract candidate terms from the frozen review pool (§5.2). Every adopted term records its source review and is verifiable against that review's text — the authority is the published review, never the model. Terms a model proposes from its own knowledge, with no source in the pool or in retrieved papers (§5.3), are not adopted.
2. **Auditor.** A model may adversarially review draft or frozen criteria and search strings — which classes of work would these miss; which criterion reads as tuned — with the critique logged as review input that the screener adjudicates: **every finding receives a recorded disposition** (accepted with the change, or rejected with a one-line reason). An unadjudicated audit is advice-shopping, not review. A model that helped draft the object under review is a weaker auditor of it: use a different model, or at minimum a fresh session carrying no drafting context, and record which arrangement was used. Model-asserted database syntax is verified against the database's own documentation before adoption. This may serve as (or supplement) the PRESS-style review of §24 item 4, disclosed as a limitation when it substitutes for an independent human reviewer.

Models never author criteria. An LLM's prior is a training-distribution prior — it over-weights prominent, English-language, fashionably-termed work, which is correlated with the preferential-attachment bias this protocol's date sweep and institutional route exist to counter. Substituting model judgment for screener judgment would replace a disclosed, frozen, ablatable bias with an uninspectable one.

---

## 6–8. Information sources, subject searching, sweeps, and institutional routes

*(Unchanged from v3: §6 sources table and search families with frozen verbatim strings; §7 historical/impact sweep and 48-month date-driven sweep with batch size 100; §8 funding programs and data/infrastructure platforms. The platform route remains the main protection for infrastructure builders and, per §3.0, an alternative situability channel for that stratum.)*

---

## 9. Citation-based expansion

*(§9 unchanged from v3: seed-corpus freeze point before the first iteration; backward/forward/co-citation expansion with numbered iterations.)*

### 9.1 Panel- and seed-convergence expansion

**Timing.** Runs only after Phases 2–3 are complete and §14 stopping has been evaluated per stratum — run last, so every unique find is simultaneously a candidate and a route-gap diagnostic.

**9.1a Panel backward-convergence (always runs).** Reference lists of P1–P8; candidates cited by ≥2 distinct clusters, reported at k=2 and k=3; P9 marks are descriptive corroboration only; candidates get normal screening/verification; route `panel-convergence (b)`.

*Executed once against Study A (2026-08-25) as a saturation diagnostic of the pilot: 903 distinct cited works, 112 candidates at k=2, 39 at k=3, **0 unique finds, 0 lexicon-gap alarms** — every convergence candidate was already in the pilot's discovery. 47 discovered-but-screened-out candidates were routed to the screener as a review queue. 9.1a runs again at Study B's own step 16b.*

**9.1b Ultracore seed-neighborhood expansion — INDEFINITELY GATED.** No qualified seed artifact exists: the backbone is unsuitable (§4), and a seed list requires per-paper designation rationale the screener must actually hold. If a genuinely curated seed artifact is ever frozen (identifiers + per-paper rationale + COI tags, disjoint from the §21 comparison set), the v3 operator suite applies (backward/forward convergence at k∈{2,3}; co-citation reported as lift over a degree-preserving null, minimum 5 observed; bibliographic coupling at Jaccard ≥ 0.15). Personalized PageRank remains excluded; reconsidering it is a protocol revision.

**9.1c Diagnostics.** Unique-find count per operator; lexicon-gap alarm (≥4 distinct clusters, undiscovered → diagnose which family should have caught it; a lexicon patch is a logged change, never silent); the seed-lineage limitation stated wherever results appear. No convergence statistic is ever §3.1 evidence.

---

## 10–13. Augmentation, inclusion, screening, verification, deduplication

*(Unchanged from v3, including: §10 graph augmentation as discovery/evidence variables only, self-citation excluded from centrality; §11 inclusion criteria — importance is never an inclusion criterion; §12.1 role-tag evidence fields; §12.2 screening procedure with calibration, human reliability sample (10% + all Core candidates + all COI-0/1), agent–agent agreement reported as reproducibility, never inter-rater reliability; §12.3 verification standard; §12.4 data-charting form; §12.5 COI disclosure with frozen distance-1 sets and the record tag as minimum over screeners; §13 deduplication. One §12.5 addition:)*

**§12.5 posture note.** The COI apparatus covers the *proximity* channel of screener bias and is retained as quiet bookkeeping: tags on every record, the with/without-COI-1 sensitivity, and the residual diagnostic. The screener's *design-path* channel (accumulated editorial decisions) is covered separately by the §18 ablation clause. Neither channel is claimed to be eliminated; both are measured.

---

## 14. Saturation and stopping

*(Unchanged from v3: round definition; the max(3, ⌈0.01·N⌉) scaled floor; two zero-yield rounds as saturation; per-stratum independence; incomplete labeling.)*

**Saturation reopening.** If §9.1 surfaces ≥1 new qualifying work in a stratum previously declared saturated, that stratum reopens for exactly one additional full round, after which the standard rule applies again. Reopening and yield are logged.

---

## 15. Contribution evidence (formerly investigator discovery)

The people-derived layer is retained for discovery and for the audit record, but its published form changes (§22): the unit of published analysis is the **contribution** — a dataset, tool, platform, method, or program — evidenced by works and roles, not the ranked person.

*(§15.1 authorship evidence rules unchanged: bare authorship is never evidence; qualifying roles from database metadata or CRediT; disambiguation via ORCID/OpenAlex with flagged ambiguity and per-era unresolved-identity reporting.)*

**§15.2 (revised).** The v3 person categories (field shapers, key contributors, infrastructure builders, emerging leaders) become an **internal working taxonomy** used for curriculum planning and coverage checking. They are not published as person-level classifications. Published outputs present contributions with their evidencing works and the roles the metadata supports; a person appears only as author-of-evidence.

---

## 16–17. Reviews; coverage assessment

*(Unchanged from v3: reviews as vocabulary, discovery, attestation, and training literature; §17 per-stratum coverage reporting with the same stratum list; thin strata trigger targeted searching, then are reported thin; stratum×era cell sizes reported for §3.1 merge audits.)*

---

## 18. Search-convergence, coverage, and bias diagnostics

*(v3 diagnostics carry forward: route-family overlap; capture–recapture as lower bound with its correlation caveat; pre- and post-expansion date-sweep independence; lexical saturation; era coverage; evidence redundancy (Spearman ρ); COI proximity residual. One addition:)*

**Ablations (new).** Every human-judgment overlay is reported **with and without**: (i) nominated works (§4 route `nomination`); (ii) the human screening overlay; (iii) the screener-nominated panel member (P1) in attestation counts. For each ablation: the membership delta of the corpus, each Core threshold, and the Absolute Core. A result that survives all ablations is reported plainly; a result that does not is reported with the ablation that moves it. This is the design-path counterpart of the COI sensitivity: COI measures who the screener knows; ablations measure what the screener decided.

---

## 19–20. Search documentation; quality control

*(Unchanged from v3. §20's QC list gains two checks: frozen artifacts whose byte-stream hash does not match their sidecar; tier claims lacking the §3.0 situability evidence or, for emergent works, lacking the verified reference list.)*

---

## 21. Corroboration and gap diagnosis (formerly "held-out validation")

Only after the Study B corpus is frozen is it compared against:

1. **The pilot corpus (primary).** Frozen Study A, never a Study B seed. Interpretation is asymmetric and stated wherever results appear: *agreement is weak evidence* (the protocol was calibrated from pilot experience; overlap is expected and both share the screener's blind spots); *disagreement is strong evidence of a gap in one method or the other*. Every miss in either direction is adjudicated: protocol-missed-pilot works get a route-family diagnosis (which family should have retrieved it); pilot-missed-protocol works get a screening-era diagnosis. Analyzed by year, stratum, organism, dataset, work type, and COI tag.
2. **Convergence diagnostics** (§9.1c) at Study B's step 16b.
3. **The backbone-126, optionally, as a labeled spot-check only** — reported, if at all, with its historical-artifact status stated; never as validation.

Comparison-identified misses are **not silently added**. The diagnosis is recorded; a missed work may subsequently enter only through the §25 nomination class, which cross-references the diagnosis. The word "validation" is not used in the paper for any of these comparisons.

---

## 22. Final outputs

- **A. Full Training Corpus** — every verified work meeting §11, with data-charting fields including COI tags and all routes.
- **B. Field-Defining Core** — three thresholds with membership deltas; dial-invariant members distinguished from `sensitive-to-analytic-choice` members; both evidence types per paper; COI-sensitivity and ablation variants; cell merges; Absolute Core with route-family and attestation evidence.
- **C. Contribution Evidence Map** *(revised)* — datasets, tools, platforms, methods, and programs, each with its evidencing works, the roles metadata supports, and provenance. People appear as authors-of-evidence only. No person-level tiers are published; the internal person taxonomy (§15.2) is retained in the working repository, clearly marked non-publication.
- **D. Search and Audit Record** — queries, provenance with iteration stamps, screening counts and agreement (human–agent κ and agent–agent reproducibility separately), citation iterations, diagnostics, ablations, adjudication log (§25), QC results, deviations.

Outputs remain separable so metadata improvements never require repeating discovery.

### 22.1 Audience views are a different thing *(new)*

Outputs A–D are the protocol's claims; they carry the evidence rules of this document. **Audience views** — a student curriculum, a newcomer reading path, a stratum syllabus, a funder-facing overview, a "start here" shelf — are *editorial products built from a released corpus version*, and are explicitly outside the protocol's claim apparatus:

- Each view names the release it draws from (e.g., "built from corpus v1.0") and states its selection rule in a sentence, but the rule is editorial and **may be opinionated** — a curriculum is allowed to say "read these twelve first" without that being a Core claim.
- Views carry **no evidentiary weight**: appearing in a view confers nothing toward tiers, and no view is cited as evidence anywhere in outputs A–D.
- Views **never feed back**: changing a view requires no adjudication (§25 governs the corpus, not its presentations), and nothing flows from a view into the corpus except through the ordinary nomination route, like any other human conviction.
- Views may freely use the internal working taxonomies (§15.2) that the protocol itself does not publish, because a teaching judgment ("students should know this lab's arc") is a different act from an evidentiary classification — the same distinction, in both directions.

This keeps both things healthy: the evidence map stays defensible because it never bends to presentation needs, and the views stay useful because they are free to be curatorial.

---

## 23. Bias register

*(The v3 table carries forward — author prior knowledge, screener-network proximity, citation age, preferential attachment, evidence redundancy, database venue coverage, language/geography, consortium authorship, role-metadata availability, review-derived vocabulary, threshold choice, Absolute-Core era bias, screener drift — with two changes:)*

| Bias | Expected direction | Mitigation | Residual diagnostic |
|---|---|---|---|
| **Pilot-corpus knowledge** (new) | Toward reproducing Study A's contents and framings | Externally derived era-stratified lexicon; frozen strings; pilot never seeds discovery; pilot outputs not consulted during Study B screening | §21 comparison against the pilot, misses diagnosed by route family |
| **Screener design-path** (new; split out of "author prior knowledge") | Toward the screener's accumulated editorial choices (nominations, overlays, panel composition) | Every human-judgment act is an enumerated, dated artifact; freeze-then-derive discipline; §18 ablations | Ablation membership deltas; nomination counts per release |

Residuals that cannot be reduced are reported as limitations.

---

## 24. Execution checklist

**Critical path.** Twelve steps constitute the study; everything else in this document supports them and cannot block them. If execution ever feels like it is drowning in machinery, this is the study:

1. Extract and **freeze** the lexicon from the review pool.
2. **Freeze** search strings (after PRESS-style review) and parameters (with calibration papers listed).
3. **Deposit** protocol + frozen artifacts; record the DOI.
4. Calibrate on 50 records.
5. Run the frozen subject searches.
6. Run the institutional route and the date sweep.
7. Screen, verify, deduplicate; **freeze** the seed corpus.
8. Expand by citation until §14 saturation, then run the §9.1a convergence audit.
9. Derive tiers through the §3.0 gates and §3.1 thresholds.
10. Run the human reliability screen; compute ablations and COI sensitivity.
11. **Freeze** release v1.0; run the §21 pilot comparison; record diagnoses.
12. Write limitations; handle all later change through §25.

Full ordered checklist below. **FREEZE** items produce a byte-stream-hashed artifact (SHA-256 sidecar) committed to the repository and included in the registration deposit. Items marked ✓ were executed during protocol development and are recorded here in past tense with their artifacts; they are deposited as-is.

**Phase 0 — Registration**
1. ✓ Screener roster: WGR (ORCID 0000-0002-7362-9665; OpenAlex + verified S2 author IDs in the COI artifact). Agents operate under the named human and inherit their COI tags.
2. ✓ COI distance-1 sets frozen 2026-08-21 (94 works, 349 d1 coauthors; d2 retained for completeness, unused per D-001). **Re-freeze required** under the byte-stream convention (the original's internal hash is not independently reproducible — D-004); the original file is retained.
3. ✓ §5.2 bootstrap pass 1 executed 2026-08-25 (~6,506-record candidate review pool, frozen in-repo). Remaining: extract lexicon; tag terms by era and class; **FREEZE** lexicon.
   3b. ✓ Gap-fill executed 2026-08-25 (9 works; Ware DOI resolved; Vogelstein COI-0 confirmed by author-ID match).
   3c. ✓ Panel frozen 2026-08-25 (`probe_panel_frozen.json`, SHA `0029158e…`).
4. Write database-specific search strings per family × era × source. Subject the strings to a **PRESS-style review** (McGowan et al. 2016): by a person who has not seen the pilot outputs where feasible; otherwise the §5.6 LLM audit substitutes, disclosed as such in the methods with the substitution named as a limitation. The review is structured around the PRESS elements (translation of the question, Boolean and proximity logic, subject headings, text-word variants and spelling, limits and filters, syntax per database), and **every finding receives a recorded disposition** — accepted with the change made, or rejected with a one-line reason — frozen alongside the strings. **FREEZE** strings.
5. Record pre-registered parameters: Core thresholds 5/10/20%; minimum cell size 30; stopping floor max(3, 1%N); date-sweep window 48 months; batch size 100; reliability sample 10% + all Core candidates + all COI-0/1; emergent-rule parameters; ablation list (§18); **and the calibration papers** — the list of touchstone works used to sanity-check the draft criteria, disclosed so criterion-shaping around specific papers is visible rather than possible in private. Criteria themselves are justified in field terms, never by which papers they admit. **FREEZE** parameters.
6. **Deposit** protocol (this document), items 1–5, the pilot-corpus pointer (repo tag + run-manifest SHAs), the bias register, and the deviations register to OSF/Zenodo. Record DOI. *(After this step, "deviation" is a defined term.)*

**Phase 1 — Calibration**
7. 50 calibration records across strata and eras; dual screen (≥1 human); record rulings; update §2.2; log boundary-table changes.

**Phase 2 — Primary retrieval (families a, c, d)**
8–13. *(As v3: frozen subject searches per source and era; funding/platform route; date sweep in batches; two-stage screening with per-record rationale, §2.1 test, COI tags on entry; dedup; verify; **FREEZE** seed-corpus snapshot; pre-expansion date-sweep diagnostic.)*

**Phase 3 — Citation expansion (family b)**
14–16. *(As v3: iterate backward/forward/co-citation with numbered iterations; screen and verify; evaluate §14 per stratum.)*
16b. Run §9.1: 9.1a against the Study B corpus; 9.1b iff a qualified seed artifact exists; compute 9.1c; apply §14 reopening where triggered.

**Phase 4 — Augmentation and derivation**
17–26. *(As v3, plus:)* apply the §3.0 situability gate and the emergent outbound-verification guard before tier assignment; compute §18 ablations alongside COI-sensitivity variants; derive the contribution evidence map (§15/§22) instead of person-tier classifications.

**Phase 5 — Freeze, corroborate, release**
27. **FREEZE** corpus, Core, contribution map, audit record (byte-stream hashes; release v1.0 per §25).
28. Run §21 corroboration and gap diagnosis. Record diagnoses; add nothing directly.
29. Write limitations from §23 residuals.

---

## 25. Post-freeze adjudication: how works are added, removed, and re-tiered after the run *(new)*

After the Phase-5 freeze, the corpus is a versioned artifact. Nothing in a frozen release is ever edited or deleted; all change happens through **typed adjudications** recorded in a single log and materialized in the next release. This section is the complete specification of post-run change.

### 25.1 Change classes

| Class | What it covers | Entry conditions | Effect |
|---|---|---|---|
| **E — Erratum** | A work the frozen retrieval touched that was mis-screened, mis-verified, or mis-charted (either direction: wrong exclusion or wrong inclusion) | Adjudication entry citing the criterion misapplied and the evidence; second human screener where the record is COI-0/1 and one exists, else `self-tagged` flag | Status overlay in the next point release; frozen decision retained in the record with the reversal linked |
| **N — Nomination** | A work the frozen routes never retrieved, added on human conviction (including anything salvaged from the historical backbone, and §21-diagnosed misses) | Route `nomination (a)` with named nominator, date, one-line rationale, and — for §21 misses — a link to the route-gap diagnosis; then full §12 screening and verification, no shortcuts | Enters a dated **addendum layer**, never backfilled into frozen provenance; counted separately in every headline number ("corpus n = X, of which Y post-freeze nominations"); included in the §18 nomination ablation |
| **R — Removal** | (i) Retraction (checked per §12.3 against Crossref/Retraction Watch at every release); (ii) identity failure (the record does not resolve to the claimed work); (iii) scope reversal via class E | As E; retractions need no second screener | Status flag (`retracted`, `identity-failed`, `descoped`), never deletion; retracted works are excluded from all evidence computations and reported; the record and its history remain in the artifact |
| **T — Tier recomputation** | Core/tier membership changes, including emergent→core transitions as citation windows mature | **Item-wise tier edits are prohibited** — this is the single place curation bias would otherwise re-enter. Tiers change only by re-running the complete frozen derivation (§3.0 gates, §3.1 thresholds, dial-invariance, ablations) over the release corpus | New tier tables in the next minor or major release, with a membership diff and the analytic reason (new citations, new attestation, adjudicated status change) per moved work |

### 25.2 The adjudication log

One append-only file, `adjudication_log.csv`, is the source of record for every post-freeze change: date · work identifier · class (E/N/R/T) · prior state · new state · criterion invoked · evidence (one or two sentences with identifiers) · screener · COI tag · second screener or `self-tagged` · release in which materialized. Contested cases are retained as `contested`, never forced (per §12.2). The log is published with every release.

### 25.3 Releases and versioning

- **v1.0** is the Phase-5 freeze. Every release is byte-stream-hashed with a sidecar and deposited alongside the registration.
- **Point releases (v1.x)** materialize accumulated E/R adjudications and N addenda. No re-retrieval, no re-derivation except the T recomputation triggered by status changes.
- **Major releases (v2.0, …)** re-execute the frozen searches with an extended date window (living-review update) plus full expansion, screening, derivation, diagnostics, and ablations. The frozen strings and rules are re-used verbatim; changing them is a protocol revision (new deposited version), not a release.
- Every release publishes a **diff against its predecessor**: works added (by class and route), status changes, tier moves with reasons, updated diagnostics, and the current nomination share. Headline counts always separate frozen-retrieval works from post-freeze nominations.
- Cadence: point releases as needed; major releases at most annually. Between releases, adjudications accumulate in the log and change nothing downstream.

### 25.4 Honesty rule

The adjudication system exists so that post-run judgment is expressed as *named, dated, evidence-bearing rows* rather than silent edits. If the nomination share of any tier grows large enough to change that tier's character (pre-registered alarm: nominations > 5% of a tier's membership), that fact is itself reported prominently, and the correct response is a route-gap fix and a major release, not more nominations.

---

## Governing principle

represent the field's major ideas, datasets, and labs → scope the important tiers strictly to nanoscale → freeze vocabulary, panel, strings, parameters, and COI sets, then deposit → search broadly by pipeline, system, date, and institution → verify identity → screen with recorded tests and disclosed proximity → expand through citation relationships → infer missing links with graphs, last, so unique finds are diagnostic → stop by demonstrated within-stratum saturation → derive tiers through scope, situability, and dial-invariant evidence — emerging work must still cite the core → compare against the pilot as gap diagnosis, never validation → publish contributions with their evidence, not people in tiers → change nothing after the freeze except through typed, logged, versioned adjudication

Retrieve broadly. Verify identity. Record every route. Enumerate every human judgment and ablate it. Disclose proximity rather than pretend distance. Stop by saturation and test the stopping. Report limits as limits.
