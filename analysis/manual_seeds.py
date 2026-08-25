"""Load human-seeded landmark works without mutating frozen discovery or agent JSON.

`postanalysis/works/manual_seed_works.csv` is the source of record. These works
were missing from the frozen Semantic Scholar discovery set (Helmstaedter 2025
NRN coverage holes). They are concatenated into citation-role / corpus views
as `source_group=manual_seed` with human `core_relevant` decisions.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_PATH = Path("postanalysis/works/manual_seed_works.csv")
SOURCE_GROUP = "manual_seed"
SEED_MODEL = "human-seed"
SEED_PROMPT = "IA-007-v3-manual-seed"
SEED_RUN_MODE = "human_seed"

RESULT_FIELDS = (
    "work_id",
    "canonical_paper_id",
    "source_group",
    "version_count",
    "member_paper_ids",
    "title",
    "model",
    "prompt_version",
    "run_mode",
    "prompt_sha256",
    "adjudication_batch",
    "decision",
    "roles",
    "confidence",
    "evidence",
    "reason",
    "noise_flags",
    "scale_relationship",
    "core_gate",
    "human_review_priority",
    "human_review_reason",
)

WORK_FIELDS = (
    "work_id",
    "canonical_paper_id",
    "source_group",
    "version_count",
    "member_paper_ids",
    "member_dois",
    "title",
    "abstract",
    "authors",
    "year",
    "venue",
    "doi",
    "publication_types",
    "citation_count_work",
    "citation_count_sum_versions",
    "citation_aggregation_note",
    "has_recovered_bridge_version",
    "has_retained_version",
)


def s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    t = str(v).strip()
    return "" if t.lower() in {"", "nan", "none", "null"} else t


def norm_doi(v: Any) -> str:
    t = s(v).lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if t.startswith(prefix):
            t = t[len(prefix) :]
    return t.strip()


def parse_roles(v: Any) -> str:
    text = s(v)
    if not text:
        return "[]"
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return str(parsed)
    except Exception:
        pass
    return str([text])


def load_manual_seeds(path: Path | None = None) -> pd.DataFrame:
    p = Path(path) if path is not None else DEFAULT_PATH
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, low_memory=False)


def seed_dois(seeds: pd.DataFrame) -> set[str]:
    out: set[str] = set()
    if seeds.empty:
        return out
    for row in seeds.itertuples(index=False):
        d = norm_doi(getattr(row, "doi", ""))
        if d:
            out.add(d)
    return out


def existing_dois(works: pd.DataFrame) -> set[str]:
    out: set[str] = set()
    if works is None or works.empty:
        return out
    for col in ("doi", "member_dois"):
        if col not in works.columns:
            continue
        for val in works[col].fillna(""):
            for part in str(val).split(";"):
                d = norm_doi(part)
                if d:
                    out.add(d)
    return out


def result_row(row: Any) -> dict[str, Any]:
    pid = s(getattr(row, "canonical_paper_id", ""))
    title = s(getattr(row, "title", ""))
    note = s(getattr(row, "seed_note", ""))
    return {
        "work_id": s(getattr(row, "work_id", "")),
        "canonical_paper_id": pid,
        "source_group": SOURCE_GROUP,
        "version_count": 1,
        "member_paper_ids": pid,
        "title": title,
        "model": SEED_MODEL,
        "prompt_version": SEED_PROMPT,
        "run_mode": SEED_RUN_MODE,
        "prompt_sha256": "",
        "adjudication_batch": "",
        "decision": s(getattr(row, "decision", "")) or "core_relevant",
        "roles": parse_roles(getattr(row, "roles", "[]")),
        "confidence": float(getattr(row, "confidence", 1.0) or 1.0),
        "evidence": title,
        "reason": note or "Human-seeded landmark missing from frozen discovery.",
        "noise_flags": "[]",
        "scale_relationship": s(getattr(row, "scale_relationship", "")) or "nanoscale_only",
        "core_gate": s(getattr(row, "core_gate", "")) or "em_or_synaptic_reconstruction",
        "human_review_priority": False,
        "human_review_reason": "",
    }


def work_row(row: Any) -> dict[str, Any]:
    pid = s(getattr(row, "canonical_paper_id", ""))
    doi = s(getattr(row, "doi", ""))
    cites = pd.to_numeric(getattr(row, "citation_count_work", 0), errors="coerce")
    cites_i = int(cites) if pd.notna(cites) else 0
    return {
        "work_id": s(getattr(row, "work_id", "")),
        "canonical_paper_id": pid,
        "source_group": SOURCE_GROUP,
        "version_count": 1,
        "member_paper_ids": pid,
        "member_dois": doi.lower(),
        "title": s(getattr(row, "title", "")),
        "abstract": s(getattr(row, "abstract", "")),
        "authors": s(getattr(row, "authors", "")),
        "year": getattr(row, "year", ""),
        "venue": s(getattr(row, "venue", "")),
        "doi": doi,
        "publication_types": s(getattr(row, "publication_types", "")) or "JournalArticle",
        "citation_count_work": cites_i,
        "citation_count_sum_versions": cites_i,
        "citation_aggregation_note": "manual seed; single version",
        "has_recovered_bridge_version": False,
        "has_retained_version": False,
    }


def merge_seed_works(
    works: pd.DataFrame,
    *,
    path: Path | None = None,
) -> pd.DataFrame:
    """Append seed metadata rows that are not already in canonical works."""
    seeds = load_manual_seeds(path)
    if seeds.empty or "work_id" not in seeds.columns:
        return works
    have_ids = (
        set(works.work_id.astype(str))
        if works is not None and not works.empty and "work_id" in works.columns
        else set()
    )
    have_dois = existing_dois(works)
    extra: list[dict[str, Any]] = []
    for row in seeds.itertuples(index=False):
        wid = s(getattr(row, "work_id", ""))
        doi = norm_doi(getattr(row, "doi", ""))
        if not wid:
            continue
        if wid in have_ids or (doi and doi in have_dois):
            continue
        extra.append(work_row(row))
        have_ids.add(wid)
        if doi:
            have_dois.add(doi)
    if not extra:
        return works
    seeded = pd.DataFrame(extra)
    if works is None or works.empty:
        return seeded
    return pd.concat([works, seeded], ignore_index=True, sort=False)


def merge_manual_seeds(
    results: pd.DataFrame,
    works: pd.DataFrame,
    *,
    path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Append seed works that are not already in results or canonical works."""
    seeds = load_manual_seeds(path)
    if seeds.empty or "work_id" not in seeds.columns:
        return results, works
    have_ids = set(results.work_id.astype(str)) if results is not None and not results.empty else set()
    have_dois = existing_dois(works)
    extra_results: list[dict[str, Any]] = []
    extra_works: list[dict[str, Any]] = []
    for row in seeds.itertuples(index=False):
        wid = s(getattr(row, "work_id", ""))
        doi = norm_doi(getattr(row, "doi", ""))
        if not wid:
            continue
        if wid in have_ids or (doi and doi in have_dois):
            continue
        extra_results.append(result_row(row))
        extra_works.append(work_row(row))
        have_ids.add(wid)
        if doi:
            have_dois.add(doi)
    works_out = works
    if extra_works:
        seeded_works = pd.DataFrame(extra_works)
        works_out = (
            pd.concat([works, seeded_works], ignore_index=True, sort=False)
            if works is not None and not works.empty
            else seeded_works
        )
    if not extra_results:
        return results, works_out
    seeded_results = pd.DataFrame(extra_results)
    results_out = (
        pd.concat([results, seeded_results], ignore_index=True, sort=False)
        if results is not None and not results.empty
        else seeded_results
    )
    return results_out, works_out
