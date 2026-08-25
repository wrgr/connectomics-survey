# IA-010 — Deterministic record-type triage

## Status

Derived post-processing extension. It adds a *label*, not a filter. It does not alter the
preregistered retrieval corpus, original `keep` values, IA-004 core labels, IA-005/006
bridge labels, IA-008 work/version links or abstract status, and it does not modify
`analysis/llm_relevance_screen.py`, the IA-007 prompt, the IA-007 denominator, or any
screening decision already made.

The frozen retrieval provenance is untouched and stays exactly as `docs/POSTANALYSIS_PAPER_FLOW.md`
states it: **3,768 retained records, 391 recovered role-bridge records, a 4,159-record
semantic-analysis universe, 4,136 canonical works.** What IA-010 changes is the *paper*
denominator used for reporting, and it changes it by labelling 50 of those 4,136 canonical
works as records that are not research papers. Those 50 records are retained, counted and
re-joinable; none is deleted.

## Why this is necessary

Some records in the corpus are not research papers at all. They lack abstracts — or carry
short publisher stubs, or carry a full editorial essay — because of *what they are*, not
because of a metadata gap. The corpus contains referee reports titled `Review for "…"`,
eLife-style `Author response: …` items, errata and corrigenda, journal editorials, replies
and commentaries, numbered meeting-abstract stubs, and a whole workshop proceedings volume.

IA-007 currently routes every abstract-less work to `insufficient_abstract` and from there
into the human review queue. For a genuine paper whose abstract could not be rescued that is
exactly right: the IA-007/IA-008 contract is that no work may be excluded from its title
alone. For an erratum it is wrong twice over. It inflates the paper denominator, and it
spends scarce human adjudication effort deciding the scientific "relevance" of a correction
notice. Human screening capacity is the binding constraint and is itself error-prone — Wang
Z, Nayfeh T, Tetzlaff J, O'Blenis P, Murad MH, *Error rates of human reviewers during abstract
screening in systematic reviews*, PLOS ONE 2020;15(1):e0227742, measured a combined
false-inclusion/false-exclusion rate of 10.76% (95% CI 7.43–14.09) across 329,332
dual-independent decisions — so spending it on record types that are decidable
deterministically from metadata is a poor allocation.

IA-007 does have a `paratext_or_peer_review_record` noise flag, but it can only fire on works
that reach the model, and works without abstracts never reach the model. The signal that
would catch these records is therefore structurally unavailable exactly where it is most
needed. IA-010 supplies it before and outside the model path.

Record type is a first-class, curated metadata property in every bibliographic source this
project touches, which is why it can be handled deterministically rather than semantically:

