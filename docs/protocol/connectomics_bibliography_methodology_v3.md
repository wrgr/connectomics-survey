# Methodology for Building the Nanoscale Connectomics Training Bibliography (v3)

> **Superseded 2026-08-25 by the v4 draft** (`connectomics_bibliography_methodology_v4.md`), which consolidates the execution amendments below and the design decisions recorded in IA-015/IA-016. This v3 text is retained unchanged as the historical record.

## Summary of revisions from v2

| # | Issue in v2 | Change in v3 |
|---|---|---|
| 17 | Screener conflict of interest unaddressed; screeners are candidates for Core and investigator map | New §12.5: coauthorship-distance COI tags on every record, carried through all outputs; COI-linked attestation tagged and Core reported with/without; §23 row added. Disclosure, not recusal (§12.5 states why) |
| 18 | Structural and attestational evidence presented as independent | §3.1: reframed as complementary; correlation reported; Absolute Core uses 3-of-4 route *families* rather than raw route count |
| 19 | Percentile Core unstable in small stratum×era cells; Core size scales with corpus size | §3.1: minimum cell size 30 with era-merge rule; absolute counts reported alongside percentiles; percentile stated as ranking device, not size claim |
| 20 | Scope test for adjacent work still undefined (§2.1 pointed to a role-tag table) | §2.1: substantive-use citation test; citing paper and location recorded |
| 21 | Agent–agent agreement presented as inter-rater reliability | §12.2: human required on the 10% sample and all Core candidates; agent–agent agreement reported as reproducibility only |
| 22 | Absolute stopping floor (<3) unreachable in large strata | §14: floor = max(3, 1% of stratum size) |
| 23 | Date-sweep-only diagnostic conflated with forward citation | §18: computed before and after citation expansion; both reported |
| 24 | No execution order | New §24: execution checklist with freeze points |
| 25 | COI-2 on full graph uninformative (86,742 authors via non-field hubs) | §12.5: tagging limited to COI-0/COI-1; group-independence rules moved to corpus-internal graph (D-001) |

## Amendments logged during execution

This document entered the repository `wrgr/connectomics-survey` on 2026-08-25 (sync event; see IA-015 §1). Amendments below were made after the v3 text was consolidated and are dated; each points at its implementation record. They are protocol amendments, logged as such, not silent revisions.

| # | Date | Change | Implementation record |
|---|---|---|---|
| 26 | 2026-08-25 | Review-corpus gap-fill: 9 works added under route `targeted-title-search (gap-fill)`, family (a). Ware & LoPresti 1975 identifier resolved via Crossref bibliographic query (doi:10.1016/s0074-7696(08)60956-0). The unverifiable "Collinson et al. 2023 community-standards piece" claim is retracted; the retraction is itself the log entry. Declared standing gap: alignment/registration has no review. | `postanalysis/review_pool/review_pool.json`; IA-015 §3 |
| 27 | 2026-08-25 | New §5.5: probe/attestation panel (P1–P9) defined and frozen as an artifact, with role separation (probe vs. attestation), the Kornfeld & Denk exclusion, and declared panel gaps. | `postanalysis/review_pool/probe_panel_frozen.json`, SHA-256 `0029158eed5344c358e38d9780e2a86bda5ec04ce0f5eb065aebbb28bd3f3149`; IA-015 §4 |
| 28 | 2026-08-25 | New §9.1 (panel- and seed-convergence expansion) and §14 saturation-reopening rule; §24 checklist insertions 3b/3c and 16b. | `analysis/panel_convergence.py`; `postanalysis/review_pool/convergence/`; IA-015 §5 |

---

## 1. Purpose and study design

This project constructs a broad, verified evidence map of nanoscale connectomics research for use as the reading corpus behind a training curriculum, and derives from it a map of the investigators and technical contributors who have shaped the field.

The objective is not a fixed number of papers or a citation ranking. It is to retrieve, verify, and organize the literature a working nanoscale-connectomics researcher would expect a trainee to encounter.

This is a scoping/evidence-mapping review with bibliometric augmentation. Search reporting follows PRISMA-S. Citation searching follows TARCiS terminology; citation searching supplements, and does not replace, primary subject searching.

There is no target corpus size and no cap. Corpus size is an outcome.

**Protocol registration.** This protocol, the frozen lexicon (§5), the frozen search strings (§6), the screener roster with ORCIDs (§12.5), and the pre-registered thresholds (§3.1, §14) will be deposited with a timestamp (OSF) before the first formal search is executed. Deviations will be logged with dates and reasons.

**Execution context.** If any part of retrieval, screening, or metadata extraction is performed by an LLM-based agent, this must be stated in the audit record, and the verification standard (§12) applies without exception. Confabulated references are the dominant failure mode of LLM-assisted bibliography work and are the primary reason §12 exists.

**Positionality.** The investigators designing and executing this protocol are active researchers in the field and will appear, with their coauthors, among the candidates for Core status and the investigator map. This is handled by disclosure (§12.5), not by exclusion or recusal, for reasons stated there.

---

## 2. Field boundary

The corpus covers nanoscale (synaptic-resolution) connectomics: reconstruction or direct measurement of individual neurons and the synapses between them at resolution sufficient to establish synaptic connectivity.

The core technological lineage is volume electron microscopy (ssTEM, ssSEM, SBEM, FIB-SEM, automated tape/grid collection, multibeam acquisition) and associated preparation and reconstruction technologies.

The field is defined functionally by the pipeline:

tissue preparation and staining → sectioning or block-face milling → EM acquisition → image alignment → segmentation → agglomeration → proofreading and QC → synapse detection and partner assignment → graph construction → analysis and modeling

Infrastructure needed to execute this pipeline at scale (annotation systems, chunked storage, versioning, serving, collaborative proofreading, distributed computation, dataset release) is part of the field.

### 2.1 Included adjacent work (revised)

Adjacent literature — work whose own subject is not nanoscale connectomics — is in scope iff **at least one in-scope primary work cites it and substantively uses the method, result, or data for which it is being included**. "Substantive use" means the citing paper applies, extends, or evaluates against the cited work; a citation that merely mentions it (background, related-work list) does not qualify.

