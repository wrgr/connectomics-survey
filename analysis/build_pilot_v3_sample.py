#!/usr/bin/env python3
"""Build stratified IA-007-v3 pilot sample and export prompts."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import pandas as pd

# Hand-picked boundary cases for golden reference screening
GOLDEN_WORK_IDS = [
    # v2 false-positive ultra-core / core noise
    "work_087e18b9051261d3",  # motion detection Drosophila - true core
    "work_5b3cc3d12b85117b",  # computational framework ultrastructural - borderline
    # We'll resolve by title lookup below - use known titles from ultra_core list
]

GOLDEN_TITLES = [
    "Microglia Sculpt Postnatal Neural Circuits",
    "The Caenorhabditis elegans Gene unc-25Encodes Glutamic Acid Decarboxylase",
    "Computer visualization of three-dimensional image data using IMOD",
    "Comparative Connectomics.",
    "Microscopy Image Browser: A Platform for Segmentation",
    "A connectome and analysis of the adult Drosophila central brain",
    "FlyWire: Online community for whole-brain connectomics",
    "TrakEM2 Software for Neural Circuit Reconstruction",
    "Harmonizing 10,000 connectomes",
    "Semi-Metric Topology of the Human Connectome",
    "The human connectome in Alzheimer disease",
    "Crowdsourcing the creation of image segmentation algorithms for connectomics",
    "Volume electron microscopy for neuronal circuit reconstruction.",
    "The complete connectome of a learning and memory centre in an insect brain",
    "A petavoxel fragment of human cerebral cortex reconstructed at nanoscale resolution",
    "Whole-brain annotation and multi-connectome cell typing of Drosophila",
    "The neural circuit for touch sensitivity in Caenorhabditis elegans",
    "Structural Properties of the Caenorhabditis elegans Neuronal Network",
    "The Rich Club of the C. elegans Neuronal Connectome",
    "Connectomic comparison of mouse and human cortex",
    "Large Scale Image Segmentation with Structured Loss Based Deep Learning for Connectomics",
    "A dopamine gradient controls access to distributed working memory in monkey cortex",
    "Intrinsic elaboration of prefrontal modularity",
    "Role of neural activity during synaptogenesis in Drosophila",
    "Scalable graph analysis tools for the connectomics community",
    "DotMotif: an open-source tool for connectome subgraph isomorphism search",
    "CONFIRMS: A Toolkit for Scalable, Black Box Connectome Assessment",
    "An automated images-to-graphs framework for high resolution connectomics",
    "Nanoscale Connectomics Annotation Standards Framework",
    "Exploiting large neuroimaging datasets to create connectome-constrained approaches",
]


def match_golden(corpus: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for frag in GOLDEN_TITLES:
        hit = corpus[corpus.title.fillna("").str.contains(frag[:40], case=False, regex=False)]
        if len(hit):
            rows.append(hit.iloc[0])
    return pd.DataFrame(rows).drop_duplicates("work_id") if rows else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=Path("postanalysis/llm_agent/llm_relevance_results.csv"))
    ap.add_argument("--works-csv", type=Path, default=Path("postanalysis/enriched/canonical_works_enriched.csv"))
    ap.add_argument("--ultra-core", type=Path, default=Path("postanalysis/checkpoint/label_ultra_core.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/llm_agent/pilot_v3"))
    ap.add_argument("--n-random", type=int, default=165)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    results = pd.read_csv(args.results, low_memory=False)
    works = pd.read_csv(args.works_csv, low_memory=False)
    results["work_id"] = results.work_id.astype(str)
    works["work_id"] = works.work_id.astype(str)
    merged = results.merge(
        works[["work_id", "abstract", "citation_count_work", "year", "venue"]],
        on="work_id",
        how="left",
    )

    golden = match_golden(merged)
    golden_ids = set(golden.work_id.astype(str))

    # Stratified remainder from v2 decisions not in golden
    pool = merged[~merged.work_id.isin(golden_ids)].copy()
    rng = random.Random(args.seed)
    strata = []
    targets = [
        ("core_relevant", 40),
        ("adjacent_relevant", 35),
        ("role_bridge", 25),
        ("out_of_scope", 35),
        ("uncertain", 15),
    ]
    for decision, n in targets:
        sub = pool[pool.decision == decision]
        if len(sub) <= n:
            strata.append(sub)
        else:
            strata.append(sub.sample(n=n, random_state=args.seed + hash(decision) % 1000))

    sample = pd.concat([golden.assign(pilot_stratum="golden")] + [s.assign(pilot_stratum=decision) for s, (decision, _) in zip(strata, targets)], ignore_index=True)
    sample = sample.drop_duplicates("work_id")
    if len(sample) < 200 and len(pool) > len(sample):
        extra = pool[~pool.work_id.isin(sample.work_id)].sample(
            n=min(200 - len(sample), len(pool) - len(sample)),
            random_state=args.seed,
        )
        sample = pd.concat([sample, extra.assign(pilot_stratum="fill")], ignore_index=True)

    args.out.mkdir(parents=True, exist_ok=True)
    sample.to_csv(args.out / "pilot_v3_sample.csv", index=False)

    summary = {
        "n_total": int(len(sample)),
        "golden_n": int((sample.pilot_stratum == "golden").sum()),
        "v2_decision_counts": sample.decision.value_counts().to_dict(),
        "stratum_counts": sample.pilot_stratum.value_counts().to_dict(),
    }
    (args.out / "pilot_v3_sample_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
