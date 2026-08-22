#!/usr/bin/env python3
"""Apply one harmonized IA-006 role-bridge rule to retained and discarded papers.

Inputs:
- frozen pipeline outputs (`papers_all.csv`, `papers_retained.csv`, `paper_graph_edges.csv`)
- IA-004 cleanup output (`paper_cleanup_review_queue.csv`) containing `derived_nanoscale_core`

Outputs keep retained and recovered origins separate, then emit one canonical combined
bridge table. The preregistered `keep` values and source records are never changed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import pandas as pd

ROLE_RULES = {
    "training_outreach": {
        "source": "people_development_hits",
        "title": r"\b(?:outreach|undergraduate|student|education|educational|curriculum|summer school|workforce|citizen science|mentorship)\b",
        "min_direct": 1,
    },
    "health": {
        "source": "health_hits",
        "title": r"\b(?:alzheimer|parkinson|epilep|autis|schizophren|disease|disorder|patholog|clinical|patient|therap|diagnos|neurodegener|trauma|injury|stroke|cancer|tumou?r)\b",
        "min_direct": 2,
    },
    "proofreading_annotation": {
        "source": "qc_hits",
        "title": r"\b(?:proofread|annotation|annotat|error correction|merge error|segmentation error|human[- ]in[- ]the[- ]loop|quality control)\b",
        "min_direct": 1,
    },
    "infrastructure_methods": {
        "source": "infrastructure_hits",
        "title": r"\b(?:connectom|segmentation|agglomerat|alignment|registration|synapse detection|reconstruction|volume electron|electron microscopy|data infrastructure|dataservice|visualization)\b",
        "min_direct": 2,
    },
    "network_science": {
        "source": "network_hits",
        "title": r"\b(?:connectom|circuit|network analys|graph analys|motif|centrality|community detection|subgraph|graph quer)\b",
        "min_direct": 2,
    },
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", required=True, type=Path)
    ap.add_argument("--cleanup-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    src = args.outputs_dir.resolve()
    cleanup = args.cleanup_dir.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    allp = pd.read_csv(src / "papers_all.csv", low_memory=False)
    retained = pd.read_csv(src / "papers_retained.csv", low_memory=False)
    edges = pd.read_csv(src / "paper_graph_edges.csv", low_memory=False)
    clean = pd.read_csv(cleanup / "paper_cleanup_review_queue.csv", low_memory=False)

    for df in (allp, retained, clean):
        df["paper_id"] = df["paper_id"].astype(str)
    edges["source"] = edges["source"].astype(str)
    edges["target"] = edges["target"].astype(str)

    if "derived_nanoscale_core" not in clean.columns:
        raise RuntimeError("cleanup table lacks derived_nanoscale_core; run IA-004 cleanup first")

    core = set(clean.loc[clean["derived_nanoscale_core"].fillna(False), "paper_id"])
    retained_ids = set(retained["paper_id"])

    # Direct citation proximity only establishes eligibility. Indirect proximity remains
    # available from IA-005 for ranking but is intentionally not a recovery gate here.
    core_refs = {}
    core_citers = {}
    for pid in allp["paper_id"]:
        core_refs[pid] = 0
        core_citers[pid] = 0
    for r in edges.itertuples(index=False):
        if r.target in core and r.source in core_refs:
            core_refs[r.source] += 1
        if r.source in core and r.target in core_citers:
            core_citers[r.target] += 1

    allp["core_refs_cited"] = allp["paper_id"].map(core_refs).fillna(0).astype(int)
    allp["core_citers"] = allp["paper_id"].map(core_citers).fillna(0).astype(int)
    allp["core_direct_proximity"] = allp["core_refs_cited"] + allp["core_citers"]
    allp["is_retained"] = allp["paper_id"].isin(retained_ids)
    allp["is_core"] = allp["paper_id"].isin(core)
    allp["bridge_origin"] = "none"
    allp.loc[allp["is_retained"] & ~allp["is_core"], "bridge_origin"] = "retained_noncore"
    allp.loc[~allp["is_retained"], "bridge_origin"] = "recovered_keep_false"
    allp["macroscale_flag"] = allp["macroscale_hits"].fillna("").astype(str).str.strip().ne("")

    title = allp["title"].fillna("").astype(str).str.lower()
    role_cols = []
    for role, rule in ROLE_RULES.items():
        source_hit = allp[rule["source"]].fillna("").astype(str).str.strip().ne("")
        title_hit = title.str.contains(rule["title"], regex=True, na=False)
        eligible_origin = ~allp["is_core"]
        flag = eligible_origin & source_hit & title_hit & (allp["core_direct_proximity"] >= rule["min_direct"])
        col = f"bridge_{role}"
        allp[col] = flag
        role_cols.append(col)

    allp["bridge_any"] = allp[role_cols].any(axis=1)
    bridges = allp[allp["bridge_any"]].copy()
    bridges["bridge_review_class"] = "role_bridge_review"
    bridges.loc[bridges["macroscale_flag"], "bridge_review_class"] = "macroscale_role_bridge_review"

    retained_bridges = bridges[bridges["bridge_origin"] == "retained_noncore"].copy()
    recovered_bridges = bridges[bridges["bridge_origin"] == "recovered_keep_false"].copy()

    retained_bridges.to_csv(out / "retained_noncore_role_bridges_final.csv", index=False)
    recovered_bridges.to_csv(out / "recovered_role_bridges_final.csv", index=False)
    bridges.to_csv(out / "all_role_bridges_final.csv", index=False)

    role_stats = []
    for role, rule in ROLE_RULES.items():
        col = f"bridge_{role}"
        for origin in ("retained_noncore", "recovered_keep_false"):
            x = bridges[(bridges[col]) & (bridges["bridge_origin"] == origin)]
            role_stats.append({
                "role": role,
                "origin": origin,
                "paper_count": len(x),
                "min_direct_core_relations": rule["min_direct"],
                "cites_core": int((x["core_refs_cited"] >= 1).sum()),
                "cited_by_core": int((x["core_citers"] >= 1).sum()),
                "macroscale_flagged": int(x["macroscale_flag"].sum()),
            })
    pd.DataFrame(role_stats).to_csv(out / "role_bridge_stats_final.csv", index=False)

    positive_id = "17356a69dd1a1a0708e927aa8fc2279d399dcd76"
    positive = bridges[bridges["paper_id"] == positive_id]
    positive.to_csv(out / "positive_control_CIRCUIT.csv", index=False)

    summary = {
        "papers_all": len(allp),
        "retained_papers": len(retained),
        "derived_nanoscale_core": len(core),
        "retained_noncore_total": len(retained_ids - core),
        "retained_role_bridges": len(retained_bridges),
        "recovered_keep_false_role_bridges": len(recovered_bridges),
        "combined_unique_role_bridges": len(bridges),
        "macroscale_role_bridge_review": int(bridges["macroscale_flag"].sum()),
        "nonmacroscale_role_bridges": int((~bridges["macroscale_flag"]).sum()),
        "positive_control_CIRCUIT_recovered": bool(len(positive)),
        "role_rules": ROLE_RULES,
    }
    (out / "role_bridge_summary_final.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
