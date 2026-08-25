#!/usr/bin/env python3
"""Deterministic checks for citation_tier_overlay.py.

    python analysis/test_citation_tier_overlay.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
S = importlib.util.spec_from_file_location("citation_tier_overlay", HERE / "citation_tier_overlay.py")
mod = importlib.util.module_from_spec(S)
S.loader.exec_module(mod)


def test_old_cite_band_becomes_gem() -> None:
    q, reason = mod.contextual_quality(
        year=2018, cites=3, max_io=0, out_deg=0, decision="adjacent_relevant"
    )
    assert q == "hidden_gem" and reason == "old_cite_band_2_to_4"
    q, reason = mod.contextual_quality(
        year=2016, cites=4, max_io=1, out_deg=1, decision="core_relevant"
    )
    assert q == "hidden_gem" and reason == "old_cite_band_2_to_4"


def test_old_five_cites_stays_contextual() -> None:
    q, reason = mod.contextual_quality(
        year=2019, cites=5, max_io=0, out_deg=0, decision="adjacent_relevant"
    )
    assert q == "pass" and reason == "ok"


def test_old_uncited_split() -> None:
    q, reason = mod.contextual_quality(
        year=2015, cites=1, max_io=0, out_deg=0, decision="adjacent_relevant"
    )
    assert q == "drop" and reason == "old_uncited_unlinked"
    q, reason = mod.contextual_quality(
        year=2015, cites=1, max_io=1, out_deg=0, decision="adjacent_relevant"
    )
    assert q == "hidden_gem" and reason == "old_uncited_linked"


def test_young_untouched() -> None:
    q, reason = mod.contextual_quality(
        year=2022, cites=3, max_io=0, out_deg=0, decision="adjacent_relevant"
    )
    assert q == "pass"
    q, reason = mod.contextual_quality(
        year=2024, cites=0, max_io=0, out_deg=0, decision="core_relevant"
    )
    assert q == "hidden_gem" and reason == "young_core_thin"


def test_connected_old_low_cite_stays_in_ring() -> None:
    q, _ = mod.contextual_quality(
        year=2018, cites=3, max_io=6, out_deg=6, decision="adjacent_relevant"
    )
    assert q == "pass"


def test_annotate_layers() -> None:
    corpus = pd.DataFrame(
        [
            {
                "work_id": "u1",
                "decision": "core_relevant",
                "ultra_core": True,
                "citation_count_work": 400,
                "corpus_in_degree": 10,
                "corpus_out_degree": 2,
                "citation_role": "broker",
                "graph_status": "integrated",
                "year": 2015,
                "title": "Ultra",
            },
            {
                "work_id": "g1",
                "decision": "adjacent_relevant",
                "ultra_core": False,
                "citation_count_work": 3,
                "corpus_in_degree": 0,
                "corpus_out_degree": 0,
                "citation_role": "isolate",
                "graph_status": "weak_unlinked",
                "year": 2018,
                "title": "Old 3 cites",
            },
        ]
    )
    out = mod.annotate_corpus(corpus, emergent_ids=set(), roles_map={})
    assert out.loc[out.work_id == "u1", "proposed_layer"].iloc[0] == "ultra"
    assert out.loc[out.work_id == "g1", "proposed_layer"].iloc[0] == "hidden_gem"


def main() -> None:
    test_old_cite_band_becomes_gem()
    test_old_five_cites_stays_contextual()
    test_old_uncited_split()
    test_young_untouched()
    test_connected_old_low_cite_stays_in_ring()
    test_annotate_layers()
    print("ok")


if __name__ == "__main__":
    main()
