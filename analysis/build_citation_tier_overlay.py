#!/usr/bin/env python3
"""Write the citation-tier overlay (ultra / core / contextual / gem / drop).

View layer only. Does not mutate frozen IA-007-v3 agent JSON.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from citation_tier_overlay import annotate_corpus, parse_roles
from manual_seeds import load_manual_seeds

OUT_DEFAULT = Path("postanalysis/llm_agent_v3")


def load_roles(results_csv: Path) -> dict[str, list[str]]:
    roles: dict[str, list[str]] = {}
    if results_csv.exists():
        results = pd.read_csv(results_csv, low_memory=False)
        for row in results.itertuples(index=False):
            roles[str(row.work_id)] = parse_roles(getattr(row, "roles", []))
    seeds = load_manual_seeds()
    if not seeds.empty:
        for row in seeds.itertuples(index=False):
            roles.setdefault(str(row.work_id), parse_roles(getattr(row, "roles", [])))
    return roles


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=OUT_DEFAULT / "corpus_full_works.csv")
    ap.add_argument("--results", type=Path, default=OUT_DEFAULT / "llm_relevance_results.csv")
    ap.add_argument("--emergent", type=Path, default=OUT_DEFAULT / "label_emergent_core.csv")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()

    corpus = pd.read_csv(args.corpus, low_memory=False)
    emergent = pd.read_csv(args.emergent, low_memory=False) if args.emergent.exists() else pd.DataFrame()
    emergent_ids = set(emergent.work_id.astype(str)) if not emergent.empty else set()
    annotated = annotate_corpus(corpus, emergent_ids=emergent_ids, roles_map=load_roles(args.results))

    keep = [
        "work_id",
        "title",
        "year_n",
        "cites",
        "decision",
        "proposed_layer",
        "contextual_sublabel",
        "quality",
        "quality_reason",
        "is_ultra",
        "is_emergent",
        "max_io",
        "in_deg",
        "out_deg",
        "citation_role",
        "graph_status",
        "venue",
        "authors",
    ]
    keep = [c for c in keep if c in annotated.columns]
    overlay = annotated[keep].sort_values(
        ["proposed_layer", "cites", "year_n"],
        ascending=[True, False, True],
        na_position="last",
    )
    args.out.mkdir(parents=True, exist_ok=True)
    overlay.to_csv(args.out / "overlay_citation_tiers.csv", index=False)
    gems = overlay[overlay.proposed_layer == "hidden_gem"]
    drops = overlay[overlay.proposed_layer == "drop"]
    gems.to_csv(args.out / "overlay_hidden_gems.csv", index=False)
    drops.to_csv(args.out / "overlay_drops.csv", index=False)
    band = gems[gems.quality_reason == "old_cite_band_2_to_4"]
    band.to_csv(args.out / "overlay_hidden_gems_old_2_to_4_cites.csv", index=False)

    ctx = overlay[overlay.proposed_layer == "contextual"]
    summary = {
        "n_inclusive": int(len(overlay)),
        "layers": overlay.proposed_layer.value_counts().to_dict(),
        "contextual_sublabels": ctx.contextual_sublabel.value_counts().to_dict(),
        "hidden_gem_reasons": gems.quality_reason.value_counts().to_dict(),
        "drop_reasons": drops.quality_reason.value_counts().to_dict(),
        "old_2_to_4_gems": int(len(band)),
        "old_2_to_4_by_decision": band.decision.value_counts().to_dict(),
        "rule": {
            "old_year": 2020,
            "contextual_cites": 5,
            "drop_cites": 2,
            "weak_max_io": 2,
            "2_to_4_cites": "hidden_gem",
        },
    }
    (args.out / "overlay_citation_tiers.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
