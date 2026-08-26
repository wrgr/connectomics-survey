#!/usr/bin/env python3
"""IA-015 second sync round: merge the gap-fill into the bootstrap review pool
and apply screener-COI tags now that the frozen COI artifact is in the repo.

Inputs (all already in the repo; no network):
  postanalysis/review_pool/bootstrap_2026-08-25/review_pool.json  (pristine, 6,506 records)
  postanalysis/review_pool/gapfill_panel_resolution.json          (15 resolved works)
  postanalysis/review_pool/coi/COI_sets_WGR_frozen.json           (screener + d1 sets)

Outputs:
  postanalysis/review_pool/review_pool.json          working pool = bootstrap pool
      + route `targeted-title-search (gap-fill)` appended on G1-G9 (records
      created for the six not retrieved by the bootstrap passes)
      + `coi_screener_tag` on the 15 gap-fill/panel works
  postanalysis/review_pool/coi/coi_tags_gapfill_panel.json   tag evidence overlay
      (the frozen panel artifact itself is never rewritten)

COI tagging per protocol §12.5: COI-0 when the screener is an author;
COI-1 when a qualifying-role author is at coauthorship distance 1.
Qualifying roles are first/co-first, last/co-last, corresponding; author
*position* here is approximated by OpenAlex authorship order (first and last
listed), because corresponding-author metadata was not captured — the
approximation is recorded in the overlay.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL_DIR = REPO / "postanalysis" / "review_pool"
BOOTSTRAP_POOL = POOL_DIR / "bootstrap_2026-08-25" / "review_pool.json"
RESOLUTION = POOL_DIR / "gapfill_panel_resolution.json"
COI_FILE = POOL_DIR / "coi" / "COI_sets_WGR_frozen.json"
OUT_POOL = POOL_DIR / "review_pool.json"
OUT_TAGS = POOL_DIR / "coi" / "coi_tags_gapfill_panel.json"

GAPFILL_IDS = {f"G{i}" for i in range(1, 10)}
GAPFILL_ROUTE = "targeted-title-search (gap-fill)"


def main() -> int:
    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pool = json.loads(BOOTSTRAP_POOL.read_text(encoding="utf-8"))
    res = json.loads(RESOLUTION.read_text(encoding="utf-8"))
    coi = json.loads(COI_FILE.read_text(encoding="utf-8"))

    screener_ids = set(coi["screener"]["openalex_author_ids"])
    d1_ids = set(coi["d1"].keys())
    d1_names = {k: v.get("name") for k, v in coi["d1"].items()}

    tags = {
        "generated_at": run_ts,
        "coi_artifact": {
            "path": "postanalysis/review_pool/coi/COI_sets_WGR_frozen.json",
            "file_sha256": "b162b0ca4aea466c272bb7fd62f8a188d6748a49660bf0dcfd4b616b6ef3d060",
            "internal_content_sha256": coi.get("sha256_of_content_excluding_this_field"),
        },
        "role_approximation": (
            "Qualifying roles approximated as first- and last-listed OpenAlex "
            "authorship; corresponding-author metadata not captured. "
            "Middle-author d1 matches are reported as evidence but do not "
            "raise the tag to COI-1 on their own."
        ),
        "works": {},
    }

    merged_gapfill, created, route_appended = [], [], []
    for e in res["entries"]:
        doi = e["doi"].lower()
        authors = e.get("openalex", {}).get("authors", [])
        ids = [a.get("openalex_author_id") for a in authors]
        names = [a.get("name") for a in authors]

        # --- COI tag ---
        tag, evidence = "none", []
        if any(i in screener_ids for i in ids if i):
            tag = "COI-0"
            evidence.append("screener OpenAlex author ID present in authorship")
        else:
            qualifying = [x for x in {0, len(ids) - 1} if 0 <= x < len(ids)]
            for pos in qualifying:
                if ids[pos] in d1_ids:
                    tag = "COI-1"
                    evidence.append(
                        f"{'first' if pos == 0 else 'last'}-listed author "
                        f"{names[pos]} ({ids[pos]}) in frozen d1 set"
                    )
            middles = [
                f"{n} ({i})"
                for j, (i, n) in enumerate(zip(ids, names))
                if i in d1_ids and j not in qualifying
            ]
            if middles:
                evidence.append("d1 middle-author overlap (not tag-raising): " + "; ".join(middles))
        # Spec-declared COI-0 on G7 must hold regardless of ID matching.
        if e["pool_id"] == "G7" and tag != "COI-0":
            tag = "COI-0"
            evidence.append(
                "spec-declared COI-0 (screener is author); OpenAlex authorship "
                "list did not surface a screener author ID - ID-resolution gap "
                "recorded, tag taken from declaration"
            )
        tags["works"][e["pool_id"]] = {
            "doi": doi,
            "citation": e["citation"],
            "coi_screener_tag": tag,
            "evidence": evidence,
        }

        # --- pool merge (gap-fill route on G1-G9 only) ---
        rec = pool.get(doi)
        if e["pool_id"] in GAPFILL_IDS:
            if rec is None:
                oa = e.get("openalex", {})
                s2 = e.get("semantic_scholar", {})
                cr = e.get("crossref", {})
                rec = {
                    "oa_id": ("https://openalex.org/" + oa["openalex_id"]) if oa.get("openalex_id") else None,
                    "doi": doi,
                    "title": cr.get("title") or s2.get("title"),
                    "year": cr.get("year") or s2.get("year"),
                    "cites": oa.get("cited_by_count", s2.get("citation_count")),
                    "venue": cr.get("container") or s2.get("venue"),
                    "abstract": None,
                    "routes": [],
                }
                pool[doi] = rec
                created.append(e["pool_id"])
            if GAPFILL_ROUTE not in rec.get("routes", []):
                rec.setdefault("routes", []).append(GAPFILL_ROUTE)
                route_appended.append(e["pool_id"])
            rec["gapfill"] = {
                "pool_id": e["pool_id"],
                "rationale": e["rationale"],
                "stratum_era": e["stratum_era"],
                "added": run_ts,
            }
            merged_gapfill.append(e["pool_id"])
        if rec is not None:
            rec["coi_screener_tag"] = tag

    OUT_POOL.write_text(json.dumps(pool, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_TAGS.write_text(json.dumps(tags, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"pool records: {len(pool)}")
    print(f"gap-fill merged: {sorted(merged_gapfill)}")
    print(f"  records created: {sorted(created)}")
    print(f"  route appended to existing: {sorted(set(route_appended) - set(created))}")
    for pid, t in tags["works"].items():
        print(f"  {pid}: {t['coi_screener_tag']}" + (f"  [{t['evidence'][0]}]" if t["evidence"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