For each adjacent inclusion the record stores: the citing in-scope work's identifier; the location of use (section/figure); and a one-line statement of what was used.

This replaces judgment of whether adjacent work "materially informs" the field with a single retrievable link, auditable per record. Examples of adjacent work that will typically pass:

- alternative methods capable of approaching synaptic-resolution connectivity;
- X-ray or light-microscopy approaches evaluated against EM;
- expansion or molecular/sequencing-based connectomics;
- computer-vision algorithms directly applied to connectomic reconstruction;
- graph/network methods applied to connectome graphs;
- modality comparisons explaining what nanoscale vs. mesoscale/macroscale measurement can establish.

Adjacent work that fails the test is excluded regardless of general influence. A foundational CV paper cited only as background by in-scope work is out of scope; one whose architecture an in-scope segmentation paper trains and reports is in scope.

### 2.2 Explicit boundary rulings

| Category | Ruling |
|---|---|
| Correlated light–EM (CLEM) | Included when the EM component yields connectivity; excluded when EM is used only for ultrastructural localization |
| Array tomography | Included (synaptic-resolution molecular mapping); tagged as alternative modality |
| Cryo-ET of synapses | Excluded unless connectivity is established; ultrastructure alone is out of scope |
| Functional + EM datasets (e.g., calcium imaging co-registered with EM) | Included; the EM connectivity component is the qualifying element |
| Super-resolution light microscopy of synapses | Included only when evaluated against or used for circuit-level connectivity |
| Pre-2005 serial-section reconstruction | Included; handled by the era-stratified lexicon (§5.4) |
| Diffusion MRI, resting-state fMRI, generic network neuroscience, general microscopy, generic ML/CV, generic graph theory | Excluded unless passing the §2.1 substantive-use test |

Borderline cases will be recorded with the ruling applied, so the boundary is auditable and can be re-applied.

The proportion of MRI/macroscale papers retrieved is monitored as a boundary diagnostic; aggressive `NOT MRI` filters are not used.

---

## 3. Corpus architecture

A single broad training corpus with a derived Field-Defining Core.

### 3.1 Field-Defining Core

A paper belongs in the Core when retrieved evidence shows it did at least one of:

1. established a result that changed understanding of neural connectivity;
2. introduced a method, algorithm, tool, or infrastructure that became foundational or broadly adopted;
3. released a dataset or resource on which substantial subsequent work depends;
4. demonstrated a new feasibility or scale threshold;
5. became the canonical conceptual or review treatment of an essential field problem.

**Operational requirement (revised).** Core status requires two *complementary* evidence types, recorded per paper:

- one structural: year-normalized citation influence, citation-network centrality, or documented downstream dependency (datasets or tools built on it), each computed within the paper's stratum×era cell;
- one attestational: explicit characterization as foundational/landmark in a retrieved review, textbook, award description, or platform documentation, with the source cited and its COI tag (§12.5) recorded.

These evidence types are not independent: reviews preferentially attest to highly cited work. The protocol does not claim independence. It reports the correlation (Spearman ρ between within-cell structural rank and attesting-source count, over all Core candidates) so the degree of redundancy is visible. The value of requiring both is that each has a failure mode the other does not: structural evidence misses infrastructure and very recent work; attestational evidence is subject to reviewer-network effects. Their conjunction is a stricter gate than either alone even when correlated.

**Threshold handling.** The structural cutoff is pre-registered before retrieval. Because any single cutoff is arbitrary, the Core is derived and reported at three pre-registered percentile thresholds (top 5%, 10%, 20% within stratum×era cell), and the set of works whose membership changes between thresholds is reported explicitly. The middle threshold is the primary Core; the other two are sensitivity analyses. A paper retained at all three thresholds is a robust Core member; a paper present only at the loosest threshold is reported as Core-candidate, not Core.

Percentile-within-cell is a ranking device, not a size claim: it follows the within-field top-X% convention (Leiden PP(top 10%), Scopus field-normalized percentiles) and is chosen because a fixed N per cell has no precedent and cannot be compared across cells of different size. Absolute counts are reported alongside every percentile figure.

**Minimum cell size (new).** Percentile thresholds are computed only in cells containing ≥ 30 works. A cell below 30 merges with the adjacent earlier-or-later era in the same stratum (pre-2005 merges into 2005–2015 first; 2005–2015 merges toward whichever neighbor is smaller). If a merged cell is still below 30, no percentile Core is computed for it; its works may enter as Core-candidates on attestational evidence alone and are flagged `attestation-only-cell`. All merges are listed in the outputs.

**Absolute Core (revised).** A further tier identifies works on which all lines of evidence converge. Discovery routes (§4) are grouped into four **route families** with distinct failure modes:

- (a) term-based subject search;
- (b) citation-mediated: backward, forward, co-citation/co-citing, canonical-review reference lists, citation-network analysis;
- (c) institutional: funding awards, data/infrastructure platforms;
- (d) date-driven sweep.

A work is Absolute Core when all of the following hold:

1. present at the strictest threshold (top 5%) in a cell meeting the minimum size;
2. retrieved by at least **three of the four route families**;
3. attested as foundational in at least two reviews whose author sets share no author and have no direct coauthorship link on the corpus-internal coauthorship graph (distance ≥ 2), at least one published in a later era (§5.4) than the work itself.

Route families replace raw route counts because the citation-mediated routes are near-duplicates of each other and would make any famous paper satisfy a count criterion trivially. Three of four families is the smallest requirement that forces convergence across genuinely different retrieval mechanisms. Pre-2005 works cannot satisfy family (d); this is a known structural limit and the Absolute Core is expected to be biased toward 2005+ works accordingly. The tier is reported at whatever size the criteria yield. It is a claim about the field's history, not a curriculum.

Citation count alone is never sufficient. The Core is derived after retrieval, is not a seed list, and has no predetermined size.

**COI sensitivity (new).** The Core at every threshold and the Absolute Core are each reported twice: (i) using all attestational sources; (ii) excluding attestations from sources within COI-1 of the attested work (§12.5). Membership deltas between (i) and (ii) are listed.

### 3.2 Broader Training Corpus

