#!/usr/bin/env python3
"""Citation-graph roles and coauthor-community crosswalk for screened works."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_corpus_tiers import (
    LANDMARK_RE,
    build_author_mentions,
    build_coauthorship,
    coauthors_for_paper,
    consortium_middle_stats,
    eligible_coauthor_persons,
    load_person_map,
    parse_authors,
)
from human_review import apply_human_decisions_frame
from manual_seeds import merge_manual_seeds

INCLUSIVE = {"core_relevant", "adjacent_relevant", "role_bridge"}
HUB_IN_DEGREE = 50
WEAK_MAX_TOTAL_DEGREE = 2


def citation_role(in_deg: int, out_deg: int) -> str:
    if in_deg >= HUB_IN_DEGREE:
        return "hub"
    if in_deg == 0 and out_deg == 0:
        return "isolate"
    if in_deg == 0 and out_deg > 0:
        return "only_out"
    if in_deg > 0 and out_deg == 0:
        return "only_in"
    return "broker"


def citation_asymmetry(in_deg: int, out_deg: int) -> float | None:
    """out/in ratio; high values are normal in young or importing subfields."""
    if in_deg <= 0 and out_deg <= 0:
        return None
    if in_deg <= 0:
        return float(out_deg)
    return round(out_deg / in_deg, 3)


def citation_link_strength(in_deg: int, out_deg: int) -> str | None:
    """Corpus citation connectivity strength (directed in+out within nanoscale core)."""
    total = in_deg + out_deg
    if total <= WEAK_MAX_TOTAL_DEGREE:
        if in_deg == 0:
            return "weak_unlinked"
        return "weak"
    if total <= 9:
        return "moderate"
    return "strong"


def ultra_core_row(decision: str, title: str, cites: float) -> bool:
    landmark = bool(LANDMARK_RE.search(str(title or "")))
    return decision == "core_relevant" and (cites >= 200 or (landmark and cites >= 100))


def load_graph(path: Path) -> pd.DataFrame:
    graph = pd.read_csv(path, low_memory=False)
    keep = [
        "paper_id",
        "corpus_in_degree",
        "corpus_out_degree",
        "k_core",
        "pagerank_percentile",
        "component",
        "derived_nanoscale_core",
        "direct_nanoscale_view",
        "graph_supported_adjacent_view",
    ]
    cols = [c for c in keep if c in graph.columns]
    return graph[cols].drop_duplicates("paper_id")


def community_labels(nodes: pd.DataFrame) -> dict[int, str]:
    labels: dict[int, str] = {}
    for comm, sub in nodes.groupby("community_id"):
        if int(comm) < 0:
            continue
        top = sub.sort_values(["works_in_corpus", "weighted_degree"], ascending=False).head(2)
        names = [str(x) for x in top.display_name if pd.notna(x)]
        labels[int(comm)] = " / ".join(names) if names else f"community_{comm}"
    return labels


def assign_work_communities(
    corpus: pd.DataFrame,
    nodes: pd.DataFrame,
    norm_to_person: dict[str, str],
    eligible_persons: set[str],
    *,
    trim_middle: bool,
    consortium_min: int,
) -> pd.Series:
    node_comm = dict(zip(nodes.author_norm.astype(str), nodes.community_id.astype(int)))

    comm_ids: list[int] = []
    for row in corpus.itertuples(index=False):
        scores: Counter[int] = Counter()
        for pid, _, weight in coauthors_for_paper(
            getattr(row, "authors", ""),
            norm_to_person,
            eligible_persons,
            consortium_min=consortium_min,
            trim_middle=trim_middle,
        ):
            comm = node_comm.get(pid, -1)
            if comm >= 0:
                scores[int(comm)] += weight
        comm_ids.append(scores.most_common(1)[0][0] if scores else -1)
    return pd.Series(comm_ids, index=corpus.index, dtype="int64")


def summarize_group(sub: pd.DataFrame, label: str) -> dict[str, Any]:
    total = int(len(sub))
    sub = sub.dropna(subset=["corpus_in_degree"])
    roles = Counter(sub.citation_role) if len(sub) else Counter()
    strength = Counter(sub.citation_link_strength.dropna()) if len(sub) else Counter()
    asym = sub.citation_out_in_ratio.dropna()
    return {
        "label": label,
        "works": total,
        "graph_matched": int(len(sub)),
        "median_in_degree": round(float(sub.corpus_in_degree.median()), 2) if len(sub) else None,
        "median_out_degree": round(float(sub.corpus_out_degree.median()), 2) if len(sub) else None,
        "median_total_degree": round(float(sub.citation_total_degree.median()), 2) if len(sub) else None,
        "median_out_in_ratio": round(float(asym.median()), 3) if len(asym) else None,
        "median_k_core": round(float(sub.k_core.median()), 2) if len(sub) else None,
        "median_pagerank_percentile": round(float(sub.pagerank_percentile.median()), 4)
        if len(sub)
        else None,
        "citation_roles": dict(roles),
        "citation_link_strength": dict(strength),
        "weak_links": int((sub.citation_link_strength == "weak").sum()) if len(sub) else 0,
        "weak_unlinked": int((sub.citation_link_strength == "weak_unlinked").sum()) if len(sub) else 0,
        "ultra_core": int(sub.ultra_core.sum()) if len(sub) else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--results",
        type=Path,
        default=Path("postanalysis/llm_agent_v3/llm_relevance_results.csv"),
    )
    ap.add_argument(
        "--works",
        type=Path,
        default=Path("postanalysis/enriched/canonical_works_enriched.csv"),
    )
    ap.add_argument(
        "--graph",
        type=Path,
        default=Path("postanalysis/cleanup/derived_nanoscale_core.csv"),
    )
    ap.add_argument(
        "--aliases",
        type=Path,
        default=Path("postanalysis/checkpoint/person_aliases.csv"),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("postanalysis/llm_agent_v3"),
    )
    ap.add_argument(
        "--author-policy",
        choices=["all", "trim_middle", "first_last"],
        default="trim_middle",
        help="trim_middle: drop authors whose only corpus credit is one middle-author slot",
    )
    ap.add_argument(
        "--consortium-min-authors",
        type=int,
        default=20,
        help="Treat papers with this many authors as consortium for middle-author exclusion",
    )
    args = ap.parse_args()

    results = pd.read_csv(args.results, low_memory=False)
    works = pd.read_csv(args.works, low_memory=False)
    results, works = merge_manual_seeds(results, works)
    results = apply_human_decisions_frame(results)
    graph = load_graph(args.graph)
    first_last_only = args.author_policy in {"first_last", "trim_middle"}
    trim_middle = first_last_only

    corpus = results[results.decision.isin(INCLUSIVE)].merge(
        works[
            [
                "work_id",
                "canonical_paper_id",
                "authors",
                "title",
                "citation_count_work",
                "year",
                "venue",
            ]
        ],
        on="work_id",
        how="left",
        suffixes=("_res", ""),
    )
    if "title_res" in corpus.columns:
        corpus["title"] = corpus["title"].fillna(corpus["title_res"])

    corpus = corpus.merge(graph, left_on="canonical_paper_id", right_on="paper_id", how="left")
    cites = pd.to_numeric(corpus.citation_count_work, errors="coerce").fillna(0)
    corpus["ultra_core"] = [
        ultra_core_row(d, t, c) for d, t, c in zip(corpus.decision, corpus.title, cites)
    ]

    in_deg = corpus.corpus_in_degree.fillna(-1).astype(int)
    out_deg = corpus.corpus_out_degree.fillna(-1).astype(int)
    corpus["citation_role"] = [
        "no_graph" if i < 0 else citation_role(int(i), int(o))
        for i, o in zip(in_deg, out_deg)
    ]
    corpus["citation_out_in_ratio"] = [
        citation_asymmetry(int(i), int(o)) if i >= 0 else None for i, o in zip(in_deg, out_deg)
    ]
    corpus["citation_total_degree"] = [
        int(i) + int(o) if i >= 0 else None for i, o in zip(in_deg, out_deg)
    ]
    corpus["citation_link_strength"] = [
        citation_link_strength(int(i), int(o)) if i >= 0 else None for i, o in zip(in_deg, out_deg)
    ]

    nodes_df, _, graph_summary = build_coauthorship(
        corpus,
        aliases_path=args.aliases,
        author_policy=args.author_policy,
        consortium_min=args.consortium_min_authors,
    )
    norm_to_person, _ = load_person_map(args.aliases)
    mentions = build_author_mentions(corpus, norm_to_person)
    eligible, excluded_single_middle = (
        eligible_coauthor_persons(mentions)
        if trim_middle
        else ({str(x) for x in mentions.person_id.unique()}, [])
    )
    cons_stats = consortium_middle_stats(
        mentions,
        excluded_single_middle,
        consortium_min=args.consortium_min_authors,
    )
    corpus["primary_community_id"] = assign_work_communities(
        corpus,
        nodes_df,
        norm_to_person,
        eligible,
        trim_middle=trim_middle,
        consortium_min=args.consortium_min_authors,
    )
    labels = community_labels(nodes_df)
    corpus["primary_community_label"] = corpus.primary_community_id.map(
        lambda c: labels.get(int(c), "unassigned") if c >= 0 else "unassigned"
    )
    n_authors = corpus.authors.fillna("").astype(str).apply(lambda s: len(parse_authors(s)))
    corpus["n_authors"] = n_authors
    corpus["is_consortium"] = n_authors >= args.consortium_min_authors
    middle_per_work = (
        mentions[mentions.position == "middle"]
        .groupby("work_id")
        .size()
        .rename("consortium_middle_count")
    )
    corpus = corpus.merge(
        middle_per_work,
        left_on="work_id",
        right_index=True,
        how="left",
    )
    corpus["consortium_middle_count"] = corpus.consortium_middle_count.fillna(0).astype(int)
    corpus.loc[~corpus.is_consortium, "consortium_middle_count"] = 0

    args.out.mkdir(parents=True, exist_ok=True)
    if excluded_single_middle:
        excl = mentions[mentions.person_id.isin(excluded_single_middle)].drop_duplicates("person_id")
        excl[["person_id", "author_raw", "work_id", "author_order", "n_authors", "position"]].to_csv(
            args.out / "excluded_single_middle_authors.csv",
            index=False,
        )
    cons_papers = corpus[corpus.is_consortium][
        ["work_id", "title", "decision", "n_authors", "consortium_middle_count"]
    ].sort_values("n_authors", ascending=False)
    cons_papers.to_csv(args.out / "consortium_papers.csv", index=False)
    work_cols = [
        "work_id",
        "title",
        "decision",
        "confidence",
        "ultra_core",
        "citation_count_work",
        "corpus_in_degree",
        "corpus_out_degree",
        "citation_total_degree",
        "citation_out_in_ratio",
        "citation_link_strength",
        "k_core",
        "pagerank_percentile",
        "n_authors",
        "is_consortium",
        "consortium_middle_count",
        "citation_role",
        "primary_community_id",
        "primary_community_label",
        "authors",
        "year",
        "venue",
    ]
    corpus[work_cols].to_csv(args.out / "citation_roles_by_work.csv", index=False)

    by_tier = [summarize_group(corpus[corpus.decision == d], d) for d in sorted(INCLUSIVE)]
    by_comm_rows: list[dict[str, Any]] = []
    for comm, sub in corpus.groupby("primary_community_id"):
        if int(comm) < 0:
            label = "unassigned"
        else:
            label = labels.get(int(comm), f"community_{comm}")
        row = summarize_group(sub, label)
        row["community_id"] = int(comm)
        row["community_label"] = label
        row["core"] = int((sub.decision == "core_relevant").sum())
        row["adjacent"] = int((sub.decision == "adjacent_relevant").sum())
        row["role_bridge"] = int((sub.decision == "role_bridge").sum())
        by_comm_rows.append(row)
    by_comm = sorted(by_comm_rows, key=lambda r: (-r["works"], r["community_id"]))
    pd.DataFrame(by_comm).to_csv(args.out / "citation_roles_by_community.csv", index=False)

    matched = corpus[corpus.citation_role != "no_graph"]
    cross = pd.crosstab(
        matched.primary_community_label,
        matched.citation_role,
        margins=True,
    )
    summary = {
        "results": str(args.results),
        "graph_source": str(args.graph),
        "author_policy": args.author_policy,
        "consortium_min_authors": args.consortium_min_authors,
        "author_trim_note": (
            "Trim only authors whose sole corpus credit is one middle-author appearance "
            "(including middle on a consortium paper when that is their only inclusion). "
            "Consortium middles with other first/last/middle credit elsewhere are kept."
        ),
        "consortium_author_counts": cons_stats,
        "excluded_single_middle_only_persons": len(excluded_single_middle),
        "citation_graph_note": (
            "Directed citation roles are asymmetric by construction; high out/in is normal. "
            "only_out does not mean peripheral — it often reflects importing methods/reviews. "
            "only_in reflects landmark outputs that others cite without reciprocal in-corpus cites. "
            f"Papers with total in+out <= {WEAK_MAX_TOTAL_DEGREE} in the corpus graph are weak; "
            "weak_unlinked (in=0) are especially weak — cited-back links are absent."
        ),
        "weak_link_threshold_total_degree": WEAK_MAX_TOTAL_DEGREE,
        "inclusive_works": int(len(corpus)),
        "graph_matched_works": int((corpus.citation_role != "no_graph").sum()),
        "graph_match_rate": round((corpus.citation_role != "no_graph").mean(), 4),
        "by_tier": by_tier,
        "by_community": by_comm[:12],
        "community_count": int(corpus[corpus.primary_community_id >= 0].primary_community_id.nunique()),
        "community_labels": {str(k): v for k, v in sorted(labels.items())},
        "role_by_tier_crosstab": pd.crosstab(corpus.decision, corpus.citation_role).to_dict(),
        "link_strength_by_tier": pd.crosstab(
            corpus.decision,
            corpus.citation_link_strength.fillna("no_graph"),
        ).to_dict(),
        "top_communities_role_crosstab": cross.head(12).to_dict(),
        "coauthorship": graph_summary,
    }
    (args.out / "citation_role_analysis.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
