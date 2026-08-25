#!/usr/bin/env python3
"""Quick v2 vs v3 screening comparison on intersecting work_ids."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

INCLUSIVE = {"core_relevant", "adjacent_relevant", "role_bridge"}
LANDMARK_RE = re.compile(
    r"(whole[- ]brain|petascale|first (complete )?connectome|wiring diagram of|"
    r"flywire|hemibrain|fafb|h01|microns|c\. elegans connectome|complete connectome|"
    r"millimetre-scale|mm3|cubic millimeter)",
    re.I,
)


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df["work_id"] = df.work_id.astype(str)
    return df.drop_duplicates("work_id", keep="last")


def attach_ultra_core(df: pd.DataFrame, works: pd.DataFrame) -> pd.DataFrame:
    """ultra_core = core_relevant AND (cites>=200 OR landmark title AND cites>=100)."""
    out = df.merge(
        works[["work_id", "title", "citation_count_work"]],
        on="work_id",
        how="left",
        suffixes=("", "_enriched"),
    )
    if "title_enriched" in out.columns:
        out["title"] = out["title"].fillna(out["title_enriched"])
    cites = pd.to_numeric(
        out["citation_count_work"].fillna(out.get("citation_count_work_enriched")),
        errors="coerce",
    ).fillna(0)
    landmark = out["title"].fillna("").astype(str).str.contains(LANDMARK_RE, regex=True)
    out["ultra_core"] = (out.decision == "core_relevant") & (
        (cites >= 200) | (landmark & (cites >= 100))
    )
    out["citation_count_work"] = cites
    return out


def ultra_core_summary(df: pd.DataFrame) -> dict[str, int]:
    sub = df[df.ultra_core]
    routes = Counter()
    for row in sub.itertuples(index=False):
        cites = float(getattr(row, "citation_count_work", 0) or 0)
        title = str(getattr(row, "title", "") or "")
        if cites >= 200:
            routes["cites>=200"] += 1
        elif LANDMARK_RE.search(title) and cites >= 100:
            routes["landmark+cites>=100"] += 1
    return {
        "ultra_core": int(sub.shape[0]),
        "ultra_core_routes": dict(routes),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", type=Path, default=Path("postanalysis/llm_agent/llm_relevance_results.csv"))
    ap.add_argument("--v3", type=Path, default=Path("postanalysis/llm_agent_v3/llm_relevance_results.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/llm_agent_v3/v2_v3_comparison.json"))
    ap.add_argument(
        "--works",
        type=Path,
        default=Path("postanalysis/enriched/canonical_works_enriched.csv"),
    )
    ap.add_argument(
        "--ultra-core-out",
        type=Path,
        default=Path("postanalysis/llm_agent_v3/label_ultra_core.csv"),
    )
    args = ap.parse_args()

    if not args.v3.exists():
        raise SystemExit(f"v3 results not found: {args.v3}")
    works = load(args.works)
    v2 = attach_ultra_core(load(args.v2), works)
    v3 = attach_ultra_core(load(args.v3), works)
    both = v2.merge(v3, on="work_id", suffixes=("_v2", "_v3"))
    tier_changes = both[both.decision_v2 != both.decision_v3]
    incl_flip = both[
        both.decision_v2.isin(INCLUSIVE) != both.decision_v3.isin(INCLUSIVE)
    ]
    summary = {
        "v2_works": len(v2),
        "v3_works": len(v3),
        "scored_both": len(both),
        "v2_decisions": dict(Counter(v2.decision)),
        "v3_decisions": dict(Counter(v3.decision)),
        "tier_changes": len(tier_changes),
        "inclusive_flips": len(incl_flip),
        "core_v2": int((v2.decision == "core_relevant").sum()),
        "core_v3": int((v3.decision == "core_relevant").sum()),
        "core_demotions": int(
            ((both.decision_v2 == "core_relevant") & (both.decision_v3 != "core_relevant")).sum()
        ),
        "core_promotions": int(
            ((both.decision_v2 != "core_relevant") & (both.decision_v3 == "core_relevant")).sum()
        ),
        "ultra_core_v2": ultra_core_summary(v2)["ultra_core"],
        "ultra_core_v3": ultra_core_summary(v3)["ultra_core"],
        "ultra_core_routes_v2": ultra_core_summary(v2)["ultra_core_routes"],
        "ultra_core_routes_v3": ultra_core_summary(v3)["ultra_core_routes"],
        "ultra_core_demotions": int((both.ultra_core_v2 & ~both.ultra_core_v3).sum()),
        "confusion": pd.crosstab(both.decision_v2, both.decision_v3).to_dict(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    ultra = v3[v3.ultra_core].sort_values("citation_count_work", ascending=False)
    ultra_out = ultra[
        ["work_id", "title", "citation_count_work", "decision", "confidence"]
    ].copy()
    ultra_out.to_csv(args.ultra_core_out, index=False)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
