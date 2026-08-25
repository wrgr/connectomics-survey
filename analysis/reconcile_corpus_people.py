#!/usr/bin/env python3
"""Reconcile author-name variants in the checkpoint corpus.

Blocking uses unicode-normalized names with single-letter middle initials removed.
Variants in the same block merge unless they co-occur on the same work (collision).
Additional probable merges use shared coauthor neighborhoods when first/last tokens match.

Outputs an auditable alias table mapping author_norm -> person_id without mutating raw strings.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


class UnionFind:
    def __init__(self, values: set[str] | list[str]):
        self.parent = {str(v): str(v) for v in values}

    def find(self, x: str) -> str:
        x = str(x)
        self.parent.setdefault(x, x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        root, child = sorted([ra, rb])
        self.parent[child] = root


def fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(c for c in text if not unicodedata.combining(c))


def norm_name(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", fold(value).lower())).strip()


def norm_no_middle(value: object) -> str:
    toks = norm_name(value).split()
    if len(toks) <= 2:
        return " ".join(toks)
    return " ".join(
        [toks[0], *[t for t in toks[1:-1] if not (len(t) == 1 and t.isalpha())], toks[-1]]
    )


def first_last_tokens(value: object) -> tuple[str, str]:
    toks = norm_name(value).split()
    if len(toks) < 2:
        return ("", toks[0] if toks else "")
    return (toks[0], toks[-1])


def classify_pair(*, shared: int, co_j: float, year_overlap: bool, collision: bool) -> str:
    if collision:
        return "same_name_coauthor_collision"
    if shared >= 3 and co_j >= 0.20 and year_overlap:
        return "probable_same_person"
    if shared >= 1 and co_j >= 0.10 and year_overlap:
        return "possible_same_person"
    return "ambiguous"


def build_coauthor_neighborhoods(authors: pd.DataFrame) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return work co-occurrence sets and coauthor block neighborhoods per author_norm."""
    work_norms: dict[str, set[str]] = defaultdict(set)
    norm_blocks: dict[str, str] = {}
    for row in authors.itertuples(index=False):
        norm = str(row.author_norm)
        if not norm:
            continue
        work_norms[str(row.work_id)].add(norm)
        norm_blocks[norm] = norm_no_middle(str(row.author_raw))

    co_blocks: dict[str, set[str]] = defaultdict(set)
    for norms in work_norms.values():
        blocks = {norm_blocks[n] for n in norms if norm_blocks.get(n)}
        for n in norms:
            co_blocks[n].update(blocks - {norm_blocks.get(n, "")})

    collisions: set[tuple[str, str]] = set()
    for norms in work_norms.values():
        by_block: dict[str, list[str]] = defaultdict(list)
        for n in norms:
            by_block[norm_blocks.get(n, "")].append(n)
        for ns in by_block.values():
            uniq = sorted(set(ns))
            for i in range(len(uniq)):
                for j in range(i + 1, len(uniq)):
                    collisions.add((uniq[i], uniq[j]))
    return co_blocks, collisions


def author_metadata(authors: pd.DataFrame) -> tuple[dict[str, str], dict[str, set[str]], dict[str, tuple[int | None, int | None]]]:
    names: dict[str, str] = {}
    raw_variants: dict[str, set[str]] = defaultdict(set)
    years: dict[str, list[int]] = defaultdict(list)
    work_years = authors[["work_id", "year"]].drop_duplicates() if "year" in authors.columns else pd.DataFrame()
    year_map = dict(zip(work_years.get("work_id", pd.Series(dtype=str)), work_years.get("year", pd.Series(dtype=float))))

    for row in authors.itertuples(index=False):
        norm = str(row.author_norm)
        if not norm:
            continue
        raw = str(row.author_raw)
        raw_variants[norm].add(raw)
        if norm not in names or len(raw) > len(names[norm]):
            names[norm] = raw
        y = year_map.get(getattr(row, "work_id", None))
        if y is not None and not pd.isna(y):
            years[norm].append(int(y))

    year_span = {
        n: (min(v), max(v)) if v else (None, None)
        for n, v in years.items()
    }
    return names, raw_variants, year_span


def year_overlap(a: tuple[int | None, int | None], b: tuple[int | None, int | None]) -> bool:
    if None in a or None in b:
        return True
    return not (a[1] < b[0] or b[1] < a[0])


