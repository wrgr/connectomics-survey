#!/usr/bin/env python3
"""Build emergent-core watch-list (IA-013 §3).

Young non-ultra core with high relative impact (citation lag). Never auto-promotes to ultra.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REF_YEAR = 2026
MIN_YEAR = 2019
PCT_FLOOR = 0.90
RECENT_FLOOR_YEAR = 2023
RECENT_FLOOR_CITES = 20


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("postanalysis/llm_agent_v3"))
    ap.add_argument("--ref-year", type=int, default=REF_YEAR)
    args = ap.parse_args()
    out = args.out

    corpus = pd.read_csv(out / "corpus_full_works.csv", low_memory=False)
    core = corpus[corpus.decision == "core_relevant"].copy()
    core["year_n"] = pd.to_numeric(core.year, errors="coerce")
    core["citation_count_work"] = pd.to_numeric(core.citation_count_work, errors="coerce").fillna(0)
    core["is_ultra"] = core.ultra_core.fillna(False).astype(bool)
    core["age"] = (args.ref_year - core.year_n).clip(lower=0.5)
    core["cites_per_year"] = core.citation_count_work / core.age
    core["cites_pct_in_year"] = core.groupby("year_n")["citation_count_work"].rank(pct=True)

    recent = core[(~core.is_ultra) & (core.year_n >= MIN_YEAR)]
    cpy_p90 = float(recent.cites_per_year.quantile(0.9)) if len(recent) else float("nan")

    emergent = core[
        (~core.is_ultra)
        & (core.year_n >= MIN_YEAR)
        & (
            (core.cites_per_year >= cpy_p90)
            | (core.cites_pct_in_year >= PCT_FLOOR)
            | ((core.year_n >= RECENT_FLOOR_YEAR) & (core.citation_count_work >= RECENT_FLOOR_CITES))
        )
    ].sort_values(["year_n", "cites_per_year"], ascending=[False, False])

    cols = [
        "work_id",
        "title",
        "year_n",
        "citation_count_work",
        "cites_per_year",
        "cites_pct_in_year",
        "citation_link_strength",
        "corpus_in_degree",
        "k_core",
        "primary_community_label",
        "confidence",
        "graph_status",
        "in_integrated_plus_rescue",
    ]
    cols = [c for c in cols if c in emergent.columns]
    emergent[cols].to_csv(out / "label_emergent_core.csv", index=False)

    summary = {
        "ia": "IA-013 §3",
        "definition": (
            f"core_relevant ∧ ¬ultra ∧ year≥{MIN_YEAR} ∧ "
            f"(cites_per_year≥p90_recent={cpy_p90:.4f} ∨ cites_pct_in_year≥{PCT_FLOOR} ∨ "
            f"(year≥{RECENT_FLOOR_YEAR} ∧ cites≥{RECENT_FLOOR_CITES}))"
        ),
        "ref_year": args.ref_year,
        "n": int(len(emergent)),
        "cites_per_year_p90_recent_non_ultra": cpy_p90,
        "by_link_strength": emergent.citation_link_strength.fillna("no_graph").value_counts().to_dict()
        if "citation_link_strength" in emergent
        else {},
        "in_integrated_plus_rescue": int(emergent.in_integrated_plus_rescue.sum())
        if "in_integrated_plus_rescue" in emergent
        else None,
        "weak_unlinked": int((emergent.citation_link_strength == "weak_unlinked").sum())
        if "citation_link_strength" in emergent
        else None,
    }
    (out / "emergent_core_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
