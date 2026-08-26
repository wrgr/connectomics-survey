#!/usr/bin/env python3
"""Exploration dry-run of v5 charting (DRAFT; no protocol standing).

Machine-tags the pilot working corpus (1,806 works) with the placeholder
registry's controlled vocabularies — dataset mentions and pipeline stages —
by keyword matching over title+abstract. Purpose: test whether the charting
taxonomy partitions the literature, and preview stage × era and
dataset-usage counts. Entirely descriptive, entirely provisional; formal
charting re-does this per-work with human verification.

Outputs under postanalysis/registry/:
  dryrun_charting_counts.json   stage×era matrix, dataset usage, coverage
  dryrun_work_tags.csv          per-work draft tags (audit)
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "postanalysis" / "registry"
FULL = REPO / "postanalysis" / "llm_agent_v3" / "corpus_full_works.csv"
ENRICHED = REPO / "postanalysis" / "enriched2" / "canonical_works_enriched_pass2.csv"
SEEDS = REPO / "postanalysis" / "works" / "manual_seed_works.csv"

DATASETS = {
    "DS01 C. elegans (White+)": r"c\.? ?elegans|caenorhabditis|nematode",
    "DS03 Drosophila larva": r"larva[el]? (brain|cns|drosophila)|drosophila larva",
    "DS04 FAFB": r"fafb|full adult fly brain",
    "DS05 hemibrain": r"hemibrain",
    "DS06 FlyWire": r"flywire",
    "DS07 VNC (FANC/MANC)": r"ventral nerve cord|\bfanc\b|\bmanc\b",
    "DS09/DS10 mouse retina": r"retina",
    "DS11 Kasthuri neocortex": r"saturated reconstruction|kasthuri",
    "DS12 L4 barrel cortex": r"barrel cortex|layer 4",
    "DS13 MICrONS": r"microns|mm\^?3|cubic millimet",
    "DS14 H01 human cortex": r"\bh01\b|human (cerebral )?cortex.*(petavoxel|nanoscale|electron)",
    "DS15 zebrafish": r"zebrafish",
    "DS16 calyx of Held": r"calyx of held|mntb",
    "DS19 songbird": r"songbird|zebra finch|area x",
    "DS20 Ciona": r"\bciona\b|tadpole larva",
    "DS21 octopus": r"octopus",
    "DS22 Platynereis": r"platynereis|annelid",
}

STAGES = {
    "preparation": r"stain|fixat|embed|osmium|roto\b|sample preparation|extracellular space",
    "sectioning": r"serial.section|ultramicrotom|\batum\b|tape.collect|fib.sem|focused ion beam|block.?face|milling|hot.knife|gridtape",
    "acquisition": r"multibeam|multi.beam|camera array|temca|imaging speed|acquisition|scanning electron|transmission electron",
    "alignment": r"alignment|registration|stitching",
    "segmentation": r"segment|affinit|agglomerat|flood.filling|supervoxel",
    "proofreading": r"proofread|annotation|tracing|skeleton|crowd|citizen",
    "synapses": r"synapse detection|synaptic partner|synapse prediction|synaptic cleft",
    "infrastructure": r"database|storage|platform|versioning|serving|scalable|framework|cloud|neuroglancer|catmaid|bossdb|neuprint",
    "graph_analysis": r"motif|topolog|graph|network analysis|connectivity matrix|wiring diagram|hub|modularity|centrality",
    "modeling": r"connectome.constrained|simulat|biophysical model|computational model|neural network model",
}

ERAS = [(0, 2004, "pre-2005"), (2005, 2015, "2005-2015"), (2016, 2100, "2015-present")]


def era_of(y):
    try:
        y = int(float(y))
    except (TypeError, ValueError):
        return "unknown"
    for lo, hi, name in ERAS:
        if lo <= y <= hi:
            return name
    return "unknown"


def main():
    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    abstracts = {}
    with ENRICHED.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            abstracts[r["work_id"]] = r.get("abstract") or ""
    with SEEDS.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            abstracts.setdefault(r["work_id"], r.get("abstract") or "")

    ds_pat = {k: re.compile(v, re.I) for k, v in DATASETS.items()}
    st_pat = {k: re.compile(v, re.I) for k, v in STAGES.items()}

    rows_out = []
    ds_counter, st_counter = Counter(), Counter()
    st_era = defaultdict(Counter)
    n_any_ds = n_any_st = n_neither = 0

    with FULL.open(newline="", encoding="utf-8") as f:
        works = list(csv.DictReader(f))
    for w in works:
        text = (w.get("title") or "") + " " + abstracts.get(w["work_id"], "")
        ds = [k for k, p in ds_pat.items() if p.search(text)]
        st = [k for k, p in st_pat.items() if p.search(text)]
        era = era_of(w.get("year") or w.get("year_enr"))
        for k in ds:
            ds_counter[k] += 1
        for k in st:
            st_counter[k] += 1
            st_era[k][era] += 1
        n_any_ds += bool(ds)
        n_any_st += bool(st)
        n_neither += not ds and not st
        rows_out.append(
            {"work_id": w["work_id"], "year": w.get("year") or w.get("year_enr") or "",
             "decision": w.get("decision", ""), "datasets": ";".join(ds), "stages": ";".join(st),
             "title": (w.get("title") or "")[:140]}
        )

    with (OUT_DIR / "dryrun_work_tags.csv").open("w", newline="", encoding="utf-8") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows_out)

    counts = {
        "generated_at": run_ts,
        "status": "EXPLORATION DRY-RUN - draft tags, no protocol standing",
        "n_works": len(works),
        "coverage": {
            "tagged_with_any_dataset": n_any_ds,
            "tagged_with_any_stage": n_any_st,
            "untagged_by_both": n_neither,
        },
        "dataset_usage": dict(ds_counter.most_common()),
        "stage_counts": dict(st_counter.most_common()),
        "stage_by_era": {k: dict(v) for k, v in st_era.items()},
    }
    (OUT_DIR / "dryrun_charting_counts.json").write_text(
        json.dumps(counts, indent=2) + "\n", encoding="utf-8")

    print(f"works: {len(works)} | any-dataset: {n_any_ds} | any-stage: {n_any_st} | neither: {n_neither}")
    print("\ndataset usage (draft keyword tags):")
    for k, c in ds_counter.most_common():
        print(f"  {c:5d}  {k}")
    print("\nstage counts:")
    for k, c in st_counter.most_common():
        print(f"  {c:5d}  {k}")


if __name__ == "__main__":
    main()
