# IA-011 — Second-pass abstract recovery

## Status

Derived enrichment after IA-008 pass one. It does not mutate `postanalysis/enriched/` (pass-one outputs remain the immutable baseline). Results live in `postanalysis/enriched2/`.

## Why a second pass

Pass one left **153** canonical works without abstracts. Two implementation gaps caused recoverable misses:

1. **OpenAlex was never queried.** Pass one gated OpenAlex behind `OPENALEX_API_KEY`. OpenAlex does not require a key; polite use is a `mailto=` parameter. Unkeyed OpenAlex recovered the majority of pass-two fills.
2. **No title-based fallback.** **55** residual works had neither DOI nor PMID, so Europe PMC/Crossref identifier lookups never ran.

IA-010 further showed **18/153** residuals are non-papers (peer-review reports, errata, editorials, book chapters). Those are often structurally abstract-less; the real target is the **135** research papers.

## Mechanism

`analysis/rescue_abstracts_pass2.py` targets only works still missing abstracts after pass one:

1. internal `papers_all.csv` mining (DOI, then normalized title + year/author corroboration);
2. OpenAlex unkeyed (DOI → PMID → title search);
3. Semantic Scholar by DOI/title;
4. Europe PMC / Crossref title search;
5. PubMed `efetch` for PMIDs;
6. DataCite descriptions for figshare-like DOIs;
7. optional `web_findings.json` ingest — prefer recovered DOI/PMID, then re-query structured APIs; page-scraped text only as a labelled last resort.

Title similarity floor **0.92** is a local calibration choice. Title and web fills land in `title_match_review_queue.csv`. Progress streams to `pass2_progress.jsonl` (resumable; compatible with `watch_progress.py`).

## Frozen-run outcome

| | count |
|---|---|
| Residual after pass one | 153 |
| Pass-two rescued | **75** |
| Still missing | 78 |
| Of which research papers | 68 |
| Of which non-papers | 10 |

Sources among the 75: OpenAlex 60, web_identifier 7, Semantic Scholar 3, web_page 2, Crossref 1, Europe PMC 1, internal corpus 1.

Cumulative: **321 → 168 (pass one) → 75 (pass two) → 78 still missing**, of which **68** are research papers awaiting title/abstract screening as `insufficient_abstract` unless later enrichment succeeds.

## Honesty

Wrong abstracts are worse than gaps. Web-derived page text is labelled `web_page` and queued. Many remaining DOIs are Springer/Elsevier/IEEE book chapters or comments with no deposited abstract anywhere — further chasing has diminishing return relative to adjudication.
