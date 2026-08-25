#!/usr/bin/env python3
"""Build D3 graph_data.json for checkpoint authorship and paper networks."""
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


def parse_authors(value: Any) -> list[str]:
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()
    if not text or text.lower() == "nan":
        return []
    out: list[str] = []
    for part in re.split(r"[;|]", text):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            toks = [t.strip() for t in part.split(",") if t.strip()]
            name = f"{toks[0]}, {' '.join(toks[1:])}".strip(", ") if len(toks) >= 2 else toks[0]
        else:
            name = re.sub(r"\s+", " ", part)
        out.append(name)
    return out


def norm_author(name: str) -> str:
    name = re.sub(r"\s+", " ", name.strip()).strip(" .")
    toks = name.replace(",", " ").split()
    if not toks:
        return ""
    surname = toks[-1].lower().strip(".")
    given_initials = "".join(t[0].lower() for t in toks[:-1] if t)
    return f"{surname}|{given_initials}" if surname else ""


def parse_labels(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except (SyntaxError, ValueError):
        return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=Path("postanalysis/checkpoint/corpus_inclusive_labeled.csv"))
    ap.add_argument("--nodes", type=Path, default=Path("postanalysis/checkpoint/coauthorship_nodes.csv"))
    ap.add_argument("--edges", type=Path, default=Path("postanalysis/checkpoint/coauthorship_edges.csv"))
    ap.add_argument("--aliases", type=Path, default=Path("postanalysis/checkpoint/person_aliases.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/checkpoint/viz/graph_data.json"))
    ap.add_argument("--top-authors", type=int, default=100)
    ap.add_argument("--top-papers", type=int, default=120)
    ap.add_argument("--min-shared-works", type=int, default=2)
    ap.add_argument("--min-shared-authors", type=int, default=2)
    args = ap.parse_args()

    corpus = pd.read_csv(args.corpus, low_memory=False)
    nodes = pd.read_csv(args.nodes, low_memory=False)
    edges = pd.read_csv(args.edges, low_memory=False)

    norm_to_person: dict[str, str] = {}
    person_label: dict[str, str] = {}
    if args.aliases.exists():
        aliases = pd.read_csv(args.aliases, low_memory=False)
        norm_to_person = {
            str(k).lower(): str(v)
            for k, v in zip(aliases.author_norm.astype(str), aliases.person_id.astype(str))
        }
        person_label = dict(zip(aliases.person_id.astype(str), aliases.person_display_name.astype(str)))

    nodes = nodes.copy()
    if norm_to_person and not nodes.author_norm.astype(str).str.startswith("person:").all():
        nodes["person_id"] = nodes.author_norm.astype(str).str.lower().map(lambda n: norm_to_person.get(n, f"person:{n}"))
    else:
        nodes["person_id"] = nodes.author_norm.astype(str)
    nodes["label"] = nodes["person_id"].map(lambda p: person_label.get(p, ""))
    missing = nodes["label"].eq("")
    nodes.loc[missing, "label"] = nodes.loc[missing, "display_name"]

    agg = (
        nodes.groupby("person_id", as_index=False)
        .agg(
            works_in_corpus=("works_in_corpus", "sum"),
            weighted_degree=("weighted_degree", "sum"),
            community_id=("community_id", "first"),
            label=("label", "first"),
        )
        .sort_values(["works_in_corpus", "weighted_degree"], ascending=False)
    )
    top_people = set(agg.head(args.top_authors)["person_id"])

    edges = edges.copy()
    if norm_to_person and not edges.author_a.astype(str).str.startswith("person:").all():
        edges["person_a"] = edges.author_a.astype(str).str.lower().map(lambda n: norm_to_person.get(n, f"person:{n}"))
        edges["person_b"] = edges.author_b.astype(str).str.lower().map(lambda n: norm_to_person.get(n, f"person:{n}"))
    else:
        edges["person_a"] = edges.author_a.astype(str)
        edges["person_b"] = edges.author_b.astype(str)

    edge_w: Counter[tuple[str, str]] = Counter()
    for row in edges.itertuples(index=False):
        a, b = sorted((row.person_a, row.person_b))
        if a == b or a not in top_people or b not in top_people:
            continue
        edge_w[(a, b)] += int(row.shared_works)

    author_nodes = []
    comm_map = dict(zip(agg.person_id, agg.community_id))
    for row in agg.head(args.top_authors).itertuples(index=False):
        author_nodes.append({
            "id": row.person_id,
            "label": row.label,
            "works": int(row.works_in_corpus),
            "group": int(row.community_id) if pd.notna(row.community_id) else -1,
        })

    author_links = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in sorted(edge_w.items(), key=lambda x: -x[1])
        if w >= args.min_shared_works
    ]

    # Paper subgraph
    paper_rows = corpus[
        corpus.curriculum_labels.fillna("[]").astype(str).str.contains("field_defining|core_methods", regex=True)
    ].copy()
    paper_rows["label_primary"] = paper_rows.curriculum_labels.map(
        lambda xs: "field_defining" if "field_defining" in parse_labels(xs) else "core_methods"
    )
    paper_rows = paper_rows.sort_values(["citation_count_work", "confidence"], ascending=False).head(args.top_papers)

    # Build paper-paper edges via shared reconciled authors
    selected = set(paper_rows.work_id.astype(str))
    paper_people: dict[str, set[str]] = {}
    for row in paper_rows.itertuples(index=False):
        wid = str(row.work_id)
        norms = [norm_author(a) for a in parse_authors(getattr(row, "authors", ""))]
        paper_people[wid] = {norm_to_person.get(n, f"person:{n}") for n in norms if n}

    pp_edge_w: Counter[tuple[str, str]] = Counter()
    wids = list(paper_people.keys())
    for i, a in enumerate(wids):
        pa = paper_people[a]
        for b in wids[i + 1:]:
            shared = len(pa & paper_people[b])
            if shared >= args.min_shared_authors:
                pp_edge_w[tuple(sorted((a, b)))] = shared

    paper_nodes = []
    for row in paper_rows.itertuples(index=False):
        wid = str(row.work_id)
        labels = parse_labels(getattr(row, "curriculum_labels", []))
        group = "field_defining" if "field_defining" in labels else "core_methods"
        paper_nodes.append({
            "id": wid,
            "label": str(getattr(row, "title", wid))[:80],
            "year": int(row.year) if pd.notna(getattr(row, "year", None)) else None,
            "citations": int(row.citation_count_work) if pd.notna(getattr(row, "citation_count_work", None)) else 0,
            "authors": len(paper_people.get(wid, set())),
            "tier": str(getattr(row, "analysis_tier", getattr(row, "decision", ""))),
            "group": group,
        })

    paper_links = [{"source": a, "target": b, "weight": w} for (a, b), w in pp_edge_w.items()]

    payload = {
        "meta": {
            "top_authors": args.top_authors,
            "top_papers": args.top_papers,
            "min_shared_works": args.min_shared_works,
            "min_shared_authors": args.min_shared_authors,
            "reconciled": args.aliases.exists(),
        },
        "author": {"nodes": author_nodes, "links": author_links},
        "paper": {"nodes": paper_nodes, "links": paper_links},
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({
        "author_nodes": len(author_nodes),
        "author_links": len(author_links),
        "paper_nodes": len(paper_nodes),
        "paper_links": len(paper_links),
        "out": str(args.out),
    }, indent=2))


if __name__ == "__main__":
    main()
