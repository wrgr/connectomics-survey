#!/usr/bin/env python3
"""Export ranked ultra/core paper lists and PNG figures for offline review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REF_YEAR = 2026


def short_title(text: object, n: int = 72) -> str:
    s = "" if pd.isna(text) else str(text).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def last_author(authors: object) -> str:
    text = "" if pd.isna(authors) else str(authors).strip()
    if not text:
        return ""
    parts = [p.strip() for p in text.split(";") if p.strip()]
    return parts[-1] if parts else ""


def cites_per_year(row: pd.Series) -> float | None:
    year = row.get("year")
    cites = row.get("citation_count_work")
    if pd.isna(year) or pd.isna(cites):
        return None
    age = max(1.0, float(REF_YEAR) - float(year) + 1.0)
    return round(float(cites) / age, 2)


def rank_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["cites_per_year"] = out.apply(cites_per_year, axis=1)
    out["last_author"] = out["authors"].map(last_author) if "authors" in out.columns else ""
    out = out.sort_values(
        ["citation_count_work", "cites_per_year", "year"],
        ascending=[False, False, True],
        na_position="last",
    ).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out


EXPORT_COLS = [
    "rank",
    "work_id",
    "title",
    "year",
    "venue",
    "last_author",
    "citation_count_work",
    "cites_per_year",
    "ultra_core",
    "citation_link_strength",
    "citation_role",
    "corpus_in_degree",
    "corpus_out_degree",
    "citation_total_degree",
    "k_core",
    "pagerank_percentile",
    "primary_community_label",
    "confidence",
    "n_authors",
    "is_consortium",
]


def export_lists(corpus: pd.DataFrame, out: Path) -> dict[str, int]:
    core = corpus[corpus.decision == "core_relevant"].copy()
    ultra = core[core.ultra_core.fillna(False).astype(bool)].copy()
    core_r = rank_frame(core)
    ultra_r = rank_frame(ultra)

    for frame, name in (
        (ultra_r, "label_ultra_core_ranked.csv"),
        (core_r, "label_core_ranked.csv"),
        (core_r[core_r.ultra_core.fillna(False).astype(bool) == False], "label_core_non_ultra_ranked.csv"),
    ):
        cols = [c for c in EXPORT_COLS if c in frame.columns]
        frame[cols].to_csv(out / name, index=False)

    # Keep legacy ultra file in sync (minimal columns)
    ultra_legacy = ultra_r.copy()
    if "decision" not in ultra_legacy.columns:
        ultra_legacy["decision"] = "core_relevant"
    ultra_legacy[
        ["work_id", "title", "citation_count_work", "decision", "confidence"]
    ].to_csv(out / "label_ultra_core.csv", index=False)

    # Top papers across inclusive (by cites) and top core non-ultra
    inclusive = rank_frame(corpus.copy())
    top_inclusive = inclusive.head(50)
    top_inclusive[[c for c in EXPORT_COLS if c in top_inclusive.columns]].to_csv(
        out / "label_top50_inclusive_by_cites.csv", index=False
    )

    return {
        "ultra": len(ultra_r),
        "core": len(core_r),
        "core_non_ultra": int((~core_r.ultra_core.fillna(False).astype(bool)).sum()),
        "inclusive": len(corpus),
    }


def style_ax(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle="--")


def _view_counts(view: dict) -> list[int]:
    return [
        view["works"],
        view["decision_counts"].get("core_relevant", 0),
        view["decision_counts"].get("adjacent_relevant", 0),
        view["decision_counts"].get("role_bridge", 0),
        view["ultra_core"],
    ]


def fig_ladder(views: dict, path: Path) -> None:
    """IA-013 preferred ladder: full → integrated → integrated+rescue."""
    full = views["full"]
    integrated = views["integrated"]
    rescued = views["integrated_plus_rescue"]
    cats = ["inclusive", "core", "adjacent", "bridge", "ultra"]
    series = [
        ("full", _view_counts(full), "#8da0cb"),
        ("integrated (−no_graph −weak_unlinked)", _view_counts(integrated), "#4c72b0"),
        ("integrated+rescue", _view_counts(rescued), "#55a868"),
    ]
    x = np.arange(len(cats))
    n = len(series)
    w = 0.24
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    for i, (label, vals, color) in enumerate(series):
        offset = (i - (n - 1) / 2) * w
        bars = ax.bar(x + offset, vals, w, label=label, color=color)
        for bar, val in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                val + 10,
                str(val),
                ha="center",
                va="bottom",
                fontsize=7,
            )
    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel("works")
    ax.set_title("IA-013 layer ladder (full → integrated → +rescue)")
    ax.legend(frameon=False, fontsize=8)
    style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_link_strength(corpus: pd.DataFrame, path: Path) -> None:
    order = ["weak_unlinked", "weak", "moderate", "strong", "no_graph"]
    colors = {
        "weak_unlinked": "#c44e52",
        "weak": "#ccb974",
        "moderate": "#4c72b0",
        "strong": "#55a868",
        "no_graph": "#8172b2",
    }
    tiers = ["core_relevant", "adjacent_relevant", "role_bridge"]
    labels = ["core", "adjacent", "bridge"]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    bottoms = np.zeros(len(tiers))
    for strength in order:
        vals = []
        for tier in tiers:
            sub = corpus[corpus.decision == tier]
            if strength == "no_graph":
                vals.append(int((sub.citation_role == "no_graph").sum()))
            else:
                vals.append(int((sub.citation_link_strength == strength).sum()))
        ax.bar(labels, vals, bottom=bottoms, label=strength, color=colors[strength])
        bottoms = bottoms + np.array(vals, dtype=float)
    ax.set_ylabel("works")
    ax.set_title("Citation link strength by tier (full view)")
    ax.legend(frameon=False, ncol=3, fontsize=8, loc="upper right")
    style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_roles(corpus: pd.DataFrame, path: Path) -> None:
    roles = ["hub", "broker", "only_out", "only_in", "isolate", "no_graph"]
    colors = ["#55a868", "#4c72b0", "#ccb974", "#8172b2", "#c44e52", "#999999"]
    tiers = ["core_relevant", "adjacent_relevant", "role_bridge"]
    labels = ["core", "adjacent", "bridge"]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    bottoms = np.zeros(len(tiers))
    for role, color in zip(roles, colors):
        vals = [int((corpus[corpus.decision == t].citation_role == role).sum()) for t in tiers]
        ax.bar(labels, vals, bottom=bottoms, label=role, color=color)
        bottoms = bottoms + np.array(vals, dtype=float)
    ax.set_ylabel("works")
    ax.set_title("Directed citation roles by tier (full view)")
    ax.legend(frameon=False, ncol=3, fontsize=8)
    style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_people(people_csv: Path, path: Path, title: str) -> None:
    df = pd.read_csv(people_csv).head(20)
    fig, ax = plt.subplots(figsize=(8.5, 6.2))
    y = np.arange(len(df))[::-1]
    ax.barh(y, df.works, color="#4c72b0", label="works")
    ax.barh(y, df.last, color="#55a868", height=0.45, label="last-author")
    ax.set_yticks(y)
    ax.set_yticklabels(df.display_name.tolist(), fontsize=8)
    ax.set_xlabel("count")
    ax.set_title(title)
    ax.legend(frameon=False, loc="lower right")
    style_ax(ax)
    ax.grid(axis="x", alpha=0.25, linestyle="--")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_top_papers(df: pd.DataFrame, path: Path, title: str, n: int = 25) -> None:
    top = df.head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.2, 8.0))
    labels = [
        f"{short_title(t, 48)} ({int(y) if pd.notna(y) else '?'})"
        for t, y in zip(top.title, top.year)
    ]
    colors = ["#55a868" if bool(u) else "#4c72b0" for u in top.ultra_core]
    ax.barh(np.arange(len(top)), top.citation_count_work, color=colors)
    ax.set_yticks(np.arange(len(top)))
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlabel("citations")
    ax.set_title(title)
    from matplotlib.patches import Patch

    ax.legend(
        handles=[
            Patch(facecolor="#55a868", label="ultra_core"),
            Patch(facecolor="#4c72b0", label="core (non-ultra)"),
        ],
        frameon=False,
        loc="lower right",
    )
    style_ax(ax)
    ax.grid(axis="x", alpha=0.25, linestyle="--")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_year_hist(core: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    years = core.year.dropna().astype(int)
    ultra_years = core[core.ultra_core.fillna(False).astype(bool)].year.dropna().astype(int)
    bins = range(int(years.min()), int(years.max()) + 2)
    ax.hist(years, bins=bins, color="#8da0cb", label=f"core (n={len(core)})", edgecolor="white")
    ax.hist(
        ultra_years,
        bins=bins,
        color="#55a868",
        label=f"ultra_core (n={len(ultra_years)})",
        edgecolor="white",
    )
    ax.set_xlabel("year")
    ax.set_ylabel("papers")
    ax.set_title("Core vs ultra-core by publication year")
    ax.legend(frameon=False)
    style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_degree_scatter(core: pd.DataFrame, path: Path) -> None:
    matched = core.dropna(subset=["corpus_in_degree", "corpus_out_degree"])
    fig, ax = plt.subplots(figsize=(6.8, 5.6))
    non = matched[~matched.ultra_core.fillna(False).astype(bool)]
    ult = matched[matched.ultra_core.fillna(False).astype(bool)]
    ax.scatter(
        non.corpus_out_degree,
        non.corpus_in_degree,
        s=18,
        alpha=0.45,
        c="#4c72b0",
        label="core",
        edgecolors="none",
    )
    ax.scatter(
        ult.corpus_out_degree,
        ult.corpus_in_degree,
        s=42,
        alpha=0.85,
        c="#55a868",
        label="ultra_core",
        edgecolors="white",
        linewidths=0.4,
    )
    ax.set_xlabel("corpus out-degree (cites within corpus)")
    ax.set_ylabel("corpus in-degree (cited by corpus)")
    ax.set_title("Core citation graph position (asymmetric)")
    ax.legend(frameon=False)
    style_ax(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_communities(views: dict, path: Path, view_key: str = "integrated_plus_rescue") -> None:
    rows = views[view_key]["top_communities"][:10]
    labels = [short_title(r["community_label"], 36) for r in rows][::-1]
    core = [r["core"] for r in rows][::-1]
    adj = [r["adjacent"] for r in rows][::-1]
    bridge = [r.get("role_bridge", r.get("bridge", 0)) for r in rows][::-1]
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    ax.barh(y, core, color="#4c72b0", label="core")
    ax.barh(y, adj, left=core, color="#8da0cb", label="adjacent")
    left2 = np.array(core) + np.array(adj)
    ax.barh(y, bridge, left=left2, color="#ccb974", label="bridge")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("works")
    title_map = {
        "integrated": "Top coauthor communities (integrated)",
        "integrated_plus_rescue": "Top coauthor communities (integrated+rescue)",
        "prime": "Top coauthor communities (legacy prime)",
    }
    ax.set_title(title_map.get(view_key, f"Top coauthor communities ({view_key})"))
    ax.legend(frameon=False, loc="lower right")
    style_ax(ax)
    ax.grid(axis="x", alpha=0.25, linestyle="--")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("postanalysis/llm_agent_v3"))
    args = ap.parse_args()
    out = args.out
    viz = out / "viz" / "figures"
    viz.mkdir(parents=True, exist_ok=True)

    corpus = pd.read_csv(out / "corpus_full_works.csv", low_memory=False)
    if "decision" not in corpus.columns:
        raise SystemExit("corpus_full_works.csv missing decision")
    views = json.loads((out / "corpus_graph_views.json").read_text())

    counts = export_lists(corpus, out)
    core = corpus[corpus.decision == "core_relevant"].copy()
    core_r = rank_frame(core)

    fig_ladder(views, viz / "01_ia013_layer_ladder.png")
    # Keep legacy filename as a copy alias for older markdown links.
    fig_ladder(views, viz / "01_full_vs_prime_ladder.png")
    fig_link_strength(corpus, viz / "02_link_strength_by_tier.png")
    fig_roles(corpus, viz / "03_citation_roles_by_tier.png")
    fig_communities(
        views,
        viz / "04_top_communities_integrated_plus_rescue.png",
        view_key="integrated_plus_rescue",
    )
    fig_communities(
        views,
        viz / "04_top_communities_prime.png",
        view_key="integrated_plus_rescue",
    )
    fig_year_hist(core_r, viz / "05_core_ultra_by_year.png")
    fig_degree_scatter(core_r, viz / "06_core_in_out_degree.png")
    fig_top_papers(
        core_r,
        viz / "07_top25_core_by_cites.png",
        "Top 25 core papers by citations (ultra highlighted)",
        n=25,
    )
    fig_people(
        out / "people_full_top100.csv",
        viz / "08_top20_people_full.png",
        "Top 20 people — full corpus (works vs last-author)",
    )
    rescue_people = out / "people_integrated_plus_rescue_top100.csv"
    if not rescue_people.exists():
        rescue_people = out / "people_prime_top100.csv"
    fig_people(
        rescue_people,
        viz / "09_top20_people_integrated_plus_rescue.png",
        "Top 20 people — integrated+rescue (works vs last-author)",
    )
    fig_people(
        rescue_people,
        viz / "09_top20_people_prime.png",
        "Top 20 people — integrated+rescue (works vs last-author)",
    )

    # Ultra-only bar for quick reference
    ultra_r = rank_frame(core[core.ultra_core.fillna(False).astype(bool)].copy())
    fig_top_papers(
        ultra_r.assign(ultra_core=True),
        viz / "10_ultra_core_all_by_cites.png",
        f"All ultra-core papers by citations (n={len(ultra_r)})",
        n=len(ultra_r),
    )

    manifest = {
        "lists": {
            "label_ultra_core_ranked.csv": counts["ultra"],
            "label_core_ranked.csv": counts["core"],
            "label_core_non_ultra_ranked.csv": counts["core_non_ultra"],
            "label_top50_inclusive_by_cites.csv": 50,
            "label_ultra_core.csv": counts["ultra"],
        },
        "figures": sorted(p.name for p in viz.glob("*.png")),
        "counts": counts,
    }
    (viz / "figures_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
