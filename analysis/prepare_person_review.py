#!/usr/bin/env python3
"""Prepare a human-review sheet from person reconciliation candidates."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--include-ambiguous", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.candidates, low_memory=False)
    if not args.include_ambiguous:
        df = df[df["classification"].isin(["probable_same_person", "possible_same_person"])].copy()

    df["s2_url_a"] = df["author_id_a"].astype(str).map(lambda x: f"https://www.semanticscholar.org/author/{x}")
    df["s2_url_b"] = df["author_id_b"].astype(str).map(lambda x: f"https://www.semanticscholar.org/author/{x}")
    for col in ["decision", "canonical_person_id", "evidence_url_or_identifier", "reviewer", "review_date", "notes"]:
        if col not in df.columns:
            df[col] = ""

    preferred = [
        "classification", "normalized_name", "name_a", "name_b", "author_id_a", "author_id_b",
        "s2_url_a", "s2_url_b", "shared_coauthor_names", "coauthor_jaccard", "axis_jaccard", "year_overlap",
        "retained_papers_a", "retained_papers_b", "recommended_action", "decision", "canonical_person_id",
        "evidence_url_or_identifier", "reviewer", "review_date", "notes"
    ]
    extras = [c for c in df.columns if c not in preferred]
    df[preferred + extras].to_csv(args.out, index=False)
    print(f"wrote {len(df)} review rows to {args.out}")


if __name__ == "__main__":
    main()
