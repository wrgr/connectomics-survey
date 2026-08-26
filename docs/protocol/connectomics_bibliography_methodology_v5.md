# Mapping Nanoscale Connectomics: Scoping Review Protocol (v5)

**Status: DRAFT — to be deposited (OSF or equivalent DOI archive) before full screening and charting begin.** Supersedes v4, which is retained unchanged as the design record. Conduct follows JBI scoping-review guidance; reporting follows PRISMA-ScR for the review and PRISMA-S for searches. Amendments after deposit are logged with dates and reasons.

**Why v5.** v4 accumulated bespoke machinery (probe panel, convergence operators, dual-evidence Core with dial-invariance, ablation clauses, typed adjudication classes) whose purpose was to defend *ranked importance claims*. This review's contribution is the **map**, not a canon, so that machinery is removed rather than defended. Two structural facts about the field replace it: (1) **the field is dataset-anchored** — a small number of significant volumes exist, and nearly every paper produces one, builds methods for one, analyzes one, or serves them with infrastructure — so lineage and usage are chartable facts, not adjudicated judgments; and (2) **the pipeline is stereotyped** — preparation → acquisition → alignment → segmentation → proofreading → synapse detection → graph construction → analysis — so the charting form is the field's own taxonomy. Everything a reader would want from "importance" emerges descriptively from dataset genealogy and usage.

---

## 1. Review question and objective

**Question (PCC).** *Population:* the published literature (including preprints, datasets, and software records). *Concept:* nanoscale (synaptic-resolution) connectomics — the reconstruction or direct measurement of neurons and the synapses between them, and the methods, infrastructure, and analyses of the stereotyped pipeline that produces such reconstructions. *Context:* all organisms, all years, English-language sources.

**Objective.** To chart this literature onto the field's datasets and pipeline stages, producing: a dataset registry with genealogies (producing works, method lineages, analysis and reuse); per-stage and per-era coverage of methods and infrastructure; and identified gaps. There is no target corpus size and no importance-based inclusion or ranking. A training curriculum is a downstream editorial product (§10), not a review output.

## 2. Eligibility criteria

In scope: work whose subject is synaptic-resolution connectivity — any pipeline stage, dataset production or release, infrastructure serving the pipeline at scale, graph analysis of connectomes, connectome-constrained modeling, and organism applications. The core technological lineage is volume electron microscopy; alternative modalities (X-ray, expansion, molecular/sequencing) are in scope when they establish or are evaluated against synaptic-resolution connectivity.

Adjacent work (own subject not nanoscale connectomics) is eligible only via the **substantive-use test**: at least one in-scope work cites it and applies, extends, or evaluates against it; the citing work and location of use are recorded. Background-only citations do not qualify.

Boundary rulings (recorded and reapplied; borderline cases logged): CLEM in when the EM yields connectivity; array tomography in (alternative modality); cryo-ET out unless connectivity is established; functional+EM datasets in; super-resolution LM in only when used for circuit-level connectivity; pre-2005 serial-section reconstruction in; diffusion MRI/fMRI/generic network neuroscience/generic ML out unless passing the substantive-use test. The proportion of macroscale records retrieved is monitored as a boundary diagnostic; aggressive NOT-filters are not used.

Eligible work types: primary research, reviews/tutorials, benchmarks, dataset releases, software/infrastructure records (repository or archived release suffices; a publication is never invented), commentaries that define a field argument, theses/preprints without published versions.

## 3. Information sources and search

**Sources:** PubMed/MEDLINE; OpenAlex; Semantic Scholar (CS-venue coverage — PubMed under-indexes computer-vision venues); bioRxiv/arXiv; Crossref and Retraction Watch for verification. Google Scholar is not a formal source (non-reproducible); any targeted use is logged.

**Initial search (JBI step; executed).** An initial limited search and term-refinement phase was conducted during protocol development: an exploratory pilot corpus (deterministic Semantic Scholar pipeline, 118,165 discovered → 3,768 retained, frozen 2026-08-22 with SHA-pinned outputs) and a review-candidate pool re-derived under a written procedure (four anchor searches in PubMed `Review[pt]` and OpenAlex, plus a rule-based dedicated-review-venue supplement resolved to 336 OpenAlex source IDs; 1,278 records; per-query logs in `postanalysis/review_pool/derivation_log_v2.json`). Vocabulary for the full search strategy is extracted from the top-cited in-scope reviews per 5-year window and per pipeline stage from that pool, with each adopted term traceable to its source review. The pilot corpus does not seed the full search and serves afterward as a comparison set for gap diagnosis (§7).