- **NLM/MEDLINE** treats publication type as a controlled vocabulary with published scope
  notes ([Publication Characteristics (Publication Types) with Scope Notes](https://www.nlm.nih.gov/mesh/pubtypes.html)).
  `Published Erratum` is "an acknowledgment of an error, issued by a publisher, editor, or
  author"; `Editorial` is "a statement of the opinions, beliefs, and policy of the editor or
  publisher of a journal"; `Comment` is "a critical or explanatory note written to discuss,
  support, or dispute an article … it appears in publications under a variety of names:
  comment, commentary, editorial comment, viewpoint"; `Retracted Publication` marks the
  retracted item and is explicitly distinguished from the notice that retracts it (renamed
  from `Retraction of Publication` to `Retraction Notice`, [NLM Technical Bulletin 2026
  Mar–Apr](https://www.nlm.nih.gov/pubs/techbull/ma26/ma26_pubmed_update_MeSH_changes.html)).
- **Crossref** has a dedicated `peer_review` record type since schema 4.4.1, covering
  "referee reports, decision letters, and author responses", with an `isReviewOf` relation to
  the reviewed DOI ([Peer reviews markup guide](https://www.crossref.org/documentation/schema-library/markup-guide-record-types/peer-reviews/)).
  The `Review for "…"` and `Author response: …` records in this corpus are exactly that class
  of artifact, surfacing as ordinary paper records because the harvest did not distinguish them.
- **Semantic Scholar**, the corpus's actual source, exposes `publicationTypes` with the closed
  vocabulary `Review, JournalArticle, CaseReport, ClinicalTrial, Conference, Dataset, Editorial,
  LettersAndComments, MetaAnalysis, News, Study, Book, BookSection`
  ([Academic Graph API](https://api.semanticscholar.org/api-docs/)). Every value observed in
  this corpus is drawn from that list.

Reporting a denominator that mixes research papers with correction notices is also a
reporting-integrity problem, not only an efficiency one: PRISMA 2020 (Page MJ et al., *The
PRISMA 2020 statement: an updated guideline for reporting systematic reviews*, BMJ
2021;372:n71) asks for the number of records screened and excluded **with reasons**. "Not a
research paper — deterministically identified referee report" is a reason that should be
stated and counted, not silently folded into `insufficient_abstract`. Excluding
non-research item types (editorials, comments, letters, errata) at screening is ordinary
practice in evidence synthesis, and the identifiability of those types is precisely why NLM
publishes them as filterable publication types; IA-010 does not claim any particular review's
protocol as its authority for the taxonomy below.

## Taxonomy

`analysis/triage_record_types.py` assigns exactly one type per canonical work:

| type | meaning |
|---|---|
| `research_paper` | the default, and it includes **review articles**, data-descriptor articles and conference papers |
| `peer_review_report` | referee reports, decision letters, author responses to review |
| `erratum_correction` | erratum, corrigendum, correction to, author/publisher correction, addendum |
| `retraction` | retraction notices, retracted items, withdrawals, expressions of concern |
| `editorial_commentary` | editorials, replies, comments/commentaries, correspondence, news items, Q&A interviews |
| `front_back_matter` | tables of contents, indices, front/back matter, mastheads, prefaces, editorial boards |
| `dataset_or_software` | a bare dataset record, *not* a peer-reviewed data descriptor |
| `book_or_chapter` | whole books, proceedings volumes, named book chapters |
| `conference_abstract` | numbered meeting-abstract stubs and abstract collections |
| `unknown_non_paper` | reserved for clearly-not-a-paper records fitting nothing above; no rule currently emits it |

Two taxonomy decisions differ from a naive reading of the publication-type vocabulary, and
both were forced by the data:

- **`Dataset` does not mean `dataset_or_software`.** All five `Dataset` works in this corpus
  are tagged `JournalArticle;Dataset` and are peer-reviewed data-descriptor articles with full
  abstracts. The signal only fires on a bare `Dataset` record with no article type alongside
  it, which yields zero records here. Treating data descriptors as non-papers would have
  removed five genuine papers.
- **`Book` usually means an ACM/LNCS proceedings paper.** Fourteen of the fifteen `Book`-tagged
  works are conference or proceedings papers that also carry `Conference` or `JournalArticle`
  (ACM SIGKDD, CHI, MICCAI workshops). The signal fires only when `Book` appears without either
  of those, which correctly isolates the one real volume, the CNI 2019 workshop proceedings.

## Mechanism

Two independent evidence channels, each recorded explicitly per record so every label is
auditable without rerunning anything.

**Channel 1 — `publication_types`.** `Editorial` and `News` are strong non-paper signals.
`LettersAndComments` is a *weak* signal (see below). `Dataset`, `Book` and `BookSection` are
conditional, firing only in the absence of the blocker types above. `Review`, `Study`,
`MetaAnalysis`, `ClinicalTrial`, `CaseReport` and `Conference` are affirmative claims that the
item is a research article. `JournalArticle` is a **container**, not a content claim: an
erratum is also a `JournalArticle`, so it never counts as evidence either way.

**Channel 2 — anchored title patterns.** Every classifying pattern is anchored at the start of
the normalized title. This is not stylistic. `correction` matched anywhere in a title hits
nineteen works in this corpus, of which fifteen are ordinary methods papers about distortion
correction, motion correction, merge-error correction and topological error correction.
Anchored, the same family matches four correction notices and none of the fifteen. Titles are
NFKC-normalized, curly quotes are folded to straight quotes, and whitespace is collapsed, so
`Review for “X”` and `Review for "X"` match the same rule.

**A review ARTICLE is never a peer-review report.** `Review;JournalArticle` and
`JournalArticle;Review` describe 631 works here and always stay `research_paper`. Only the
anchored `^Review for ["']` form — the shape used by journals that publish referee reports as
separate items — produces `peer_review_report`.

**Combination.** A title anchor is more specific than a coarse source-level publication type
and therefore determines the type when the two disagree; the disagreement is recorded and
demotes confidence. Confidence is three-valued:

- `high` — both channels assert the same type, or an unambiguous title anchor fires with no
  contradiction;
- `medium` — one channel only, or a contradicted `high`;
- `low` — a suggestive anchor with no support, or a doubly-demoted case.

Two demotions apply, and they compose. A record whose `publication_types` asserts a research
article type while the record is being called a non-paper drops one level and is marked
`signals_conflict`. A record classified from title evidence alone, where `publication_types`
is *empty*, also drops one level: 661 of the 4,136 works have no publication types at all, so
title evidence has to be able to stand alone, but standing alone is weaker than standing
supported.

**Two deliberately conservative refusals.**

- `LettersAndComments` never classifies on its own. It corroborates a title anchor and
  otherwise only flags the record. In this corpus it tags *BigDataViewer: visualization and
  processing for large image data sets* — a heavily cited methods paper — as well as
  *Mapping connectomes with diffusion MRI: Deterministic or probabilistic tractography?* and
  *Structural brain networks and functional motor outcome after stroke — a prospective cohort
  study*. A signal that would remove those from the denominator is not usable as an
  independent classifier here, whatever its meaning at NLM.
- An unsupported `Editorial` or `News` signal is **vetoed** by a research article type in the
  same metadata string. `Editorial;Review` describes five works whose titles read like
  substantive reviews (*Visual circuits in arthropod brains*, *What do the mushroom bodies do
  for the insect brain?*). Those stay `research_paper` and are flagged, rather than being
  removed on a contradicted signal.

**Watchlist.** A separate pattern set never classifies and only flags: `proceedings`,
`^special issue`, `^tutorial|^keynote`, `^viewpoint`, `book review`, `^supplement`,
unanchored correction mentions. `^viewpoint` is on this list rather than among the classifying
rules specifically because "viewpoint" is both NLM's own alternate name for a comment and a
common technical prefix (`viewpoint-invariant`, `viewpoint estimation`) in a corpus that
contains computer-vision work.

**Review queue.** `record_type_review_queue.csv` collects the ambiguous middle: any non-paper
below `high` confidence, any conflict, any non-paper carrying a substantial abstract
(`--long-abstract-chars`, default 1500), any paper that had a weak or vetoed non-paper signal,
and any watchlist hit. The queue is a strict subset of `work_record_types.csv` with identical
columns.

## Thresholds are local calibration, not literature constants

Everything numeric or lexical here is a local choice, in the same sense as the IA-008
similarity thresholds and the IA-007 confidence threshold, and should be re-derived rather
than inherited:

- the pattern list is tuned to what this 4,136-work corpus actually contains, and was built by
  reading every candidate match rather than by importing a generic paratext regex set;
- which publication types count as "research", "container", "weak" and "vetoing" is a
  judgement about *Semantic Scholar's* labelling behaviour on *this* corpus, not about the
  vocabulary's formal definitions — `LettersAndComments` is demoted here on the evidence of
  specific false positives, and would not necessarily be demoted elsewhere;
- the 1500-character "substantial abstract" queue trigger is an arbitrary round number chosen
  so that full-text editorials get a human look;
- the three-level confidence scale is an ordering device for triage, not a probability.

The asymmetry is the part that should be inherited, not the constants. Calling a real paper a
non-paper removes it from the denominator; calling a non-paper a paper leaves it in the queue
where IA-007 would have put it anyway. Every ambiguous case therefore resolves toward
`research_paper` plus review.

## Frozen-run result

On `postanalysis/works/canonical_works.csv` (4,136 canonical works):

| record type | works | of which abstract-less |
|---|---|---|
| `research_paper` | 4,086 | 303 |
| `editorial_commentary` | 24 | 4 |
| `peer_review_report` | 10 | 8 |
| `erratum_correction` | 9 | 3 |
| `conference_abstract` | 4 | 0 |
| `book_or_chapter` | 3 | 3 |
| **total** | **4,136** | **321** |

`4,136 canonical works = 4,086 research papers + 50 non-paper records.`

By source group: `core_audit` 1,653 papers + 25 non-papers; `unresolved` 2,038 papers + 24
non-papers; `role_bridge` 395 papers + 1 non-paper. The 25 non-papers inside `core_audit` are
worth noting on their own — errata and author responses inherited the core label from the
paper they attach to, which is an IA-004 noise finding that the IA-007 `core_noise_audit`
queue would otherwise have had to rediscover semantically.

Of the 321 abstract-less works, **18 are non-papers** and 303 remain genuine papers awaiting
full-text review. So the deterministic pass removes about 5.6% of the abstract-less human
queue at zero adjudication cost, and — more importantly — it names *why* those 18 have no
abstract.

The review queue holds 66 rows: 46 non-papers awaiting confirmation and 20 papers flagged for
a second look (5 vetoed `Editorial;Review` works, 9 `LettersAndComments` works, 6 watchlist
titles).

## Applying it without disturbing the screen

The IA-007/IA-009 adjudication runs against the full 4,136-work denominator and stays that
way. `analysis/apply_record_type_partition.py` partitions a completed
`llm_relevance_results.csv` after the fact into a paper view and a non-paper view, reports
both denominators, and lifts non-paper records out of the human queue into their own queue.
It asserts that every input row lands in exactly one partition, and a work with no
record-type row is kept as a paper: the partition may only leave the paper denominator on
positive, recorded evidence.

## Reproducibility

```bash
python analysis/triage_record_types.py \
  --works-csv postanalysis/works/canonical_works.csv \
  --out postanalysis/record_types \
  --expected-works 4136

python analysis/apply_record_type_partition.py \
  --results-csv postanalysis/llm_agent/llm_relevance_results.csv \
  --record-types-csv postanalysis/record_types/work_record_types.csv \
  --queue-csv postanalysis/llm_agent/human_review_queue.csv \
  --out postanalysis/record_types/partition_agent \
  --label agent

python analysis/test_triage_record_types.py
```

Both tools refuse to write into an input directory, and the triage hashes its input CSV before
and after the run and fails if it changed. Output is byte-identical on rerun: the rules are
pure functions of one record, there is no sampling, no ordering dependence and no network.
`work_record_types.csv` records, per work, the firing title rule and its matched substring, the
firing publication-type token, any vetoed or weak token, any research-article token, the
conflict flag, the watchlist hits and the resulting confidence, so a label can be audited from
the row alone. `record_type_summary.json` records the input path and SHA-256, the counts by
type and by source group × type, the signal provenance, the abstract-less breakdown, and both
denominators side by side.

The taxonomy is a reporting label. No `keep`, core, bridge, work-link or abstract status is
mutated by either tool, and the 4,136-work retrieval provenance stands.
