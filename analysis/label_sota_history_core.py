#!/usr/bin/env python3
"""Label the SOTA+history core on this run's analysis base.

Read-only on paper_links.csv. Does not overwrite dryrun_work_tags.csv.
Uses the dry-run codebook (pipeline stages + registry datasets) plus v5 axis
names already used in exploration_strays_adjudicated.csv.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from build_corpus_filter_comparison import (  # noqa: E402
    STAGE_NAMES,
    TIME_BINS,
    analysis_base_ids,
    sota_history_flags,
    time_bin_of,
)

CATALOG = ROOT / "postanalysis/pdfs/paper_links.csv"
JSON_IN = ROOT / "postanalysis/llm_agent_v3/corpus_filter_comparison.json"
TAGS = ROOT / "postanalysis/registry/dryrun_work_tags.csv"
STRAYS = ROOT / "postanalysis/registry/exploration_strays_adjudicated.csv"
METHODS = ROOT / "postanalysis/registry/methods_registry_draft.csv"
ENRICHED = ROOT / "postanalysis/enriched2/canonical_works_enriched_pass2.csv"
SEEDS = ROOT / "postanalysis/works/manual_seed_works.csv"
OUT_CSV = ROOT / "postanalysis/registry/sota_history_core_labeled.csv"
OUT_JSON = ROOT / "postanalysis/llm_agent_v3/sota_history_core_labeled.json"

# Same codebook as analysis/dryrun_charting.py (do not invent a parallel taxonomy).
DATASETS = {
    "DS01 C. elegans (White+)": r"c\.? ?elegans|caenorhabditis",
    "DS03 Drosophila larva": r"drosophila larva|larval drosophila",
    "DS04 FAFB": r"\bfafb\b|full adult fly brain",
    "DS05 hemibrain": r"\bhemibrain\b",
    "DS06 FlyWire": r"\bflywire\b",
    "DS07 VNC (FANC/MANC)": r"ventral nerve cord|\bfanc\b|\bmanc\b",
    "DS09/DS10 mouse retina": r"mouse retina|retinal connectom",
    "DS11 Kasthuri neocortex": r"\bkasthuri\b|saturated reconstruction of a volume of neocortex",
    "DS13 MICrONS": r"\bmicrons\b",
    "DS14 H01 human cortex": r"\bh01\b|petavoxel fragment of human",
    "DS15 zebrafish": r"\bzebrafish\b|\bdanio\b",
    "DS19 songbird": r"songbird|zebra finch",
    "DS21 octopus": r"\boctopus\b",
    "DS22 Platynereis": r"\bplatynereis\b",
}
STAGES = {
    "preparation": r"stain|fixat|embed|osmium|\broto\b|sample preparation|extracellular space",
    "sectioning": r"serial.section|ultramicrotom|\batum\b|tape.collect|fib.?sem|focused ion beam|block.?face|milling|hot.?knife|gridtape|gcib",
    "acquisition": r"multibeam|multi.?beam|camera array|\btemca\b|scanning electron|transmission electron|volume electron",
    "alignment": r"\balignment\b|\bregistration\b|\bstitching\b",
    "segmentation": r"segment|affinit|agglomerat|flood.?filling|supervoxel",
    "proofreading": r"proofread|annotation|tracing|skeleton|eyewire|catmaid",
    "synapses": r"synapse detection|synaptic partner|synapse prediction|synaptic cleft",
    "infrastructure": r"\bbossdb\b|\bneuprint\b|neuroglancer|cloudvolume|\bdvid\b|\bcave\b",
    "graph_analysis": r"wiring diagram|connectome graph|connectivity matrix|\bmotifs?\b",
    "modeling": r"connectome.?constrained|connectome.?based model",
}
DS_ORG = {
    "DS01": "elegans",
    "DS02": "elegans",
    "DS03": "fly",
    "DS04": "fly",
    "DS05": "fly",
    "DS06": "fly",
    "DS07": "fly",
    "DS08": "fly",
    "DS09": "mouse",
    "DS10": "mouse",
    "DS11": "mouse",
    "DS12": "mouse",
    "DS13": "mouse",
    "DS16": "mouse",
    "DS14": "human",
    "DS15": "zebrafish",
    "DS19": "other",
    "DS20": "other",
    "DS21": "other",
    "DS22": "other",
}
ORG_TITLE = [
    (r"c\.? ?elegans|caenorhabditis", "elegans"),
    (r"\bdrosophila\b|\bflywire\b|\bhemibrain\b|\bfafb\b", "fly"),
    (r"\bzebrafish\b|\bdanio\b", "zebrafish"),
    (r"\bhuman (cerebral )?cortex\b|\bh01\b", "human"),
    (r"\bmouse\b|\bmus musculus\b|\bmicrons\b", "mouse"),
]


def _compile(d: dict[str, str]) -> dict[str, re.Pattern]:
    return {k: re.compile(v, re.I) for k, v in d.items()}


def load_abstracts() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (ENRICHED, SEEDS):
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                wid = str(r.get("work_id") or "")
                abs_ = (r.get("abstract") or "").strip()
                if wid and abs_ and wid not in out:
                    out[wid] = abs_
    return out


def datasets_to_orgs(datasets: str) -> str:
    orgs: list[str] = []
    seen: set[str] = set()
    for part in str(datasets or "").split(";"):
        tok = part.strip()
        if not tok:
            continue
        key = tok.split()[0].split("/")[0]
        org = DS_ORG.get(key)
        if org and org not in seen:
            seen.add(org)
            orgs.append(org)
    return ";".join(orgs)


def axis_from_stray(raw: str) -> str:
    s = (raw or "").lower()
    if s.startswith("bridge"):
        return "bridge"
    if s.startswith("conceptual") or "field synthesis" in s:
        return "field_synthesis"
    if s.startswith("biology") or s.startswith("analysis"):
        return "biological_application"
    if s.startswith("stage"):
        return ""
    return ""


def fill_labels(
    title: str,
    abstract: str,
    stages0: str,
    datasets0: str,
    stray_axis: str,
    method_name: str,
) -> tuple[str, str, str, str, str, str]:
    """Return stages, datasets, organism, axis, method, tag_source."""
    sources: list[str] = []
    stages = [s for s in str(stages0 or "").split(";") if s.strip()]
    datasets = [d for d in str(datasets0 or "").split(";") if d.strip()]
    if stages or datasets:
        sources.append("dryrun")
    text = f"{title} {abstract}"
    st_pat = _compile(STAGES)
    ds_pat = _compile(DATASETS)
    added_st = False
    added_ds = False
    if not stages:
        for name, pat in st_pat.items():
            if pat.search(title):  # title only for fills — abstract is too noisy
                stages.append(name)
                added_st = True
    if not datasets:
        for name, pat in ds_pat.items():
            if pat.search(title):
                datasets.append(name)
                added_ds = True
    if added_st or added_ds:
        sources.append("title_fill")
    organism = datasets_to_orgs(";".join(datasets))
    title_org = ""
    for pat, org in ORG_TITLE:
        if re.search(pat, title, re.I):
            title_org = org
            break
    if title_org:
        if organism and title_org not in organism.split(";"):
            organism = title_org
            sources.append("title_organism_overrides_dryrun")
        elif not organism:
            organism = title_org
            sources.append("title_organism")
    axis = axis_from_stray(stray_axis)
    if axis:
        sources.append("strays_axis")
    elif stages:
        axis = "pipeline_stage"
    elif datasets:
        axis = "registry_dataset"
    else:
        tl = title.lower()
        if re.search(r"\b(review|perspective|commentary|primer|editorial)\b", tl):
            axis = "field_synthesis"
            sources.append("title_axis")
        elif re.search(r"\b(circuit|wiring|connectome of)\b", tl) and not stages:
            axis = "biological_application"
            sources.append("title_axis")
    method = method_name
    if method:
        sources.append("methods_registry")
    src = "+".join(sources) if sources else "blank"
    return (
        ";".join(dict.fromkeys(stages)),
        ";".join(dict.fromkeys(datasets)),
        organism,
        axis,
        method,
        src,
    )


def main() -> None:
    cat = pd.read_csv(CATALOG, low_memory=False).drop_duplicates("work_id", keep="first")
    base = analysis_base_ids(cat)
    ws = base["ws"]
    payload = json.loads(JSON_IN.read_text())
    papers = payload["papers"]

    tags = pd.read_csv(TAGS)
    tag_map = {
        str(w): (str(s or ""), str(d or ""))
        for w, s, d in zip(
            tags["work_id"].astype(str),
            tags.get("stages", pd.Series("", index=tags.index)).fillna(""),
            tags.get("datasets", pd.Series("", index=tags.index)).fillna(""),
        )
    }
    stray = pd.read_csv(STRAYS)
    stray_map = {
        str(w): str(a or "")
        for w, a, adj in zip(
            stray["work_id"].astype(str),
            stray["axis_or_reason"].fillna(""),
            stray["adjudication"].fillna(""),
        )
        if str(adj) == "keep"
    }
    methods = pd.read_csv(METHODS)
    method_by_doi = {
        str(d).strip().lower(): str(m)
        for d, m in zip(methods["doi"].fillna(""), methods["method"].fillna(""))
        if str(d).strip()
    }
    abstracts = load_abstracts()

    rows = []
    if len(cat) != len(papers):
        raise SystemExit(f"catalog {len(cat)} vs papers {len(papers)}")
    n_mismatch = 0
    for r, p in zip(cat.itertuples(index=False), papers):
        rd = str(r.doi or "").strip().lower()
        pd_ = str(p.get("d") or "").strip().lower()
        if rd and pd_ and rd != pd_:
            n_mismatch += 1
    if n_mismatch:
        raise SystemExit(f"catalog/JSON order mismatch: {n_mismatch} DOI pairs differ")
    for r, p in zip(cat.itertuples(index=False), papers):
        wid = str(r.work_id)
        if not p.get("ws") or wid not in ws:
            continue
        doi = str(r.doi or "").strip()
        y = p.get("y")
        inn = int(p.get("i") or 0)
        out = int(p.get("o") or 0)
        k = int(p.get("k") or 0)
        pct = int(p.get("p") or 0)
        cites = int(p.get("c") or 0)
        inc, why = sota_history_flags(y, inn, out, pct, k, False)
        if not inc:
            continue
        era, _role = time_bin_of(y)
        st0, ds0 = tag_map.get(wid, ("", ""))
        stages, datasets, organism, axis, method, src = fill_labels(
            str(r.title or ""),
            abstracts.get(wid, ""),
            st0,
            ds0,
            stray_map.get(wid, ""),
            method_by_doi.get(doi.lower(), ""),
        )
        time_role = inc
        rows.append(
            {
                "work_id": wid,
                "doi": doi,
                "title": str(r.title or ""),
                "year": y if y is not None else "",
                "era": era,
                "time_role": time_role,
                "in_degree": inn,
                "out_degree": out,
                "k_core": k,
                "year_cites_percentile": pct,
                "cites": cites,
                "in_core": 1,
                "decision": str(getattr(r, "decision", "") or ""),
                "datasets": datasets,
                "stages": stages,
                "organism": organism,
                "axis": axis,
                "method": method,
                "tag_source": src,
                "why": why,
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    n_hist = sum(1 for r in rows if r["time_role"] == "history")
    n_sota = sum(1 for r in rows if r["time_role"] == "sota")

    def filled(col: str) -> tuple[int, float]:
        k = sum(1 for r in rows if str(r.get(col) or "").strip())
        return k, round(100.0 * k / n, 1) if n else 0.0

    stats = {
        "n_catalog": 1806,
        "n_named_working_set": 1544,
        "n_analysis_base": len(ws),
        "n_core": n,
        "n_history": n_hist,
        "n_sota": n_sota,
        "n_fill_outside_catalog": base["n_fill_outside"],
        "n_unavail_dropped": len(base["unavail"]),
        "unavail_disposition": "drop all four (none a unique milestone; GCIB landmark is 10.1038/s41592-019-0641-2 in the working set)",
        "bins": [b[0] for b in TIME_BINS],
        "bin_scheme": "2-year for 2016–2023 (yearly cells too sparse per topic); 2024–2026 yearly SOTA",
        "fill_pct": {c: filled(c) for c in ("stages", "datasets", "organism", "axis", "method")},
        "tag_source_counts": {},
        "untagged_axis_and_stage": sum(
            1 for r in rows if not r["stages"] and not r["datasets"] and not r["axis"]
        ),
    }
    from collections import Counter

    stats["tag_source_counts"] = dict(Counter(r["tag_source"] for r in rows))

    compact = []
    for r in rows:
        compact.append(
            {
                "y": r["year"] if r["year"] != "" else None,
                "i": r["in_degree"],
                "o": r["out_degree"],
                "k": r["k_core"],
                "p": r["year_cites_percentile"],
                "c": r["cites"],
                "id": r["work_id"],
                "role": r["time_role"],
                "era": r["era"],
                "st": r["stages"],
                "ds": r["datasets"],
                "og": r["organism"],
                "ax": r["axis"],
                "m": r["method"],
                "dec": r["decision"],
                "t": (r["title"][:96] + "…") if len(r["title"]) > 96 else r["title"],
                "d": r["doi"],
            }
        )
    OUT_JSON.write_text(
        json.dumps({"meta": stats, "papers": compact}, separators=(",", ":")),
        encoding="utf-8",
    )
    print("base", len(ws), "core", n, "history", n_hist, "sota", n_sota)
    print("fill %", stats["fill_pct"])
    print("sources", stats["tag_source_counts"])
    print("blank stage+dataset+axis", stats["untagged_axis_and_stage"])
    print("wrote", OUT_CSV)
    print("wrote", OUT_JSON)
    # example rows
    for role in ("history", "sota"):
        cands = [r for r in rows if r["time_role"] == role]
        if not cands:
            continue
        key = (lambda r: (r["k_core"], r["year_cites_percentile"], r["in_degree"])) if role == "history" else (
            lambda r: (r["out_degree"], r["in_degree"], r["k_core"])
        )
        ex = max(cands, key=key)
        print(
            f"EX {role} {ex['year']} {ex['stages'] or '—'} {ex['organism'] or '—'} "
            f"{ex['title'][:70]} | {ex['doi']}"
        )


if __name__ == "__main__":
    main()
