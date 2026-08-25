#!/usr/bin/env python3
"""Remap IA-007 screening rows after IA-008 work reconciliation changes work_id.

When multiple screened versions collapse into one work, keep the published/canonical
metadata from IA-008 and take the highest relevance tier among member decisions.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

# Higher score wins when collapsing duplicate versions.
TIER_RANK = {
    "core_relevant": 60,
    "adjacent_relevant": 50,
    "role_bridge": 40,
    "uncertain": 30,
    "insufficient_abstract": 20,
    "out_of_scope": 10,
}


def tier_rank(decision: object) -> int:
    return TIER_RANK.get(str(decision or "").strip(), 0)


def pick_row(group: pd.DataFrame, target_canon: str) -> pd.Series:
    """Prefer highest tier; break ties with canonical-paper match, then confidence."""
    g = group.copy()
    g["_tier"] = g["decision"].map(tier_rank)
    g["_canon"] = (g.canonical_paper_id.astype(str) == target_canon).astype(int)
    g["_conf"] = pd.to_numeric(g.get("confidence"), errors="coerce").fillna(0)
    g = g.sort_values(["_tier", "_canon", "_conf"], ascending=[False, False, False])
    return g.iloc[0].drop(labels=["_tier", "_canon", "_conf"], errors="ignore")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--works", type=Path, required=True)
    ap.add_argument("--versions", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or args.results

    results = pd.read_csv(args.results, low_memory=False)
    works = pd.read_csv(args.works, low_memory=False)
    versions = pd.read_csv(args.versions, low_memory=False)

    results["work_id"] = results.work_id.astype(str)
    works["work_id"] = works.work_id.astype(str)
    versions["paper_id"] = versions.paper_id.astype(str)
    pid_to_wid = dict(zip(versions.paper_id, versions.work_id.astype(str)))
    work_meta = works.set_index("work_id")

    # Map each screening row via any of its member paper_ids (handles multi-version rows).
    def map_wid(mids: object) -> str:
        for pid in str(mids or "").split(";"):
            pid = pid.strip()
            if pid and pid in pid_to_wid:
                return pid_to_wid[pid]
        return ""

    mapped: list[pd.Series] = []
    dropped = 0
    tier_upgrades = 0
    for new_wid, group in results.groupby(results.member_paper_ids.map(map_wid)):
        if not new_wid or new_wid not in work_meta.index:
            dropped += len(group)
            continue
        meta = work_meta.loc[new_wid]
        target_canon = str(meta.canonical_paper_id)
        row = pick_row(group, target_canon).copy()
        pub = group[group.canonical_paper_id.astype(str) == target_canon]
        if len(pub) and tier_rank(row.get("decision")) > tier_rank(pub.iloc[0].get("decision")):
            tier_upgrades += 1
        row["work_id"] = new_wid
        row["canonical_paper_id"] = target_canon
        row["version_count"] = int(meta.version_count)
        row["member_paper_ids"] = str(meta.member_paper_ids)
        row["title"] = meta.title
        row["source_group"] = meta.source_group
        mapped.append(row)

    out_df = pd.DataFrame(mapped)
    out_df.to_csv(out, index=False)
    print(
        {
            "input_rows": int(len(results)),
            "output_rows": int(len(out_df)),
            "dropped_unmapped": dropped,
            "collisions_resolved": int(len(results) - len(out_df) - dropped),
            "tier_upgrades_vs_canonical": tier_upgrades,
        }
    )


if __name__ == "__main__":
    main()
