#!/usr/bin/env python3
"""People counts and top-100 author tables for corpus graph views."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from analyze_corpus_tiers import (
    build_author_mentions,
    eligible_coauthor_persons,
    load_person_map,
)

INCLUSIVE = {"core_relevant", "adjacent_relevant", "role_bridge"}


def person_table(
    df: pd.DataFrame,
    *,
    view: str,
    norm_to_person: dict[str, str],
    person_label: dict[str, str],
) -> tuple[pd.DataFrame, dict]:
    mentions = build_author_mentions(df, norm_to_person)
    eligible, excluded = eligible_coauthor_persons(mentions)
    elig = mentions[mentions.person_id.isin(eligible)].copy()

    rows = []
    for pid, g in elig.groupby("person_id"):
        works_ids = set(g.work_id)
        slots = Counter(g.position)
        sub = df[df.work_id.isin(works_ids)]
        display = max(g.author_raw.astype(str), key=len)
        if str(pid) in person_label and person_label[str(pid)]:
            display = person_label[str(pid)]
        rows.append(
            {
                "person_id": pid,
                "display_name": display,
                "works": len(works_ids),
                "first_or_single": int(slots.get("first", 0) + slots.get("single", 0)),
                "last": int(slots.get("last", 0)),
                "middle": int(slots.get("middle", 0)),
                "core_works": int((sub.decision == "core_relevant").sum()),
                "adjacent_works": int((sub.decision == "adjacent_relevant").sum()),
                "role_bridge_works": int((sub.decision == "role_bridge").sum()),
                "ultra_core_works": int(sub.ultra_core.sum()) if "ultra_core" in sub else 0,
                "view": view,
            }
        )
    people = pd.DataFrame(rows).sort_values(
        ["works", "last", "first_or_single", "ultra_core_works", "core_works"],
        ascending=False,
    )
    summary = {
        "view": view,
        "works": int(len(df)),
        "author_mentions_raw": int(len(mentions)),
        "unique_persons_raw": int(mentions.person_id.nunique()),
        "excluded_single_middle_only": len(excluded),
        "unique_persons_trim_middle": int(len(people)),
        "persons_with_first_or_last": int(((people.first_or_single + people.last) > 0).sum()),
        "top_100_min_works": int(people.head(100).works.min()) if len(people) >= 100 else None,
        "top_100_median_works": float(people.head(100).works.median()) if len(people) >= 100 else None,
    }
    return people, summary


def write_people(people: pd.DataFrame, out: Path, stem: str) -> None:
    people.to_csv(out / f"people_{stem}.csv", index=False)
    people.head(100).to_csv(out / f"people_{stem}_top100.csv", index=False)
    people.sort_values(["last", "works", "ultra_core_works"], ascending=False).head(100).to_csv(
        out / f"people_{stem}_top100_by_last.csv", index=False
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roles", type=Path, default=Path("postanalysis/llm_agent_v3/citation_roles_by_work.csv"))
    ap.add_argument("--works", type=Path, default=Path("postanalysis/enriched/canonical_works_enriched.csv"))
    ap.add_argument("--aliases", type=Path, default=Path("postanalysis/checkpoint/person_aliases.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/llm_agent_v3"))
    args = ap.parse_args()

    # Prefer annotated full works from IA-013 build when present
    full_path = args.out / "corpus_full_works.csv"
    if full_path.exists() and "in_integrated_plus_rescue" in pd.read_csv(full_path, nrows=1).columns:
        corpus = pd.read_csv(full_path, low_memory=False)
    else:
        roles = pd.read_csv(args.roles, low_memory=False)
        works = pd.read_csv(args.works, low_memory=False)
        corpus = roles.merge(works[["work_id", "authors"]], on="work_id", how="left", suffixes=("", "_enr"))
        if "authors_enr" in corpus.columns:
            corpus["authors"] = corpus["authors"].fillna(corpus["authors_enr"])
        corpus = corpus[corpus.decision.isin(INCLUSIVE)].copy()

    norm_to_person, person_label = load_person_map(args.aliases)
    views: dict[str, pd.DataFrame] = {
        "full": corpus,
        "prime": corpus[corpus.citation_link_strength.fillna("") != "weak_unlinked"].copy(),
    }
    if "in_graph_matched" in corpus.columns:
        views["graph_matched"] = corpus[corpus.in_graph_matched.fillna(False)].copy()
        views["integrated"] = corpus[corpus.in_integrated.fillna(False)].copy()
        views["integrated_plus_rescue"] = corpus[corpus.in_integrated_plus_rescue.fillna(False)].copy()

    args.out.mkdir(parents=True, exist_ok=True)
    summary: dict = {
        "ranking": "works desc, then last, first_or_single, ultra_core, core (trim_middle eligible only)",
        "ia": "IA-013",
        "files": {},
    }
    for stem, df in views.items():
        people, view_sum = person_table(
            df, view=stem, norm_to_person=norm_to_person, person_label=person_label
        )
        write_people(people, args.out, stem)
        summary[stem] = view_sum
        summary["files"][stem] = f"people_{stem}.csv"
        summary["files"][f"top100_{stem}"] = f"people_{stem}_top100.csv"

    (args.out / "people_counts.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in summary if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
