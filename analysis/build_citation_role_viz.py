#!/usr/bin/env python3
"""Figures (SVG) and consolidated stats for the corpus graph interpretation view."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import pandas as pd

TIER_ORDER = ["core_relevant", "adjacent_relevant", "role_bridge"]
TIER_LABELS = {"core_relevant": "core", "adjacent_relevant": "adjacent", "role_bridge": "bridge"}
STRENGTH_ORDER = ["weak_unlinked", "weak", "moderate", "strong"]
STRENGTH_COLORS = {
    "weak_unlinked": "#c44e52",
    "weak": "#e8956a",
    "moderate": "#8da0cb",
    "strong": "#4c72b0",
}
ROLE_ORDER = ["hub", "broker", "only_in", "only_out", "isolate"]
ROLE_COLORS = ["#4c72b0", "#55a868", "#8172b3", "#ccb974", "#c44e52"]


def parse_dict_cell(value: object) -> dict:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = ast.literal_eval(text)
        return parsed if isinstance(parsed, dict) else {}
    except (SyntaxError, ValueError):
        return {}


def svg_bar_chart(
    categories: list[str],
    series: list[tuple[str, list[float], str]],
    *,
    title: str,
    ylabel: str,
    stacked: bool = False,
    width: int = 720,
    height: int = 400,
) -> str:
    margin = dict(l=70, r=20, t=50, b=60)
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]
    n = len(categories)
    if stacked:
        totals = [sum(s[1][i] for s in series) for i in range(n)]
    else:
        totals = [max(s[1][i] for s in series) for i in range(n)] if series else [1]
    ymax = max(totals) * 1.15 or 1
    bar_w = plot_w / max(n, 1) * 0.65
    gap = plot_w / max(n, 1)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="#fafafa"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" font-weight="600">{title}</text>',
        f'<text x="{margin["l"]-45}" y="{margin["t"]+plot_h/2}" transform="rotate(-90 {margin["l"]-45},{margin["t"]+plot_h/2})" text-anchor="middle" font-family="system-ui,sans-serif" font-size="11">{ylabel}</text>',
        f'<line x1="{margin["l"]}" y1="{margin["t"]+plot_h}" x2="{margin["l"]+plot_w}" y2="{margin["t"]+plot_h}" stroke="#333"/>',
        f'<line x1="{margin["l"]}" y1="{margin["t"]}" x2="{margin["l"]}" y2="{margin["t"]+plot_h}" stroke="#333"/>',
    ]
    for i, cat in enumerate(categories):
        cx = margin["l"] + gap * i + gap / 2
        lines.append(
            f'<text x="{cx}" y="{margin["t"]+plot_h+18}" text-anchor="middle" font-family="system-ui,sans-serif" font-size="11">{cat}</text>'
        )
    if stacked:
        for i in range(n):
            x = margin["l"] + gap * i + (gap - bar_w) / 2
            y_base = margin["t"] + plot_h
            for name, vals, color in series:
                h = plot_h * (vals[i] / ymax)
                y_base -= h
                lines.append(
                    f'<rect x="{x:.1f}" y="{y_base:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}"/>'
                )
    else:
        group_w = bar_w / max(len(series), 1)
        for si, (name, vals, color) in enumerate(series):
            for i, v in enumerate(vals):
                x = margin["l"] + gap * i + (gap - bar_w) / 2 + si * group_w
                h = plot_h * (v / ymax)
                y = margin["t"] + plot_h - h
                lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{group_w*0.9:.1f}" height="{h:.1f}" fill="{color}"/>')
    ly = height - 18
    lx = margin["l"]
    for name, _, color in series:
        lines.append(f'<rect x="{lx}" y="{ly-10}" width="10" height="10" fill="{color}"/>')
        lines.append(
            f'<text x="{lx+14}" y="{ly}" font-family="system-ui,sans-serif" font-size="10">{name}</text>'
        )
        lx += 14 + len(name) * 6 + 16
    lines.append("</svg>")
    return "\n".join(lines)


def svg_hbar(
    labels: list[str],
    segments: list[tuple[str, list[float], str]],
    *,
    title: str,
    xlabel: str,
    width: int = 780,
    height: int = 420,
) -> str:
    margin = dict(l=160, r=20, t=50, b=50)
    n = len(labels)
    row_h = (height - margin["t"] - margin["b"]) / max(n, 1)
    plot_w = width - margin["l"] - margin["r"]
    totals = [sum(seg[1][i] for seg in segments) for i in range(n)]
    xmax = max(totals) * 1.1 or 1
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<rect width="100%" height="100%" fill="#fafafa"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" font-weight="600">{title}</text>',
        f'<text x="{width/2}" y="{height-12}" text-anchor="middle" font-family="system-ui,sans-serif" font-size="11">{xlabel}</text>',
    ]
    for i, lab in enumerate(labels):
        y = margin["t"] + i * row_h + row_h * 0.25
        short = lab.replace(" / ", "\n")[:40]
        lines.append(
            f'<text x="{margin["l"]-8}" y="{y+row_h*0.35}" text-anchor="end" font-family="system-ui,sans-serif" font-size="9">{short.split(chr(10))[0]}</text>'
        )
        x = margin["l"]
        for _, vals, color in segments:
            w = plot_w * (vals[i] / xmax)
            lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{row_h*0.5:.1f}" fill="{color}"/>')
            x += w
    lx = margin["l"]
    ly = height - 32
    for name, _, color in segments:
        lines.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}"/>')
        lines.append(f'<text x="{lx+14}" y="{ly+9}" font-size="10" font-family="system-ui,sans-serif">{name}</text>')
        lx += 60
    lines.append("</svg>")
    return "\n".join(lines)


def plot_tier_ladder(v2v3: dict, out: Path) -> None:
    cats = ["inclusive", "core", "ultra_core"]
    v2 = [
        sum(v2v3["v2_decisions"][k] for k in ("core_relevant", "adjacent_relevant", "role_bridge")),
        v2v3["core_v2"],
        v2v3["ultra_core_v2"],
    ]
    v3 = [
        sum(v2v3["v3_decisions"][k] for k in ("core_relevant", "adjacent_relevant", "role_bridge")),
        v2v3["core_v3"],
        v2v3["ultra_core_v3"],
    ]
    svg = svg_bar_chart(
        cats,
        [("v2", v2, "#8da0cb"), ("v3", v3, "#4c72b0")],
        title="Screening tier ladder (v2 vs v3 agent)",
        ylabel="works",
        stacked=False,
    )
    (out / "01_tier_ladder_v2_v3.svg").write_text(svg)


def plot_link_strength(by_tier: list[dict], out: Path) -> None:
    cats = [TIER_LABELS[t["label"]] for t in by_tier if t["label"] in TIER_ORDER]
    rows = {t["label"]: t for t in by_tier}
    series = [
        (s.replace("_", " "), [rows[l]["citation_link_strength"].get(s, 0) for l in TIER_ORDER], STRENGTH_COLORS[s])
        for s in STRENGTH_ORDER
    ]
    (out / "02_link_strength_by_tier.svg").write_text(
        svg_bar_chart(
            cats,
            series,
            title="Citation link strength by v3 tier (in+out ≤ 2 = weak)",
            ylabel="graph-matched works",
            stacked=True,
        )
    )


def plot_citation_roles(by_tier: list[dict], out: Path) -> None:
    cats = [TIER_LABELS[t["label"]] for t in by_tier if t["label"] in TIER_ORDER]
    rows = {t["label"]: t for t in by_tier}
    series = [
        (r, [rows[l]["citation_roles"].get(r, 0) for l in TIER_ORDER], ROLE_COLORS[i])
        for i, r in enumerate(ROLE_ORDER)
    ]
    (out / "03_citation_roles_by_tier.svg").write_text(
        svg_bar_chart(
            cats,
            series,
            title="Directed citation roles (nanoscale-core graph)",
            ylabel="graph-matched works",
            stacked=True,
        )
    )


def plot_communities(comm_df: pd.DataFrame, out: Path, top_n: int = 8) -> None:
    sub = comm_df.head(top_n)
    labels = [str(x) for x in sub.community_label]
    svg = svg_hbar(
        labels,
        [
            ("core", sub["core"].tolist(), "#4c72b0"),
            ("adjacent", sub["adjacent"].tolist(), "#8da0cb"),
            ("bridge", sub["role_bridge"].tolist(), "#ccb974"),
        ],
        title=f"Top {top_n} coauthor communities (trim_middle)",
        xlabel="works by assigned community",
    )
    (out / "04_top_communities_by_tier.svg").write_text(svg)


def plot_author_trim(analysis: dict, out: Path) -> None:
    cons = analysis["consortium_author_counts"]
    cats = ["excluded\nsingle middle", "consortium\nmiddle kept", "consortium\nmiddle trimmed", "graph\nnodes"]
    vals = [
        analysis["excluded_single_middle_only_persons"],
        cons["consortium_middle_mentions"] - cons["consortium_middle_excluded_single_only"],
        cons["consortium_middle_excluded_single_only"],
        analysis["coauthorship"]["nodes"],
    ]
    colors = ["#c44e52", "#55a868", "#e8956a", "#4c72b0"]
    series = [("count", vals, colors[i]) for i in range(len(cats))]
    # simple grouped as single series with per-bar colors
    svg = svg_bar_chart(
        [c.replace("\n", " ") for c in cats],
        [(str(i), [vals[i] if j == i else 0 for j in range(len(vals))], colors[i]) for i in range(len(vals))],
        title="Author trim: sole middle credit vs consortium",
        ylabel="persons / mentions",
        stacked=False,
    )
    (out / "05_author_trim_and_consortium.svg").write_text(svg)


def build_stats(analysis: dict, v2v3: dict, comm_df: pd.DataFrame) -> dict:
    by_tier = {t["label"]: t for t in analysis["by_tier"]}
    return {
        "interpretation_doc": "postanalysis/llm_agent_v3/CORPUS_GRAPH_VIEW.md",
        "screening": {
            "v2_core": v2v3["core_v2"],
            "v3_core": v2v3["core_v3"],
            "v2_ultra_core": v2v3["ultra_core_v2"],
            "v3_ultra_core": v2v3["ultra_core_v3"],
            "v3_inclusive": analysis["inclusive_works"],
            "core_demotions_v2_to_v3": v2v3["core_demotions"],
        },
        "citation_graph": {
            "graph_matched_rate": analysis["graph_match_rate"],
            "weak_threshold_total_degree": analysis["weak_link_threshold_total_degree"],
            "by_tier": {
                k: {
                    "graph_matched": by_tier[k]["graph_matched"],
                    "median_total_degree": by_tier[k]["median_total_degree"],
                    "median_out_in_ratio": by_tier[k]["median_out_in_ratio"],
                    "weak_unlinked": by_tier[k]["weak_unlinked"],
                    "ultra_core": by_tier[k]["ultra_core"],
                    "citation_link_strength": by_tier[k]["citation_link_strength"],
                }
                for k in TIER_ORDER
            },
        },
        "authorship": {
            "policy": analysis["author_policy"],
            "trim_note": analysis["author_trim_note"],
            "excluded_single_middle_only": analysis["excluded_single_middle_only_persons"],
            "consortium": analysis["consortium_author_counts"],
            "coauthor_nodes": analysis["coauthorship"]["nodes"],
            "coauthor_edges": analysis["coauthorship"]["edges"],
            "communities": analysis["coauthorship"]["communities"],
        },
        "top_communities": comm_df.head(10).to_dict(orient="records"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", type=Path, default=Path("postanalysis/llm_agent_v3/citation_role_analysis.json"))
    ap.add_argument("--v2v3", type=Path, default=Path("postanalysis/llm_agent_v3/v2_v3_comparison.json"))
    ap.add_argument("--communities", type=Path, default=Path("postanalysis/llm_agent_v3/citation_roles_by_community.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/llm_agent_v3/viz"))
    args = ap.parse_args()

    analysis = json.loads(args.analysis.read_text())
    v2v3 = json.loads(args.v2v3.read_text())
    comm = pd.read_csv(args.communities)
    for col in ("citation_roles", "citation_link_strength"):
        if col in comm.columns:
            comm[col] = comm[col].map(parse_dict_cell)
    comm = comm.sort_values("works", ascending=False)

    args.out.mkdir(parents=True, exist_ok=True)
    plot_tier_ladder(v2v3, args.out)
    plot_link_strength(analysis["by_tier"], args.out)
    plot_citation_roles(analysis["by_tier"], args.out)
    plot_communities(comm, args.out)
    plot_author_trim(analysis, args.out)

    stats = build_stats(analysis, v2v3, comm)
    (args.out / "corpus_graph_view_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps({"out": str(args.out), "figures": 5, "stats_path": str(args.out / "corpus_graph_view_stats.json")}, indent=2))


if __name__ == "__main__":
    main()
