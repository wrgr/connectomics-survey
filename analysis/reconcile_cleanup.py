#!/usr/bin/env python3
"""Create derived scope-cleanup and person-reconciliation products.

This is post-processing only. It never mutates or deletes the preregistered broad
corpus and never rewrites source Semantic Scholar author IDs.

IA-004 paper rule (empirically calibrated on the frozen run):
  nanoscale_core = direct_scope+resolution OR inherited_connectome_provenance
  inherited_connectome_provenance requires:
    * non-direct paper;
    * specific connectome-analysis language;
    * >=2 directed citations from the candidate to direct-resolution papers; and
    * no existing macroscale flag.

Author reconciliation:
  candidate blocking uses both exact normalized names and a conservative variant
  that removes only single-letter middle initials. Name similarity creates
  candidates only. Coauthor overlap and temporal compatibility score candidates;
  actual merges remain explicit reviewed alias decisions.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

import pandas as pd


def norm_name(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).lower())).strip()


def norm_name_ignore_middle_initials(value: object) -> str:
    """Remove only one-character interior alphabetic tokens; preserve first/last."""
    toks = norm_name(value).split()
    if len(toks) <= 2:
        return " ".join(toks)
    return " ".join([toks[0], *[t for t in toks[1:-1] if not (len(t) == 1 and t.isalpha())], toks[-1]])


def split_set(value: object) -> set[str]:
    if pd.isna(value):
        return set()
    return {x.strip() for x in str(value).split(";") if x.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    src = args.outputs_dir.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    papers = pd.read_csv(src / "papers_retained.csv", low_memory=False)
    edges = pd.read_csv(src / "paper_graph_edges.csv")
    people = pd.read_csv(src / "people.csv", low_memory=False)
    coedges = pd.read_csv(src / "coauthor_edges.csv")

    # ---- Paper scope: direct evidence + inherited connectome provenance ----
    papers["paper_id"] = papers["paper_id"].astype(str)
    papers["direct_nanoscale_view"] = papers["scope_reasons"].fillna("").str.contains("direct_scope\\+resolution", regex=True)
    papers["macroscale_flag"] = papers["macroscale_hits"].fillna("").astype(str).str.strip().ne("")
    papers["health_flag"] = papers["health_hits"].fillna("").astype(str).str.strip().ne("")
    papers["training_outreach_flag"] = papers["people_development_hits"].fillna("").astype(str).str.strip().ne("")

    text = (papers["title"].fillna("") + " " + papers["abstract"].fillna("")).str.lower()
    specific_patterns = {
        "connectome": r"\bconnectom(?:e|es|ics)\b",
        "wiring_diagram": r"\bwiring diagram\b",
        "synaptic_graph": r"\bsynaptic (?:graph|network|connectivity)\b",
        "connectome_constrained": r"\bconnectome[- ]constrained\b",
        "graph_query": r"\b(?:graph|subgraph) quer(?:y|ies)\b|\bsubgraph isomorphism\b",
    }
    for name, pattern in specific_patterns.items():
        papers[f"provenance_term_{name}"] = text.str.contains(pattern, regex=True, na=False)
    term_cols = [f"provenance_term_{x}" for x in specific_patterns]
    papers["specific_connectome_analysis"] = papers[term_cols].any(axis=1)

    retained_ids = set(papers["paper_id"])
    direct_ids = set(papers.loc[papers["direct_nanoscale_view"], "paper_id"])
    rr = edges[
        edges["source"].astype(str).isin(retained_ids)
        & edges["target"].astype(str).isin(retained_ids)
    ].copy()
    rr["source"] = rr["source"].astype(str)
    rr["target"] = rr["target"].astype(str)

    # Graph semantics are citing source -> cited target. Count distinct established
    # direct-resolution papers cited by each candidate; do not use undirected adjacency.
    direct_refs: dict[str, set[str]] = collections.defaultdict(set)
    for r in rr.itertuples(index=False):
        if r.target in direct_ids:
            direct_refs[r.source].add(r.target)
    papers["direct_resolution_refs_cited"] = papers["paper_id"].map(lambda x: len(direct_refs.get(x, set()))).astype(int)
    papers["inherited_connectome_provenance"] = (
        ~papers["direct_nanoscale_view"]
        & papers["specific_connectome_analysis"]
        & (papers["direct_resolution_refs_cited"] >= 2)
        & ~papers["macroscale_flag"]
    )
    papers["derived_nanoscale_core"] = papers["direct_nanoscale_view"] | papers["inherited_connectome_provenance"]
    papers["high_priority_nanoscale_core"] = papers["derived_nanoscale_core"] & papers["tier"].isin(["core_candidate", "supported"])

    # Keep a broader adjacency diagnostic, but do not use it to establish provenance.
    support = collections.Counter()
    for r in rr.itertuples(index=False):
        if r.source in direct_ids and r.target not in direct_ids:
            support[r.target] += 1
        if r.target in direct_ids and r.source not in direct_ids:
            support[r.source] += 1
    papers["direct_core_graph_links"] = papers["paper_id"].map(support).fillna(0).astype(int)
    papers["graph_supported_adjacent_view"] = (~papers["derived_nanoscale_core"]) & (papers["direct_core_graph_links"] >= 2)

    def bucket(r):
        if r.direct_nanoscale_view:
            return "direct_nanoscale"
        if r.inherited_connectome_provenance:
            return "inherited_connectome_provenance"
        if r.graph_supported_adjacent_view:
            return "graph_supported_adjacent"
        if r.macroscale_flag:
            return "macroscale_review"
        if r.health_flag or r.training_outreach_flag:
            return "bridge_term_review"
        return "low_specificity_review"

    papers["cleanup_bucket"] = papers.apply(bucket, axis=1)
    papers[papers["direct_nanoscale_view"]].sort_values("evidence_score", ascending=False).to_csv(out / "derived_direct_nanoscale_view.csv", index=False)
    papers[papers["inherited_connectome_provenance"]].sort_values(["direct_resolution_refs_cited", "evidence_score"], ascending=False).to_csv(out / "derived_inherited_connectome_provenance.csv", index=False)
    papers[papers["derived_nanoscale_core"]].sort_values("evidence_score", ascending=False).to_csv(out / "derived_nanoscale_core.csv", index=False)
    papers[papers["high_priority_nanoscale_core"]].sort_values("evidence_score", ascending=False).to_csv(out / "derived_high_priority_nanoscale_curriculum_view.csv", index=False)
    papers[papers["graph_supported_adjacent_view"]].sort_values(["direct_core_graph_links", "evidence_score"], ascending=False).to_csv(out / "derived_graph_supported_adjacent_view.csv", index=False)
    papers.sort_values(["cleanup_bucket", "evidence_score"], ascending=[True, False]).to_csv(out / "paper_cleanup_review_queue.csv", index=False)
    papers["cleanup_bucket"].value_counts().rename_axis("bucket").reset_index(name="paper_count").to_csv(out / "paper_cleanup_bucket_counts.csv", index=False)

    # ---- Person reconciliation: blocking only, never name-based auto-merging ----
    people["author_id"] = people["author_id"].astype(str)
    people["normalized_name_exact"] = people["name"].map(norm_name)
    people["normalized_name_block"] = people["name"].map(norm_name_ignore_middle_initials)
    people["axes_set"] = people["axes"].map(split_set)
    id_to_block = dict(zip(people["author_id"], people["normalized_name_block"]))
    co_sets: dict[str, set[str]] = collections.defaultdict(set)
    for r in coedges.itertuples(index=False):
        a, b = str(r.author_1), str(r.author_2)
        na, nb = id_to_block.get(a, ""), id_to_block.get(b, "")
        if nb:
            co_sets[a].add(nb)
        if na:
            co_sets[b].add(na)

    candidates = []
    for block_name, group in people[people["normalized_name_block"].ne("")].groupby("normalized_name_block"):
        if len(group) < 2:
            continue
        rows = group.to_dict("records")
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                aid, bid = str(a["author_id"]), str(b["author_id"])
                ca, cb = co_sets[aid], co_sets[bid]
                shared = len(ca & cb)
                union = len(ca | cb)
                co_j = shared / union if union else 0.0
                aa, ba = a["axes_set"], b["axes_set"]
                ax_j = len(aa & ba) / len(aa | ba) if (aa | ba) else 0.0
                year_values = [a.get("first_relevant_year"), a.get("latest_relevant_year"), b.get("first_relevant_year"), b.get("latest_relevant_year")]
                if all(pd.notna(x) for x in year_values):
                    year_overlap = not (
                        a["latest_relevant_year"] < b["first_relevant_year"]
                        or b["latest_relevant_year"] < a["first_relevant_year"]
                    )
                else:
                    year_overlap = True

                if shared >= 3 and co_j >= 0.20 and year_overlap:
                    classification = "probable_same_person"
                elif shared >= 1 and co_j >= 0.10 and year_overlap:
                    classification = "possible_same_person"
                else:
                    classification = "ambiguous_name_collision"

                candidates.append({
                    "normalized_name_block": block_name,
                    "exact_normalized_name_match": a["normalized_name_exact"] == b["normalized_name_exact"],
                    "author_id_a": aid,
                    "author_id_b": bid,
                    "name_a": a["name"],
                    "name_b": b["name"],
                    "retained_papers_a": a["retained_paper_count"],
                    "retained_papers_b": b["retained_paper_count"],
                    "shared_coauthor_names": shared,
                    "coauthor_jaccard": round(co_j, 6),
                    "axis_jaccard": round(ax_j, 6),
                    "year_overlap": year_overlap,
                    "classification": classification,
                    "recommended_action": "manual_verify_then_merge_alias" if classification == "probable_same_person" else "manual_review",
                })

    cand = pd.DataFrame(candidates)
    if len(cand):
        order = {"probable_same_person": 0, "possible_same_person": 1, "ambiguous_name_collision": 2}
        cand["_order"] = cand["classification"].map(order)
        cand = cand.sort_values(["_order", "shared_coauthor_names", "coauthor_jaccard"], ascending=[True, False, False]).drop(columns="_order")
    cand.to_csv(out / "person_reconciliation_candidates.csv", index=False)
    if len(cand):
        cand["classification"].value_counts().rename_axis("classification").reset_index(name="pair_count").to_csv(out / "person_reconciliation_counts.csv", index=False)

    process = {
        "status": "IA-004 derived post-processing; frozen source corpus unchanged",
        "paper_scope": {
            "direct": "scope_reasons contains direct_scope+resolution",
            "inherited_connectome_provenance": "non-direct + specific connectome-analysis language + >=2 directed citations to direct-resolution papers + no macroscale flag",
            "derived_nanoscale_core": "direct OR inherited_connectome_provenance",
            "note": "The >=2 threshold is an empirical calibration on the frozen run, not a literature-standard cutoff; it must remain reported as such."
        },
        "person_reconciliation": {
            "blocking": "exact normalized name OR normalization that removes only single-letter middle initials",
            "evidence": "coauthor-neighborhood overlap + temporal compatibility; axes retained as descriptive corroboration",
            "merge_policy": "no automatic merge; require reviewed alias decision, preferably corroborated by ORCID/S2/publication evidence",
            "probable_threshold": ">=3 shared normalized coauthor names + coauthor Jaccard >=0.20 + overlapping relevant-year intervals",
            "possible_threshold": ">=1 shared normalized coauthor name + coauthor Jaccard >=0.10 + overlapping relevant-year intervals",
            "note": "Thresholds are local conservative heuristics, not universal literature-standard cutoffs."
        },
        "principles": [
            "Never mutate the preregistered broad corpus; create derived views only.",
            "Never merge people from name equality alone.",
            "Keep source author IDs and first-discovery provenance intact.",
            "Apply approved identity merges only through an auditable alias table."
        ]
    }
    (out / "RECONCILIATION_PROCESS.json").write_text(json.dumps(process, indent=2) + "\n")

    summary = {
        "papers": len(papers),
        "direct_nanoscale": int(papers["direct_nanoscale_view"].sum()),
        "inherited_connectome_provenance": int(papers["inherited_connectome_provenance"].sum()),
        "derived_nanoscale_core": int(papers["derived_nanoscale_core"].sum()),
        "paper_bucket_counts": papers["cleanup_bucket"].value_counts().to_dict(),
        "person_rows": len(people),
        "candidate_pairs": len(cand),
        "person_candidate_counts": cand["classification"].value_counts().to_dict() if len(cand) else {},
        "middle_initial_expanded_pairs": int((~cand["exact_normalized_name_match"]).sum()) if len(cand) else 0,
    }
    (out / "cleanup_reconciliation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
