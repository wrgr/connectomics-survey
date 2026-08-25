#!/usr/bin/env python3
"""Build an inclusive LLM-screening checkpoint corpus and summary statistics.

The checkpoint keeps works adjudicated as core_relevant, adjacent_relevant, or
role_bridge from the ingested IA-007-v2 run, joined to canonical metadata.
"""
from __future__ import annotations
import argparse, ast, json, re
from collections import Counter
from pathlib import Path
from typing import Any
import pandas as pd

INCLUSIVE = {"core_relevant", "adjacent_relevant", "role_bridge"}
INITIAL = re.compile(r"^[A-Z]\.?$")


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
    given = " ".join(toks[:-1]).lower().strip(".")
    given_initials = "".join(t[0] for t in given.split() if t and not INITIAL.match(t))
    return f"{surname}|{given_initials}" if surname else ""


def build_corpus(results: pd.DataFrame, works: pd.DataFrame) -> pd.DataFrame:
    corpus = results[results.decision.isin(INCLUSIVE)].copy()
    keep = [
        "work_id", "authors", "year", "venue", "doi", "abstract", "publication_types",
        "citation_count_work", "has_recovered_bridge_version", "has_retained_version",
    ]
    return corpus.merge(works[keep], on="work_id", how="left", suffixes=("", "_enriched"))


def author_table(corpus: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in corpus.itertuples(index=False):
        authors = parse_authors(getattr(row, "authors", ""))
        for i, author in enumerate(authors, start=1):
            rows.append(
                {
                    "work_id": row.work_id,
                    "author_raw": author,
                    "author_norm": norm_author(author),
                    "author_order": i,
                    "decision": row.decision,
                    "source_group": row.source_group,
                }
            )
    return pd.DataFrame(rows)


def summarize(corpus: pd.DataFrame, authors_df: pd.DataFrame, screened_total: int) -> dict[str, Any]:
    years = pd.to_numeric(corpus.year, errors="coerce")
    cites = pd.to_numeric(corpus.citation_count_work, errors="coerce").fillna(0)
    role_counts = Counter(r for roles in corpus.roles.map(parse_roles) for r in roles)
    top_auth = (
        authors_df.groupby("author_norm", as_index=False)
        .agg(works=("work_id", "nunique"), mentions=("work_id", "count"), sample_name=("author_raw", "first"))
        .query("author_norm != ''")
        .sort_values(["works", "mentions"], ascending=False)
        .head(20)
    )
    per_work = authors_df.groupby("work_id").size()
    return {
        "checkpoint_label": "IA-007-v2 inclusive corpus (core + adjacent + role_bridge)",
        "screened_works_total": int(screened_total),
        "corpus_works": int(len(corpus)),
        "corpus_share_of_screened": round(len(corpus) / screened_total, 4),
        "decision_counts": corpus.decision.value_counts().to_dict(),
        "source_group_counts": corpus.source_group.value_counts().to_dict(),
        "decision_by_source_group": corpus.groupby(["source_group", "decision"]).size().unstack(fill_value=0).astype(int).to_dict(orient="index"),
        "authors": {
            "unique_authors_raw_strings": int(authors_df.author_raw.nunique()),
            "unique_authors_normalized_surname_initials": int(authors_df.query("author_norm != ''").author_norm.nunique()),
            "author_mentions": int(len(authors_df)),
            "works_with_author_field": int(corpus.authors.fillna("").astype(str).str.strip().ne("").sum()),
            "works_missing_author_field": int(corpus.authors.fillna("").astype(str).str.strip().eq("").sum()),
            "mean_authors_per_work": round(float(per_work.mean()), 2),
            "median_authors_per_work": float(per_work.median()),
            "max_authors_on_one_work": int(per_work.max()) if len(per_work) else 0,
        },
        "years": {
            "min": int(years.min()) if years.notna().any() else None,
            "max": int(years.max()) if years.notna().any() else None,
            "median": float(years.median()) if years.notna().any() else None,
            "missing": int(years.isna().sum()),
        },
        "citations": {
            "median": float(cites.median()),
            "mean": round(float(cites.mean()), 2),
            "p90": float(cites.quantile(0.9)),
            "zero_citation_works": int((cites == 0).sum()),
        },
        "confidence": {
            "median": float(corpus.confidence.median()),
            "below_0.85": int((corpus.confidence < 0.85).sum()),
            "below_0.70": int((corpus.confidence < 0.70).sum()),
        },
        "human_review_flagged_in_corpus": int(corpus.human_review_priority.sum()),
        "top_roles": dict(role_counts.most_common(12)),
        "top_venues": corpus.venue.fillna("").value_counts().head(15).to_dict(),
        "decade_counts": dict(Counter(int(y // 10 * 10) for y in years.dropna()).most_common()),
        "top_authors_by_work_count": [
            {"author": row.sample_name, "works": int(row.works), "mentions": int(row.mentions)}
            for row in top_auth.itertuples(index=False)
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=Path("postanalysis/llm_agent/llm_relevance_results.csv"))
    ap.add_argument("--works-csv", type=Path, default=Path("postanalysis/enriched/canonical_works_enriched.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/checkpoint"))
    args = ap.parse_args()

    results = pd.read_csv(args.results, low_memory=False)
    works = pd.read_csv(args.works_csv, low_memory=False)
    results["work_id"] = results.work_id.astype(str)
    works["work_id"] = works.work_id.astype(str)

    args.out.mkdir(parents=True, exist_ok=True)
    corpus = build_corpus(results, works)
    authors_df = author_table(corpus)
    summary = summarize(corpus, authors_df, screened_total=len(results))

    corpus.to_csv(args.out / "corpus_inclusive.csv", index=False)
    authors_df.to_csv(args.out / "corpus_inclusive_authors.csv", index=False)
    (args.out / "checkpoint_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("corpus_works", "authors", "decision_counts")}, indent=2))


if __name__ == "__main__":
    main()
