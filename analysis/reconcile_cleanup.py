#!/usr/bin/env python3
"""Create conservative scope-cleanup and person-reconciliation queues.

Nothing in this script mutates or deletes the preregistered broad corpus.
It emits derived views and evidence-scored review candidates.
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
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


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

    # Paper scope cleanup: derived views, never deletions.
    papers["direct_nanoscale_view"] = papers["scope_reasons"].fillna("").str.contains("direct_scope\\+resolution", regex=True)
    papers["macroscale_flag"] = papers["macroscale_hits"].notna() & papers["macroscale_hits"].astype(str).str.strip().ne("")
    papers["health_flag"] = papers["health_hits"].notna() & papers["health_hits"].astype(str).str.strip().ne("")
    papers["training_outreach_flag"] = papers["people_development_hits"].notna() & papers["people_development_hits"].astype(str).str.strip().ne("")
    papers["high_priority_direct_view"] = papers["direct_nanoscale_view"] & papers["tier"].isin(["core_candidate", "supported"])

    retained_ids = set(papers["paper_id"].astype(str))
    direct_ids = set(papers.loc[papers["direct_nanoscale_view"], "paper_id"].astype(str))
    rr = edges[
        edges["source"].astype(str).isin(retained_ids)
        & edges["target"].astype(str).isin(retained_ids)
    ].copy()
    rr["source"] = rr["source"].astype(str)
    rr["target"] = rr["target"].astype(str)
    support = collections.Counter()
    for r in rr.itertuples(index=False):
        if r.source in direct_ids and r.target not in direct_ids:
            support[r.target] += 1
        if r.target in direct_ids and r.source not in direct_ids:
            support[r.source] += 1
    papers["direct_core_graph_links"] = papers["paper_id"].astype(str).map(support).fillna(0).astype(int)
    papers["graph_supported_adjacent_view"] = (~papers["direct_nanoscale_view"]) & (papers["direct_core_graph_links"] >= 2)

    def bucket(r):
        if r.direct_nanoscale_view:
            return "direct_nanoscale"
        if r.graph_supported_adjacent_view:
            return "graph_supported_adjacent"
        if r.macroscale_flag:
            return "macroscale_review"
        if r.health_flag or r.training_outreach_flag:
            return "bridge_term_review"
        return "low_specificity_review"

    papers["cleanup_bucket"] = papers.apply(bucket, axis=1)
    papers[papers["direct_nanoscale_view"]].sort_values("evidence_score", ascending=False).to_csv(out / "derived_direct_nanoscale_view.csv", index=False)
    papers[papers["high_priority_direct_view"]].sort_values("evidence_score", ascending=False).to_csv(out / "derived_high_priority_direct_nanoscale_curriculum_view.csv", index=False)
    papers[papers["graph_supported_adjacent_view"]].sort_values(["direct_core_graph_links", "evidence_score"], ascending=False).to_csv(out / "derived_graph_supported_adjacent_view.csv", index=False)
    papers.sort_values(["cleanup_bucket", "evidence_score"], ascending=[True, False]).to_csv(out / "paper_cleanup_review_queue.csv", index=False)
    papers["cleanup_bucket"].value_counts().rename_axis("bucket").reset_index(name="paper_count").to_csv(out / "paper_cleanup_bucket_counts.csv", index=False)

    # Person reconciliation candidates: name equality generates candidates only.
    people["normalized_name"] = people["name"].map(norm_name)
    people["axes_set"] = people["axes"].map(split_set)
    id_to_norm = dict(zip(people["author_id"].astype(str), people["normalized_name"]))
    co_sets: dict[str, set[str]] = collections.defaultdict(set)
    for r in coedges.itertuples(index=False):
        a, b = str(r.author_1), str(r.author_2)
        na, nb = id_to_norm.get(a, ""), id_to_norm.get(b, "")
        if nb:
            co_sets[a].add(nb)
        if na:
            co_sets[b].add(na)

    candidates = []
    for normalized_name, group in people[people["normalized_name"].ne("")].groupby("normalized_name"):
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
                    "normalized_name": normalized_name,
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
        "principles": [
            "Never mutate the preregistered broad corpus; create derived views only.",
            "Never merge people from name equality alone.",
            "Use exact normalized-name blocking only for candidate generation in v1.",
            "Use coauthor-neighborhood overlap plus temporal overlap as identity evidence.",
            "Require manual/ORCID/S2 profile confirmation before applying any alias merge.",
            "Keep an alias table mapping source author IDs to a canonical person ID; never rewrite source author IDs."
        ],
        "paper_views": {
            "direct_nanoscale": "scope_reasons contains direct_scope+resolution",
            "high_priority_direct": "direct_nanoscale AND tier is core_candidate or supported",
            "graph_supported_adjacent": "not direct_nanoscale AND at least 2 corpus citation edges to direct_nanoscale papers"
        },
        "person_candidate_rules": {
            "probable_same_person": "exact normalized name + >=3 shared normalized coauthor names + coauthor Jaccard >=0.20 + overlapping relevant-year intervals",
            "possible_same_person": "exact normalized name + >=1 shared normalized coauthor name + coauthor Jaccard >=0.10 + overlapping relevant-year intervals",
            "ambiguous_name_collision": "same normalized name but insufficient relational evidence"
        },
        "next_manual_fields": ["decision", "canonical_person_id", "evidence_url_or_identifier", "reviewer", "review_date", "notes"]
    }
    (out / "RECONCILIATION_PROCESS.json").write_text(json.dumps(process, indent=2) + "\n")

    summary = {
        "papers": len(papers),
        "paper_bucket_counts": papers["cleanup_bucket"].value_counts().to_dict(),
        "person_rows": len(people),
        "candidate_pairs": len(cand),
        "person_candidate_counts": cand["classification"].value_counts().to_dict() if len(cand) else {}
    }
    (out / "cleanup_reconciliation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
