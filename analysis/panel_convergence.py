#!/usr/bin/env python3
"""IA-015 Step 3a/3c: panel backward-convergence and diagnostics.

Reads the frozen probe panel and retrieves each probe member's full
reference list, then reports:

  - convergence candidates cited by panel members from >=2 distinct clusters
    (candidate sets reported at k=2 and k=3; k = distinct clusters);
  - P9 (Abbott 2020) corroboration marks (descriptive only, never a
    threshold input);
  - 3c diagnostics: unique-find counts (flagged by convergence, retrieved by
    NO frozen route) and the lexicon-gap alarm (cited by >=4 distinct
    clusters yet absent from frozen discovery).

Reference-list sources, in fallback order per panel member (some publishers
elide reference lists from Semantic Scholar):

  1. Semantic Scholar `/references` (S2 paper IDs join the frozen discovery
     log exactly);
  2. OpenAlex `referenced_works` (the execution spec's designated source);
  3. Crossref deposited references.

The source actually used is recorded per member in the audit output.
Cited works are keyed canonically by DOI where available, else S2 ID, else
normalized title; corpus joins use S2-ID exact match, DOI match, and
normalized-title match against the frozen screening log, in that order.

Step 3b (ultracore seed-neighborhood expansion) is GATED: it runs only if a
frozen seed artifact exists at
postanalysis/review_pool/ultracore_seeds_frozen.json and passes the
mutual-exclusivity check. No such artifact has been designated; this script
records the gate status and does not run 3b.

Convergence output is DISCOVERY ONLY (route `panel-convergence (b)`).
Nothing here mutates the frozen corpus, screening decisions, or overlays.

Outputs under postanalysis/review_pool/convergence/:
  panel_convergence_candidates.csv   all k>=2 candidates with corpus status
  panel_reference_lists.json         per-member cited-work keys + source (audit)
  convergence_diagnostics.json       3c diagnostics + 3b gate status
  PANEL_CONVERGENCE.md               human-readable summary
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL_DIR = REPO / "postanalysis" / "review_pool"
OUT_DIR = POOL_DIR / "convergence"
PANEL_JSON = POOL_DIR / "probe_panel_frozen.json"
SEED_ARTIFACT = POOL_DIR / "ultracore_seeds_frozen.json"

OUTPUTS = REPO / "source_artifact" / "connectomics_deterministic_pipeline" / "outputs"
SCREENING_LOG = OUTPUTS / "screening_log.csv"
RETAINED_CSV = OUTPUTS / "papers_retained.csv"
ENRICHED_CSV = REPO / "postanalysis" / "enriched2" / "canonical_works_enriched_pass2.csv"
FULL_WORKS_CSV = REPO / "postanalysis" / "llm_agent_v3" / "corpus_full_works.csv"
SEEDS_CSV = REPO / "postanalysis" / "works" / "manual_seed_works.csv"

S2_BASE = "https://api.semanticscholar.org/graph/v1"
S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")  # never printed or logged
MIN_INTERVAL_S = 1.5
_last = {"t": 0.0}
# Optional response cache (directory path via env); keeps re-runs off the API.
CACHE_DIR = os.environ.get("IA015_CACHE_DIR")


def _cache_path(name: str) -> Path | None:
    if not CACHE_DIR:
        return None
    p = Path(CACHE_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p / (re.sub(r"[^A-Za-z0-9_.-]", "_", name) + ".json")


def _get(url: str, tries: int = 8, backoff: float = 15.0) -> dict | None:
    for attempt in range(tries):
        wait = MIN_INTERVAL_S - (time.time() - _last["t"])
        if wait > 0:
            time.sleep(wait)
        headers = {"User-Agent": "connectomics-survey-IA015"}
        if S2_API_KEY and url.startswith(S2_BASE):
            headers["x-api-key"] = S2_API_KEY
        req = urllib.request.Request(url, headers=headers)
        _last["t"] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(backoff * (1.4**attempt))
                continue
            if e.code in (403, 404):
                return None
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < tries - 1:
                time.sleep(backoff)
                continue
            raise
    return None


def _post(url: str, payload: dict, tries: int = 6, backoff: float = 15.0) -> dict | list | None:
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(tries):
        wait = MIN_INTERVAL_S - (time.time() - _last["t"])
        if wait > 0:
            time.sleep(wait)
        headers = {"User-Agent": "connectomics-survey-IA015", "Content-Type": "application/json"}
        if S2_API_KEY and url.startswith(S2_BASE):
            headers["x-api-key"] = S2_API_KEY
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        _last["t"] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(backoff * (1.4**attempt))
                continue
            if e.code in (400, 403, 404):
                return None
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < tries - 1:
                time.sleep(backoff)
                continue
            raise
    return None


def _norm_title(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t or "")
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def _norm_doi(d: str | None) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return d


# --- reference-list backends ------------------------------------------------


def refs_s2(paper_id: str) -> list[dict] | None:
    fields = "paperId,externalIds,title,year,venue,citationCount"
    out, offset = [], 0
    while True:
        data = _get(
            f"{S2_BASE}/paper/{paper_id}/references?fields={fields}&limit=500&offset={offset}"
        )
        if not data:
            break
        rows = data.get("data") or []
        for row in rows:
            cited = row.get("citedPaper") or {}
            if cited.get("paperId"):
                out.append(
                    {
                        "s2_paper_id": cited["paperId"],
                        "doi": _norm_doi((cited.get("externalIds") or {}).get("DOI")),
                        "title": cited.get("title") or "",
                        "year": cited.get("year"),
                        "venue": cited.get("venue") or "",
                        "citation_count": cited.get("citationCount"),
                    }
                )
        nxt = data.get("next")
        if nxt is None or not rows:
            break
        offset = nxt
    return out or None  # publisher-elided lists come back empty


def refs_openalex(openalex_id: str) -> list[dict] | None:
    if not openalex_id:
        return None
    try:
        work = _get(
            f"https://api.openalex.org/works/{openalex_id}?select=referenced_works",
            tries=2,
        )
    except urllib.error.HTTPError:
        return None
    ids = [w.rsplit("/", 1)[-1] for w in (work or {}).get("referenced_works", [])]
    if not ids:
        return None
    out = []
    for i in range(0, len(ids), 50):
        batch = "|".join(ids[i : i + 50])
        try:
            data = _get(
                "https://api.openalex.org/works?filter=openalex_id:"
                + batch
                + "&select=id,doi,title,publication_year,cited_by_count&per-page=50",
                tries=3,
            )
        except urllib.error.HTTPError:
            return None
        for w in (data or {}).get("results", []):
            out.append(
                {
                    "s2_paper_id": "",
                    "openalex_id": w["id"].rsplit("/", 1)[-1],
                    "doi": _norm_doi(w.get("doi")),
                    "title": w.get("title") or "",
                    "year": w.get("publication_year"),
                    "venue": "",
                    "citation_count": w.get("cited_by_count"),
                }
            )
    return out or None


def refs_crossref(doi: str) -> list[dict] | None:
    data = _get("https://api.crossref.org/works/" + urllib.parse.quote(doi))
    refs = (data or {}).get("message", {}).get("reference", [])
    out = []
    for r in refs:
        title = r.get("article-title") or r.get("volume-title") or ""
        if not title and r.get("unstructured"):
            title = r["unstructured"]
        out.append(
            {
                "s2_paper_id": "",
                "doi": _norm_doi(r.get("DOI")),
                "title": title,
                "year": r.get("year"),
                "venue": r.get("journal-title") or "",
                "citation_count": None,
            }
        )
    return out or None


def fetch_references(member: dict) -> tuple[list[dict], str]:
    cp = _cache_path("refs_" + member["panel_id"] + "_" + member["s2_paper_id"])
    if cp and cp.exists():
        cached = json.loads(cp.read_text(encoding="utf-8"))
        return cached["refs"], cached["source"] + " (cached)"
    refs = refs_s2(member["s2_paper_id"])
    source = "semantic_scholar" if refs else None
    if not refs:
        refs = refs_openalex(member.get("openalex_id") or "")
        source = "openalex" if refs else None
    if not refs:
        refs = refs_crossref(member["doi"])
        source = "crossref" if refs else None
    if refs and cp:
        cp.write_text(json.dumps({"refs": refs, "source": source}), encoding="utf-8")
    return refs or [], source or "none"


def canonical_key(ref: dict) -> str | None:
    if ref.get("doi"):
        return "doi:" + ref["doi"]
    if ref.get("s2_paper_id"):
        return "s2:" + ref["s2_paper_id"]
    nt = _norm_title(ref.get("title", ""))
    return "t:" + nt if nt else None


# --- frozen-corpus indexes --------------------------------------------------


def load_indexes():
    screened_ids = {}
    screened_titles = {}
    with SCREENING_LOG.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = row["paper_id"]
            keep = row.get("keep")
            if screened_ids.get(pid) != "True":
                screened_ids[pid] = keep
            nt = _norm_title(row.get("title", ""))
            if nt and screened_titles.get(nt) != "True":
                screened_titles[nt] = keep
    retained_ids, retained_dois = set(), set()
    with RETAINED_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            retained_ids.add(row["paper_id"])
            d = _norm_doi(row.get("doi"))
            if d:
                retained_dois.add(d)
    pid2work, doi2work = {}, {}
    with ENRICHED_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            wid = row["work_id"]
            for pid in (row.get("member_paper_ids") or "").split(";"):
                if pid.strip():
                    pid2work[pid.strip()] = wid
            for d in (row.get("member_dois") or "").split(";"):
                d = _norm_doi(d)
                if d:
                    doi2work[d] = wid
            d = _norm_doi(row.get("doi"))
            if d:
                doi2work[d] = wid
    # Manual-seed works live outside the enriched works table but are part
    # of the working corpus; include their ID mappings.
    with SEEDS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            wid = row["work_id"]
            if row.get("canonical_paper_id"):
                pid2work[row["canonical_paper_id"]] = wid
            d = _norm_doi(row.get("doi"))
            if d:
                doi2work[d] = wid
    work_decision = {}
    with FULL_WORKS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            work_decision[row["work_id"]] = row["decision"]
    return screened_ids, screened_titles, retained_ids, retained_dois, pid2work, doi2work, work_decision


def main() -> int:
    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    panel = json.loads(PANEL_JSON.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    probes = [m for m in panel["members"] if m["probe"] and not m["confirmation_only"]]
    p9_members = [m for m in panel["members"] if m["confirmation_only"]]

    (screened_ids, screened_titles, retained_ids, retained_dois,
     pid2work, doi2work, work_decision) = load_indexes()
    print(
        f"indexes: {len(screened_ids)} discovered IDs, {len(retained_ids)} retained, "
        f"{len(pid2work)} work-member IDs, {len(work_decision)} working-corpus works"
    )

    ref_meta: dict[str, dict] = {}
    member_refs: dict[str, set[str]] = {}
    member_source: dict[str, str] = {}
    for m in probes + p9_members:
        refs, source = fetch_references(m)
        keys = set()
        for r in refs:
            k = canonical_key(r)
            if not k:
                continue
            keys.add(k)
            prev = ref_meta.get(k)
            if prev is None or (not prev.get("s2_paper_id") and r.get("s2_paper_id")):
                merged = dict(prev or {})
                merged.update({kk: vv for kk, vv in r.items() if vv not in (None, "")})
                ref_meta[k] = merged
        member_refs[m["panel_id"]] = keys
        member_source[m["panel_id"]] = source
        print(f"{m['panel_id']} ({m['cluster']}): {len(keys)} unique refs via {source}")

    p9_cited = set()
    for m in p9_members:
        p9_cited |= member_refs.get(m["panel_id"], set())

    by_member = defaultdict(set)
    by_cluster = defaultdict(set)
    for m in probes:  # P9 never counts toward convergence
        for k in member_refs[m["panel_id"]]:
            by_member[k].add(m["panel_id"])
            by_cluster[k].add(m["cluster"])

    # Crossref-sourced references carry unstructured citation strings, not
    # clean titles, and no S2 ID; resolve candidate DOIs through the S2 batch
    # endpoint so corpus joins use real IDs/titles before novelty is claimed.
    unresolved = [
        k for k, clusters in by_cluster.items()
        if len(clusters) >= 2
        and k.startswith("doi:")
        and not ref_meta.get(k, {}).get("s2_paper_id")
    ]
    for i in range(0, len(unresolved), 100):
        chunk = unresolved[i : i + 100]
        resp = _post(
            f"{S2_BASE}/paper/batch?fields=paperId,externalIds,title,year,venue,citationCount",
            {"ids": ["DOI:" + k[4:] for k in chunk]},
        )
        for k, item in zip(chunk, resp or []):
            if not item or not item.get("paperId"):
                continue
            ref_meta[k].update(
                {
                    "s2_paper_id": item["paperId"],
                    "title": item.get("title") or ref_meta[k].get("title", ""),
                    "year": item.get("year") or ref_meta[k].get("year"),
                    "venue": item.get("venue") or ref_meta[k].get("venue", ""),
                    "citation_count": item.get("citationCount"),
                }
            )
    still = [k for k in unresolved if not ref_meta[k].get("s2_paper_id")]
    if unresolved:
        print(f"batch-resolved {len(unresolved) - len(still)}/{len(unresolved)} candidate DOIs via S2")
    # S2 lacks DOI mappings for a few works; take clean titles from Crossref
    # so the normalized-title join against the frozen screening log can apply.
    for k in still:
        data = _get("https://api.crossref.org/works/" + urllib.parse.quote(k[4:]))
        m = (data or {}).get("message", {})
        title = (m.get("title") or [""])[0]
        if title:
            ref_meta[k]["title"] = title
            yr = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
            if yr:
                ref_meta[k]["year"] = yr
    if still:
        print(f"crossref-title fallback for {len(still)} candidates")

    panel_keys = set()
    for m in panel["members"]:
        panel_keys.add("doi:" + _norm_doi(m["doi"]))
        panel_keys.add("s2:" + m["s2_paper_id"])

    def corpus_status(meta: dict) -> dict:
        pid = meta.get("s2_paper_id") or ""
        doi = meta.get("doi") or ""
        nt = _norm_title(meta.get("title", ""))
        in_disc, keep, match = False, "", ""
        if pid and pid in screened_ids:
            in_disc, keep, match = True, screened_ids[pid], "s2_id"
        elif doi and doi in retained_dois:
            in_disc, keep, match = True, "True", "doi_retained"
        elif nt and nt in screened_titles:
            in_disc, keep, match = True, screened_titles[nt], "title"
        wid = pid2work.get(pid) or doi2work.get(doi) or ""
        return {
            "in_frozen_discovery": in_disc,
            "frozen_keep": keep or "",
            "discovery_match_method": match,
            "in_frozen_retained": (pid in retained_ids) or (doi in retained_dois),
            "work_id": wid,
            "working_corpus_decision": work_decision.get(wid, "") if wid else "",
        }

    candidates = []
    for k, clusters in by_cluster.items():
        if len(clusters) < 2 or k in panel_keys:
            continue
        meta = ref_meta.get(k, {})
        row = {
            "canonical_key": k,
            "s2_paper_id": meta.get("s2_paper_id", ""),
            "doi": meta.get("doi", ""),
            "title": meta.get("title", ""),
            "year": meta.get("year") or "",
            "venue": meta.get("venue", ""),
            "citation_count": meta.get("citation_count"),
            "n_panel_members": len(by_member[k]),
            "n_clusters": len(clusters),
            "panel_members": ";".join(sorted(by_member[k])),
            "clusters": ";".join(sorted(clusters)),
            "abbott_corroborated": k in p9_cited,
            "provenance_route": "panel-convergence (b)",
        }
        row.update(corpus_status(meta))
        candidates.append(row)
    candidates.sort(
        key=lambda c: (-c["n_clusters"], -c["n_panel_members"], -(c["citation_count"] or 0))
    )

    k2 = candidates
    k3 = [c for c in candidates if c["n_clusters"] >= 3]
    unique_finds = [c for c in k2 if not c["in_frozen_discovery"]]
    lexicon_gap = [c for c in k2 if c["n_clusters"] >= 4 and not c["in_frozen_discovery"]]
    not_in_working = [
        c for c in k2 if c["in_frozen_discovery"] and not c["working_corpus_decision"]
    ]

    cand_path = OUT_DIR / "panel_convergence_candidates.csv"
    with cand_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(k2[0].keys()) if k2 else ["canonical_key"])
        w.writeheader()
        w.writerows(k2)

    (OUT_DIR / "panel_reference_lists.json").write_text(
        json.dumps(
            {
                "generated_at": run_ts,
                "panel_sha256": (POOL_DIR / "probe_panel_frozen.sha256").read_text().strip(),
                "reference_list_source_per_member": member_source,
                "reference_lists": {k: sorted(v) for k, v in member_refs.items()},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    diagnostics = {
        "generated_at": run_ts,
        "step_3a": {
            "probe_members": len(probes),
            "reference_list_source_per_member": member_source,
            "total_distinct_cited_works": len(by_cluster),
            "candidates_k2": len(k2),
            "candidates_k3": len(k3),
            "abbott_corroborated_among_k2": sum(1 for c in k2 if c["abbott_corroborated"]),
        },
        "step_3b": {
            "ran": False,
            "gate": (
                "no ultracore seed artifact designated "
                f"({SEED_ARTIFACT.name} absent); designation is a screener "
                "decision (IA-015 open item), and the mutual-exclusivity "
                "check against held-out validation sets must pass before any run."
            ),
        },
        "step_3c": {
            "unique_find_count": len(unique_finds),
            "unique_find_note": (
                "candidates flagged by convergence and absent from the frozen "
                "discovery log (S2-ID exact join, then DOI, then normalized "
                "title); this is the operator's marginal discovery value."
            ),
            "unique_find_items": [
                {kk: c[kk] for kk in ("canonical_key", "doi", "title", "year", "n_clusters", "clusters")}
                for c in unique_finds
            ],
            "lexicon_gap_alarm_count": len(lexicon_gap),
            "lexicon_gap_rule": ">=4 distinct clusters and not retrieved by frozen searches",
            "lexicon_gap_items": [
                {kk: c[kk] for kk in ("canonical_key", "doi", "title", "year", "n_clusters")}
                for c in lexicon_gap
            ],
            "discovered_but_not_in_working_corpus": len(not_in_working),
            "seed_lineage_limitation": (
                "convergence finds the panel's lineage - ancestors, descendants, "
                "peers, parallel work. It systematically misses important work "
                "disconnected from that lineage (sparse-coupling infrastructure, "
                "very recent work, untouched subfields). It supplements the "
                "term/institutional/date routes; it substitutes for none."
            ),
        },
        "discovery_only": (
            "No convergence statistic is evidence; every candidate requires "
            "normal screening, verification, and inclusion decisions."
        ),
    }
    (OUT_DIR / "convergence_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Panel backward-convergence (IA-015 Step 3a/3c)",
        "",
        f"Generated {run_ts}. Panel SHA-256: `{(POOL_DIR / 'probe_panel_frozen.sha256').read_text().strip()}`.",
        "",
        "Discovery only (route `panel-convergence (b)`); never evidence. P9 marks are descriptive corroboration.",
        "",
        "Reference-list source per member: "
        + ", ".join(f"{k}={v}" for k, v in sorted(member_source.items())),
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Probe members (P1-P8) | {len(probes)} |",
        f"| Distinct cited works across probes | {len(by_cluster)} |",
        f"| Candidates, >=2 clusters (k=2) | {len(k2)} |",
        f"| Candidates, >=3 clusters (k=3) | {len(k3)} |",
        f"| P9-corroborated among k=2 | {diagnostics['step_3a']['abbott_corroborated_among_k2']} |",
        f"| Unique finds (not in frozen discovery) | {len(unique_finds)} |",
        f"| Lexicon-gap alarms (>=4 clusters, undiscovered) | {len(lexicon_gap)} |",
        f"| Discovered but absent from working corpus | {len(not_in_working)} |",
        "",
        "## Candidates at k=3 (>=3 distinct clusters)",
        "",
        "| Clusters | Members | P9 | In discovery | Working-corpus decision | Year | Title |",
        "|---:|---|:--:|:--:|---|---:|---|",
    ]
    for c in k3:
        lines.append(
            f"| {c['n_clusters']} | {c['panel_members']} | "
            f"{'yes' if c['abbott_corroborated'] else ''} | "
            f"{'yes' if c['in_frozen_discovery'] else 'NO'} | "
            f"{c['working_corpus_decision'] or '-'} | {c['year']} | {c['title'][:90]} |"
        )
    lines += [
        "",
        "## Step 3b (seed-neighborhood expansion)",
        "",
        f"NOT RUN - {diagnostics['step_3b']['gate']}",
        "",
        "## Seed-lineage limitation",
        "",
        diagnostics["step_3c"]["seed_lineage_limitation"],
        "",
    ]
    (OUT_DIR / "PANEL_CONVERGENCE.md").write_text("\n".join(lines), encoding="utf-8")

    print(
        f"k2={len(k2)} k3={len(k3)} unique={len(unique_finds)} "
        f"lexicon_gap={len(lexicon_gap)} not_in_working={len(not_in_working)}"
    )
    print(f"wrote {cand_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