Additionally includes enabling methods, technical refinements, benchmarks and validation studies, QC and error-analysis work, infrastructure and software, major biological applications, comparative and developmental connectomics, frontier work, and reviews/tutorials with pedagogical value.

Reviews are first-class corpus members.

Role tags (one or more per work): Field-defining core · Major enabling · Important application · Teaching/reference · Specialized/frontier

---

## 4. Independence and provenance

The pre-existing bespoke bibliography, the earlier 136-paper core, and the seven-paper held-out set will not seed discovery. They are held-out comparison sets, merged only after the new corpus is frozen.

**Limits of this independence.** The investigator designing the search has seen these lists. Independence is therefore procedural, not epistemic: it is enforced by (a) deriving the lexicon from external sources with recorded provenance (§5), (b) freezing and timestamping the lexicon and search strings before any comparison, and (c) not consulting the held-out lists during execution. Where feasible, search-string development should be reviewed by someone who has not seen the held-out lists. The held-out test is accordingly treated as a sanity check (§21), not as validation of completeness.

**Provenance.** Every included work and investigator records *every* route that retrieved it, not only the first, together with the route family (§3.1):

subject search (a) · canonical review reference list (b) · funding award (c) · public data platform (c) · backward citation (b) · forward citation (b) · co-citation/co-citing (b) · citation-network analysis (b) · author-derived supplementary search (a) · date-driven sweep (d)

Each route record carries the date and the expansion iteration in which it occurred, so that §18 diagnostics can be computed at defined points.

No person enters because they are presumed important.

---

## 5. Search vocabulary development

### 5.1 Controlled vocabulary

Indexing terms and entry terms from MeSH (and Emtree if Embase is used) establish stable modality terminology.

### 5.2 Canonical reviews — bootstrap procedure

Reviews supply vocabulary, but retrieving them requires vocabulary. The bootstrap is:

1. Run anchor-term searches (connectom*, "serial section" AND "electron microscopy", "volume electron microscopy", "dense reconstruction") with a review/publication-type filter in PubMed and OpenAlex.
2. Select the top-cited review per 5-year window from 1990 onward, plus the top-cited review per pipeline stage, to a minimum of one review per stratum in §17. Record selection counts.
3. Extract from each: title/abstract terminology, author keywords, section headings, modality names, pipeline terms, software/infrastructure names, organism- and dataset-specific vocabulary.
4. Re-run step 1 with the expanded lexicon once; add newly surfaced reviews; stop.

Reviews will deliberately span acquisition, reconstruction, biology, infrastructure, and analysis. Reviews selected here are tagged with their COI status relative to the screener roster (§12.5) at selection time.

### 5.3 Retrieved-paper vocabulary

Terms repeatedly encountered among independently retrieved relevant papers may be added when they identify a genuine methodological or scientific branch. Additions are logged with the triggering papers and recorded as protocol deviations with dates.

### 5.4 Era stratification

"Connectome" dates from 2005; "connectomics" is later still. The lexicon is stratified into three eras, each with its own anchor terms:

- **Pre-2005:** serial section reconstruction, serial electron microscopy, three-dimensional reconstruction, ultrastructural reconstruction, synaptic circuitry, wiring diagram, neuropil reconstruction;
- **2005–2015:** connectome, connectomics, dense reconstruction, saturated reconstruction, SBEM/SBF-SEM, FIB-SEM, automated segmentation;
- **2015–present:** volume EM, flood-filling, affinity, proofreading, synaptic partner prediction, connectome-constrained models, plus named entities.

Each term is classed as anchor, pipeline, or named entity, and tagged with its era(s). Named entities are used only for supplementary searches after discovery.

The lexicon is a frozen, timestamped, reproducible artifact.

### 5.5 Probe/attestation panel (added 2026-08-25; revision 27)

A fixed panel of reviews serves two separable roles. A panel member may act as (i) a **reference-list probe** — its bibliography is a discovery route (family b); and/or (ii) an **attestation source** — its prose statements are §3.1 attestational evidence. Discovery is never evidence: a paper found via a probe's reference list gains nothing toward Core status from having been cited; only what a source *says* about a work counts as attestation.

The panel (P1–P8 probes spanning eight institutional/intellectual clusters, plus P9 Abbott et al. 2020 as **confirmation-only** — its citations are descriptive corroboration marks, never threshold inputs) is frozen as `probe_panel_frozen.json` with resolved identifiers, full author-ID lists per member, cluster labels, probe/attestation flags, timestamp, and SHA-256, deposited alongside the lexicon. Changes after freeze are logged deviations.

Explicit exclusion (logged): Kornfeld & Denk 2018 — in the corpus, NOT on the panel; same intellectual lineage as P1 (Denk trained Helmstaedter); its reference list is a second draw from the MPI distribution, not an independent probe. Declared panel gaps (not patched): proofreading/QC and alignment strata have no probe because no comprehensive review exists; Plaza et al. 2014 remains corpus-member and attestation-eligible but is a perspective, not a systematic probe.

Attestation-source COI: each panel member's author set is COI-tagged relative to any work it attests, per §12.5 handling rule 2; panel membership does not exempt from the with/without-COI-1 Core sensitivity reporting.

---

## 6. Primary subject searching

### 6.0 Information sources

| Source | Role | Rationale |
|---|---|---|
| PubMed/MEDLINE | Biomedical core | MeSH; biological literature |
| OpenAlex | Primary bibliometric backbone; coauthorship graph for §12.5 | Open, CS-inclusive, year-level citation counts, author IDs, citation graph |
| Semantic Scholar or Scopus/Web of Science (at least one) | CS-venue and cross-check | CVPR, NeurIPS, MICCAI, ISBI coverage; FWCI-type normalized metrics where available |
| bioRxiv, arXiv | Preprints | Recent and CS-lineage work; reconciled against published versions |
| Crossref, Retraction Watch | Verification | Identifier resolution; retraction status |
| Google Scholar | Not a formal source | Non-reproducible; may be used only for targeted gap checks, logged as such |

The known limitation that PubMed under-indexes computer-vision venues is the reason for requiring a CS-inclusive index.

### 6.1 Search families

Primary retrieval uses multiple search families, each executed per era where relevant:

- **Field identity:** connectomics, connectome, synaptic-resolution connectomics, neural circuit reconstruction, dense/saturated reconstruction, wiring diagram, plus pre-2005 equivalents.
- **Tissue preparation and staining:** fixation, extracellular-space preservation, embedding, osmication, en bloc staining, rOTO.
- **Sectioning and material removal:** serial sections, ultramicrotomy, ATUM, GridTape, hot-knife partitioning, FIB milling.
- **EM acquisition:** volume EM, ssTEM, ssSEM, SBEM/SBF-SEM, FIB-SEM, multibeam SEM/TEM, ML-guided acquisition.
- **Alignment and registration:** serial-section alignment, elastic registration.
- **Segmentation and agglomeration:** neuron segmentation, affinity prediction, supervoxels, agglomeration, flood-filling networks.
- **Proofreading and QC:** proofreading, split/merge errors, error detection, skeletonization, accuracy metrics.
- **Synapses:** synapse detection, partner prediction/assignment, molecular annotation.
- **Data infrastructure:** annotation systems, versioning, materialization, chunked storage, visualization, serving, distributed pipelines.
- **Graph analysis:** connectome graphs, motifs, null models, topology, wiring rules.
- **NeuroAI and modeling:** connectome-constrained networks, structure-to-function prediction, circuit simulation.
- **Alternative modalities:** X-ray nanotomography, expansion-microscopy connectomics, light-microscopy connectomics, molecular/sequencing approaches.
- **Organism/dataset searches:** C. elegans and related nematodes; Drosophila adult, hemibrain, larva, VNC; retina; mouse cortex, hippocampus, cerebellum; human cortical volumes; zebrafish; other comparative connectomes encountered.

Exact database-specific strings are frozen and recorded verbatim before execution.

---

## 7. Two independent literature sweeps

### 7.1 Historical/impact sweep

Candidates retrieved using bibliometric relevance and age-normalized citation influence. Raw counts are recorded but never used for cross-year comparison. Normalization method and source (e.g., OpenAlex citations per year since publication; Scopus FWCI) are recorded. The era-stratified lexicon (§5.4) is applied so that pre-2005 work is retrievable on its own terms.

### 7.2 Date-driven sweep

A separate search retrieves recent literature ordered by publication date, independent of citation prominence, to counteract preferential attachment and citation lag.

**Window.** The window is defined relative to the search date: the most recent 48 months.

**Volume control.** Date-ordered retrieval without a citation signal is high-volume. Screening proceeds in batches of fixed size per stratum (batch size pre-registered; default 100); the stratum stopping rule in §14 applies to consecutive batches.

The number of qualifying papers found by the date sweep and by no other route is reported at two points (§18).

---

## 8. Independent institutional and infrastructure route

### 8.1 Funding programs

NIH BRAIN Initiative; BRAIN CONNECTS; other relevant NIH programs; ERC and successor initiatives; Brain/MINDS; HHMI Janelia project pages where publicly listed; Wellcome, Simons (SCGB), and national programs encountered.

For each qualifying award: award → named PI/project leader → associated publications/resources.

Funding status confers no importance; it is a discovery path.

### 8.2 Data and infrastructure platforms

BossDB; neuPrint/FlyEM; FlyWire/Codex; MICrONS/CAVE; OpenOrganelle; WormWiring; DANDI; EBRAINS; additional platforms discovered systematically.

Publication, dataset, contributor, and citation pages are searched. This route is the main protection for infrastructure builders under-served by citation metrics.

---

## 9. Citation-based expansion

After primary subject and institutional searches produce an eligible seed corpus, supplementary citation searching begins using TARCiS terminology.

**Freeze point.** Before the first expansion iteration, the seed corpus (all works retained from families a, c, and d) is snapshotted with a timestamp. This snapshot is the basis for the pre-expansion diagnostic in §18.

- **Backward:** references of included papers, especially reviews, screened for foundational work.
- **Forward:** citing works screened for later methods, datasets, applications.
- **Co-cited and co-citing:** neighboring works identify intellectual clusters and vocabulary the subject search missed.
- **Iterative:** newly eligible works become seeds in subsequent rounds; each iteration is numbered and recorded in provenance (§4).

Citation expansion supplements the term-based search.

### 9.1 Panel- and seed-convergence expansion (added 2026-08-25; revision 28)

**Timing.** Runs ONLY after Phase 2 (primary retrieval, families a/c/d) AND Phase 3 (citation expansion, family b) are complete and §14 stopping has been evaluated per stratum; never earlier. Rationale: the operators' value is what they add beyond the standard routes. Run early, "convergence found it" is indistinguishable from "anything would have found it"; run last, every unique find is simultaneously a candidate and a route-gap diagnostic.

**9.1a Panel backward-convergence (always runs).** Retrieve the full reference list of each probe member P1–P8 (not P9). For every referenced work, count distinct panel members and distinct clusters citing it. Convergence candidates: cited by members from ≥2 different clusters; candidate sets reported at k=2 and k=3 (k = distinct clusters). P9 is used afterward as corroboration only: candidates it also cites are marked descriptively; the mark is never a threshold input. Every candidate not already in the corpus goes through normal §12.2 screening, §12.3 verification, §11 inclusion, and §3.1 dual evidence for any Core claim. Provenance route: `panel-convergence (b)`, recorded alongside any other routes.

**9.1b Ultracore seed-neighborhood expansion (runs only if a seed list is designated).** Preconditions, all mandatory: a frozen, timestamped seed artifact from the screener (identifiers + designation rationale per paper + COI tag per paper against the frozen COI sets); and a **mutual-exclusivity check** — the seed list must be disjoint from the seven-paper held-out set and the 136-paper independent core. On any overlap: STOP and return the overlap to the screener, who chooses (i) remove overlapping seeds or (ii) consume those held-out papers as seeds and shrink the validation set, logged as a deviation. Never both roles for one paper; never seed from the 136 and later report agreement with the 136 as validation. Four operators, all run and reported separately: backward convergence (referenced by ≥k seeds; k at 2 and 3); forward convergence (citing ≥k seeds; k at 2 and 3; review/synthesis enrichment expected and noted); co-citation (report **lift over a degree-preserving null**, minimum 5 observed co-citations before lift is computed; raw counts recorded, never used for flagging); bibliographic coupling (Jaccard overlap per seed; flag at pre-registered Jaccard ≥ 0.15 — the only operator expected to surface low-cited contemporaneous work; its unique finds are the most valuable output). Personalized PageRank is NOT used (threshold arbitrary; not defensible as "referenced by n of m seeds, here is the list"); reconsidering it is a protocol amendment, not an execution choice. All flagged works are discovery only, route `seed-convergence (b)` + operator name.

