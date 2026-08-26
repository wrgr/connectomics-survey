# Exploration working set — corpus overlays (fill + prune)

**PLACEHOLDER (2026-08-26), views only.** Per the layered-overlay discipline
(IA-014 §10): these lists change nothing in the frozen pilot or its screening
record. They define an *exploration working set* as views over the 1,806-work
pilot corpus, for use during the placeholder phase. Formal membership changes
happen only through v5 charting or logged nominations.

## Is the pilot the best corpus source?

Yes, as substrate — frozen, provenance-complete, screened once — **plus the two
overlays below**, which correct its two measured defects. The formal v5 run
supersedes all of this.

## Fill: 53 candidates (`exploration_fill_candidates.csv`)

Works with independent evidence of relevance that the pilot's screen dropped:

- **47 convergence-rescue candidates** — in frozen discovery, screened out,
  yet cited by ≥2 of the 8 review-panel clusters (5 by ≥4 clusters: Knott
  FIB-SEM 2008, GCIB-SEM, Ohyama 2015, Eberle multibeam, Buhmann synapse
  detection).
- **6 additional verified methods-registry papers** absent from the corpus
  (beyond those already in the convergence list): whole-brain staining
  (Mikula), FAST-EM, ilastik, synful, network motifs, and the **BossDB
  ecosystem paper — the screener's own infrastructure work, dropped by the
  same lexical screen** (methods papers rarely say "connectome"; they say
  "focused ion beam"). Its even-handedness is noted; the stratum bias it
  reveals is the real finding.

**Diagnosis** (for the formal run): the pilot's lexical screen underweights
the *methods stratum* — corroborated independently by the convergence run and
the verified methods registry. The v5 search families (preparation, sectioning,
acquisition, alignment per se) are the designed fix; this overlay is the
interim patch.

## Prune: 240 candidates (`exploration_prune_candidates.csv`)

Adjacent-tier works with **no dataset mention, no wet/pipeline stage tag, and
no situability in the corpus citation graph** — i.e., failing the screener's
two-sided filter at keyword level. Mostly macroscale/graph-only literature
(connectome-based computing in disease, generic network papers).

**Never auto-dropped.** The list demonstrably contains false positives from
keyword granularity (e.g., a microwasp 3D-ultrastructure paper and a
preBötzinger circuit paper flagged only because their abstracts lack the
keywords). It is a *review queue*, applied as a view during exploration and
adjudicated per-work at formal charting.

## LLM-guided sanity pass (2026-08-26; screener-directed)

Per §5.6 discipline: adjudicator = this session's screening agent (operating
under WGR), rubric stated here, every disposition recorded.

**Prune adjudication** (`exploration_prune_adjudicated.csv`): all 240
candidates read and adjudicated against the scope rubric — keep if the work is
EM/ultrastructure, a vEM/pipeline method, an alternative *synaptic-resolution*
modality (multipatch, monosynaptic rabies, mGRASP-class detectors, ExM, X-ray),
analysis or modeling *on* a nanoscale connectome, comparative connectomics, a
field essay, or a training/infrastructure piece; drop if macroscale network
modeling, generic graph/ML theory, molecular synapse biology without mapping,
or functional-only inference. Result: **67 rescued (28% false-positive rate —
the keyword filter alone is not safe to apply unreviewed), 173 confirmed
drops.** Rescues include the fly-medulla connectome paper, Helmstaedter's dense
vEM review, EM computer-vision methods, ExM/X-ray modality papers, Chklovskii
2002 potential connectivity, and the Neurokernel emulation.

**Disconnection rule** (screener-directed: works citing neither into nor out of
the corpus network can be dropped; `exploration_disconnected.csv`): applied to
graph-matched works with corpus in-degree = out-degree = 0. **61 dropped**
(including 19 `core_relevant` works, listed — in-scope but isolated; removed
from the exploration view per the rule, recoverable at charting), **28
deferred** (year ≥ 2024: citation/reference lag), and the **492 graph-unmatched
works are NOT treated as disconnected** — unmatched is a measurement gap, not a
zero.

