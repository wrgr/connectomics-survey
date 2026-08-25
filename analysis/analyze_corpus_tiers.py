#!/usr/bin/env python3
"""Tier splits, curatorial labels, and coauthorship graph for the checkpoint corpus."""
from __future__ import annotations
import argparse, ast, json, re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import networkx as nx
import pandas as pd

METHOD_ROLES = {
    "acquisition_preparation", "reconstruction_segmentation", "synapse_inference",
    "proofreading_qc", "infrastructure",
}
LANDMARK_RE = re.compile(
    r"(whole[- ]brain|petascale|first (complete )?connectome|wiring diagram of|"
    r"flywire|hemibrain|fafb|h01|microns|c\. elegans connectome|complete connectome|"
    r"millimetre-scale|mm3|cubic millimeter)",
    re.I,
)
STUDENT_RE = re.compile(
    r"(review|survey|primer|introduction|tutorial|tool|software|open[- ]source|"
    r"perspective|guide|course|undergraduate|training)",
    re.I,
)


def parse_roles(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        return [str(x) for x in parsed] if isinstance(parsed, list) else [text]
    except (SyntaxError, ValueError):
        return [text.strip("[]'\"")]


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


def author_slot(order: int, n_authors: int) -> str:
    if n_authors <= 1:
        return "single"
    if order == 1:
        return "first"
    if order == n_authors:
        return "last"
    return "middle"


POSITION_WEIGHT = {"first": 3, "last": 2, "single": 3, "middle": 1}


def build_author_mentions(
    corpus: pd.DataFrame,
    norm_to_person: dict[str, str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in corpus.itertuples(index=False):
        work_id = str(getattr(row, "work_id", ""))
        authors = parse_authors(getattr(row, "authors", ""))
        n_authors = len(authors)
        for order, author in enumerate(authors, start=1):
            n = norm_author(author)
            if not n:
                continue
            slot = author_slot(order, n_authors)
            rows.append(
                {
                    "work_id": work_id,
                    "author_raw": author,
                    "author_norm": n,
                    "person_id": person_key(n, norm_to_person),
                    "author_order": order,
                    "n_authors": n_authors,
                    "position": slot,
                }
            )
    return pd.DataFrame(rows)


def eligible_coauthor_persons(
    mentions: pd.DataFrame,
) -> tuple[set[str], list[str]]:
    """Drop authors whose only corpus credit is a single middle-author appearance."""
    eligible: set[str] = set()
    excluded: list[str] = []
    for pid, group in mentions.groupby("person_id"):
        slots = set(group.position)
        n_works = int(group.work_id.nunique())
        if slots & {"first", "last", "single"}:
            eligible.add(str(pid))
            continue
        if n_works == 1 and slots <= {"middle"}:
            excluded.append(str(pid))
            continue
        eligible.add(str(pid))
    return eligible, excluded


def consortium_middle_stats(
    mentions: pd.DataFrame,
    excluded_persons: list[str],
    *,
    consortium_min: int = 20,
) -> dict[str, int]:
    """Count consortium scale; report middle slots excluded as single-only appearances."""
    if mentions.empty:
        return {
            "consortium_papers": 0,
            "consortium_middle_mentions": 0,
            "consortium_middle_unique_persons": 0,
            "consortium_first_last_mentions": 0,
            "consortium_middle_excluded_single_only": 0,
        }
    is_consortium = mentions.n_authors >= consortium_min
    cons = mentions[is_consortium]
    middle = cons[cons.position == "middle"]
    fl = cons[cons.position.isin(["first", "last", "single"])]
    excluded_set = set(excluded_persons)
    middle_excl = middle[middle.person_id.isin(excluded_set)]
    return {
        "consortium_papers": int(cons.work_id.nunique()),
        "consortium_middle_mentions": int(len(middle)),
        "consortium_middle_unique_persons": int(middle.person_id.nunique()),
        "consortium_first_last_mentions": int(len(fl)),
        "consortium_middle_excluded_single_only": int(len(middle_excl)),
    }


def coauthors_for_paper(
    authors_value: Any,
    norm_to_person: dict[str, str],
    eligible_persons: set[str],
    *,
    consortium_min: int = 20,
    trim_middle: bool = False,
) -> list[tuple[str, str, int]]:
    """Return (person_id, position, weight) for graph/community use on one work.

    trim_middle policy:
    - exclude authors whose only corpus credit is one middle-author appearance
      (includes middle on a consortium paper when that is their sole inclusion)
    - otherwise keep all positions including consortium middles with repeat credit
    """
    authors = parse_authors(authors_value)
    n_authors = len(authors)
    out: list[tuple[str, str, int]] = []
    for order, author in enumerate(authors, start=1):
        n = norm_author(author)
        if not n:
            continue
        pid = person_key(n, norm_to_person)
        slot = author_slot(order, n_authors)
        if trim_middle and pid not in eligible_persons:
            continue
        out.append((pid, slot, POSITION_WEIGHT[slot]))
    return out


def assign_labels(row: pd.Series) -> list[str]:
    roles = set(parse_roles(row.get("roles")))
    title = str(row.get("title") or "")
    ptypes = str(row.get("publication_types") or "")
    cites = float(row.get("citation_count_work") or 0)
    decision = str(row.get("decision") or "")
    conf = float(row.get("confidence") or 0)
    labels: list[str] = []

    landmark = bool(LANDMARK_RE.search(title))
    # field_defining: high-impact core only (IA-007 decisions + cites/landmark heuristics).
    # Ultra-core can later tighten further (e.g. cites≥200 or landmark∩cites≥100).
    if decision == "core_relevant" and (
        cites >= 100 or (cites >= 40 and landmark)
    ):
        labels.append("field_defining")

    if decision == "core_relevant" and roles & METHOD_ROLES:
        labels.append("core_methods")

    if (
        "training_outreach" in roles
        or "Review" in ptypes
        or STUDENT_RE.search(title)
        or (decision in {"core_relevant", "adjacent_relevant"} and "infrastructure" in roles and cites >= 10)
        or (decision == "adjacent_relevant" and conf >= 0.85 and "review" in title.lower())
    ):
        labels.append("key_for_students")

    return labels


def tier_name(row: pd.Series) -> str:
    d = str(row.get("decision") or "")
    conf = float(row.get("confidence") or 0)
    review = bool(row.get("human_review_priority"))
    if d == "core_relevant" and conf >= 0.85 and not review:
        return "core_high_confidence"
    if d == "core_relevant":
        return "core_review"
    if d == "adjacent_relevant":
        return "adjacent"
    if d == "role_bridge":
        return "role_bridge"
    return d


def load_person_map(aliases_path: Path | None) -> tuple[dict[str, str], dict[str, str]]:
    if not aliases_path or not aliases_path.exists():
        return {}, {}
    aliases = pd.read_csv(aliases_path, low_memory=False)
    norm_to_person = {
        str(k).lower(): str(v)
        for k, v in zip(aliases.author_norm.astype(str), aliases.person_id.astype(str))
    }
    person_label = dict(zip(aliases.person_id.astype(str), aliases.person_display_name.astype(str)))
    return norm_to_person, person_label


def person_key(author_norm: str, norm_to_person: dict[str, str]) -> str:
    return norm_to_person.get(author_norm.lower(), f"person:{author_norm.lower()}")


def build_coauthorship(
    corpus: pd.DataFrame,
    aliases_path: Path | None = None,
    *,
    author_policy: str = "all",
    consortium_min: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    norm_to_person, person_label = load_person_map(aliases_path)
    reconciled = bool(norm_to_person)
    trim_middle = author_policy in {"first_last", "trim_middle"}

    mentions = build_author_mentions(corpus, norm_to_person)
    eligible_persons, excluded_single_middle = (
        eligible_coauthor_persons(mentions)
        if trim_middle
        else ({str(x) for x in mentions.person_id.unique()}, [])
    )
    cons_stats = consortium_middle_stats(
        mentions,
        excluded_single_middle,
        consortium_min=consortium_min,
    )

    edge_w: Counter[tuple[str, str]] = Counter()
    node_works: Counter[str] = Counter()
    node_names: dict[str, str] = {}
    for row in corpus.itertuples(index=False):
        slots = coauthors_for_paper(
            getattr(row, "authors", ""),
            norm_to_person,
            eligible_persons,
            consortium_min=consortium_min,
            trim_middle=trim_middle,
        )
        people = [pid for pid, _, _ in slots]
        for pid, _, _ in slots:
            node_works[pid] += 1
        for author in parse_authors(getattr(row, "authors", "")):
            n = norm_author(author)
            if not n:
                continue
            pid = person_key(n, norm_to_person)
            if pid in people and (pid not in node_names or len(author) > len(node_names[pid])):
                node_names[pid] = person_label.get(pid, author)
        for i, a in enumerate(people):
            for b in people[i + 1:]:
                edge = tuple(sorted((a, b)))
                edge_w[edge] += 1
    G = nx.Graph()
    for n, c in node_works.items():
        G.add_node(n, works=c, display_name=node_names.get(n, n))
    for (a, b), w in edge_w.items():
        G.add_edge(a, b, weight=w)

    deg = dict(G.degree(weight="weight"))
    # Betweenness is expensive at corpus scale; compute on the high-degree subgraph.
    top_nodes = {n for n, _ in sorted(deg.items(), key=lambda x: -x[1])[:400]}
    sub = G.subgraph(top_nodes).copy()
    btw = nx.betweenness_centrality(sub, weight="weight") if sub.number_of_nodes() else {}
    try:
        comms = list(nx.community.greedy_modularity_communities(G, weight="weight"))
    except Exception:
        comms = []

    nodes = []
    comm_map: dict[str, int] = {}
    for i, comm in enumerate(comms):
        for n in comm:
            comm_map[n] = i
    for n in G.nodes:
        nodes.append({
            "author_norm": n,
            "person_id": n if reconciled else "",
            "display_name": G.nodes[n].get("display_name", n),
            "works_in_corpus": int(G.nodes[n].get("works", 0)),
            "weighted_degree": round(float(deg.get(n, 0)), 2),
            "betweenness": round(float(btw.get(n, 0)), 6),
            "community_id": comm_map.get(n, -1),
        })
    nodes_df = pd.DataFrame(nodes).sort_values(["works_in_corpus", "weighted_degree"], ascending=False)

    edges = [
        {"author_a": a, "author_b": b, "shared_works": int(w), "weight": int(w)}
        for (a, b), w in sorted(edge_w.items(), key=lambda x: -x[1])
    ]
    edges_df = pd.DataFrame(edges)

    top_comm = []
    for i, comm in enumerate(sorted(comms, key=len, reverse=True)[:8]):
        members = sorted(comm, key=lambda n: node_works[n], reverse=True)[:6]
        top_comm.append({
            "community_id": i,
            "size": len(comm),
            "top_members": [node_names.get(m, m) for m in members],
        })

    summary = {
        "reconciled_people": reconciled,
        "author_policy": author_policy,
        "consortium_min_authors": consortium_min if trim_middle else None,
        "eligible_authors": int(len(eligible_persons)),
        "excluded_single_middle_only_persons": len(excluded_single_middle) if trim_middle else 0,
        "consortium": cons_stats,
        "middle_mentions_trimmed": cons_stats["consortium_middle_excluded_single_only"]
        + (len(excluded_single_middle) - cons_stats["consortium_middle_excluded_single_only"])
        if trim_middle
        else 0,
        "nodes": int(G.number_of_nodes()),
        "edges": int(G.number_of_edges()),
        "connected_components": int(nx.number_connected_components(G)) if G.number_of_nodes() else 0,
        "largest_component_nodes": int(len(max(nx.connected_components(G), key=len))) if G.number_of_nodes() else 0,
        "communities": len(comms),
        "top_weighted_degree": nodes_df.head(15)[["display_name", "works_in_corpus", "weighted_degree"]].to_dict("records"),
        "top_betweenness": nodes_df.sort_values("betweenness", ascending=False).head(10)[["display_name", "betweenness"]].to_dict("records"),
        "top_communities": top_comm,
    }
    return nodes_df, edges_df, summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=Path("postanalysis/checkpoint/corpus_inclusive.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/checkpoint"))
    ap.add_argument("--aliases", type=Path, default=Path("postanalysis/checkpoint/person_aliases.csv"))
    args = ap.parse_args()

    corpus = pd.read_csv(args.corpus, low_memory=False)
    corpus["survey_tier"] = corpus.decision
    corpus["analysis_tier"] = corpus.apply(tier_name, axis=1)
    corpus["curriculum_labels"] = corpus.apply(assign_labels, axis=1)
    corpus["curriculum_label_primary"] = corpus.curriculum_labels.apply(lambda xs: xs[0] if xs else "")
    corpus["curriculum_label_count"] = corpus.curriculum_labels.apply(len)

    args.out.mkdir(parents=True, exist_ok=True)
    corpus.to_csv(args.out / "corpus_inclusive_labeled.csv", index=False)

    for tier in ["core_high_confidence", "core_review", "adjacent", "role_bridge"]:
        sub = corpus[corpus.analysis_tier == tier]
        sub.to_csv(args.out / f"tier_{tier}.csv", index=False)

    for label in ["field_defining", "core_methods", "key_for_students"]:
        sub = corpus[corpus.curriculum_labels.apply(lambda xs: label in xs)]
        sub.to_csv(args.out / f"label_{label}.csv", index=False)

    nodes_df, edges_df, graph_summary = build_coauthorship(corpus, aliases_path=args.aliases)
    nodes_df.to_csv(args.out / "coauthorship_nodes.csv", index=False)
    edges_df.to_csv(args.out / "coauthorship_edges.csv", index=False)

    summary = {
        "corpus_works": int(len(corpus)),
        "analysis_tier_counts": corpus.analysis_tier.value_counts().to_dict(),
        "survey_tier_counts": corpus.survey_tier.value_counts().to_dict(),
        "curriculum_label_counts": {
            label: int(corpus.curriculum_labels.apply(lambda xs: label in xs).sum())
            for label in ["field_defining", "core_methods", "key_for_students"]
        },
        "multi_label_works": int((corpus.curriculum_label_count > 1).sum()),
        "coauthorship": graph_summary,
    }
    (args.out / "corpus_tier_analysis.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
