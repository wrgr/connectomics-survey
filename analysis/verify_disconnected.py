#!/usr/bin/env python3
"""Verify apparent graph-disconnection against actual reference lists (S2).

Screener rules (2026-08-26): very recent works must at least have verified
links TO the corpus graph (outbound); an out-degree of 0 in the retrieved
graph is a trigger for reference-list verification, never an automatic fact.
Graph-unmatched works are a separate resolution queue and are prune-ineligible
until matched.

Modes:
  --recent      verify the deferred >=2024 zero-degree works (from
                exploration_disconnected.csv)
  --unmatched   resolve the graph-unmatched works' outbound links
Writes results CSVs under postanalysis/registry/.
"""

from __future__ import annotations

import argparse
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
FULL = REPO / "postanalysis" / "llm_agent_v3" / "corpus_full_works.csv"

S2 = "https://api.semanticscholar.org/graph/v1"
KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
_last = {"t": 0.0}


def _get(url, tries=10, backoff=30.0):
    for a in range(tries):
        w = 1.5 - (time.time() - _last["t"])
        if w > 0:
            time.sleep(w)
        h = {"User-Agent": "connectomics-survey-exploration"}
        if KEY:
            h["x-api-key"] = KEY
        _last["t"] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=45) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and a < tries - 1:
                time.sleep(backoff * (1.35**a))
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


def load_corpus_ids():
    s2ids, dois, id2work = set(), set(), {}
    with ENRICHED.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for p in (r.get("member_paper_ids") or "").split(";"):
                if p.strip():
                    s2ids.add(p.strip())
            for d in ((r.get("member_dois") or "") + ";" + (r.get("doi") or "")).split(";"):
                if d.strip():
                    dois.add(nd(d))
            id2work[r["work_id"]] = r
    return s2ids, dois, id2work


def outbound_links(doi, s2ids, dois):
    """Return (status, n_links) for a work's verified outbound corpus links."""
    if not doi:
        return "no-doi", None
    rec = _get(f"{S2}/paper/DOI:{urllib.parse.quote(doi)}?fields=paperId,referenceCount")
    if not rec:
        return "not-in-s2", None
    refs, offset = [], 0
    while True:
        data = _get(f"{S2}/paper/{rec['paperId']}/references?fields=paperId,externalIds&limit=500&offset={offset}")
        if not data:
            break
        rows = data.get("data") or []
        refs += rows
        nxt = data.get("next")
        if nxt is None or not rows:
            break
        offset = nxt
    if not refs:
        return "refs-elided-or-none", None
    n = 0
    for row in refs:
        c = row.get("citedPaper") or {}
        if c.get("paperId") in s2ids or nd((c.get("externalIds") or {}).get("DOI")) in dois:
            n += 1
    return "verified", n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recent", action="store_true")
    ap.add_argument("--unmatched", action="store_true")
    args = ap.parse_args()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    s2ids, dois, id2work = load_corpus_ids()

    if args.recent:
        rows = [r for r in csv.DictReader((REG / "exploration_disconnected.csv").open())
                if r["disposition"].startswith("defer")]
        out = []
        for r in rows:
            doi = nd(id2work.get(r["work_id"], {}).get("doi"))
            status, n = outbound_links(doi, s2ids, dois)
            if status == "verified":
                disp = "keep (verified outbound links)" if n and n > 0 else "drop (verified zero outbound links)"
            else:
                disp = f"unresolved ({status})"
            out.append({**r, "ref_check": status, "verified_outbound_links": n if n is not None else "",
                        "final_disposition": disp})
            print(f"{disp:42s} | {r['year']} | {r['title'][:70]}")
        with (REG / "exploration_recent_verified.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        print(f"\nwrote exploration_recent_verified.csv ({ts})")

    if args.unmatched:
        unmatched = []
        for r in csv.DictReader(FULL.open()):
            if not (r.get("corpus_in_degree") or "").strip() and not (r.get("corpus_out_degree") or "").strip():
                unmatched.append(r)
        # resume support: progress journal survives crashes/429 storms
        prog_path = Path(os.environ.get("IA015_CACHE_DIR", str(REG))) / "unmatched_progress.jsonl"
        done = {}
        if prog_path.exists():
            for line in prog_path.open():
                rec = json.loads(line)
                done[rec["work_id"]] = rec
        print(f"resume: {len(done)}/{len(unmatched)} already done")
        prog = prog_path.open("a")
        out = []
        for i, r in enumerate(unmatched):
            if r["work_id"] in done:
                out.append(done[r["work_id"]])
                continue
            doi = nd(id2work.get(r["work_id"], {}).get("doi"))
            status, n = outbound_links(doi, s2ids, dois)
            if status == "verified":
                disp = "resolved: linked to graph" if n and n > 0 else "resolved: verified zero outbound links"
            else:
                disp = f"unresolved ({status})"
            rec = {"work_id": r["work_id"], "year": r.get("year") or r.get("year_enr") or "",
                   "decision": r["decision"], "ref_check": status,
                   "verified_outbound_links": n if n is not None else "",
                   "final_disposition": disp, "title": (r["title"] or "")[:120]}
            out.append(rec)
            prog.write(json.dumps(rec) + "\n")
            prog.flush()
            if (i + 1) % 25 == 0:
                print(f"...{i+1}/{len(unmatched)}", flush=True)
        with (REG / "exploration_unmatched_resolved.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        from collections import Counter
        print(Counter(o["final_disposition"].split(" (")[0].split(":")[0] + (":"+o["final_disposition"].split(":")[1][:30] if ":" in o["final_disposition"] else "") for o in out))
        print(f"wrote exploration_unmatched_resolved.csv ({len(out)} works, {ts})")


if __name__ == "__main__":
    main()