**Full search.** Era-stratified strings (pre-2005 serial-section vocabulary; 2005–2015 connectomics vocabulary; 2015-present volume-EM/ML vocabulary) per search family — field identity; preparation; sectioning; acquisition; alignment; segmentation; proofreading/QC; synapses; infrastructure; graph analysis; modeling/NeuroAI; alternative modalities; organism/dataset names — written verbatim per source and frozen before execution, after a PRESS-guided review of the strings (by an independent person where feasible, otherwise a logged LLM audit disclosed as a limitation; every finding gets a recorded accept/reject disposition). Documentation per PRISMA-S: source, exact query, date, counts.

**Supplementary searching.** Backward and forward citation searching from included works, iterated to saturation and reported per TARCiS (seeds, direction, index, date, iteration, deduplication, stopping). Funding-program and data-platform pages (BossDB, neuPrint, FlyWire/Codex, MICrONS/CAVE, WormWiring, DANDI, EBRAINS, and platforms encountered) are searched as a discovery route for infrastructure under-served by citation indexing. Saturation per stratum: a round adding fewer than 5% and fewer than max(3, 1% of stratum) new qualifying works, revealing no new dataset or major method, permits stopping; strata still thin after targeted searching are reported thin.

**LLM assistance.** Any LLM use in search, screening, or extraction is logged (model, prompt, date, input, output, human adjudication). LLMs may extract terms traceable to source reviews and audit strings/criteria adversarially; they do not author criteria. Confabulated references are the known failure mode; the verification standard below applies without exception.

## 4. Source selection

Two-stage screening (title/abstract, then full text or repository/documentation for software and datasets), with per-record rationale. Screening is agent-assisted under a frozen prompt; a calibration set of 50 records spanning strata and eras is dual-screened (≥1 human) before formal screening, with rulings recorded. A random 10% of full-text decisions is independently screened by a human; agreement is reported as percent agreement and Cohen's κ (human–agent). A second agent pass over the same sample is reported as reproducibility, never as inter-rater reliability. Disagreements are discussed; unresolved cases are retained as *contested*, never forced.

**Verification (every included record):** the artifact is actually retrieved; the identifier resolves to the intended work; title/year/venue are mutually consistent; publication status established; preprint/published versions reconciled (one work, published preferred); retraction status checked via Crossref/Retraction Watch. Works without DOIs are eligible with a resolvable authoritative identifier.

## 5. Dataset registry

A controlled registry of the field's significant datasets is maintained as a first-class artifact, seeded with the known volumes (e.g., *C. elegans* White 1986 and successors; the *Drosophila* family — FAFB, hemibrain, FlyWire, larva, VNC, male CNS; mouse retina volumes; Kasthuri neocortex; MICrONS; H01; zebrafish; others as encountered) and grown as charting encounters new ones. Each entry: registry ID, organism/region, producing publication(s), hosting platform, release date. New entries require a verified producing publication or archived release. The registry is a controlled vocabulary for charting, not a ranking.

## 6. Data charting

One form per included work, drafted by the agent and human-verified on the reliability sample:

- identifiers (DOI/PMID/arXiv; database IDs) · work type · year · venue · open-access status
- organism/region · **dataset(s) from the registry** (produced / method-developed-on / analyzed / hosted-served / none)
- **pipeline stage(s)** (the stereotyped flow, §Why-v5) · era (pre-2005 / 2005–2015 / 2015–present)
- adjacent-work citing link where applicable (§2) · discovery route(s) with dates · screening decision + rationale · contested flag
- author identifiers where retrieved (ORCID/OpenAlex; consortium authorship never interpreted from memory)

## 7. Synthesis (descriptive)

- **Dataset genealogy map:** per registry entry — producing work, method lineage (works developing methods on it), analysis/reuse works, serving infrastructure; counts and timelines. Usage counts are reported as facts; no derived importance tier.
- **Stage × era coverage:** counts of works per pipeline stage per era; thin cells reported as gaps with the targeted searches that were attempted.
- **Descriptive bibliometrics:** year-normalized citation distributions and platform/funding provenance reported descriptively, clearly labeled as description, never as inclusion or ranking criteria.
- **Gap diagnosis against the pilot:** after charting is frozen, the corpus is compared with the pilot corpus; misses in either direction are diagnosed (which search family or screening era failed) and reported. Agreement is weak evidence (shared blind spots); disagreement is a gap diagnosis. Diagnosed misses are not silently added; late additions enter as labeled post-freeze nominations (§9).

