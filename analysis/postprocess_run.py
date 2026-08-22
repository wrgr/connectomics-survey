#!/usr/bin/env python3
"""Post-process a completed deterministic connectomics run without mutating source outputs.

Consumes either an extracted outputs directory or a GitHub Actions artifact ZIP and emits
QC summaries, ranking tables, and visualization panels.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import tempfile
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_outputs(artifact: Path | None, outputs_dir: Path | None):
    if outputs_dir:
        return outputs_dir.resolve(), None, None
    if not artifact:
        raise ValueError("Provide --artifact or --outputs-dir")
    tmp = tempfile.TemporaryDirectory(prefix="connectomics_postprocess_")
    root = Path(tmp.name)
    with zipfile.ZipFile(artifact) as z:
        z.extractall(root)
    candidates = list(root.rglob("papers_retained.csv"))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one papers_retained.csv, found {len(candidates)}")
    return candidates[0].parent, tmp, sha256_file(artifact)


def split_counts(series: pd.Series) -> pd.Series:
    counts = collections.Counter()
    for value in series.dropna().astype(str):
        for term in value.split(";"):
            term = term.strip()
            if term:
                counts[term] += 1
    return pd.Series(counts, dtype="int64").sort_values(ascending=False)


def savefig(out: Path, name: str, title: str):
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out / name, dpi=180, bbox_inches="tight")
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", type=Path)
    ap.add_argument("--outputs-dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expected-sha256")
    args = ap.parse_args()

    src, tmp, digest = resolve_outputs(args.artifact, args.outputs_dir)
    if args.expected_sha256 and digest != args.expected_sha256:
        raise RuntimeError(f"Artifact digest mismatch: expected {args.expected_sha256}, got {digest}")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    ret = pd.read_csv(src / "papers_retained.csv", low_memory=False)
    people = pd.read_csv(src / "people.csv", low_memory=False)
    pedges = pd.read_csv(src / "paper_graph_edges.csv")
    coedges = pd.read_csv(src / "coauthor_edges.csv")
    cross = pd.read_csv(src / "crossref_verification.csv")
    health = pd.read_csv(src / "health_bridge.csv")
    training = pd.read_csv(src / "training_outreach.csv")
    coverage = json.loads((src / "coverage_summary.json").read_text())
    manifest = json.loads((src / "manifest.json").read_text())

    ret["year_num"] = pd.to_numeric(ret["year"], errors="coerce")
    ret["is_macroscale"] = ret["macroscale_hits"].notna() & ret["macroscale_hits"].astype(str).str.strip().ne("")
    ret["is_direct_resolution"] = ret["scope_reasons"].fillna("").str.contains("direct_scope\\+resolution", regex=True)
    ret["has_doi"] = ret["doi"].notna() & ret["doi"].astype(str).str.strip().ne("")
    ret["is_health"] = ret["health_hits"].notna() & ret["health_hits"].astype(str).str.strip().ne("")
    ret["is_people_dev"] = ret["people_development_hits"].notna() & ret["people_development_hits"].astype(str).str.strip().ne("")

    axis_counts = pd.Series(coverage["axis_counts"]).sort_values(ascending=False)
    tier_counts = pd.Series(coverage["tier_counts"]).sort_values(ascending=False)
    years = (
        ret.dropna(subset=["year_num"])
        .assign(year=lambda d: d["year_num"].astype(int))
        .groupby("year")
        .agg(
            retained=("paper_id", "count"),
            direct_nanoscale=("is_direct_resolution", "sum"),
            macroscale_flag=("is_macroscale", "sum"),
            health_flag=("is_health", "sum"),
            training_outreach_flag=("is_people_dev", "sum"),
        )
        .reset_index()
    )
    years.to_csv(out / "year_summary.csv", index=False)

    top_papers = ret.sort_values(
        ["evidence_score", "pagerank_percentile", "age_normalized_citation_percentile"], ascending=False
    ).head(100)
    top_papers.to_csv(out / "top_100_papers_by_evidence.csv", index=False)
    top_people = people.sort_values(
        ["core_candidate_paper_count", "retained_paper_count", "axis_breadth", "coauthor_weighted_degree"], ascending=False
    ).head(200)
    top_people.to_csv(out / "top_200_people.csv", index=False)

    health_terms = split_counts(health["health_terms"])
    health_terms.rename_axis("term").reset_index(name="paper_count").to_csv(out / "health_term_counts.csv", index=False)
    training_terms = split_counts(training["people_development_terms"])
    training_terms.rename_axis("term").reset_index(name="paper_count").to_csv(out / "training_outreach_term_counts.csv", index=False)
    cross.groupby("crossref_status", dropna=False).size().rename("count").reset_index().to_csv(out / "crossref_status_summary.csv", index=False)

    plt.figure(figsize=(11, 5.5))
    ys = years[years["year"] >= 1980]
    for col, label in [("retained", "All retained"), ("direct_nanoscale", "Direct + resolution"), ("macroscale_flag", "Macroscale-flagged")]:
        plt.plot(ys["year"], ys[col], label=label)
    plt.xlabel("Publication year")
    plt.ylabel("Retained papers")
    plt.legend()
    savefig(out, "01_corpus_over_time.png", "Retained corpus over time")

    plt.figure(figsize=(10, 6))
    ac = axis_counts.sort_values()
    plt.barh(ac.index, ac.values)
    plt.xlabel("Papers tagged to lexical axis")
    savefig(out, "02_axis_coverage.png", "Coverage by protocol axis")

    plt.figure(figsize=(7, 5))
    plt.bar(tier_counts.index, tier_counts.values)
    plt.ylabel("Papers")
    plt.xticks(rotation=20, ha="right")
    savefig(out, "03_tier_counts.png", "Retained papers by evidence tier")

    scope_rows = pd.DataFrame({
        "category": ["Direct + resolution", "Macroscale flagged", "Health-term flagged", "Training/outreach-term flagged", "Has DOI"],
        "count": [int(ret.is_direct_resolution.sum()), int(ret.is_macroscale.sum()), int(ret.is_health.sum()), int(ret.is_people_dev.sum()), int(ret.has_doi.sum())],
    })
    scope_rows.to_csv(out / "scope_boundary_summary.csv", index=False)
    plt.figure(figsize=(9, 5))
    plt.barh(scope_rows["category"], scope_rows["count"])
    plt.xlabel("Retained papers")
    savefig(out, "04_scope_boundary.png", "Scope-boundary diagnostics")

    plotdf = ret.dropna(subset=["pagerank_percentile", "age_normalized_citation_percentile", "evidence_score"])
    plt.figure(figsize=(8, 6))
    sizes = 10 + 18 * plotdf["evidence_score"].clip(0, 8)
    plt.scatter(plotdf["pagerank_percentile"], plotdf["age_normalized_citation_percentile"], s=sizes, alpha=0.35)
    plt.xlabel("Corpus PageRank percentile")
    plt.ylabel("Age-normalized citation percentile")
    for _, r in plotdf.nlargest(12, "evidence_score").iterrows():
        title = str(r["title"])
        plt.annotate(title[:36] + ("…" if len(title) > 36 else ""), (r["pagerank_percentile"], r["age_normalized_citation_percentile"]), fontsize=7)
    savefig(out, "05_paper_signal_map.png", "Paper influence signals within the retained corpus")

    tp = top_people.head(25).sort_values("core_candidate_paper_count")
    plt.figure(figsize=(10, 8))
    plt.barh(tp["name"], tp["core_candidate_paper_count"])
    plt.xlabel("Core-candidate papers")
    savefig(out, "06_top_people.png", "Top contributors by core-candidate paper count")

    ht = health_terms.head(20).sort_values()
    plt.figure(figsize=(9, 6))
    plt.barh(ht.index, ht.values)
    plt.xlabel("Health-bridge papers")
    savefig(out, "07_health_bridge_terms.png", "Most frequent health-bridge trigger terms")

    tt = training_terms.head(20).sort_values()
    plt.figure(figsize=(9, 6))
    plt.barh(tt.index, tt.values)
    plt.xlabel("Training/outreach papers")
    savefig(out, "08_training_outreach_terms.png", "Most frequent training/outreach trigger terms")

    # Network snapshots are deliberately bounded to readable high-centrality subsets.
    ret_ids = set(ret["paper_id"].astype(str))
    e = pedges[pedges["source"].astype(str).isin(ret_ids) & pedges["target"].astype(str).isin(ret_ids)].copy()
    e["source"] = e["source"].astype(str)
    e["target"] = e["target"].astype(str)
    graph = nx.from_pandas_edgelist(e, "source", "target", create_using=nx.DiGraph())
    pr_map = dict(zip(ret["paper_id"].astype(str), ret["pagerank"].fillna(0)))
    top_nodes = sorted(graph.nodes, key=lambda n: pr_map.get(str(n), 0), reverse=True)[:180]
    sub = graph.subgraph(top_nodes).to_undirected()
    plt.figure(figsize=(11, 9))
    if len(sub):
        pos = nx.spring_layout(sub, seed=7, iterations=75)
        nx.draw_networkx_edges(sub, pos, alpha=0.12, width=0.6)
        nx.draw_networkx_nodes(sub, pos, node_size=[25 + 3500 * pr_map.get(str(n), 0) for n in sub.nodes], alpha=0.72)
    plt.axis("off")
    savefig(out, "09_top_paper_network.png", "High-PageRank retained-paper citation network")

    name_map = dict(zip(people["author_id"].astype(str), people["name"].astype(str)))
    degree_map = dict(zip(people["author_id"].astype(str), people["coauthor_weighted_degree"].fillna(0)))
    top_auth = set(sorted(degree_map, key=degree_map.get, reverse=True)[:140])
    ce = coedges.copy()
    ce["author_1"] = ce["author_1"].astype(str)
    ce["author_2"] = ce["author_2"].astype(str)
    ce = ce[ce["author_1"].isin(top_auth) & ce["author_2"].isin(top_auth)]
    co_graph = nx.from_pandas_edgelist(ce, "author_1", "author_2", edge_attr="weight")
    plt.figure(figsize=(11, 9))
    if len(co_graph):
        pos = nx.spring_layout(co_graph, seed=11, iterations=80, weight="weight")
        nx.draw_networkx_edges(co_graph, pos, alpha=0.12)
        nx.draw_networkx_nodes(co_graph, pos, node_size=[20 + math.sqrt(max(degree_map.get(str(n), 0), 0)) * 7 for n in co_graph.nodes], alpha=0.7)
        labels = {n: name_map.get(str(n), str(n)) for n in sorted(co_graph.nodes, key=lambda n: degree_map.get(str(n), 0), reverse=True)[:18]}
        nx.draw_networkx_labels(co_graph, pos, labels=labels, font_size=7)
    plt.axis("off")
    savefig(out, "10_top_coauthor_network.png", "High-degree coauthor network")

    funding_errors = []
    funding_path = src / "funding_projects.jsonl"
    if funding_path.exists():
        for line in funding_path.read_text().splitlines():
            if line.strip():
                obj = json.loads(line)
                if "_error" in obj:
                    funding_errors.append(obj)

    summary = {
        "artifact_sha256": digest,
        "package_version": manifest.get("package_version"),
        "mode": manifest.get("mode"),
        "retained_papers": len(ret),
        "people_rows": len(people),
        "paper_edges_manifest": coverage.get("paper_edges"),
        "coauthor_edges": len(coedges),
        "direct_plus_resolution_papers": int(ret["is_direct_resolution"].sum()),
        "macroscale_flagged_papers": int(ret["is_macroscale"].sum()),
        "doi_papers": int(ret["has_doi"].sum()),
        "crossref_found": int((cross["crossref_status"] == "found").sum()),
        "health_bridge_papers": len(health),
        "training_outreach_papers": len(training),
        "funding_successful_projects": coverage.get("funding_projects"),
        "funding_error_records": len(funding_errors),
    }
    (out / "postprocess_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if tmp:
        tmp.cleanup()


if __name__ == "__main__":
    main()
