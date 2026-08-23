#!/usr/bin/env python3
"""Triage retained and originally-discarded role-bridge papers by core proximity.

IA-005/IA-006 derived post-processing only. The preregistered discovery and keep
flags remain untouched.

IA-005 principle:
  Role evidence nominates a paper; citation proximity to the derived nanoscale core
  supplies field-specific evidence. Direct citation, bibliographic coupling, and
  co-citation-like proximity are emitted separately.

IA-006 correction:
  Role-bridge analysis must not be restricted to papers_retained.csv, because a
  scientific-core keep gate can systematically reject legitimate training/outreach,
  health, proofreading, infrastructure, or network-science bridge records. We
  therefore inspect explicit role-bearing records in papers_all.csv. Originally
  discarded papers are only placed into the *actionable recovery queue* when they
  satisfy a role-specific title gate AND a directed citation-proximity requirement.
  Indirect proximity ranks candidates but cannot recover a discarded paper alone.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

import pandas as pd

ROLE_SOURCE_COLUMNS = {
    "health": "health_hits",
    "training_outreach": "people_development_hits",
    "proofreading_annotation": "qc_hits",
    "infrastructure_methods": "infrastructure_hits",
    "network_science": "network_hits",
}

# Title-level role specificity for *discarded-paper recovery*. These are deliberately
# narrower than the original discovery vocabulary. A source role tag is also required.
RECOVERY_TITLE_PATTERNS = {
    "training_outreach": r"\b(?:outreach|undergraduate|student|education|educational|curriculum|summer school|workforce|citizen science|mentorship)\b",
    "health": r"\b(?:alzheimer|parkinson|epilep|autis|schizophren|disease|disorder|patholog|clinical|patient|therap|diagnos|neurodegener|trauma|injury|stroke|cancer|tumou?r)\b",
    "proofreading_annotation": r"\b(?:proofread|annotation|annotat|error correction|merge error|segmentation error|human[- ]in[- ]the[- ]loop|quality control)\b",
    "infrastructure_methods": r"\b(?:connectom|segmentation|agglomerat|alignment|registration|synapse detection|reconstruction|volume electron|electron microscopy|data infrastructure|dataservice|visualization)\b",
    "network_science": r"\b(?:connectom|circuit|network analys|graph analys|motif|centrality|community detection|subgraph|graph quer)\b",
}

# Human-development and proofreading roles are relatively specific, so one direct
# core relationship is sufficient for actionable review. Broad scientific roles
# require >=2 direct relationships before recovery.
RECOVERY_MIN_DIRECT = {
    "training_outreach": 1,
    "health": 2,
    "proofreading_annotation": 1,
    "infrastructure_methods": 2,
    "network_science": 2,
}


def nonempty(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().ne("")


def build_graph_indexes(edges: pd.DataFrame, core: set[str]):
    outnbr: dict[str, set[str]] = collections.defaultdict(set)
    innbr: dict[str, set[str]] = collections.defaultdict(set)
    for r in edges.itertuples(index=False):
        outnbr[str(r.source)].add(str(r.target))
        innbr[str(r.target)].add(str(r.source))

    # Efficient bibliographic-coupling lookup: reference -> core papers citing it.
    ref_to_core: dict[str, set[str]] = collections.defaultdict(set)
    for c in core:
        for ref in outnbr[c]:
            ref_to_core[ref].add(c)

    # Efficient co-citation-like lookup: citer -> core targets cited by that paper.
    citer_to_core: dict[str, set[str]] = collections.defaultdict(set)
    for c in core:
        for citer in innbr[c]:
            citer_to_core[citer].add(c)
    return outnbr, innbr, ref_to_core, citer_to_core


def proximity(pid: str, core: set[str], outnbr, innbr, ref_to_core, citer_to_core):
    refs = outnbr[pid]
    citers = innbr[pid]
    cited_core = refs & core
    citing_core = citers & core

    coupled: set[str] = set()
    for ref in refs:
        coupled.update(ref_to_core.get(ref, ()))
    cocited: set[str] = set()
    for citer in citers:
        cocited.update(citer_to_core.get(citer, ()))
    coupled.discard(pid)
    cocited.discard(pid)
    return len(cited_core), len(citing_core), len(coupled), len(cocited)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", required=True, type=Path)
    ap.add_argument("--cleanup-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    allp = pd.read_csv(args.outputs_dir / "papers_all.csv", low_memory=False)
    cleanup = pd.read_csv(args.cleanup_dir / "paper_cleanup_review_queue.csv", low_memory=False)
    edges = pd.read_csv(args.outputs_dir / "paper_graph_edges.csv", low_memory=False)

    allp["paper_id"] = allp["paper_id"].astype(str)
    cleanup["paper_id"] = cleanup["paper_id"].astype(str)
    edges["source"] = edges["source"].astype(str)
    edges["target"] = edges["target"].astype(str)

    core = set(cleanup.loc[cleanup["derived_nanoscale_core"].fillna(False), "paper_id"])
    retained = set(cleanup["paper_id"])

    # Use role signals already recorded by the discovery pipeline as nomination
    # evidence. This avoids reopening all 118k discovered records indiscriminately.
    for role, source_col in ROLE_SOURCE_COLUMNS.items():
        allp[f"role_{role}"] = nonempty(allp[source_col])
    role_cols = [f"role_{x}" for x in ROLE_SOURCE_COLUMNS]
    allp["role_count"] = allp[role_cols].sum(axis=1)
    p = allp[allp["role_count"] > 0].copy()

    outnbr, innbr, ref_to_core, citer_to_core = build_graph_indexes(edges, core)
    vals = [proximity(pid, core, outnbr, innbr, ref_to_core, citer_to_core) for pid in p["paper_id"]]
    p[["core_refs_cited", "core_citers", "core_bibcoupled", "core_cocited"]] = pd.DataFrame(vals, index=p.index)
    p["core_direct_proximity"] = p["core_refs_cited"] + p["core_citers"]
    p["core_hybrid_proximity"] = p["core_direct_proximity"] + p["core_bibcoupled"] + p["core_cocited"]
    p["is_retained"] = p["paper_id"].isin(retained)
    p["is_core"] = p["paper_id"].isin(core)

    # Retained-paper IA-005 descriptive strata. Indirect proximity remains useful
    # here for review prioritization because these papers already passed keep.
    p["proximity_stratum"] = "none"
    p.loc[(p["core_direct_proximity"] >= 1) | (p["core_hybrid_proximity"] >= 2), "proximity_stratum"] = "moderate"
    p.loc[(p["core_direct_proximity"] >= 2) | (p["core_hybrid_proximity"] >= 5), "proximity_stratum"] = "strong"

    title = p["title"].fillna("").astype(str).str.lower()
    for role, pattern in RECOVERY_TITLE_PATTERNS.items():
        p[f"recovery_title_{role}"] = title.str.contains(pattern, regex=True, na=False)
        p[f"recover_{role}"] = (
            ~p["is_retained"]
            & p[f"role_{role}"]
            & p[f"recovery_title_{role}"]
            & (p["core_direct_proximity"] >= RECOVERY_MIN_DIRECT[role])
        )

    recover_cols = [f"recover_{r}" for r in RECOVERY_TITLE_PATTERNS]
    p["recovery_role_count"] = p[recover_cols].sum(axis=1)
    p["actionable_recovery"] = p["recovery_role_count"] > 0

    def action(r):
        if r.is_core:
            return "retain_core"
        if r.is_retained and r.proximity_stratum == "strong" and r.role_count > 0:
            return "priority_retained_adjacent_review"
        if r.is_retained and r.proximity_stratum == "moderate" and r.role_count > 0:
            return "retained_adjacent_review"
        if r.actionable_recovery:
            return "recovered_role_bridge_review"
        if not r.is_retained and r.role_count > 0:
            return "discarded_role_record_not_recovered"
        return "other"

    p["triage_action"] = p.apply(action, axis=1)
    p.to_csv(args.out / "paper_category_proximity_triage_all_role_bearing.csv", index=False)

    recovered = p[p["actionable_recovery"]].sort_values(
        ["core_direct_proximity", "core_bibcoupled", "citation_count"],
        ascending=False,
    )
    recovered.to_csv(args.out / "recovered_role_bridge_candidates.csv", index=False)

    for role in ROLE_SOURCE_COLUMNS:
        p[p[f"role_{role}"]].sort_values(
            ["core_direct_proximity", "core_bibcoupled", "citation_count"], ascending=False
        ).to_csv(args.out / f"role_{role}_all_discovered_review.csv", index=False)
        p[p[f"recover_{role}"]].sort_values(
            ["core_direct_proximity", "core_bibcoupled", "citation_count"], ascending=False
        ).to_csv(args.out / f"role_{role}_recovered_review.csv", index=False)

    role_stats = {}
    for role in ROLE_SOURCE_COLUMNS:
        x = p[p[f"role_{role}"]]
        rx = p[p[f"recover_{role}"]]
        role_stats[role] = {
            "all_discovered_role": int(len(x)),
            "retained": int(x["is_retained"].sum()),
            "discarded_originally": int((~x["is_retained"]).sum()),
            "actionable_recovered": int(len(rx)),
            "minimum_direct_core_relations_for_recovery": RECOVERY_MIN_DIRECT[role],
        }

    stats = {
        "papers_all": int(len(allp)),
        "derived_core": int(len(core)),
        "explicit_role_bearing_discovered": int(len(p)),
        "actionable_recovered_unique": int(len(recovered)),
        "actions": p["triage_action"].value_counts().to_dict(),
        "roles": role_stats,
        "recovery_rule": "originally discarded + original source role hit + role-specific title evidence + role-specific minimum directed citation relationship(s) with derived nanoscale core; indirect proximity ranks but never recovers a discarded paper alone",
    }
    (args.out / "paper_category_triage_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