**9.1c Diagnostics (both operators).** (1) **Unique-find count**: works flagged by convergence and retrieved by no other route — the operators' marginal value, per operator. (2) **Lexicon-gap alarm**: any work cited by ≥4 distinct clusters that the frozen subject searches did not retrieve → evidence of a lexicon gap; diagnose which search family should have caught it and log the diagnosis (a lexicon patch is a logged deviation, never silent). (3) **Seed-lineage limitation**, stated wherever results appear: the method finds the seed set's lineage — ancestors, descendants, peers, parallel work — and systematically misses important work disconnected from that lineage; it supplements the term/institutional/date routes and substitutes for none. No convergence statistic ever appears as §3.1 structural or attestational evidence.

---

## 10. Bibliometric and network augmentation

Where access permits, a graph is built over the corpus and its citation neighborhood. Analyses may include citation-network PageRank or centrality, co-citation structure, co-authorship networks, author betweenness, and year-normalized influence.

These are discovery and evidence variables, not inclusion rules. Centrality measures on citation graphs favor older papers; results are interpreted within era, and recent papers are protected explicitly.

Self-citation is excluded from centrality inputs where the data permit.

---

## 11. Inclusion criteria

This is a scoping corpus. A work enters when all three hold:

1. **In scope** under §2, including the substantive-use test (§2.1) and boundary rulings (§2.2);
2. **Verified** under §12.3;
3. **Eligible work type:** primary research, review/tutorial, benchmark or validation study, dataset release, software/infrastructure record, commentary or response that defines a field argument, or thesis/preprint where no published version exists.

Importance is **not** an inclusion criterion. Judgments of importance are made only at role-tagging (§12.1) and Core derivation (§3.1), where they are recorded with evidence and subjected to sensitivity analysis.

No paper is included or excluded because of author identity or citation count. No stratum is padded for balance.

Consequence: the corpus will be large. That is the intended outcome; curriculum selection is done downstream from role tags and Core status, not by narrowing the corpus.

---

## 12. Screening and verification

### 12.1 Evidence fields for role tags

Role tags (§3.2) are assigned with recorded evidence. The table lists what is *recorded*, not a threshold that must be passed. Thresholds appear only in Core derivation (§3.1) and are subject to sensitivity analysis there.

| Role tag / claim | Evidence recorded |
|---|---|
| Changed understanding | Retrieved review(s) or subsequent primary papers that restate the finding as established; identifiers listed |
| Method/tool adopted | Count and identity of retrieved papers using it, and number of independent groups (no shared author with, and no direct coauthorship link to, the originating group, on the corpus-internal graph) |
| Dataset/resource | Count and identity of retrieved papers analyzing it from groups other than the releasing group |
| Pipeline improvement | The benchmark or capability claim, quoted or paraphrased with location |
| Failure mode | Subsequent works referencing the named error type |
| Field argument | Published response, commentary, or contested review claim |
| Teaching/reference | Selection under §5.2, or use in a retrieved syllabus/curriculum |
| Application | Review(s) citing the result as a connectomics finding |
| Infrastructure | Datasets released through it and publications depending on it |

Counts are recorded as integers, not compared to fixed minimums at tagging time.

### 12.2 Screening procedure (revised)

1. **Calibration.** Before formal screening, 50 candidate records spanning strata and eras are screened independently by two screeners, at least one human. Disagreements are discussed, rulings recorded, and the boundary table (§2.2) updated.
2. **Two-stage screening.** Title/abstract, then full text or equivalent (for software/resources: repository and documentation).
3. **Reliability sample.** A random 10% of full-text decisions and 100% of Core candidates are screened independently by a second screener who is **human**. Agreement is reported as percent agreement and Cohen's κ, by screening phase. Where the primary screener is an LLM agent, the reported κ is human–agent.
4. **Reproducibility (separate from reliability).** If agent screening is used, a second agent pass over the same 10% sample is reported as agent–agent agreement, labeled reproducibility. It is never reported as inter-rater reliability: two runs of one model measure sampling variance, not validity.
5. **Per-record rationale.** Every include/exclude decision records the criterion invoked and the operational evidence, in one or two sentences.
6. **Adjudication.** Disagreements are resolved by discussion; unresolved cases are retained as "contested" rather than forced.

### 12.3 Verification standard

For inclusion:

1. a scholarly record or citable artifact is actually retrieved;
2. the identifier resolves to the intended work;
3. title, publication identity, year, and venue are mutually consistent;
4. publication status is established;
5. preprint/published versions are reconciled;
6. retraction status is checked (Crossref, Retraction Watch).

Crossref, publisher records, PubMed, OpenAlex, and other authoritative indexes may be combined. Material disagreements are retained, not harmonized.

**Author metadata.** Full author-list transcription is not a prerequisite. But: authorship supporting an investigator claim must be retrieved from a database record; large consortium authorship is never interpreted from memory; role claims (first/last/corresponding) use database metadata; ORCID and database author IDs are retained.

**Works without DOIs** remain eligible with a resolvable authoritative identifier.

**Software without papers** enters as a software/resource record via repository or archived release (Zenodo, Software Heritage). A publication is never invented to stand in for it.

### 12.4 Data-charting form

Each record captures: persistent identifier(s); title; year; venue; work type (primary/review/preprint/software/dataset); organism/system; dataset(s); pipeline stratum/strata (§17); era (§5.4); modality; role tag(s); inclusion criterion and evidence; adjacent-work citing link (§2.1) where applicable; all retrieving routes with family, date, and expansion iteration (§4); screening decisions and screener IDs; **COI tag per screener (§12.5)**; open-access status; language; author IDs where retrieved; contested flag; notes.

### 12.5 Conflict-of-interest disclosure (new)