## 8. Conflicts of interest and positionality

The screener of record (W. Gray Roncal, ORCID 0000-0002-7362-9665) is an active researcher in this field; he and his coauthors appear among candidate works. Handling is disclosure, not recusal: his frozen distance-1 coauthorship set (349 coauthors, frozen 2026-08-21) is retained; records where the screener is an author are flagged and always included in the human reliability sample; the paper discloses this arrangement. Self-authored works receive no special treatment in either direction.

## 9. Updates and corrections

The charted corpus is released in versions (v1.0 at freeze; byte-stream SHA-256 with sidecars). Errata (screening or metadata corrections) and retractions are status changes recorded in an append-only log — date, record, prior state, new state, evidence, adjudicator — and materialized in point releases; nothing is silently edited or deleted. Post-freeze additions are labeled **nominations** (named nominator, dated one-line rationale, normal screening and verification) and counted separately in headline numbers. Search re-execution with an extended date window is a major release (living-review update) reusing the frozen strings verbatim.

## 10. Outputs and audience views

Outputs: **(A)** the charted corpus with all fields; **(B)** the dataset registry and genealogy map; **(C)** stage × era coverage and gap report; **(D)** the search and audit record (queries, screening counts, κ, verification results, deviations, update log). Person-level classifications are not an output; people appear only as authors of charted works and credited dataset/platform contributors.

**Audience views are a different thing:** curricula, reading paths, and "start here" shelves are downstream editorial products built from a named release. They may be opinionated, carry no evidentiary weight, never feed back into the corpus, and are labeled as editorial.

## 11. Standards and reporting

| Element | Standard | Citation (DOIs Crossref-verified 2026-08-25) |
|---|---|---|
| Conduct | JBI scoping reviews | Peters et al. 2020, doi:10.11124/JBIES-20-00167 |
| Reporting | PRISMA-ScR | Tricco et al. 2018, doi:10.7326/M18-0850 |
| Search reporting | PRISMA-S | Rethlefsen et al. 2021, doi:10.1186/s13643-020-01542-z |
| Search-string review | PRESS | McGowan et al. 2016, doi:10.1016/j.jclinepi.2016.01.021 |
| Citation searching | TARCiS | Hirt et al. 2024, doi:10.1136/bmj-2023-078384 |
| Framework | Scoping studies | Arksey & O'Malley 2005, doi:10.1080/1364557032000119616 |
| Evidence-map form | Miake-Lye et al. 2016, doi:10.1186/s13643-016-0204-x |
| Updates | Living systematic reviews | Elliott et al. 2014, doi:10.1371/journal.pmed.1001603 |

The PRISMA-ScR checklist is completed at reporting; the flow diagram covers identification through charting.

## 12. Relationship to prior versions and artifacts

v1–v4 are retained as the design record. Artifacts produced during protocol development keep defined, reduced roles: the **pilot corpus** = the JBI initial search, then a §7 comparison set; the **review pool v2** = the vocabulary source; the **nine-review panel and its reference-list convergence run** = a one-time supplementary saturation check (reported as such: 112 cross-cluster candidates, zero not already retrieved), no longer protocol machinery; the frozen **COI set** = §8; the **126-row backbone** = historical artifact with no role. The v4 apparatus (percentile Core, dual evidence, dial-invariance, ablation clauses, typed adjudication taxonomy, route families) is withdrawn with this version, not silently — any future importance-claiming publication would need to re-adopt and re-justify such machinery explicitly.

---

## Execution checklist

1. Extract vocabulary from the review pool; write era-stratified strings per family × source. PRESS-guided review with recorded dispositions. **FREEZE** strings.
2. Seed the dataset registry. **FREEZE** initial registry (it grows during charting; growth is logged).
3. **DEPOSIT** this protocol + frozen strings + registry + COI set + pilot pointer. Record DOI.
4. Calibrate (50 records). Screen title/abstract, then full text. Verify every inclusion.
5. Citation expansion to saturation; platform/funding route; targeted searches for thin strata.
6. Chart; human-verify the reliability sample; report κ.
7. **FREEZE** corpus v1.0. Run the pilot comparison; write the gap report and limitations.
8. Build audience views editorially from the release.
