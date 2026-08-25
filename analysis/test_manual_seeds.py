#!/usr/bin/env python3
"""Deterministic checks for `analysis/manual_seeds.py`.

    python analysis/test_manual_seeds.py
"""
from __future__ import annotations

import csv
import importlib.util
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
S = importlib.util.spec_from_file_location("manual_seeds", HERE / "manual_seeds.py")
mod = importlib.util.module_from_spec(S)
S.loader.exec_module(mod)


def write_seeds(path: Path, rows: list[dict[str, str]]) -> Path:
    fields = [
        "work_id",
        "canonical_paper_id",
        "doi",
        "pmid",
        "title",
        "abstract",
        "authors",
        "year",
        "venue",
        "citation_count_work",
        "publication_types",
        "decision",
        "roles",
        "core_gate",
        "confidence",
        "scale_relationship",
        "seed_note",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})
    return path


def test_merge_adds_new_landmark(td: Path) -> None:
    seeds = write_seeds(
        td / "manual_seed_works.csv",
        [
            {
                "work_id": "work_seed1",
                "canonical_paper_id": "s2abc",
                "doi": "10.1038/nature12346",
                "title": "Connectomic reconstruction of the inner plexiform layer",
                "authors": "M. Helmstaedter",
                "year": "2013",
                "venue": "Nature",
                "citation_count_work": "988",
                "decision": "core_relevant",
                "roles": "['biological_application']",
                "core_gate": "em_or_synaptic_reconstruction",
                "confidence": "1.0",
                "scale_relationship": "nanoscale_only",
                "seed_note": "test seed",
            }
        ],
    )
    results = pd.DataFrame(
        [{"work_id": "work_old", "decision": "core_relevant", "title": "Already in"}]
    )
    works = pd.DataFrame(
        [{"work_id": "work_old", "doi": "10.9999/existing", "member_dois": "10.9999/existing", "title": "Already in"}]
    )
    out_r, out_w = mod.merge_manual_seeds(results, works, path=seeds)
    assert "work_seed1" in set(out_r.work_id.astype(str))
    assert "work_seed1" in set(out_w.work_id.astype(str))
    seeded = out_r[out_r.work_id == "work_seed1"].iloc[0]
    assert seeded.decision == "core_relevant"
    assert seeded.source_group == "manual_seed"
    assert int(out_w[out_w.work_id == "work_seed1"].iloc[0].citation_count_work) == 988


def test_skip_existing_doi_and_id(td: Path) -> None:
    seeds = write_seeds(
        td / "manual_seed_works.csv",
        [
            {
                "work_id": "work_dup_id",
                "canonical_paper_id": "x",
                "doi": "10.1111/new",
                "title": "Dup id",
                "citation_count_work": "10",
                "decision": "core_relevant",
            },
            {
                "work_id": "work_dup_doi",
                "canonical_paper_id": "y",
                "doi": "10.1038/already",
                "title": "Dup doi",
                "citation_count_work": "10",
                "decision": "core_relevant",
            },
        ],
    )
    results = pd.DataFrame([{"work_id": "work_dup_id", "decision": "adjacent_relevant"}])
    works = pd.DataFrame(
        [{"work_id": "work_other", "doi": "10.1038/already", "member_dois": "10.1038/already"}]
    )
    out_r, out_w = mod.merge_manual_seeds(results, works, path=seeds)
    assert list(out_r.work_id) == ["work_dup_id"]
    assert "work_dup_doi" not in set(out_w.work_id.astype(str))


def test_merge_seed_works_when_results_already_have_id(td: Path) -> None:
    seeds = write_seeds(
        td / "manual_seed_works.csv",
        [
            {
                "work_id": "work_seed1",
                "canonical_paper_id": "s2abc",
                "doi": "10.1038/nature12346",
                "title": "Connectomic reconstruction of the inner plexiform layer",
                "authors": "M. Helmstaedter",
                "year": "2013",
                "venue": "Nature",
                "citation_count_work": "988",
                "decision": "core_relevant",
            }
        ],
    )
    results = pd.DataFrame([{"work_id": "work_seed1", "decision": "core_relevant"}])
    works = pd.DataFrame([{"work_id": "work_old", "doi": "10.9999/existing"}])
    out_w = mod.merge_seed_works(works, path=seeds)
    assert "work_seed1" in set(out_w.work_id.astype(str))
    assert out_w[out_w.work_id == "work_seed1"].iloc[0].authors == "M. Helmstaedter"


def test_missing_file_is_noop(td: Path) -> None:
    results = pd.DataFrame([{"work_id": "w1", "decision": "core_relevant"}])
    works = pd.DataFrame([{"work_id": "w1", "doi": "10.1/x"}])
    out_r, out_w = mod.merge_manual_seeds(results, works, path=td / "absent.csv")
    assert list(out_r.work_id) == ["w1"]
    assert list(out_w.work_id) == ["w1"]


def main() -> None:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        test_merge_adds_new_landmark(td)
        test_skip_existing_doi_and_id(td)
        test_merge_seed_works_when_results_already_have_id(td)
        test_missing_file_is_noop(td)
    print("ok")


if __name__ == "__main__":
    main()
