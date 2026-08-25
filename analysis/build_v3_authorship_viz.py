#!/usr/bin/env python3
"""Build D3 graph_data.json for the v3 full corpus (top authors + top papers)."""
from __future__ import annotations

import argparse
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


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_person_map(aliases_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    if not aliases_path.exists():
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


def year_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=Path("postanalysis/llm_agent_v3/corpus_full_works.csv"))
    ap.add_argument("--people", type=Path, default=Path("postanalysis/llm_agent_v3/people_full_top100.csv"))
    ap.add_argument("--aliases", type=Path, default=Path("postanalysis/checkpoint/person_aliases.csv"))
    ap.add_argument("--emergent", type=Path, default=Path("postanalysis/llm_agent_v3/label_emergent_core.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/llm_agent_v3/viz/graph_data.json"))
    ap.add_argument("--top-authors", type=int, default=100)
    ap.add_argument("--top-papers", type=int, default=120)
    ap.add_argument("--min-shared-works", type=int, default=2)
    ap.add_argument("--min-shared-authors", type=int, default=2)
    args = ap.parse_args()

    corpus = pd.read_csv(args.corpus, low_memory=False)
    people = pd.read_csv(args.people, low_memory=False).head(args.top_authors)
    norm_to_person, person_label = load_person_map(args.aliases)

    top_people = [str(x) for x in people.person_id]
    top_set = set(top_people)
    people_by_id = {str(r.person_id): r for r in people.itertuples(index=False)}

    work_people: dict[str, set[str]] = {}
    person_works: dict[str, list[str]] = {pid: [] for pid in top_people}
    person_comm: dict[str, Counter] = {pid: Counter() for pid in top_people}
    for row in corpus.itertuples(index=False):
        wid = str(row.work_id)
        norms = [norm_author(a) for a in parse_authors(getattr(row, "authors", ""))]
        pids = {person_key(n, norm_to_person) for n in norms if n}
        work_people[wid] = pids
        comm_id = getattr(row, "primary_community_id", -1)
        comm_lab = str(getattr(row, "primary_community_label", "") or "")
        try:
            comm_i = int(comm_id) if pd.notna(comm_id) else -1
        except (TypeError, ValueError):
            comm_i = -1
        for pid in pids & top_set:
            person_works[pid].append(wid)
            if comm_i >= 0:
                person_comm[pid][(comm_i, comm_lab)] += 1

    edge_w: Counter[tuple[str, str]] = Counter()
    for pids in work_people.values():
        present = sorted(pids & top_set)
        for i, a in enumerate(present):
            for b in present[i + 1 :]:
                edge_w[(a, b)] += 1

    author_nodes = []
    for pid in top_people:
        row = people_by_id[pid]
        comms = person_comm.get(pid) or Counter()
        if comms:
            (group, community), _ = comms.most_common(1)[0]
        else:
            group, community = -1, ""
        label = str(row.display_name)
        if pid in person_label and person_label[pid]:
            label = person_label[pid]
        author_nodes.append({
            "id": pid,
            "label": label,
            "works": int(row.works),
            "first_or_single": int(row.first_or_single),
            "last": int(row.last),
            "ultra_core_works": int(row.ultra_core_works),
            "core_works": int(row.core_works),
            "group": int(group),
            "community": community,
        })

    author_links = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in sorted(edge_w.items(), key=lambda x: -x[1])
        if w >= args.min_shared_works
    ]

    papers = corpus.copy()
    papers["ultra"] = papers.ultra_core.map(is_true) if "ultra_core" in papers else False
    papers["cites"] = pd.to_numeric(papers.get("citation_count_work"), errors="coerce").fillna(0)
    papers["conf"] = pd.to_numeric(papers.get("confidence"), errors="coerce").fillna(0)
    emergent_ids: set[str] = set()
    if args.emergent.exists():
        emergent_ids = set(pd.read_csv(args.emergent, low_memory=False).work_id.astype(str))
    papers["emergent"] = papers.work_id.astype(str).isin(emergent_ids)
    core = papers[papers.decision.astype(str).eq("core_relevant")].copy()
    ranked = core.sort_values(["ultra", "cites", "conf"], ascending=[False, False, False])
    want = set(ranked.head(args.top_papers).work_id.astype(str)) | emergent_ids
    selected = papers[papers.work_id.astype(str).isin(want)].sort_values(
        ["ultra", "emergent", "cites", "conf"], ascending=[False, False, False, False]
    )

    paper_people: dict[str, set[str]] = {}
    for row in selected.itertuples(index=False):
        wid = str(row.work_id)
        paper_people[wid] = work_people.get(wid, set())

    pp_edge_w: Counter[tuple[str, str]] = Counter()
    wids = list(paper_people.keys())
    for i, a in enumerate(wids):
        pa = paper_people[a]
        for b in wids[i + 1 :]:
            shared = len(pa & paper_people[b])
            if shared >= args.min_shared_authors:
                pp_edge_w[tuple(sorted((a, b)))] = shared

    paper_nodes = []
    for row in selected.itertuples(index=False):
        wid = str(row.work_id)
        ultra = is_true(getattr(row, "ultra", False))
        emergent = is_true(getattr(row, "emergent", False))
        if ultra:
            group = "ultra_core"
        elif emergent:
            group = "emergent_core"
        else:
            group = "core_relevant"
        paper_nodes.append({
            "id": wid,
            "label": str(getattr(row, "title", wid))[:80],
            "year": year_int(getattr(row, "year", None)),
            "citations": int(getattr(row, "cites", 0) or 0),
            "authors": len(paper_people.get(wid, set())),
            "tier": str(getattr(row, "decision", "")),
            "group": group,
            "community": str(getattr(row, "primary_community_label", "") or ""),
        })

    paper_links = [{"source": a, "target": b, "weight": w} for (a, b), w in pp_edge_w.items()]

    payload = {
        "meta": {
            "view": "v3_full",
            "corpus_works": int(len(corpus)),
            "top_authors": args.top_authors,
            "top_papers": len(paper_nodes),
            "min_shared_works": args.min_shared_works,
            "min_shared_authors": args.min_shared_authors,
            "reconciled": args.aliases.exists(),
            "ultra_core_in_graph": int(sum(1 for n in paper_nodes if n["group"] == "ultra_core")),
            "emergent_core_in_graph": int(sum(1 for n in paper_nodes if n["group"] == "emergent_core")),
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
        "ultra_core_papers": payload["meta"]["ultra_core_in_graph"],
        "emergent_core_papers": payload["meta"]["emergent_core_in_graph"],
        "out": str(args.out),
    }, indent=2))


if __name__ == "__main__":
    main()