def reconcile(authors: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    authors = authors.copy()
    authors["author_norm"] = authors["author_norm"].fillna("").astype(str)
    authors = authors[authors["author_norm"].ne("")]

    all_norms = set(authors["author_norm"].unique())
    uf = UnionFind(all_norms)
    merge_log: list[dict[str, Any]] = []

    norm_to_block: dict[str, str] = {}
    block_to_norms: dict[str, set[str]] = defaultdict(set)
    for row in authors.drop_duplicates(["author_norm", "author_raw"]).itertuples(index=False):
        block = norm_no_middle(row.author_raw)
        if not block:
            continue
        norm_to_block[str(row.author_norm)] = block
        block_to_norms[block].add(str(row.author_norm))

    co_blocks, collisions = build_coauthor_neighborhoods(authors)
    names, raw_variants, year_span = author_metadata(authors)

    for block, norms in sorted(block_to_norms.items()):
        norms = sorted(norms)
        if len(norms) < 2:
            continue
        for i in range(len(norms)):
            for j in range(i + 1, len(norms)):
                a, b = norms[i], norms[j]
                if (a, b) in collisions or (b, a) in collisions:
                    merge_log.append({
                        "author_norm_a": a, "author_norm_b": b, "block_key": block,
                        "classification": "same_name_coauthor_collision", "merged": False,
                    })
                    continue
                uf.union(a, b)
                merge_log.append({
                    "author_norm_a": a, "author_norm_b": b, "block_key": block,
                    "classification": "block_middle_initial_insensitive", "merged": True,
                })

    # Coauthor-evidence merges for cross-block pairs with matching first/last tokens.
    norms_by_fl: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in authors.drop_duplicates(["author_norm", "author_raw"]).itertuples(index=False):
        fl = first_last_tokens(row.author_raw)
        if fl[0] and fl[1]:
            norms_by_fl[fl].append(str(row.author_norm))
    for fl, norms in norms_by_fl.items():
        uniq = sorted(set(norms))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                if uf.find(a) == uf.find(b):
                    continue
                if (a, b) in collisions or (b, a) in collisions:
                    continue
                ca, cb = co_blocks[a], co_blocks[b]
                shared = len(ca & cb)
                union = len(ca | cb)
                co_j = shared / union if union else 0.0
                cls = classify_pair(
                    shared=shared,
                    co_j=co_j,
                    year_overlap=year_overlap(year_span[a], year_span[b]),
                    collision=False,
                )
                if cls == "probable_same_person":
                    uf.union(a, b)
                    merge_log.append({
                        "author_norm_a": a, "author_norm_b": b, "block_key": "|".join(fl),
                        "classification": cls, "shared_coauthor_blocks": shared,
                        "coauthor_jaccard": round(co_j, 6), "merged": True,
                    })

    groups: dict[str, list[str]] = defaultdict(list)
    for norm in sorted(all_norms):
        groups[uf.find(norm)].append(norm)

    aliases = []
    for root, members in sorted(groups.items()):
        members = sorted(members)
        variants = sorted({raw for m in members for raw in raw_variants.get(m, set())})
        display = max(variants, key=lambda x: (len(x), x)) if variants else names.get(root, root)
        person_id = f"person:{norm_no_middle(display) or root}"
        for norm in members:
            aliases.append({
                "author_norm": norm,
                "person_id": person_id,
                "person_display_name": display,
                "name_variants": "; ".join(variants),
                "component_size": len(members),
                "is_reconciled_merge": len(members) > 1,
            })

    alias_df = pd.DataFrame(aliases)
    log_df = pd.DataFrame(merge_log)

    merged_components = alias_df.loc[alias_df["is_reconciled_merge"], "person_id"].nunique()
    summary = {
        "source_author_norms": len(all_norms),
        "canonical_people": int(alias_df["person_id"].nunique()),
        "merged_components": int(merged_components),
        "norms_in_merged_components": int(alias_df.loc[alias_df["is_reconciled_merge"], "author_norm"].nunique()),
        "collision_pairs_skipped": int(log_df.loc[log_df["classification"].eq("same_name_coauthor_collision"), ["author_norm_a", "author_norm_b"]].drop_duplicates().shape[0]),
        "merge_rows": int(log_df["merged"].sum()),
        "reduction": int(len(all_norms) - alias_df["person_id"].nunique()),
    }
    return alias_df, log_df, summary


def apply_aliases(authors: pd.DataFrame, alias_df: pd.DataFrame) -> pd.DataFrame:
    out = authors.merge(
        alias_df[["author_norm", "person_id", "person_display_name"]],
        on="author_norm",
        how="left",
        validate="many_to_one",
    )
    out["person_id"] = out["person_id"].fillna(out["author_norm"].map(lambda n: f"person:{n}"))
    out["person_display_name"] = out["person_display_name"].fillna(out["author_raw"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--authors", type=Path, default=Path("postanalysis/checkpoint/corpus_inclusive_authors.csv"))
    ap.add_argument("--corpus", type=Path, default=Path("postanalysis/checkpoint/corpus_inclusive.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/checkpoint"))
    args = ap.parse_args()

    authors = pd.read_csv(args.authors, low_memory=False)
    if args.corpus.exists():
        years = pd.read_csv(args.corpus, usecols=["work_id", "year"], low_memory=False)
        years["work_id"] = years["work_id"].astype(str)
        authors["work_id"] = authors["work_id"].astype(str)
        authors = authors.merge(years, on="work_id", how="left")

    args.out.mkdir(parents=True, exist_ok=True)
    alias_df, log_df, summary = reconcile(authors)
    reconciled_authors = apply_aliases(authors, alias_df)

    alias_df.to_csv(args.out / "person_aliases.csv", index=False)
    log_df.to_csv(args.out / "person_reconciliation_log.csv", index=False)
    reconciled_authors.to_csv(args.out / "corpus_inclusive_authors_reconciled.csv", index=False)
    (args.out / "person_reconciliation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
