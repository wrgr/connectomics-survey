#!/usr/bin/env python3
"""Protocol v4 §5.2: derive the review pool of record from zero.

Executes the written bootstrap procedure — four anchor searches (A1–A4) in
PubMed (Review[pt]) and OpenAlex (type:review), plus the rule-based
dedicated-review-venue supplement in OpenAlex — with §19 logging, dedup, and
a diff against the exploratory pool.

Resumable: every query's raw response is cached under IA015_CACHE_DIR (or a
local .cache dir); a budget-exhausted OpenAlex query marks the run
`incomplete` and re-running later finishes only what is missing. The pool of
record is only written when every query is complete.

Outputs under postanalysis/review_pool/:
  review_pool_v2.json      pool of record (only when complete)
  derivation_log_v2.json   per-query source/query/date/count + completeness
  pool_v1_v2_diff.json     exploratory-vs-procedure diff (only when complete)
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL_DIR = REPO / "postanalysis" / "review_pool"
EXPLORATORY = POOL_DIR / "bootstrap_2026-08-25" / "review_pool.json"
CACHE = Path(os.environ.get("IA015_CACHE_DIR", str(POOL_DIR / ".cache_v2")))
CACHE.mkdir(parents=True, exist_ok=True)

ANCHORS = {
    "A1": {
        "pm": "(connectome*[tiab] OR connectomic*[tiab]) AND Review[pt]",
        "oa": "connectome OR connectomics OR connectomic",
    },
    "A2": {
        "pm": '("serial section"[tiab] OR "serial sections"[tiab] OR "serial-section"[tiab]) AND "electron microscopy"[tiab] AND Review[pt]',
        "oa": '"serial section" "electron microscopy"',
    },
    "A3": {
        "pm": '("volume electron microscopy"[tiab] OR "volume EM"[tiab]) AND Review[pt]',
        "oa": '"volume electron microscopy" OR "volume EM"',
    },
    "A4": {
        "pm": '("dense reconstruction"[tiab] OR "saturated reconstruction"[tiab]) AND Review[pt]',
        "oa": '"dense reconstruction" OR "saturated reconstruction"',
    },
}
# Dedicated-review-venue name rule (§5.2 step 2).
VENUE_FAMILIES = [
    "nature reviews",
    "annual review of",
    "current opinion in",
    "trends in",
    "physiological reviews",
]

_last = {"t": 0.0}


def _get(url: str, min_interval: float, tries: int = 5, backoff: float = 10.0):
    for attempt in range(tries):
        wait = min_interval - (time.time() - _last["t"])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": "connectomics-survey-v4-5.2"})
        _last["t"] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")[:200]
            except Exception:
                pass
            if e.code == 429 and "budget" in body.lower():
                raise BudgetExhausted(body)
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(backoff * (1.5**attempt))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < tries - 1:
                time.sleep(backoff)
                continue
            raise


class BudgetExhausted(Exception):
    pass


def cached(name: str, fn):
    p = CACHE / (re.sub(r"[^A-Za-z0-9_.-]", "_", name) + ".json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")), True
    data = fn()
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data, False


def _norm_doi(d):
    d = (d or "").strip().lower()
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", d)


def _norm_title(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


# --- PubMed ---------------------------------------------------------------

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def pubmed_search(query: str) -> list[str]:
    ids, retstart = [], 0
    while True:
        url = (
            f"{EUTILS}/esearch.fcgi?db=pubmed&retmode=json&retmax=500"
            f"&retstart={retstart}&term=" + urllib.parse.quote(query)
        )
        data = _get(url, 0.5)
        r = data["esearchresult"]
        ids += r.get("idlist", [])
        if retstart + 500 >= int(r["count"]):
            return ids
        retstart += 500


def pubmed_summaries(pmids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(pmids), 200):
        chunk = pmids[i : i + 200]
        url = f"{EUTILS}/esummary.fcgi?db=pubmed&retmode=json&id=" + ",".join(chunk)
        data = _get(url, 0.5)
        for pid in chunk:
            m = data.get("result", {}).get(pid)
            if not m:
                continue
            doi = ""
            for aid in m.get("articleids", []):
                if aid.get("idtype") == "doi":
                    doi = _norm_doi(aid.get("value"))
            out[pid] = {
                "pmid": pid,
                "doi": doi,
                "title": m.get("title", ""),
                "venue": m.get("fulljournalname", ""),
                "year": int(m["pubdate"][:4]) if m.get("pubdate", "")[:4].isdigit() else None,
            }
    return out


# --- OpenAlex -------------------------------------------------------------


def openalex_query(filt: str) -> list[dict]:
    out, cursor = [], "*"
    while True:
        url = (
            "https://api.openalex.org/works?filter=" + filt
            + "&per-page=200&cursor=" + urllib.parse.quote(cursor)
            + "&select=id,doi,title,display_name,publication_year,cited_by_count,primary_location,type"
        )
        data = _get(url, 1.2)
        for w in data.get("results", []):
            src = ((w.get("primary_location") or {}).get("source") or {})
            out.append(
                {
                    "oa_id": w["id"].rsplit("/", 1)[-1],
                    "doi": _norm_doi(w.get("doi")),
                    "title": w.get("title") or w.get("display_name") or "",
                    "venue": src.get("display_name") or "",
                    "year": w.get("publication_year"),
                    "cites": w.get("cited_by_count"),
                }
            )
        cursor = (data.get("meta") or {}).get("next_cursor")
        if not cursor:
            return out


def venue_matches_rule(venue: str) -> bool:
    v = (venue or "").lower()
    return any(v.startswith(f) or (f in v and f == "nature reviews") for f in VENUE_FAMILIES)


# --- main -----------------------------------------------------------------


def main() -> int:
    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log = {"procedure": "v4 §5.2", "run_started": run_ts, "queries": [], "complete": True}
    records = {}  # key -> record with routes

    def add(rec, route):
        key = rec.get("doi") or (("pmid:" + rec["pmid"]) if rec.get("pmid") else None) or ("t:" + _norm_title(rec["title"]))
        if not key or not rec.get("title"):
            return
        r = records.setdefault(key, {**rec, "routes": []})
        if route not in r["routes"]:
            r["routes"].append(route)
        for f in ("doi", "pmid", "oa_id", "cites", "year", "venue"):
            if not r.get(f) and rec.get(f):
                r[f] = rec[f]

    # PubMed anchors
    for aid, q in ANCHORS.items():
        ids, was_cached = cached(f"pm_{aid}", lambda q=q: pubmed_search(q["pm"]))
        log["queries"].append(
            {"source": "pubmed", "query": q["pm"], "route": f"PMv2-{aid}",
             "date": run_ts, "count": len(ids), "cached": was_cached, "status": "complete"}
        )
        sums, _ = cached(f"pm_{aid}_summaries", lambda ids=ids: pubmed_summaries(ids))
        for rec in sums.values():
            add(rec, f"PMv2-{aid}")
        print(f"PMv2-{aid}: {len(ids)} records")

    # OpenAlex anchors (typed review) + venue-rule supplement
    oa_jobs = []
    for aid, q in ANCHORS.items():
        oa_jobs.append((f"OAv2-{aid}",
                        "title_and_abstract.search:" + urllib.parse.quote(q["oa"]) + ",type:review", None))
    for aid, q in ANCHORS.items():
        for vf in VENUE_FAMILIES:
            oa_jobs.append((f"OAv2-{aid}-venue:{vf}",
                            "title_and_abstract.search:" + urllib.parse.quote(q["oa"])
                            + ",primary_location.source.display_name.search:" + urllib.parse.quote(vf),
                            vf))
    for route, filt, vf in oa_jobs:
        try:
            rows, was_cached = cached(route, lambda filt=filt: openalex_query(filt))
        except BudgetExhausted:
            log["queries"].append({"source": "openalex", "filter": filt, "route": route,
                                   "date": run_ts, "status": "PENDING (budget exhausted)"})
            log["complete"] = False
            print(f"{route}: budget exhausted; pending")
            continue
        if vf:
            rows = [r for r in rows if venue_matches_rule(r["venue"])]
        log["queries"].append({"source": "openalex", "filter": filt, "route": route,
                               "date": run_ts, "count": len(rows), "cached": was_cached, "status": "complete"})
        for rec in rows:
            add(rec, route)
        print(f"{route}: {len(rows)} records")

    (POOL_DIR / "derivation_log_v2.json").write_text(
        json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not log["complete"]:
        print("\nRUN INCOMPLETE (OpenAlex budget). Re-run after reset; cached queries are kept.")
        return 2

    # Merge on DOI where a title-keyed record gains one
    pool = {}
    for r in records.values():
        key = r.get("doi") or ("pmid:" + r["pmid"] if r.get("pmid") else "t:" + _norm_title(r["title"]))
        if key in pool:
            for route in r["routes"]:
                if route not in pool[key]["routes"]:
                    pool[key]["routes"].append(route)
        else:
            pool[key] = r
    out = {
        "artifact": "review_pool_v2.json",
        "procedure": "connectomics_bibliography_methodology_v4.md §5.2",
        "derived_at": run_ts,
        "note": "Pool of record. Exploratory pool retained at bootstrap_2026-08-25/. Selection (§5.2) happens downstream; retrieval purity is provenance, not noise-freedom.",
        "records": pool,
    }
    (POOL_DIR / "review_pool_v2.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    # Diff vs exploratory pool
    old = json.load(EXPLORATORY.open())
    old_keys = {(_norm_doi(k) or "t:" + _norm_title(v.get("title", ""))): v for k, v in old.items()}
    new_dois = {k for k in pool if not k.startswith(("pmid:", "t:"))}
    old_dois = {k for k in old_keys if not k.startswith("t:")}
    only_new = sorted(new_dois - old_dois)
    only_old = sorted(old_dois - new_dois)
    diff = {
        "generated_at": run_ts,
        "v2_records": len(pool),
        "v1_records": len(old),
        "doi_overlap": len(new_dois & old_dois),
        "v2_only_count": len(only_new),
        "v1_only_count": len(only_old),
        "v2_only_dois": only_new,
        "v1_only_sample_by_route": {},
    }
    from collections import Counter
    route_counter = Counter()
    for k in only_old:
        for rt in old_keys[k].get("routes", []):
            route_counter[rt] += 1
    diff["v1_only_by_route"] = dict(route_counter.most_common())
    (POOL_DIR / "pool_v1_v2_diff.json").write_text(
        json.dumps(diff, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\npool v2: {len(pool)} records | overlap {diff['doi_overlap']} | "
          f"v2-only {len(only_new)} | v1-only {len(only_old)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
