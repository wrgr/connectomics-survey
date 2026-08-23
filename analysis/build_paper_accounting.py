#!/usr/bin/env python3
"""Build the canonical mutually exclusive post-analysis accounting for retained papers.

This script never changes the preregistered source corpus. It partitions the
originally retained papers into:
  1) derived nanoscale core;
  2) strict retained role bridges; or
  3) one unresolved review bucket.

Recovered keep=False role bridges are reported separately and never mixed into
the retained-corpus denominator.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import pandas as pd

UNRESOLVED_PREFIX = "unresolved_"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", required=True, type=Path)
    ap.add_argument("--cleanup-dir", required=True, type=Path)
    ap.add_argument("--bridges-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    src = args.outputs_dir.resolve()
    cleanup = args.cleanup_dir.resolve()
    bridges = args.bridges_dir.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    retained = pd.read_csv(src / "papers_retained.csv", low_memory=False)
    edges = pd.read_csv(src / "paper_graph_edges.csv", low_memory=False)
    clean = pd.read_csv(cleanup / "paper_cleanup_review_queue.csv", low_memory=False)
    bridge = pd.read_csv(bridges / "all_role_bridges_final.csv", low_memory=False)

    for df in (retained, clean, bridge):
        df["paper_id"] = df["paper_id"].astype(str)
    edges["source"] = edges["source"].astype(str)
    edges["target"] = edges["target"].astype(str)

    core_by_id = dict(zip(clean["paper_id"], clean["derived_nanoscale_core"].fillna(False).astype(bool)))
    retained["derived_nanoscale_core"] = retained["paper_id"].map(core_by_id).fillna(False).astype(bool)

    retained_bridge_ids = set(bridge.loc[bridge["bridge_origin"].eq("retained_noncore"), "paper_id"])
    recovered_bridge_ids = set(bridge.loc[bridge["bridge_origin"].eq("recovered_keep_false"), "paper_id"])
    retained["strict_retained_role_bridge"] = retained["paper_id"].isin(retained_bridge_ids)

    overlap = retained["derived_nanoscale_core"] & retained["strict_retained_role_bridge"]
    if overlap.any():
        raise RuntimeError(f"{int(overlap.sum())} papers are both core and strict retained bridge")

    core_ids = set(retained.loc[retained["derived_nanoscale_core"], "paper_id"])
    retained_ids = set(retained["paper_id"])
    graph_support = collections.Counter()
    for r in edges.itertuples(index=False):
        if r.source in core_ids and r.target in retained_ids and r.target not in core_ids:
            graph_support[r.target] += 1
        if r.target in core_ids and r.source in retained_ids and r.source not in core_ids:
            graph_support[r.source] += 1
    retained["core_graph_links"] = retained["paper_id"].map(graph_support).fillna(0).astype(int)

    retained["macroscale_flag"] = retained["macroscale_hits"].fillna("").astype(str).str.strip().ne("")
    role_hit_cols = ["health_hits", "people_development_hits", "qc_hits", "infrastructure_hits", "network_hits"]
    retained["any_role_signal"] = False
    for col in role_hit_cols:
        retained["any_role_signal"] |= retained[col].fillna("").astype(str).str.strip().ne("")

    def category(r) -> str:
        if r.derived_nanoscale_core:
            return "derived_nanoscale_core"
        if r.strict_retained_role_bridge:
            return "strict_retained_role_bridge"
        if r.macroscale_flag:
            return "unresolved_macroscale_review"
        if r.core_graph_links >= 2:
            return "unresolved_graph_supported_adjacent_review"
        if r.any_role_signal:
            return "unresolved_role_signal_not_strict_bridge"
        return "unresolved_low_specificity_review"

    retained["canonical_postanalysis_category"] = retained.apply(category, axis=1)
    retained.to_csv(out / "retained_paper_accounting.csv", index=False)

    counts = retained["canonical_postanalysis_category"].value_counts().to_dict()
    core_n = counts.get("derived_nanoscale_core", 0)
    bridge_n = counts.get("strict_retained_role_bridge", 0)
    unresolved_n = sum(v for k, v in counts.items() if k.startswith(UNRESOLVED_PREFIX))

    if core_n + bridge_n + unresolved_n != len(retained):
        raise RuntimeError("retained accounting invariant failed")
    if len(retained_bridge_ids) != bridge_n:
        raise RuntimeError("retained bridge IDs do not match accounting")
    if retained_bridge_ids & recovered_bridge_ids:
        raise RuntimeError("retained and recovered bridge sets overlap")

    summary = {
        "retained_total": len(retained),
        "derived_nanoscale_core": core_n,
        "strict_retained_role_bridges": bridge_n,
        "unresolved_retained_noncore": unresolved_n,
        "unresolved_buckets": {k: v for k, v in counts.items() if k.startswith(UNRESOLVED_PREFIX)},
        "recovered_keep_false_role_bridges": len(recovered_bridge_ids),
        "strict_role_bridges_across_both_origins": bridge_n + len(recovered_bridge_ids),
        "invariants": {
            "retained_partition": f"{len(retained)} = {core_n} + {bridge_n} + {unresolved_n}",
            "recovered_bridges_are_outside_retained_denominator": True,
        },
    }
    (out / "paper_accounting_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    flow = f"""# Canonical post-analysis paper accounting\n\nThe frozen originally retained corpus is partitioned mutually exclusively:\n\n- **Originally retained:** {len(retained):,}\n  - **Derived nanoscale core:** {core_n:,}\n  - **Strict retained role bridges:** {bridge_n:,}\n  - **Unresolved retained non-core:** {unresolved_n:,}\n\nUnresolved retained non-core:\n\n"""
    for key, value in sorted(summary["unresolved_buckets"].items()):
        flow += f"- **{key}:** {value:,}\n"
    flow += (
        f"\nSeparately, **{len(recovered_bridge_ids):,}** role bridges were recovered from `papers_all.csv` records with original `keep=False`. "
        f"They are not part of the {len(retained):,}-paper retained denominator.\n\n"
        f"Total strict role bridges across both origins: **{bridge_n + len(recovered_bridge_ids):,}**.\n"
    )
    (out / "PAPER_ACCOUNTING.md").write_text(flow)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