## Rule refinements (2026-08-26, screener-directed, second round)

1. **Recent works must have verified links TO the graph.** The 28 deferred
   ≥2024 zero-degree works are being verified against their actual S2
   reference lists (`analysis/verify_disconnected.py --recent` →
   `exploration_recent_verified.csv`): verified ≥1 outbound corpus link →
   keep; verified zero → drop; reference list elided/unavailable →
   unresolved, stays deferred. Retrieved-graph out-degree is never taken as
   fact without this check.
2. **Graph-unmatched works (492) are a separate resolution queue,
   prune-ineligible until resolved.** Unmatched is a measurement gap.
   Mechanical resolution (S2 reference fetch → verified outbound links) via
   `--unmatched` mode populates `exploration_unmatched_resolved.csv`; only
   *resolved* works become eligible for the disconnection rule.
3. **Axis coverage.** Of 300 works matching no stage/dataset keyword, 183 fit
   a *biological application / circuit biology* axis and 52 a *conceptual /
   field synthesis* axis — both §17 strata missing from the dry-run tagger,
   now added to the v5 charting form's axis-coverage rule. Role-bridge works
   chart to bridge fields by design. Residual true strays: ~65 (3.6% of
   corpus), each requiring per-work adjudication (the residual demonstrably
   contains in-scope works — the Wilson cerebellar germinal-layer paper and
   the microwasp are both in it).

## DOI recovery and record-type triage (2026-08-26, third round)

- **Recent-work verification complete** (`exploration_recent_verified.csv`):
  of 28 deferred ≥2024 works, 3 keep (verified outbound corpus links), 3 drop
  (verified zero), 22 unresolved (reference lists elided/not yet served —
  stay deferred). Retrieved-graph degree alone would have wrongly dropped
  all 28.
- **DOI recovery for the 37 DOI-less unmatched works**
  (`exploration_doi_resolution.csv`): 8 are the manual seeds whose DOIs were
  already in `manual_seed_works.csv` (join artifact — White 1986 was never
  really disconnected); of the remaining 29, **22 resolved** (17 arXiv
  preprint DOIs, 2 published via Crossref, 3 via OpenAlex) and **7 remain
  unresolved** for manual identity work (mostly conference/CS items).
- **Odd record types** (`exploration_odd_types.csv`, screener rule: abstracts,
  errata, and the like drop with a note): the working view contains only 7 —
  3 drop-noted (a peer-review response, a meeting editorial, a viewpoint
  piece), 4 kept as field-argument commentary per v5 §2 eligibility (incl.
  the Open Connectome Project and synchrotron X-ray Q&As). Conference-abstract
  strays had already been caught by the prune adjudication and recents pass.

## Net

**Unmatched queue resolved (2026-08-26, via S2 batch endpoint — 9 calls, ~3
min):** of 492, **327 (66%) verified linked to the graph** (join artifact —
they rejoin fully situated), **30 verified zero outbound** (27 pre-2024 drop
under the disconnection rule; 3 recent defer), **135 protected** (107
reference-lists elided, 21 not in S2, 7 no-DOI). Audit spot-check: LICONN
(Nature 2025) confirmed in the working corpus as core_relevant/integrated;
its preprint/published pair remains a flagged version-link candidate
(`suspected_unmerged_duplicates.csv`); now also added to the methods registry
and 2025 milestone, which had missed it.

Exploration working set = **1,806 − 173 (adjudicated prunes) − 61
(disconnected) − 3 (verified-zero recents) − 27 (verified-zero unmatched,
pre-2024) + 53 (fill) = 1,595** works, as a view, with 25 recent works
deferred-protected and 135 unmatched-unresolved protected.
What only the formal run can add (not patched here): a recency sweep past the
pilot's 2026-08-22 retrieval date; targeted searches for the thin alignment
and synapse strata; PRISMA-S-logged provenance for every addition.