**Why disclosure and not recusal.** The screeners are active researchers in a small field. Adjudicators who are both expert enough to screen and outside the screeners' coauthorship network do not exist in useful numbers. Recusal would therefore either be impossible or shift decisions to less-qualified screeners. The scientometric precedent for this situation is self-citation handling: results are reported with and without the conflicted evidence, and the difference is shown. That is the approach adopted here.

**Screener roster.** Every screener (human or agent-operator) is listed in the registered protocol with ORCID and OpenAlex author ID. Agents act on behalf of a named human operator and inherit that operator's COI tags.

**Coauthorship distance.** Before screening begins, the full OpenAlex work list for each rostered screener is retrieved and the set of all coauthors (distance 1) is frozen and timestamped. Distance 1 is computed on the full publication record, not the corpus-internal graph, so that coauthorships outside connectomics count. Distance 2 is **not** used for tagging: on the full graph it reaches tens of thousands of authors through non-field hubs and the tag carries no information. (Pre-registration decision D-001; the d2 set is retained in the frozen artifact for completeness only.)

**Tags.** Every work and every investigator-map entry carries, per screener:

| Tag | Meaning |
|---|---|
| COI-0 | Screener is an author of the work / is the investigator |
| COI-1 | A qualifying-role author of the work (first/co-first, last/co-last, corresponding) is at distance 1 from the screener |
| none | Distance > 1 or unresolvable |

The record tag is the minimum over screeners who touched that record.

**Handling rules.**

1. COI-0 and COI-1 records are always included in the reliability sample (§12.2 step 3) in addition to the random 10%. Where a second human screener with a weaker COI tag on that record exists, that screener makes the role-tag and Core decision; where none exists, the decision stands and the record is flagged `self-tagged`.
2. Attestational sources (§3.1) carry their own COI tag relative to the attested work's qualifying-role authors. Attestation is never discarded; it is tagged, and the Core is reported with and without COI-1 attestation (§3.1, COI sensitivity).
3. Absolute Core criterion 3 (two attesting reviews at mutual distance ≥ 2) is computed on the **corpus-internal** coauthorship graph at derivation time, since it concerns independence between attesting author groups, not screener proximity.
4. COI tags are carried visibly into every output (§22). They are not stripped from any published table.

**Residual diagnostic.** Share of the Core (each threshold), Absolute Core, and investigator map at COI-0 and COI-1, compared against the corresponding share of the full corpus. A Core markedly more COI-proximate than the corpus is reported as such.

---

## 13. Deduplication

By persistent identifier first; then normalized title, authorship, year, venue. Preprint and published versions are one work; published preferred. Conference and journal versions are merged only when substantially the same contribution.

---

## 14. Saturation and stopping

Saturation is assessed within field strata (§17), not globally.

**Definition of a round.** One round in a stratum is: one complete execution of the stratum's frozen subject searches in all named sources, plus one iteration of backward/forward/co-citation expansion from all works retained in the stratum at the start of the round, plus screening of the results.

**Stopping rule (revised).** A stratum may stop when both:

1. a round adds fewer than 5% new qualifying works **and** fewer than **max(3, ⌈0.01 × N⌉)** new qualifying works in absolute terms, where N is the stratum size at the start of the round; and
2. the round reveals no new Core candidate, important method, major dataset, or repeatedly rediscovered omission.

The scaled floor replaces the fixed floor of 3 because iterative citation expansion in large strata (segmentation, infrastructure) reliably produces a handful of new qualifying works per round indefinitely; a fixed floor of 3 would make saturation unreachable there while a proportional floor alone would be too permissive for strata of 20–40 works. The max() form preserves the small-stratum protection.

Alternatively, two consecutive rounds retaining zero works constitute saturation.

Saturation in one stratum never stops searching in another. If practical limits end retrieval before criteria are met, the stratum is labeled **incomplete**, with the round count reached and the last-round yield.

**Saturation reopening (added 2026-08-25; revision 28).** If convergence enrichment (§9.1) surfaces ≥1 new qualifying work in a stratum previously declared saturated, that stratum reopens for exactly **one** additional full round (as defined above), after which the standard stopping rule applies again. Reopening and its yield are logged. This prevents the stopping rule from degrading into "stopped, except when we felt like continuing," while making convergence the designed test of whether saturation was real.

---

## 15. Investigator discovery and classification

The investigator pool is derived only after retrieval begins. People enter via: authorship of an included/candidate paper; named PI/project-leader status on a retrieved award; credited contributor/leader on a retrieved dataset or platform; citation or co-authorship graph expansion. No manual seeding.

### 15.1 Authorship evidence rules

- **Bare authorship is never evidence of contribution**, for any paper of any author count. Evidence is: first/co-first, last/co-last, corresponding roles from database metadata; roles named in a CRediT or contribution statement; named PI/project-leader status on an award; credited leadership on a platform. Author count is recorded as a descriptor.
- **CRediT and contribution statements** are retrieved wherever present and are the preferred evidence source. Their absence (common pre-2018) is recorded as a limitation per record, not inferred around.
- **Disambiguation.** ORCID where present; otherwise OpenAlex/Scopus author ID with affiliation history. Ambiguous identities are flagged, not merged. ORCID coverage is poor before ~2015; the proportion of unresolved identities per era is reported.

### 15.2 Evidence and categories

Evidence: Core authorship in qualifying roles; repeated landmark participation; foundational methods or datasets; sustained technical contribution; infrastructure development; program leadership; recent important work; network bridging.

Categories (non-exclusive):

- **Field shapers** — repeated leadership of landmark work, foundational methods, major resources, or field-building programs.
- **Key scientific/technical contributors** — important first/co-first or technical contributions to landmarks, broadly adopted methods, or sustained programs.
- **Infrastructure builders** — contribution disproportionately in data systems, annotation, acquisition infrastructure, software, or community resources.
- **Emerging/current leaders** — important recent contributions with immature citation history. Requires at least one qualifying-role contribution to a work tagged Major enabling or Core within the date-sweep window; not a residual bin.

Every investigator-map entry carries its COI tag (§12.5).

---

## 16. Reviews as a deliberate corpus component

