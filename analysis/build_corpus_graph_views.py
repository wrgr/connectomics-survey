#!/usr/bin/env python3
"""Build corpus-graph views: full, prime (legacy), graph-matched, integrated, rescue.

Layer ladder (IA-013):
  A Full                  — v3 inclusive
  B Graph-matched         — full minus no_graph
  C Integrated            — graph-matched minus weak_unlinked
  D Rescue                — no_graph reinstated by ultra / cites>=100 / core∧cites>=50
  C∪D Integrated+rescue   — preferred checkpoint spine when coverage gaps matter

Legacy prime = full minus weak_unlinked (keeps no_graph); retained for audit continuity.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from manual_seeds import merge_seed_works
from analyze_corpus_tiers import (
    build_author_mentions,
    build_coauthorship,
    coauthors_for_paper,
    consortium_middle_stats,
    eligible_coauthor_persons,
    load_person_map,
)
from build_citation_role_viz import (
    ROLE_COLORS,
    ROLE_ORDER,
    STRENGTH_COLORS,
    STRENGTH_ORDER,
    TIER_LABELS,
    TIER_ORDER,
    svg_bar_chart,
    svg_hbar,
)

from human_review import apply_human_decisions_frame

INCLUSIVE = {"core_relevant", "adjacent_relevant", "role_bridge"}

# Coverage rescue (IA-013 Layer D) — independent of corpus citation edges
RESCUE_CITES_HIGH = 100
RESCUE_CORE_CITES_FLOOR = 50


def no_graph_mask(df: pd.DataFrame) -> pd.Series:
    return df.citation_role.fillna("") == "no_graph"


def weak_unlinked_mask(df: pd.DataFrame) -> pd.Series:
    return df.citation_link_strength.fillna("") == "weak_unlinked"


def rescue_mask(df: pd.DataFrame) -> pd.Series:
    """no_graph papers reinstated by ultra OR high external cites OR core floor."""
    ng = no_graph_mask(df)
    cites = pd.to_numeric(df.citation_count_work, errors="coerce").fillna(0)
    ultra = df.ultra_core.fillna(False).astype(bool)
    core = df.decision == "core_relevant"
    return ng & (ultra | (cites >= RESCUE_CITES_HIGH) | (core & (cites >= RESCUE_CORE_CITES_FLOOR)))


def summarize_tier(sub: pd.DataFrame, label: str) -> dict[str, Any]:
    total = int(len(sub))
    matched = sub.dropna(subset=["corpus_in_degree"])
    roles = Counter(matched.citation_role) if len(matched) else Counter()
    strength = Counter(matched.citation_link_strength.dropna()) if len(matched) else Counter()
    asym = matched.citation_out_in_ratio.dropna() if "citation_out_in_ratio" in matched else pd.Series(dtype=float)
    return {
        "label": label,
        "works": total,
        "graph_matched": int(len(matched)),
        "median_in_degree": round(float(matched.corpus_in_degree.median()), 2) if len(matched) else None,
        "median_out_degree": round(float(matched.corpus_out_degree.median()), 2) if len(matched) else None,
        "median_total_degree": round(float(matched.citation_total_degree.median()), 2)
        if len(matched) and "citation_total_degree" in matched
        else None,
        "median_out_in_ratio": round(float(asym.median()), 3) if len(asym) else None,
        "median_k_core": round(float(matched.k_core.median()), 2) if len(matched) else None,
        "citation_roles": dict(roles),
        "citation_link_strength": dict(strength),
        "weak_links": int((matched.citation_link_strength == "weak").sum()) if len(matched) else 0,
        "weak_unlinked": int((matched.citation_link_strength == "weak_unlinked").sum()) if len(matched) else 0,
        "no_graph": int((sub.citation_role == "no_graph").sum()) if "citation_role" in sub else 0,
        "ultra_core": int(sub.ultra_core.sum()) if "ultra_core" in sub else 0,
    }


def community_labels(nodes: pd.DataFrame) -> dict[int, str]:
    labels: dict[int, str] = {}
    for comm, g in nodes.groupby("community_id"):
        if int(comm) < 0:
            continue
        top = g.sort_values(["works_in_corpus", "weighted_degree"], ascending=False).head(2)
        names = [str(x) for x in top.display_name if pd.notna(x)]
        labels[int(comm)] = " / ".join(names) if names else f"community_{comm}"
    return labels


def assign_communities(
    corpus: pd.DataFrame,
    nodes: pd.DataFrame,
    norm_to_person: dict[str, str],
    eligible: set[str],
    *,
    consortium_min: int,
) -> pd.Series:
    node_comm = dict(zip(nodes.author_norm.astype(str), nodes.community_id.astype(int)))
    ids: list[int] = []
    for row in corpus.itertuples(index=False):
        scores: Counter[int] = Counter()
        for pid, _, weight in coauthors_for_paper(
            getattr(row, "authors", ""),
            norm_to_person,
            eligible,
            consortium_min=consortium_min,
            trim_middle=True,
        ):
            comm = node_comm.get(pid, -1)
            if comm >= 0:
                scores[int(comm)] += weight
        ids.append(scores.most_common(1)[0][0] if scores else -1)
    return pd.Series(ids, index=corpus.index, dtype="int64")


def community_table(corpus: pd.DataFrame, labels: dict[int, str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for comm, sub in corpus.groupby("primary_community_id"):
        label = "unassigned" if int(comm) < 0 else labels.get(int(comm), f"community_{comm}")
        row = summarize_tier(sub, label)
        row["community_id"] = int(comm)
        row["community_label"] = label
        row["core"] = int((sub.decision == "core_relevant").sum())
        row["adjacent"] = int((sub.decision == "adjacent_relevant").sum())
        row["role_bridge"] = int((sub.decision == "role_bridge").sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("works", ascending=False)


def build_view(
    corpus: pd.DataFrame,
    *,
    view_name: str,
    aliases: Path,
    consortium_min: int,
) -> dict[str, Any]:
    nodes_df, _, graph_summary = build_coauthorship(
        corpus,
        aliases_path=aliases,
        author_policy="trim_middle",
        consortium_min=consortium_min,
    )
    norm_to_person, _ = load_person_map(aliases)
    mentions = build_author_mentions(corpus, norm_to_person)
    eligible, excluded = eligible_coauthor_persons(mentions)
    cons = consortium_middle_stats(mentions, excluded, consortium_min=consortium_min)
    corpus = corpus.copy()
    corpus["primary_community_id"] = assign_communities(
        corpus, nodes_df, norm_to_person, eligible, consortium_min=consortium_min
    )
    labels = community_labels(nodes_df)
    corpus["primary_community_label"] = corpus.primary_community_id.map(
        lambda c: labels.get(int(c), "unassigned") if c >= 0 else "unassigned"
    )
    by_tier = [summarize_tier(corpus[corpus.decision == d], d) for d in TIER_ORDER]
    by_comm = community_table(corpus, labels)
    return {
        "view": view_name,
        "works": int(len(corpus)),
        "by_tier": by_tier,
        "by_community": by_comm,
        "corpus": corpus,
        "coauthorship": {
            **graph_summary,
            "consortium": cons,
            "excluded_single_middle_only_persons": len(excluded),
        },
        "decision_counts": corpus.decision.value_counts().to_dict(),
        "ultra_core": int(corpus.ultra_core.sum()),
        "link_strength_counts": corpus.citation_link_strength.fillna("no_graph").value_counts().to_dict(),
        "citation_role_counts": corpus.citation_role.value_counts().to_dict(),
    }


def write_view_figures(view: dict[str, Any], out: Path, prefix: str) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    by_tier = view["by_tier"]
    rows = {t["label"]: t for t in by_tier}
    cats = [TIER_LABELS[t] for t in TIER_ORDER]

    series = [
        (
            s.replace("_", " "),
            [rows[l]["citation_link_strength"].get(s, 0) for l in TIER_ORDER],
            STRENGTH_COLORS[s],
        )
        for s in STRENGTH_ORDER
        if any(rows[l]["citation_link_strength"].get(s, 0) for l in TIER_ORDER)
    ]
    if series:
        p = out / f"{prefix}_01_link_strength_by_tier.svg"
        p.write_text(
            svg_bar_chart(
                cats,
                series,
                title=f"{view['view']}: citation link strength by tier",
                ylabel="graph-matched works",
                stacked=True,
            )
        )
        files.append(p.name)

    series = [
        (r, [rows[l]["citation_roles"].get(r, 0) for l in TIER_ORDER], ROLE_COLORS[i])
        for i, r in enumerate(ROLE_ORDER)
    ]
    p = out / f"{prefix}_02_citation_roles_by_tier.svg"
    p.write_text(
        svg_bar_chart(
            cats,
            series,
            title=f"{view['view']}: directed citation roles by tier",
            ylabel="graph-matched works",
            stacked=True,
        )
    )
    files.append(p.name)

    p = out / f"{prefix}_03_tier_counts.svg"
    p.write_text(
        svg_bar_chart(
            cats,
            [
                ("works", [rows[l]["works"] for l in TIER_ORDER], "#4c72b0"),
                ("graph matched", [rows[l]["graph_matched"] for l in TIER_ORDER], "#8da0cb"),
                ("ultra_core", [rows[l]["ultra_core"] for l in TIER_ORDER], "#55a868"),
            ],
            title=f"{view['view']}: works / graph-matched / ultra_core",
            ylabel="count",
        )
    )
    files.append(p.name)

    comm = view["by_community"].head(8)
    if len(comm):
        p = out / f"{prefix}_04_top_communities.svg"
        p.write_text(
            svg_hbar(
                [str(x) for x in comm.community_label],
                [
                    ("core", comm["core"].tolist(), "#4c72b0"),
                    ("adjacent", comm["adjacent"].tolist(), "#8da0cb"),
                    ("bridge", comm["role_bridge"].tolist(), "#ccb974"),
                ],
                title=f"{view['view']}: top coauthor communities",
                xlabel="works",
            )
        )
        files.append(p.name)
    return files


def layer_counts(view: dict[str, Any]) -> list[int]:
    c = view["decision_counts"]
    return [
        view["works"],
        c.get("core_relevant", 0),
        c.get("adjacent_relevant", 0),
        c.get("role_bridge", 0),
        view["ultra_core"],
    ]


def comparison_figure_legacy(full: dict[str, Any], prime: dict[str, Any], out: Path) -> str:
    cats = ["inclusive", "core", "adjacent", "bridge", "ultra_core"]
    name = "00_full_vs_prime_ladder.svg"
    (out / name).write_text(
        svg_bar_chart(
            cats,
            [
                ("full", layer_counts(full), "#8da0cb"),
                ("prime (−weak_unlinked)", layer_counts(prime), "#4c72b0"),
            ],
            title="Full vs legacy prime (drop weak_unlinked; keeps no_graph)",
            ylabel="works",
        )
    )
    return name


def comparison_figure_layers(
    full: dict[str, Any],
    matched: dict[str, Any],
    integrated: dict[str, Any],
    integrated_rescue: dict[str, Any],
    out: Path,
) -> str:
    cats = ["inclusive", "core", "adjacent", "bridge", "ultra_core"]
    name = "00_ia013_layer_ladder.svg"
    (out / name).write_text(
        svg_bar_chart(
            cats,
            [
                ("A full", layer_counts(full), "#8da0cb"),
                ("B matched", layer_counts(matched), "#8172b2"),
                ("C integrated", layer_counts(integrated), "#4c72b0"),
                ("C∪D +rescue", layer_counts(integrated_rescue), "#55a868"),
            ],
            title="IA-013 layer ladder (semantic → matched → integrated → +rescue)",
            ylabel="works",
        )
    )
    return name


def slim_stats(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "view": view["view"],
        "works": view["works"],
        "ultra_core": view["ultra_core"],
        "decision_counts": view["decision_counts"],
        "link_strength_counts": view["link_strength_counts"],
        "citation_role_counts": view["citation_role_counts"],
        "by_tier": view["by_tier"],
        "top_communities": view["by_community"].head(10).to_dict(orient="records"),
        "coauthorship": {
            "nodes": view["coauthorship"].get("nodes"),
            "edges": view["coauthorship"].get("edges"),
            "communities": view["coauthorship"].get("communities"),
            "excluded_single_middle_only_persons": view["coauthorship"].get(
                "excluded_single_middle_only_persons"
            ),
            "consortium": view["coauthorship"].get("consortium"),
        },
    }


def annotate_graph_status(corpus: pd.DataFrame) -> pd.DataFrame:
    """Tag each full inclusive work for layer membership."""
    out = corpus.copy()
    ng = no_graph_mask(out)
    wu = weak_unlinked_mask(out)
    rescued = rescue_mask(out)
    status = []
    for i in range(len(out)):
        if bool(rescued.iloc[i]):
            status.append("rescued_no_graph")
        elif bool(ng.iloc[i]):
            status.append("no_graph")
        elif bool(wu.iloc[i]):
            status.append("weak_unlinked")
        else:
            status.append("integrated")
    out["graph_status"] = status
    out["in_graph_matched"] = ~ng
    out["in_integrated"] = (~ng) & (~wu)
    out["in_rescue"] = rescued
    out["in_integrated_plus_rescue"] = out["in_integrated"] | rescued
    out["in_prime_legacy"] = ~wu
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--roles",
        type=Path,
        default=Path("postanalysis/llm_agent_v3/citation_roles_by_work.csv"),
    )
    ap.add_argument(
        "--works",
        type=Path,
        default=Path("postanalysis/enriched/canonical_works_enriched.csv"),
    )
    ap.add_argument(
        "--v2v3",
        type=Path,
        default=Path("postanalysis/llm_agent_v3/v2_v3_comparison.json"),
    )
    ap.add_argument(
        "--aliases",
        type=Path,
        default=Path("postanalysis/checkpoint/person_aliases.csv"),
    )
    ap.add_argument("--consortium-min-authors", type=int, default=20)
    ap.add_argument("--out", type=Path, default=Path("postanalysis/llm_agent_v3"))
    args = ap.parse_args()

    roles = pd.read_csv(args.roles, low_memory=False)
    works = merge_seed_works(pd.read_csv(args.works, low_memory=False))
    corpus = roles.merge(
        works[["work_id", "authors", "year", "venue"]],
        on="work_id",
        how="left",
        suffixes=("", "_enr"),
    )
    if "authors_enr" in corpus.columns:
        corpus["authors"] = corpus["authors"].fillna(corpus["authors_enr"])
    corpus = apply_human_decisions_frame(corpus)
    corpus = corpus[corpus.decision.isin(INCLUSIVE)].copy()
    corpus = annotate_graph_status(corpus)

    kw = dict(aliases=args.aliases, consortium_min=args.consortium_min_authors)

    full = build_view(corpus, view_name="full", **kw)

    # Legacy prime: drop weak_unlinked only (keeps no_graph)
    dropped_wu = corpus[weak_unlinked_mask(corpus)]
    prime = build_view(corpus[~weak_unlinked_mask(corpus)].copy(), view_name="prime", **kw)

    # IA-013 layers
    matched_df = corpus[~no_graph_mask(corpus)].copy()
    integrated_df = matched_df[~weak_unlinked_mask(matched_df)].copy()
    rescue_df = corpus[rescue_mask(corpus)].copy()
    integrated_rescue_df = corpus[corpus.in_integrated_plus_rescue].copy()
    dropped_no_graph = corpus[no_graph_mask(corpus)]
    no_graph_not_rescued = dropped_no_graph[~rescue_mask(dropped_no_graph)]

    matched = build_view(matched_df, view_name="graph_matched", **kw)
    integrated = build_view(integrated_df, view_name="integrated", **kw)
    integrated_rescue = build_view(integrated_rescue_df, view_name="integrated_plus_rescue", **kw)

    viz = args.out / "viz"
    viz.mkdir(parents=True, exist_ok=True)
    figs = [
        comparison_figure_legacy(full, prime, viz),
        comparison_figure_layers(full, matched, integrated, integrated_rescue, viz),
    ]
    for view, prefix in [
        (full, "full"),
        (prime, "prime"),
        (matched, "matched"),
        (integrated, "integrated"),
        (integrated_rescue, "integrated_rescue"),
    ]:
        figs += write_view_figures(view, viz, prefix)

    # Work lists
    full["corpus"].to_csv(args.out / "corpus_full_works.csv", index=False)
    prime["corpus"].to_csv(args.out / "corpus_prime_works.csv", index=False)
    matched["corpus"].to_csv(args.out / "corpus_graph_matched_works.csv", index=False)
    integrated["corpus"].to_csv(args.out / "corpus_integrated_works.csv", index=False)
    rescue_df.to_csv(args.out / "corpus_rescued_no_graph.csv", index=False)
    integrated_rescue["corpus"].to_csv(args.out / "corpus_integrated_plus_rescue_works.csv", index=False)
    dropped_wu.to_csv(args.out / "corpus_prime_dropped_weak_unlinked.csv", index=False)
    dropped_no_graph.to_csv(args.out / "corpus_dropped_no_graph.csv", index=False)
    no_graph_not_rescued.to_csv(args.out / "corpus_no_graph_not_rescued.csv", index=False)

    full["by_community"].to_csv(args.out / "corpus_full_communities.csv", index=False)
    prime["by_community"].to_csv(args.out / "corpus_prime_communities.csv", index=False)
    matched["by_community"].to_csv(args.out / "corpus_graph_matched_communities.csv", index=False)
    integrated["by_community"].to_csv(args.out / "corpus_integrated_communities.csv", index=False)
    integrated_rescue["by_community"].to_csv(
        args.out / "corpus_integrated_plus_rescue_communities.csv", index=False
    )

    # Review queues
    review_wu_core = corpus[weak_unlinked_mask(corpus) & (corpus.decision == "core_relevant")]
    review_ng_core = no_graph_not_rescued[no_graph_not_rescued.decision == "core_relevant"]
    review_wu_core.to_csv(args.out / "review_queue_weak_unlinked_core.csv", index=False)
    review_ng_core.to_csv(args.out / "review_queue_no_graph_core_unrescued.csv", index=False)

    v2v3 = json.loads(args.v2v3.read_text()) if args.v2v3.exists() else {}
    summary = {
        "definition": {
            "full": "All v3 inclusive works (core + adjacent + role_bridge).",
            "prime": (
                "LEGACY audit cut: full minus weak_unlinked. "
                "Keeps no_graph. Not the preferred 'integrated' definition (IA-013)."
            ),
            "graph_matched": "Full minus no_graph (citation roles / degrees defined).",
            "integrated": (
                "Graph-matched minus weak_unlinked "
                "(in-degree = 0 and in+out ≤ 2). True citation-integrated spine."
            ),
            "rescued_no_graph": (
                f"no_graph reinstated if ultra_core OR cites ≥ {RESCUE_CITES_HIGH} "
                f"OR (core_relevant AND cites ≥ {RESCUE_CORE_CITES_FLOOR}). "
                "Flagged rescued_no_graph — not claimed as graph-integrated."
            ),
            "integrated_plus_rescue": "Integrated ∪ rescued_no_graph (preferred checkpoint when coverage gaps matter).",
            "author_policy": "trim_middle (exclude sole middle-author appearances)",
            "ia": "IA-013",
        },
        "rescue_thresholds": {
            "cites_high": RESCUE_CITES_HIGH,
            "core_cites_floor": RESCUE_CORE_CITES_FLOOR,
        },
        "dropped_weak_unlinked": {
            "works": int(len(dropped_wu)),
            "by_decision": dropped_wu.decision.value_counts().to_dict(),
            "ultra_core_in_dropped": int(dropped_wu.ultra_core.sum()),
        },
        "dropped_no_graph": {
            "works": int(len(dropped_no_graph)),
            "by_decision": dropped_no_graph.decision.value_counts().to_dict(),
            "ultra_core_in_dropped": int(dropped_no_graph.ultra_core.sum()),
            "rescued": int(len(rescue_df)),
            "not_rescued": int(len(no_graph_not_rescued)),
        },
        "review_queues": {
            "weak_unlinked_core": int(len(review_wu_core)),
            "no_graph_core_unrescued": int(len(review_ng_core)),
        },
        "screening_ladder_v2_v3": {
            "core_v2": v2v3.get("core_v2"),
            "core_v3": v2v3.get("core_v3"),
            "ultra_core_v2": v2v3.get("ultra_core_v2"),
            "ultra_core_v3": v2v3.get("ultra_core_v3"),
        },
        "layer_ladder": {
            "full": {"works": full["works"], "core": full["decision_counts"].get("core_relevant"), "ultra": full["ultra_core"]},
            "prime_legacy": {"works": prime["works"], "core": prime["decision_counts"].get("core_relevant"), "ultra": prime["ultra_core"]},
            "graph_matched": {"works": matched["works"], "core": matched["decision_counts"].get("core_relevant"), "ultra": matched["ultra_core"]},
            "integrated": {"works": integrated["works"], "core": integrated["decision_counts"].get("core_relevant"), "ultra": integrated["ultra_core"]},
            "rescued_no_graph": {
                "works": int(len(rescue_df)),
                "core": int((rescue_df.decision == "core_relevant").sum()),
                "ultra": int(rescue_df.ultra_core.sum()),
            },
            "integrated_plus_rescue": {
                "works": integrated_rescue["works"],
                "core": integrated_rescue["decision_counts"].get("core_relevant"),
                "ultra": integrated_rescue["ultra_core"],
            },
        },
        "full": slim_stats(full),
        "prime": slim_stats(prime),
        "graph_matched": slim_stats(matched),
        "integrated": slim_stats(integrated),
        "integrated_plus_rescue": slim_stats(integrated_rescue),
        "figures": figs,
    }
    (args.out / "corpus_graph_views.json").write_text(json.dumps(summary, indent=2) + "\n")
    (viz / "corpus_graph_views_stats.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                "layer_ladder": summary["layer_ladder"],
                "review_queues": summary["review_queues"],
                "figures": figs,
                "out": str(args.out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
