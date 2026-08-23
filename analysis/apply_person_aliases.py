#!/usr/bin/env python3
"""Apply reviewed person-identity decisions as an auditable alias layer.

Only rows whose decision is exactly `merge` are used to build alias components.
Explicit `separate` decisions are hard constraints: if transitive merges would place
a reviewed-separate pair in one component, reconciliation fails rather than silently
overriding the reviewer's decision. Raw Semantic Scholar author IDs are never modified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


class UnionFind:
    def __init__(self, values):
        self.parent = {str(v): str(v) for v in values}

    def find(self, x):
        x = str(x)
        self.parent.setdefault(x, x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        root, child = sorted([ra, rb])
        self.parent[child] = root


def validate_separate_constraints(uf: UnionFind, separates: pd.DataFrame, all_ids: set[str]) -> None:
    """Fail if an explicit `separate` decision is contradicted by merge components."""
    if separates.empty:
        return
    separate_ids = set(separates["author_id_a"].astype(str)) | set(separates["author_id_b"].astype(str))
    unknown_ids = separate_ids - all_ids
    if unknown_ids:
        raise RuntimeError(f"Reviewed separate decisions reference unknown author IDs: {sorted(unknown_ids)[:20]}")

    conflicts = []
    for r in separates.itertuples(index=False):
        a, b = str(r.author_id_a), str(r.author_id_b)
        if uf.find(a) == uf.find(b):
            conflicts.append((a, b, uf.find(a)))
    if conflicts:
        preview = conflicts[:20]
        raise RuntimeError(
            "Reviewed identity decisions are contradictory: explicit `separate` pairs "
            f"were joined transitively by merge decisions: {preview}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", required=True, type=Path)
    ap.add_argument("--reviewed-candidates", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    src = args.outputs_dir.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    people = pd.read_csv(src / "people.csv", low_memory=False)
    pa = pd.read_csv(src / "paper_author_edges.csv", low_memory=False)
    papers = pd.read_csv(src / "papers_retained.csv", low_memory=False)
    reviewed = pd.read_csv(args.reviewed_candidates, low_memory=False)

    required = {"author_id_a", "author_id_b", "decision"}
    missing = required - set(reviewed.columns)
    if missing:
        raise RuntimeError(f"Reviewed candidate file is missing columns: {sorted(missing)}")

    all_ids = set(people["author_id"].astype(str))
    uf = UnionFind(all_ids)
    decision = reviewed["decision"].fillna("").astype(str).str.strip().str.lower()
    merges = reviewed[decision.eq("merge")].copy()
    separates = reviewed[decision.eq("separate")].copy()

    unknown_ids = (set(merges["author_id_a"].astype(str)) | set(merges["author_id_b"].astype(str))) - all_ids
    if unknown_ids:
        raise RuntimeError(f"Reviewed merges reference unknown author IDs: {sorted(unknown_ids)[:20]}")

    for r in merges.itertuples(index=False):
        uf.union(str(r.author_id_a), str(r.author_id_b))

    # A reviewer may explicitly declare a pair separate even when two merge rows form
    # a transitive path between them. Treat that as contradictory input and stop.
    validate_separate_constraints(uf, separates, all_ids)

    groups = {}
    for aid in sorted(all_ids):
        groups.setdefault(uf.find(aid), []).append(aid)

    manual = {}
    if "canonical_person_id" in reviewed.columns:
        for r in merges.itertuples(index=False):
            value = getattr(r, "canonical_person_id", None)
            if pd.isna(value) or not str(value).strip():
                continue
            root = uf.find(str(r.author_id_a))
            manual.setdefault(root, set()).add(str(value).strip())
    conflicts = {root: vals for root, vals in manual.items() if len(vals) > 1}
    if conflicts:
        raise RuntimeError(f"Conflicting canonical_person_id values in merged components: {conflicts}")

    id_to_name = dict(zip(people["author_id"].astype(str), people["name"].fillna("")))
    aliases = []
    for root, members in sorted(groups.items()):
        canonical_person_id = next(iter(manual[root])) if root in manual else f"s2:{root}"
        names = sorted({id_to_name.get(a, "") for a in members if id_to_name.get(a, "")})
        canonical_name = max(names, key=lambda x: (len(x), x)) if names else ""
        for aid in members:
            aliases.append({
                "author_id": aid,
                "source_name": id_to_name.get(aid, ""),
                "canonical_person_id": canonical_person_id,
                "canonical_name": canonical_name,
                "component_size": len(members),
                "is_reconciled_merge": len(members) > 1,
            })
    alias_df = pd.DataFrame(aliases)
    alias_df.to_csv(out / "person_aliases.csv", index=False)

    pa2 = pa.copy()
    pa2["author_id"] = pa2["author_id"].astype(str)
    pa2 = pa2.merge(alias_df[["author_id", "canonical_person_id", "canonical_name"]], on="author_id", how="left", validate="many_to_one")
    canonical_pa = pa2[["paper_id", "canonical_person_id", "canonical_name"]].drop_duplicates()
    canonical_pa.to_csv(out / "paper_canonical_person_edges.csv", index=False)

    paper_meta = papers[["paper_id", "tier", "year", "query_axes"]].copy()
    joined = canonical_pa.merge(paper_meta, on="paper_id", how="left")
    joined["is_core_candidate"] = joined["tier"].eq("core_candidate")

    def axes_union(values):
        axes = set()
        for value in values.dropna().astype(str):
            axes.update(x.strip() for x in value.split(";") if x.strip())
        return ";".join(sorted(axes))

    reconciled = (
        joined.groupby(["canonical_person_id", "canonical_name"], dropna=False)
        .agg(
            retained_paper_count=("paper_id", "nunique"),
            core_candidate_paper_count=("is_core_candidate", "sum"),
            first_relevant_year=("year", "min"),
            latest_relevant_year=("year", "max"),
            axes=("query_axes", axes_union),
        )
        .reset_index()
    )
    reconciled["axis_breadth"] = reconciled["axes"].fillna("").map(lambda x: len([a for a in str(x).split(";") if a]))
    reconciled = reconciled.sort_values(["core_candidate_paper_count", "retained_paper_count"], ascending=False)
    reconciled.to_csv(out / "people_reconciled.csv", index=False)

    merges.to_csv(out / "applied_merge_decisions.csv", index=False)
    summary = {
        "source_people_rows": len(people),
        "reviewed_merge_rows": len(merges),
        "reviewed_separate_rows": len(separates),
        "canonical_people": reconciled["canonical_person_id"].nunique(),
        "source_ids_in_multi_id_components": int(alias_df.loc[alias_df["component_size"] > 1, "author_id"].nunique()),
        "multi_id_components": int(alias_df.loc[alias_df["component_size"] > 1, "canonical_person_id"].nunique()),
    }
    (out / "person_reconciliation_applied_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