Reviews serve as vocabulary source, discovery source, attestational source, and training literature. They are not ranked below primary work for lacking data. For curriculum construction, clarity and synthesis are legitimate forms of importance.

---

## 17. Coverage assessment

Coverage is reported per stratum:

conceptual foundations and limits of inference · modality/scaling trade-offs · preparation and staining · sectioning/milling · EM acquisition · alignment · segmentation and agglomeration · proofreading and QC · synapse detection/partner assignment · data infrastructure · ultrastructure and cell typing · graph/statistical analysis · NeuroAI/connectome-constrained modeling · landmark datasets and biological applications · open science/community/citizen science · emerging alternative modalities

Descriptive coverage where metadata permit: year; work type; journal; institution; corresponding-author country; organism; open-access status; language. Non-English literature is not searched in other languages; this is reported as a limitation.

Thin strata trigger targeted searching; if still thin, they are reported thin. Stratum×era cell sizes are reported so that §3.1 merges are auditable.

---

## 18. Search-convergence and coverage diagnostics

**Route overlap.** Overlap between subject-search and funding/platform routes is reported, by route family.

**Capture–recapture.** A Lincoln–Petersen estimate (A × B / overlap) may be computed between families (a) and (c), but the two are positively correlated (well-funded labs produce well-indexed, well-cited work), which biases the estimate downward. It is reported only as a **lower bound** on the universe size, with this caveat stated wherever it appears.

**Date-sweep independence (revised).** Computed at two points using the provenance iteration stamps (§4):

1. **Pre-expansion** (from the §9 freeze-point snapshot): qualifying works retrieved by family (d) and by neither (a) nor (c). This is the route-independence diagnostic. A result near zero indicates the date sweep is not finding anything the term and institutional searches miss.
2. **Post-expansion** (after all citation iterations): qualifying works retrieved by (d) and by no other family. This is the date sweep's residual unique contribution after forward citation has done its work.

Both are reported. Reporting only the second would conflate route non-independence with forward citation functioning as designed.

**Lexical saturation.** New terminology is monitored; repeated emergence of unsearched terms triggers expansion and is logged.

**Era coverage.** Proportion of Core candidates per era, to detect the modern-terminology bias that §5.4 is designed to prevent.

**Evidence redundancy.** Spearman ρ between structural rank and attestation count (§3.1).

**COI proximity.** Per §12.5 residual diagnostic.

---

## 19. Search documentation

Every formal search records: source; platform; exact query; date; result count; number screened; number retained; exclusion counts by reason; limits or ranking applied. Purposeful website, funding, platform, and citation-index searches are also documented.

Citation-search reporting additionally records: seeds; direction; index; date; iteration number; deduplication; stopping condition.

---

## 20. Quality-control checks

Before freezing: duplicate identifiers; probable duplicates under different identifiers; unresolved identifiers; records lacking a derivation path; preprint/published duplication; retracted works; nanoscale/macroscale boundary drift; adjacent-work records lacking a citing link (§2.1); unsupported investigator attribution; underrepresented strata; cells below 30 not merged or flagged (§3.1); raw rather than normalized citations used cross-year; records lacking screening rationale; Core candidates lacking both evidence types or lacking a human reliability screen; large-N authorship used as general evidence (§15.1); records lacking COI tags; COI-0/COI-1 records missing from the reliability sample.

Failures are reported and resolved where possible; unresolved uncertainty is preserved.

---

## 21. Held-out validation

Only after the corpus is frozen is it compared with the seven-paper held-out set, the 136-paper independent core, and the bespoke bibliography.

**Interpretation.** The seven-paper set is a sanity check: one miss is a 14% failure rate and carries no statistical weight. The 136-paper core is the more informative comparison. Given the procedural-only independence noted in §4, agreement with either set is weak evidence of completeness; disagreement is strong evidence of a gap in one method or the other.

Comparisons: Independent ∩ Bespoke; Independent − Bespoke; Bespoke − Independent; analyzed by year, stratum, organism, dataset, journal, institution, work type, role, investigator, and COI tag.

Missing held-out works are not added. The route family that should have retrieved them is diagnosed and the diagnosis recorded.

---

## 22. Final outputs

- **A. Full Training Corpus** — every verified work meeting §11, with data-charting fields including COI tags.
- **B. Field-Defining Core** — the derived subset at three thresholds with membership deltas, both evidence types per paper, the COI-sensitivity variant at each threshold, cell merges, and the Absolute Core subset with its route-family and attestation evidence.
- **C. Investigator Map** — people with category, evidence, identifiers, and COI tag.
- **D. Search and Audit Record** — queries, provenance with iteration stamps, screening counts and agreement (human–agent κ and agent–agent reproducibility separately), citation iterations, diagnostics, unresolved candidates, QC results, protocol deviations.

**Handling of the investigator map.** Categorizing living people has reputational consequences. The map is a descriptive evidence summary, not a ranking. Each classification must be traceable to retrievable evidence. If published, categories are presented with their evidence rather than as a league table, and the document states that absence reflects retrieval limits, not a judgment of contribution. Screeners and their coauthors appear in the map with COI tags visible; their entries are not suppressed, since suppression would itself be an undisclosed editorial act.

Outputs remain separable so metadata or investigator improvements do not require repeating discovery.

---

## 23. Bias register

No search is unbiased. The defensible claim is that each known bias is named, its direction stated, a mitigation applied, and the residual measured. The table below is part of the registered protocol and is updated if new biases are identified during execution.

