#!/usr/bin/env python3
"""Resolve S2-elided reference lists via keyed OpenAlex (exploration §A.3/.6).

Targets: unmatched works still unresolved after the S2 batch pass, plus the
deferred recent works. For each, fetch `referenced_works` from OpenAlex,
resolve referenced W-ids to DOIs (globally cached across works), and count
verified outbound links into the corpus. Same disposition rules as before:
>=1 verified link -> resolved-linked; verified zero -> drop (pre-2024) or
defer (>=2024); no record / no refs served -> unresolved.

Key from OPENALEX_API_KEY (never logged). Output:
postanalysis/registry/exploration_oa_ref_resolution.csv
"""

from __future__ import annotations

import csv
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
REG = REPO / "postanalysis" / "registry"
ENRICHED = REPO / "postanalysis" / "enriched2" / "canonical_works_enriched_pass2.csv"
KEY = os.environ["OPENALEX_API_KEY"]
_last = {"t": 0.0}


def _get(url, tries=6, backoff=15.0):
    for a in range(tries):
        w = 1.1 - (time.time() - _last["t"])
        if w > 0:
            time.sleep(w)
        _last["t"] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url + ("&" if "?" in url else "?") + "api_key=" + KEY,
                    headers={"User-Agent": "connectomics-survey"}), timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and a < tries - 1:
                time.sleep(backoff * (1.4**a))
                continue
            if e.code == 404:
                return None
            raise
        except (urllib.error.URLError, TimeoutError):
            if a < tries - 1:
                time.sleep(backoff)
                continue
            raise


def nd(d):
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", (d or "").strip().lower())


def main():
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    corpus_dois = set()
    id2doi = {}
    for r in csv.DictReader(ENRICHED.open()):
        for d in ((r.get("member_dois") or "") + ";" + (r.get("doi") or "")).split(";"):
            if d.strip():
                corpus_dois.add(nd(d))
        id2doi[r["work_id"]] = nd(r.get("doi"))
    for r in csv.DictReader((REPO / "postanalysis" / "works" / "manual_seed_works.csv").open()):
        id2doi.setdefault(r["work_id"], nd(r.get("doi")))
        corpus_dois.add(nd(r.get("doi")))
    doires = {r["work_id"]: nd(r["resolved_doi"]) for r in csv.DictReader((REG / "exploration_doi_resolution.csv").open()) if r.get("resolved_doi")}

    targets = []
    for r in csv.DictReader((REG / "exploration_unmatched_resolved.csv").open()):
        if r["final_disposition"].startswith("unresolved"):
            doi = id2doi.get(r["work_id"], "") or doires.get(r["work_id"], "")
            targets.append({**r, "doi": doi})
    for r in csv.DictReader((REG / "exploration_recent_verified.csv").open()):
        if r["final_disposition"].startswith("unresolved"):
            doi = id2doi.get(r["work_id"], "")
            targets.append({"work_id": r["work_id"], "year": r["year"], "decision": "",
                            "title": r["title"], "doi": doi})
    print(f"targets: {len(targets)} (with DOI: {sum(1 for t in targets if t['doi'])})", flush=True)

    wid_doi_cache = {}
    out = []
    for i, t in enumerate(targets):
        if not t["doi"]:
            out.append({**t, "oa_check": "no-doi", "verified_outbound_links": "", "oa_disposition": "unresolved (no-doi)"})
            continue
        w = _get("https://api.openalex.org/works/doi:" + urllib.parse.quote(t["doi"]) + "?select=id,referenced_works")
        if not w:
            out.append({**t, "oa_check": "not-in-openalex", "verified_outbound_links": "", "oa_disposition": "unresolved (not-in-openalex)"})
            continue
        refs = [x.rsplit("/", 1)[-1] for x in (w.get("referenced_works") or [])]
        if not refs:
            out.append({**t, "oa_check": "no-refs-in-openalex", "verified_outbound_links": "", "oa_disposition": "unresolved (no refs served)"})
            continue
        unknown = [x for x in refs if x not in wid_doi_cache]
        for j in range(0, len(unknown), 50):
            batch = unknown[j:j + 50]
            data = _get("https://api.openalex.org/works?filter=openalex_id:" + "|".join(batch) + "&select=id,doi&per-page=50")
            for it in (data or {}).get("results", []):
                wid_doi_cache[it["id"].rsplit("/", 1)[-1]] = nd(it.get("doi"))
            for b in batch:
                wid_doi_cache.setdefault(b, "")
        n = sum(1 for x in refs if wid_doi_cache.get(x) in corpus_dois)
        yr = (t.get("year") or "0")[:4]
        if n > 0:
            disp = "resolved: linked to graph"
        elif yr >= "2024":
            disp = "defer-recent (verified zero via OpenAlex, citation-era guard)"
        else:
            disp = "drop (verified zero outbound links via OpenAlex)"
        out.append({**t, "oa_check": f"verified ({len(refs)} refs)", "verified_outbound_links": n, "oa_disposition": disp})
        if (i + 1) % 20 == 0:
            print(f"...{i+1}/{len(targets)} (ref-cache {len(wid_doi_cache)})", flush=True)

    fields = ["work_id", "year", "decision", "doi", "ref_check", "final_disposition", "oa_check", "verified_outbound_links", "oa_disposition", "title"]
    with (REG / "exploration_oa_ref_resolution.csv").open("w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        wtr.writeheader()
        wtr.writerows(out)
    from collections import Counter
    for k, v in Counter(o["oa_disposition"].split(" (")[0] for o in out).most_common():
        print(f"{v:5d}  {k}")
    print(f"done {ts}")


if __name__ == "__main__":
    main()