| Bias | Expected direction | Mitigation | Residual diagnostic |
|---|---|---|---|
| Author prior knowledge | Toward the author's existing lists and known labs | External, era-stratified lexicon; frozen timestamped strings; no consultation of held-out lists | Held-out comparison (§21) interpreted as gap diagnosis, not validation |
| **Screener-network proximity** (new) | Toward screeners' own work and coauthors in Core and investigator map; toward attestations from proximate reviews | COI tags on all records and sources (§12.5); COI-0/1 always in human reliability sample; Core reported with and without COI-1 attestation | Core/map share at each COI level vs. corpus share; membership delta between COI-sensitivity variants |
| Citation age | Against recent work | Year-normalization within era; date sweep; Core thresholds within era | Date-sweep-only counts (§18); Core age distribution vs. corpus age distribution |
| Preferential attachment | Toward already-famous papers and labs | Date sweep; funding/platform route; structural + attestational dual evidence; route families for Absolute Core | Proportion of Core from top-5 institutions vs. corpus proportion |
| Evidence redundancy | Structural and attestational evidence agree for reasons unrelated to merit | Neither type sufficient alone; correlation reported | Spearman ρ (§3.1) |
| Database venue coverage | Against CS/CV venues, theses, software | CS-inclusive index; preprint servers; software records | Proportion of segmentation/infrastructure strata retrievable from PubMed alone |
| Language/geography | Toward Anglophone and North American/European work | None available within scope; reported | Corresponding-author country distribution; non-English count |
| Consortium authorship | Toward members of large projects | Bare authorship not evidence; roles/CRediT only | Proportion of investigator-map entries whose only evidence is from papers with > 50 authors |
| Role-metadata availability | Against pre-CRediT and pre-ORCID eras | Limitation recorded per record | Unresolved-identity rate per era |
| Review-derived vocabulary | Toward subfields that reviews emphasize | Reviews sampled per stratum and era; lexical-saturation monitoring | New-term emergence rate by stratum |
| Threshold choice | Whatever the chosen cutoff favors | Three-threshold Core with membership deltas; minimum cell size with merge reporting | Size of the membership-change set; number of merged cells |
| Absolute Core era bias | Against pre-2005 work (cannot satisfy route family d) | Stated as structural limit | Era distribution of Absolute Core |
| Screener drift | Inconsistent boundary over time | Calibration set; human reliability sample; recorded rationale | κ reported by screening phase |

Residuals that cannot be reduced are reported as limitations in the final outputs.

---

## 24. Execution checklist (new)

Ordered. Items marked **FREEZE** produce a timestamped artifact deposited to the registration before proceeding.

**Phase 0 — Registration**
1. Enumerate screener roster with ORCID / OpenAlex IDs; for agents, the operating human.
2. Retrieve each screener's full OpenAlex work list; freeze distance-1 coauthor set. Verify screener identity across all author records (OpenAlex, Semantic Scholar, ORCID); record merged/contaminated records. **FREEZE** COI author-ID sets. *(Done 2026-08-21 for WGR; artifact `COI_sets_WGR_frozen.json`, SHA-256 46f86882…)*
3. Run §5.2 bootstrap; extract lexicon; tag terms by era and class. **FREEZE** lexicon.
3b. Execute the review-corpus gap-fill (revision 26: 9 additions; Ware identifier resolution; Vogelstein COI-0 flag). *(Done 2026-08-25; `review_pool.json`.)*
3c. Resolve panel DOIs; write and **FREEZE** `probe_panel_frozen.json` (§5.5). *(Done 2026-08-25; SHA-256 0029158e….)*
4. Write database-specific search strings per family × era × source. **FREEZE** strings.
5. Record pre-registered parameters: Core thresholds 5/10/20%; minimum cell size 30; stopping floor max(3, 1%N); date-sweep window 48 months from search date; batch size 100; reliability sample 10% + all Core candidates + all COI-0/1. **FREEZE** parameters.
6. Deposit protocol (this document), items 2–5, and bias register to OSF. Record DOI.

**Phase 1 — Calibration**
7. Pull 50 calibration records across strata and eras. Dual screen (≥1 human). Record rulings; update §2.2. Log as deviation if boundary table changes.

**Phase 2 — Primary retrieval (families a, c, d)**
8. Execute frozen subject searches per source, per era. Document per §19.
9. Execute funding and platform route (§8).
10. Execute date sweep in batches of 100 per stratum.
11. Title/abstract then full-text screening with per-record rationale; apply §2.1 substantive-use test to adjacent work; apply COI tags on entry.
12. Deduplicate (§13). Verify (§12.3).
13. **FREEZE** seed-corpus snapshot (§9 freeze point). Compute pre-expansion date-sweep diagnostic (§18.1).

**Phase 3 — Citation expansion (family b)**
14. Iterate backward / forward / co-citation from all retained works; number each iteration; stamp provenance.
15. Screen and verify each iteration as in 11–12.
16. Per stratum, evaluate §14 stopping rule after each round. Stop or label incomplete.
16b. Run §9.1: panel backward-convergence (9.1a); seed-neighborhood expansion (9.1b) iff a seed artifact exists and passes the exclusivity check; compute 9.1c diagnostics; apply the §14 reopening rule where triggered.

**Phase 4 — Augmentation and derivation**
17. Build citation graph; compute within-cell normalized influence and centrality (self-citations excluded).
18. Compute stratum×era cell sizes; apply merges; record.
19. Assign role tags with §12.1 evidence.
20. Derive Core at three thresholds; record structural and attestational evidence per candidate with source COI tags.
21. Run human reliability screen on 10% sample + all Core candidates + all COI-0/1 records. Report κ. If agents were used, run agent–agent reproducibility on the same sample and report separately.
22. Derive Absolute Core via route families and attestation-distance rule.
23. Produce COI-sensitivity variants of Core and Absolute Core.
24. Derive investigator map (§15) with COI tags.
25. Compute all §18 diagnostics including post-expansion date-sweep count and Spearman ρ.
26. Run §20 QC. Resolve or preserve.

**Phase 5 — Freeze and validate**
27. **FREEZE** corpus, Core, investigator map, audit record.
28. Compare against held-out sets (§21). Diagnose misses by route family. Do not add.
29. Write limitations from §23 residuals.

---

## Governing principle

derive vocabulary externally and by era → name sources, roster screeners, and freeze strings and COI sets → search broadly by pipeline and system → search independently by date → search funding and infrastructure → verify identity → screen with recorded tests, calibration, and disclosed proximity → snapshot before expansion → expand through citation relationships → analyze graph structure within era → re-search thin strata → stop by within-stratum saturation with scaled floors → derive Core and investigator map with complementary evidence and sensitivity variants → freeze → compare against held-out sets as a sanity check

Retrieve broadly. Verify identity. Record every route. Screen with stated tests. Disclose proximity rather than pretend distance. Expand systematically. Stop by demonstrated within-area saturation. Enrich metadata after corpus formation. Report limits as limits.
