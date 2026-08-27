#!/usr/bin/env python3
"""Precompute k-core, citation, and equitable ranks for the 1,806-work catalog.

Read-only on paper_links.csv. Writes derived JSON for the canvas.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "postanalysis/pdfs/paper_links.csv"
FULL = ROOT / "postanalysis/llm_agent_v3/corpus_full_works.csv"
EDGES = ROOT / "source_artifact/connectomics_deterministic_pipeline/outputs/paper_graph_edges.csv"
EXCL = ROOT / "postanalysis/registry/exploration_screener_exclusions.csv"
UNAVAIL = ROOT / "postanalysis/registry/exploration_pdf_unavailable.csv"
FILL = ROOT / "postanalysis/registry/exploration_fill_candidates.csv"
REG = ROOT / "postanalysis/registry"
TAGS = ROOT / "postanalysis/registry/dryrun_work_tags.csv"
OUT_JSON = ROOT / "postanalysis/llm_agent_v3/corpus_filter_comparison.json"
OUT_TOPIC = ROOT / "postanalysis/registry/importance_by_topic_time.csv"
OUT_PAPER = ROOT / "postanalysis/registry/importance_paper_measures.csv"

STAGE_NAMES = [
    "preparation",
    "sectioning",
    "acquisition",
    "alignment",
    "segmentation",
    "proofreading",
    "synapses",
    "infrastructure",
    "graph_analysis",
    "modeling",
]
ORG_NAMES = ["elegans", "fly", "mouse", "human", "zebrafish", "other"]
ORG_PREFIX = {
    "DS01": 0,
    "DS03": 1,
    "DS04": 1,
    "DS05": 1,
    "DS06": 1,
    "DS07": 1,
    "DS09": 2,
    "DS10": 2,
    "DS11": 2,
    "DS12": 2,
    "DS13": 2,
    "DS16": 2,
    "DS14": 3,
    "DS15": 4,
    "DS19": 5,
    "DS20": 5,
    "DS21": 5,
    "DS22": 5,
}
# Historical ≤2018; contemporary 2019–2024 yearly; SOTA 2025–2026.
TIME_BINS = [
    ("pre-2005", "history", 0, 2004),
    ("2005–2009", "history", 2005, 2009),
    ("2010–2015", "history", 2010, 2015),
    ("2016–2018", "history", 2016, 2018),
    ("2019", "contemporary", 2019, 2019),
    ("2020", "contemporary", 2020, 2020),
    ("2021", "contemporary", 2021, 2021),
    ("2022", "contemporary", 2022, 2022),
    ("2023", "contemporary", 2023, 2023),
    ("2024", "contemporary", 2024, 2024),
    ("2025", "sota", 2025, 2025),
    ("2026", "sota", 2026, 2026),
]
# Default inclusion (today = 2026).
# Historical ≤2018: P≥50 or k≥3.
# Contemporary 2019–2024: that bar OR Out≥3.
# SOTA: 2026 Out≥3 OR In≥1; 2025 Out≥3 AND In≥2.
DEF_OUT_MIN = 3
DEF_IN_2026 = 1
DEF_IN_2025 = 2
DEF_IN_2024 = 3
DEF_HIST_P = 50
DEF_HIST_K = 3

MIN_COHORT = 8
DAMPING = 0.85
# Newest paper gets ~10× the teleport mass of the oldest.
TPR_ALPHA_SPAN = math.log(10.0)


def _year_int(v) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        y = int(float(v))
    except (TypeError, ValueError):
        return None
    return y if 1800 < y < 2100 else None


def pagerank(
    G: nx.DiGraph,
    alpha: float = 0.85,
    personalization: dict[str, float] | None = None,
    weight: str | None = None,
    max_iter: int = 100,
    tol: float = 1.0e-6,
) -> dict[str, float]:
    """Power-iteration PageRank (dangling mass redistributed via teleport)."""
    nodes = list(G)
    n = len(nodes)
    if n == 0:
        return {}
    idx = {v: i for i, v in enumerate(nodes)}
    if personalization is None:
        pers = [1.0 / n] * n
    else:
        total = sum(personalization.get(v, 0.0) for v in nodes)
        if total <= 0:
            pers = [1.0 / n] * n
        else:
            pers = [personalization.get(v, 0.0) / total for v in nodes]
    succs: list[list[tuple[int, float]]] = []
    out_w: list[float] = []
    for v in nodes:
        if weight is None:
            edges = [(idx[u], 1.0) for u in G.successors(v)]
        else:
            edges = [(idx[u], float(G[v][u].get(weight, 1.0))) for u in G.successors(v)]
        succs.append(edges)
        out_w.append(sum(w for _, w in edges))
    dangling = [i for i, tot in enumerate(out_w) if tot == 0]
    x = pers[:]
    for _ in range(max_iter):
        xlast = x
        x = [0.0] * n
        dangle_sum = sum(xlast[i] for i in dangling)
        for i, tot in enumerate(out_w):
            if tot == 0:
                continue
            scale = alpha * xlast[i] / tot
            for j, w in succs[i]:
                x[j] += scale * w
        jump = 1.0 - alpha
        for i in range(n):
            x[i] += (jump + alpha * dangle_sum) * pers[i]
        if sum(abs(x[i] - xlast[i]) for i in range(n)) < n * tol:
            break
    return {nodes[i]: x[i] for i in range(n)}


def in_core_numbers(G: nx.DiGraph) -> dict[str, int]:
    """k-in-core: peel by in-degree. Edge citing → cited."""
    remaining = set(G.nodes())
    preds = {n: set(G.predecessors(n)) for n in G}
    core = {n: 0 for n in G}
    k = 1
    while remaining:
        changed = True
        while changed:
            changed = False
            drop = [
                n
                for n in remaining
                if sum(1 for p in preds[n] if p in remaining) < k
            ]
            if drop:
                changed = True
                for n in drop:
                    remaining.remove(n)
                    core[n] = k - 1
        if remaining:
            for n in remaining:
                core[n] = k
            k += 1
            if k > 80:
                break
    return core


def year_cohorts(years: pd.Series, min_n: int = MIN_COHORT) -> dict[int, str]:
    """Map each year to a cohort label; merge sparse years forward/back."""
    known = years.dropna().astype(int)
    if known.empty:
        return {}
    counts = known.value_counts().sort_index()
    bins: list[tuple[int, int, int]] = []  # lo, hi, n
    cur_lo = cur_hi = None
    cur_n = 0
    for y, n in counts.items():
        y, n = int(y), int(n)
        if cur_lo is None:
            cur_lo = cur_hi = y
            cur_n = n
        else:
            cur_hi = y
            cur_n += n
        if cur_n >= min_n:
            bins.append((cur_lo, cur_hi, cur_n))
            cur_lo = cur_hi = None
            cur_n = 0
    if cur_lo is not None:
        if bins:
            lo, hi, n = bins[-1]
            bins[-1] = (lo, cur_hi, n + cur_n)
        else:
            bins.append((cur_lo, cur_hi, cur_n))
    year_to = {}
    for lo, hi, _n in bins:
        label = str(lo) if lo == hi else f"{lo}–{hi}"
        for y in range(lo, hi + 1):
            year_to[y] = label
    return year_to


def decade_of(y: int | None) -> str:
    if y is None:
        return "unknown"
    if y < 1980:
        return "pre-1980"
    return f"{(y // 10) * 10}s"


def truncate(s: str, n: int = 96) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def time_bin_of(y: int | None) -> tuple[str, str]:
    if y is None:
        return "unknown", "history"
    for label, role, lo, hi in TIME_BINS:
        if lo <= y <= hi:
            return label, role
    if y < 2005:
        return "pre-2005", "history"
    return "2026", "sota"


def overlay_drop_ids() -> set[str]:
    """Unique overlay removals from the 1,806 catalog (EXPLORATION_SET.md: 315)."""
    drops: set[str] = set()
    prune = pd.read_csv(REG / "exploration_prune_adjudicated.csv")
    drops |= set(prune.loc[prune["adjudication"] == "drop-confirmed", "work_id"].astype(str))
    disc = pd.read_csv(REG / "exploration_disconnected.csv")
    drops |= set(disc.loc[disc["disposition"].astype(str).str.startswith("drop"), "work_id"].astype(str))
    unm = pd.read_csv(REG / "exploration_unmatched_resolved.csv")
    zero = unm[unm["final_disposition"].astype(str).str.contains("zero outbound", na=False)]
    drops |= set(zero.loc[zero["year"] < 2024, "work_id"].astype(str))
    recent = pd.read_csv(REG / "exploration_recent_verified.csv")
    drops |= set(
        recent.loc[recent["final_disposition"].astype(str).str.startswith("drop"), "work_id"].astype(str)
    )
    oa = pd.read_csv(REG / "exploration_oa_ref_resolution.csv")
    od = oa["oa_disposition"].fillna("").astype(str)
    drops |= set(
        oa.loc[
            od.str.contains(r"^drop|adjudicated: drop|adjudicated: out of scope", regex=True),
            "work_id",
        ].astype(str)
    )
    odd = pd.read_csv(REG / "exploration_odd_types.csv")
    drops |= set(odd.loc[odd["disposition"].astype(str).str.startswith("drop"), "work_id"].astype(str))
    stray = pd.read_csv(REG / "exploration_strays_adjudicated.csv")
    drops |= set(stray.loc[stray["adjudication"] == "drop-noted", "work_id"].astype(str))
    drops |= set(pd.read_csv(EXCL)["work_id"].astype(str))
    return drops


def analysis_base_ids(cat: pd.DataFrame) -> dict:
    """Catalog-measurable analysis base for this run.

    Named working set in EXPLORATION_SET.md is 1,544 = 1,491 retained + 53 fill.
    Fill papers not in paper_links.csv are not ingested (catalog read-only).
    Denk 2004 (fill candidate, catalog row, overlay unmatched-zero) is re-admitted.
    Four confirmed-unavailable PDFs are dropped for this run (none is a unique milestone).
    """
    cat_ids = set(cat["work_id"].astype(str))
    doi_to_wid = {
        str(d).strip().lower(): str(w)
        for d, w in zip(cat["doi"].fillna(""), cat["work_id"])
        if str(d).strip()
    }
    drops = overlay_drop_ids()
    retained = cat_ids - drops
    fill = pd.read_csv(FILL)
    fill_rescue: set[str] = set()
    fill_outside = 0
    for doi in fill["doi"].fillna(""):
        wid = doi_to_wid.get(str(doi).strip().lower())
        if not wid:
            fill_outside += 1
        elif wid in drops:
            fill_rescue.add(wid)
    unavail = set(pd.read_csv(UNAVAIL)["work_id"].astype(str))
    ws = (retained | fill_rescue) - unavail
    return {
        "ws": ws,
        "unavail": unavail,
        "retained": retained,
        "fill_rescue": fill_rescue,
        "n_fill_outside": fill_outside,
        "n_named_working_set": 1544,
    }


def stage_bits(stages_raw: str) -> int:
    bits = 0
    for part in str(stages_raw or "").split(";"):
        name = part.strip()
        if name in STAGE_NAMES:
            bits |= 1 << STAGE_NAMES.index(name)
    return bits


def org_bits(datasets_raw: str) -> int:
    bits = 0
    for part in str(datasets_raw or "").split(";"):
        tok = part.strip()
        if not tok:
            continue
        key = tok.split()[0].split("/")[0]
        if key in ORG_PREFIX:
            bits |= 1 << ORG_PREFIX[key]
        elif "/" in tok:
            for piece in tok.replace("/", " ").split():
                if piece in ORG_PREFIX:
                    bits |= 1 << ORG_PREFIX[piece]
    return bits


def has_bit(mask: int, i: int) -> bool:
    return (mask & (1 << i)) != 0


def sota_history_flags(
    y: int | None,
    inn: int,
    out: int,
    pct: int,
    core: int,
    excluded: bool,
    out_min: int = DEF_OUT_MIN,
    in_2026: int = DEF_IN_2026,
    in_2025: int = DEF_IN_2025,
    in_2024: int = DEF_IN_2024,
    hist_p: int = DEF_HIST_P,
    hist_k: int = DEF_HIST_K,
) -> tuple[str, str]:
    """Return (role, why). role is history | contemporary | sota | "".

    Historical (≤2018): year-cites percentile ≥ hist_p or k-core ≥ hist_k.
    Contemporary (2019–2024): that bar OR Out ≥ out_min.
    SOTA: 2026 Out≥out_min OR In≥in_2026; 2025 Out≥out_min AND In≥in_2025.
    in_2024 is unused (2024 is contemporary).
    """
    if excluded or y is None:
        return "", "off-topic or no year"
    if y == 2026:
        ok = out >= out_min or inn >= in_2026
        if ok:
            why = "sota_2026_out" if out >= out_min else "sota_2026_in"
        else:
            why = "unproven_2026_low_out"
        return ("sota" if ok else ""), why
    if y == 2025:
        ok = out >= out_min and inn >= in_2025
        return ("sota" if ok else ""), ("sota_2025_out_and_in" if ok else "unproven_2025_low_inout")
    if 2019 <= y <= 2024:
        ok = pct >= hist_p or core >= hist_k or out >= out_min
        return ("contemporary" if ok else ""), ("contemporary_keep" if ok else "contemporary_below_bar")
    hist = pct >= hist_p or core >= hist_k
    return ("history" if hist else ""), ("history_milestone" if hist else "history_below_bar")


def inclusion_role(p: dict, excluded: bool | None = None) -> str:
    if excluded is None:
        excluded = bool(p.get("x"))
    role, _why = sota_history_flags(p["y"], p["i"], p["o"], p["p"], p["k"], excluded)
    return role


def write_importance_tables(df: pd.DataFrame, papers: list[dict]) -> None:
    """Topic × time fill-out (v5 stage × era) plus per-work measure vectors."""
    import csv

    rows_paper = []
    wids = df["work_id"].astype(str).tolist()
    for wid, p in zip(wids, papers):
        if not p.get("ws"):
            continue
        tb, bin_role = time_bin_of(p["y"])
        inc, why = sota_history_flags(
            p["y"], p["i"], p["o"], p["p"], p["k"], not p.get("ws", False)
        )
        stages = ";".join(STAGE_NAMES[i] for i in range(len(STAGE_NAMES)) if has_bit(p["st"], i))
        orgs = ";".join(ORG_NAMES[i] for i in range(len(ORG_NAMES)) if has_bit(p["og"], i))
        rows_paper.append(
            {
                "work_id": wid,
                "year": p["y"] if p["y"] is not None else "",
                "title": p["t"],
                "doi": p["d"],
                "on_topic": "" if p["x"] else "yes",
                "pipeline_stages": stages,
                "organisms": orgs,
                "time_bin": tb,
                "time_role": bin_role,
                "in_degree": p["i"],
                "out_degree": p["o"],
                "cites": p["c"],
                "year_cites_percentile": p["p"],
                "k_core": p["k"],
                "decade_k_core": p["kd"],
                "static_pagerank_pct": p["pr"],
                "temporal_pagerank_pct": p["tpr"],
                "history_milestone": "yes" if inc == "history" else "",
                "contemporary": "yes" if inc == "contemporary" else "",
                "sota_proving": "yes" if inc == "sota" else "",
                "sota_plus_history": "yes" if inc else "",
                "why": why,
            }
        )

    OUT_PAPER.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PAPER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_paper[0].keys()))
        w.writeheader()
        w.writerows(rows_paper)

    def in_bin(p: dict, lo: int, hi: int) -> bool:
        return p["y"] is not None and lo <= p["y"] <= hi

    def pick_hist(cands: list[dict]) -> dict | None:
        if not cands:
            return None
        return max(cands, key=lambda p: (p["k"], p["p"], p["i"], p["c"]))

    def pick_sota(cands: list[dict], y: int) -> dict | None:
        if not cands:
            return None
        if y == 2026:
            return max(cands, key=lambda p: (p["o"], p["k"], p["c"]))
        return max(cands, key=lambda p: (p["i"], p["o"], p["k"], p["c"]))

    topic_rows = []
    topics: list[tuple[str, str, callable]] = [
        ("pipeline_stage", name, lambda p, i=i: has_bit(p["st"], i))
        for i, name in enumerate(STAGE_NAMES)
    ]
    topics.append(("pipeline_stage", "untagged_needs_axis_coding", lambda p: p["st"] == 0))
    for i, name in enumerate(ORG_NAMES):
        topics.append(("organism", name, lambda p, i=i: has_bit(p["og"], i)))
    topics.append(("organism", "no_dataset_tag", lambda p: p["og"] == 0))

    for kind, topic, match in topics:
        for label, role, lo, hi in TIME_BINS:
            cell = [p for p in papers if p.get("ws") and match(p) and in_bin(p, lo, hi)]
            on_t = [p for p in cell if not p["x"]]
            fill = "blocked_needs_human_axis" if topic.startswith("untagged") else "keyword_draft"
            if kind == "organism" and topic == "no_dataset_tag":
                fill = "partial_no_registry_dataset"
            kept = [p for p in on_t if inclusion_role(p) == role]
            hist_ex = pick_hist(kept) if role == "history" else None
            sota_ex = pick_sota(kept, lo) if role in ("sota", "contemporary") else None
            n_hist = sum(1 for p in on_t if inclusion_role(p) == "history")
            n_sota = sum(1 for p in on_t if inclusion_role(p) == "sota")
            n_contemp = sum(1 for p in on_t if inclusion_role(p) == "contemporary")
            topic_rows.append(
                {
                    "topic_kind": kind,
                    "topic": topic,
                    "time_bin": label,
                    "time_role": role,
                    "n_catalog": len(cell),
                    "n_on_topic": len(on_t),
                    "n_year_cites_pct_ge50": sum(1 for p in on_t if p["p"] >= 50),
                    "n_kcore_ge3": sum(1 for p in on_t if p["k"] >= 3),
                    "n_in_ge5": sum(1 for p in on_t if p["i"] >= 5),
                    "n_cites_ge50": sum(1 for p in on_t if p["c"] >= 50),
                    "n_tpr_pct_ge50": sum(1 for p in on_t if p["tpr"] >= 50),
                    "n_history_milestone": n_hist,
                    "n_contemporary": n_contemp,
                    "n_sota_proving": n_sota,
                    "n_sota_plus_history": n_hist + n_contemp + n_sota,
                    "example_history_year": hist_ex["y"] if hist_ex else "",
                    "example_history_title": hist_ex["t"] if hist_ex else "",
                    "example_history_doi": hist_ex["d"] if hist_ex else "",
                    "example_sota_year": sota_ex["y"] if sota_ex else "",
                    "example_sota_title": sota_ex["t"] if sota_ex else "",
                    "example_sota_doi": sota_ex["d"] if sota_ex else "",
                    "fill_status": fill,
                    "notes": (
                        "v5 stage×era cell; stages are keyword-draft from dryrun_work_tags.csv, not human-charted. "
                        "History ≤2018 = year-pct≥50 or k-core≥3. "
                        "Contemporary 2019–2024 = that bar or Out≥3. "
                        "SOTA = 2026 Out≥3 OR In≥1; 2025 Out≥3 AND In≥2. "
                        "Untagged row needs biological-application or field-synthesis axis coding (v5 §6)."
                        if topic.startswith("untagged")
                        else "Keyword-draft tags; human charting still required."
                    ),
                }
            )

    with OUT_TOPIC.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(topic_rows[0].keys()))
        w.writeheader()
        w.writerows(topic_rows)

    n_hist = sum(1 for p in papers if p.get("ws") and inclusion_role(p, False) == "history")
    n_contemp = sum(1 for p in papers if p.get("ws") and inclusion_role(p, False) == "contemporary")
    n_sota = sum(1 for p in papers if p.get("ws") and inclusion_role(p, False) == "sota")
    print(
        "SOTA+history defaults: history",
        n_hist,
        "contemporary",
        n_contemp,
        "sota",
        n_sota,
        "union",
        n_hist + n_contemp + n_sota,
    )
    print("wrote", OUT_PAPER)
    print("wrote", OUT_TOPIC)

    # Example pairs for a few stages
    for si, name in enumerate(["sectioning", "graph_analysis", "segmentation"]):
        i = STAGE_NAMES.index(name)
        hist_c = [
            p
            for p in papers
            if p.get("ws")
            and has_bit(p["st"], i)
            and inclusion_role(p, False) == "history"
        ]
        sota_c = [
            p
            for p in papers
            if p.get("ws")
            and has_bit(p["st"], i)
            and inclusion_role(p, False) in ("sota", "contemporary")
        ]
        h = pick_hist(hist_c)
        s = pick_sota(sota_c, 2026)
        print(f"PAIR {name}:")
        if h:
            print(f"  HIST {h['y']} k={h['k']} in={h['i']} p={h['p']} {h['t'][:70]} | {h['d']}")
        if s:
            print(f"  SOTA {s['y']} out={s['o']} in={s['i']} k={s['k']} {s['t'][:70]} | {s['d']}")


def main() -> None:
    cat = pd.read_csv(CATALOG, low_memory=False)
    cat = cat.drop_duplicates("work_id", keep="first").copy()
    n_cat = len(cat)
    if n_cat != 1806:
        print(f"WARN catalog N={n_cat} (expected 1806)")

    full = pd.read_csv(FULL, low_memory=False)
    keep = [
        c
        for c in [
            "work_id",
            "citation_count_work",
            "corpus_in_degree",
            "corpus_out_degree",
            "k_core",
            "decision",
            "year",
            "title",
            "graph_status",
        ]
        if c in full.columns
    ]
    full = full[keep].drop_duplicates("work_id", keep="first")

    df = cat.merge(full, on="work_id", how="left", suffixes=("", "_full"))
    df["year_n"] = df["year"].map(_year_int)
    if "year_full" in df.columns:
        miss = df["year_n"].isna()
        df.loc[miss, "year_n"] = df.loc[miss, "year_full"].map(_year_int)
    df["title_use"] = df["title"].fillna(df.get("title_full"))
    df["cites"] = pd.to_numeric(df["citation_count_work"], errors="coerce").fillna(0).astype(int)
    df["doi"] = df["doi"].fillna("").astype(str)
    df["decision"] = df["decision"].fillna(df.get("decision_full")).fillna("")

    excl = set(pd.read_csv(EXCL)["work_id"].astype(str))
    df["excluded"] = df["work_id"].astype(str).isin(excl)
    base = analysis_base_ids(df)
    df["ws"] = df["work_id"].astype(str).isin(base["ws"])
    df["unavail"] = df["work_id"].astype(str).isin(base["unavail"])
    print(
        "analysis base",
        int(df["ws"].sum()),
        "retained",
        len(base["retained"]),
        "fill_rescue",
        len(base["fill_rescue"]),
        "unavail dropped",
        len(base["unavail"]),
        "fill outside catalog",
        base["n_fill_outside"],
    )

    tags = pd.read_csv(TAGS, low_memory=False)
    tags["tagged"] = (
        tags.get("datasets", pd.Series("", index=tags.index)).fillna("").astype(str).str.strip().ne("")
        | tags.get("stages", pd.Series("", index=tags.index)).fillna("").astype(str).str.strip().ne("")
    )
    tag_map = dict(zip(tags["work_id"].astype(str), tags["tagged"]))
    df["tagged"] = df["work_id"].astype(str).map(tag_map).fillna(False)
    st_map = {
        str(w): stage_bits(s)
        for w, s in zip(tags["work_id"].astype(str), tags.get("stages", pd.Series("", index=tags.index)).fillna(""))
    }
    og_map = {
        str(w): org_bits(s)
        for w, s in zip(tags["work_id"].astype(str), tags.get("datasets", pd.Series("", index=tags.index)).fillna(""))
    }
    df["st"] = df["work_id"].astype(str).map(st_map).fillna(0).astype(int)
    df["og"] = df["work_id"].astype(str).map(og_map).fillna(0).astype(int)

    pid_to_wid = {
        str(p): str(w)
        for p, w in zip(df["canonical_paper_id"], df["work_id"])
        if pd.notna(p) and str(p)
    }
    works = set(df["work_id"].astype(str))
    year_of = dict(zip(df["work_id"].astype(str), df["year_n"]))

    edges_raw = pd.read_csv(EDGES)
    pairs: set[tuple[str, str]] = set()
    for src, tgt in zip(edges_raw["source"].astype(str), edges_raw["target"].astype(str)):
        u = pid_to_wid.get(src)
        v = pid_to_wid.get(tgt)
        if u and v and u in works and v in works and u != v:
            pairs.add((u, v))

    D = nx.DiGraph()
    D.add_nodes_from(works)
    D.add_edges_from(pairs)
    U = D.to_undirected()
    undirected_core = nx.core_number(U)
    in_core = in_core_numbers(D)

    in_deg = {n: int(D.in_degree(n)) for n in works}
    out_deg = {n: int(D.out_degree(n)) for n in works}

    decade_core: dict[str, int] = {n: 0 for n in works}
    by_dec: dict[str, list[str]] = defaultdict(list)
    for n, y in year_of.items():
        by_dec[decade_of(y)].append(n)
    for _dec, nodes in by_dec.items():
        H = U.subgraph(nodes).copy()
        if H.number_of_nodes() == 0:
            continue
        cn = nx.core_number(H)
        decade_core.update(cn)

    years_present = [y for y in year_of.values() if y is not None]
    y_min = min(years_present) if years_present else 1970
    y_max = max(years_present) if years_present else 2026
    y_med = int(pd.Series(years_present).median()) if years_present else 2020
    n_year_missing = sum(1 for y in year_of.values() if y is None)
    span = max(1, y_max - y_min)
    alpha = TPR_ALPHA_SPAN / span

    def y_fill(n: str) -> int:
        y = year_of.get(n)
        return int(y) if y is not None else y_med

    W = nx.DiGraph()
    W.add_nodes_from(works)
    for u, v in pairs:
        dy = max(0, y_fill(u) - y_fill(v))
        W.add_edge(u, v, weight=1.0 / (1.0 + dy))

    static_pr = pagerank(D, alpha=DAMPING, weight=None)
    teleport = {n: math.exp(alpha * (y_fill(n) - y_min)) for n in works}
    temporal_pr = pagerank(W, alpha=DAMPING, personalization=teleport, weight="weight")

    def pct_rank(vals: dict[str, float]) -> dict[str, int]:
        s = pd.Series(vals)
        r = (s.rank(method="average", pct=True) * 100).round().astype(int)
        return {k: int(v) for k, v in r.items()}

    pr_pct = pct_rank(static_pr)
    tpr_pct = pct_rank(temporal_pr)

    cohort_of = year_cohorts(df["year_n"])
    df["cohort"] = df["year_n"].map(lambda y: cohort_of.get(int(y), "unknown") if pd.notna(y) else "unknown")
    df["wid"] = df["work_id"].astype(str)
    df["in_i"] = df["wid"].map(in_deg).fillna(0).astype(int)
    df["out_i"] = df["wid"].map(out_deg).fillna(0).astype(int)
    df["k_u"] = df["wid"].map(undirected_core).fillna(0).astype(int)
    df["k_in"] = df["wid"].map(in_core).fillna(0).astype(int)
    df["k_dec"] = df["wid"].map(decade_core).fillna(0).astype(int)
    df["decade"] = df["year_n"].map(decade_of)

    def cohort_pct(series: pd.Series) -> pd.Series:
        return (series.rank(method="average", pct=True) * 100).round()

    df["cites_pct"] = df.groupby("cohort", dropna=False)["cites"].transform(cohort_pct).fillna(0).astype(int)
    df["in_pct"] = df.groupby("cohort", dropna=False)["in_i"].transform(cohort_pct).fillna(0).astype(int)

    med = df.groupby("cohort")["cites"].transform("median")
    df["resid"] = ((df["cites"] + 1) / (med.fillna(0) + 1)).round(2)

    df["dec_rank"] = (
        df.groupby("decade")["in_i"].rank(method="first", ascending=False).fillna(9999).astype(int)
    )

    dec_code = {"core_relevant": 0, "adjacent_relevant": 1, "role_bridge": 2}
    papers = []
    for r in df.itertuples(index=False):
        wid = str(r.wid)
        y = None if pd.isna(r.year_n) else int(r.year_n)
        papers.append(
            {
                "y": y,
                "c": int(r.cites),
                "i": int(r.in_i),
                "o": int(r.out_i),
                "k": int(r.k_u),
                "kd": int(r.k_dec),
                "kin": int(r.k_in),
                "p": int(r.cites_pct),
                "r": float(r.resid),
                "ip": int(r.in_pct),
                "x": bool(r.excluded),
                "u": bool(r.unavail),
                "ws": bool(r.ws),
                "g": dec_code.get(str(r.decision), 1),
                "pr": int(pr_pct.get(wid, 0)),
                "tpr": int(tpr_pct.get(wid, 0)),
                "dr": int(r.dec_rank),
                "tg": bool(r.tagged),
                "st": int(r.st),
                "og": int(r.og),
                "t": truncate(r.title_use),
                "d": str(r.doi).strip(),
            }
        )

    def n_at(pred) -> int:
        return sum(1 for p in papers if pred(p))

    k_curve = {k: n_at(lambda p, kk=k: p["k"] >= kk) for k in range(0, max(p["k"] for p in papers) + 1)}
    kd_curve = {k: n_at(lambda p, kk=k: p["kd"] >= kk) for k in range(0, max(p["kd"] for p in papers) + 1)}
    cite_cuts = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
    cite_curve = {c: n_at(lambda p, cc=c: p["c"] >= cc) for c in cite_cuts}
    pct_curve = {q: n_at(lambda p, qq=q: p["p"] >= qq) for q in range(0, 101, 5)}
    inpct_curve = {q: n_at(lambda p, qq=q: p["ip"] >= qq) for q in range(0, 101, 5)}
    tpr_curve = {q: n_at(lambda p, qq=q: p["tpr"] >= qq) for q in range(0, 101, 5)}
    pr_curve = {q: n_at(lambda p, qq=q: p["pr"] >= qq) for q in range(0, 101, 5)}
    quota_ms = [10, 20, 30, 40, 50, 75, 100, 150, 200]
    quota_curve = {m: n_at(lambda p, mm=m: p["dr"] <= mm) for m in quota_ms}

    # Recent-connector brittleness grid (on-topic = not screener-excluded).
    years_grid = [2016, 2018, 2020, 2022, 2024, 2026]
    outs_grid = [0, 1, 2, 3, 5]
    heat = []
    for y0 in years_grid:
        row = []
        for mo in outs_grid:
            row.append(
                n_at(lambda p, yy=y0, mm=mo: p.get("ws") and p["y"] is not None and p["y"] >= yy and p["o"] >= mm)
            )
        heat.append(row)

    only_out_recent = [p for p in papers if p["y"] is not None and p["y"] >= 2020 and p["i"] == 0 and p["o"] > 0 and not p["x"]]
    only_out_k3_drop = [p for p in only_out_recent if p["k"] < 3]
    only_out_c50_drop = [p for p in only_out_recent if p["c"] < 50]

    # Temporal PR risers vs static PR.
    risers = sorted(papers, key=lambda p: (p["tpr"] - p["pr"], p["tpr"]), reverse=True)[:8]
    fallers = sorted(papers, key=lambda p: (p["pr"] - p["tpr"], p["pr"]), reverse=True)[:8]
    tpr_not_k3 = sorted(
        [p for p in papers if p["tpr"] >= 50 and p["k"] < 3],
        key=lambda p: p["tpr"],
        reverse=True,
    )[:8]
    yp_not_c50 = sorted(
        [p for p in papers if p["p"] >= 50 and p["c"] < 50],
        key=lambda p: (-p["y"] if p["y"] else 0, p["p"]),
        reverse=True,
    )[:8]

    n_explore = n_at(lambda p: p.get("ws"))
    n_ws = n_explore
    max_k = max(p["k"] for p in papers)
    max_kd = max(p["kd"] for p in papers)

    meta = {
        "n": n_cat,
        "nExplore": n_ws,
        "nWorkingSet": n_ws,
        "nNamedWorkingSet": 1544,
        "nUnavailDropped": int(df["unavail"].sum()),
        "nFillOutsideCatalog": int(base["n_fill_outside"]),
        "nExcluded": int(df["excluded"].sum()),
        "nYearMissing": n_year_missing,
        "yearFill": y_med,
        "yMin": y_min,
        "yMax": y_max,
        "nEdges": len(pairs),
        "nGraphTouched": n_at(lambda p: p["i"] + p["o"] > 0),
        "maxK": max_k,
        "maxKd": max_kd,
        "maxKin": max(p["kin"] for p in papers),
        "damping": DAMPING,
        "tprAlpha": round(alpha, 5),
        "tprFormula": (
            "temporal PageRank: recency-biased teleport + age-decayed citation weights. "
            "Directed edges citing → cited. Edge weight w=1/(1+max(0,y_citing−y_cited)). "
            f"Teleport π_i ∝ exp(α(y_i−y_min)) with α=ln(10)/(y_max−y_min)={alpha:.4f} "
            f"(newest ~10× oldest). Damping d={DAMPING}. Missing years filled with median {y_med}."
        ),
        "kCoreDef": (
            "Undirected k-core on the intra-corpus citation graph: a cite is an undirected "
            "edge between citing and cited catalog works. Core number = largest k such that "
            "the paper remains in the subgraph where every node has degree ≥ k. "
            "In-core (kin) peels by in-degree on citing→cited. Decade core is undirected "
            "k-core inside each decade induced subgraph, then unioned."
        ),
        "citesDef": "citation_count_work (max across versions; OpenAlex/S2 work-level Cites), independent of In.",
        "inOutDef": "In = # of other 1806 papers that cite this work. Out = # of this work’s refs that are in the 1806. Induced on the catalog subgraph.",
        "cohortDef": f"Year-cohort percentile: rank global cites within publication-year bins merged until ≥{MIN_COHORT} papers (sparse years share a bin).",
        "kCurve": k_curve,
        "kdCurve": kd_curve,
        "citeCurve": cite_curve,
        "pctCurve": pct_curve,
        "inpctCurve": inpct_curve,
        "tprCurve": tpr_curve,
        "prCurve": pr_curve,
        "quotaCurve": quota_curve,
        "heatYears": years_grid,
        "heatOuts": outs_grid,
        "heat": heat,
        "nOnlyOutRecent": len(only_out_recent),
        "nOnlyOutRecentK3Drop": len(only_out_k3_drop),
        "nOnlyOutRecentC50Drop": len(only_out_c50_drop),
        "cohorts": sorted(set(df["cohort"].astype(str))),
        "decades": sorted(by_dec.keys()),
        "decadeNs": {d: len(v) for d, v in by_dec.items()},
        "stageNames": STAGE_NAMES,
        "orgNames": ORG_NAMES,
        "timeBins": [b[0] for b in TIME_BINS],
        "timeRoles": [b[1] for b in TIME_BINS],
        "nUntaggedStage": int(((df["ws"]) & (df["st"] == 0)).sum()),
        "sotaHistoryDefaults": {
            "outMin": DEF_OUT_MIN,
            "in2026": DEF_IN_2026,
            "in2025": DEF_IN_2025,
            "in2024": DEF_IN_2024,
            "histP": DEF_HIST_P,
            "histK": DEF_HIST_K,
            "rule": "≤2018 history (P≥50 or k≥3); 2019–2024 contemporary (that or Out≥3); 2026 Out≥3 OR In≥1; 2025 Out≥3 AND In≥2",
        },
    }

    write_importance_tables(df, papers)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "papers": papers}
    OUT_JSON.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    print("N", n_cat, "explore", n_explore, "edges", len(pairs), "touched", meta["nGraphTouched"])
    print("maxK", max_k, "maxKd", max_kd, "maxKin", meta["maxKin"])
    print("k-core remaining", k_curve)
    print("decade-k remaining", kd_curve)
    print("min cites remaining", cite_curve)
    print("year-pct remaining", {q: pct_curve[q] for q in (0, 25, 50, 75, 90)})
    print("in-pct remaining", {q: inpct_curve[q] for q in (0, 25, 50, 75, 90)})
    print("tPR remaining", {q: tpr_curve[q] for q in (0, 25, 50, 75, 90)})
    print("static PR remaining", {q: pr_curve[q] for q in (0, 25, 50, 75, 90)})
    print("quota remaining", quota_curve)
    print("heat years", years_grid, "outs", outs_grid)
    print("heat", heat)
    print("only-out ≥2020 on-topic", len(only_out_recent), "k<3", len(only_out_k3_drop), "cites<50", len(only_out_c50_drop))
    print("TPR risers vs static:")
    for p in risers:
        print(f"  +{p['tpr']-p['pr']:3d} tpr={p['tpr']:3d} pr={p['pr']:3d} k={p['k']} in={p['i']} out={p['o']} c={p['c']} {p['y']} {p['t'][:70]}")
    print("static PR stays (fall under TPR):")
    for p in fallers:
        print(f"  {p['tpr']-p['pr']:4d} tpr={p['tpr']:3d} pr={p['pr']:3d} k={p['k']} in={p['i']} out={p['o']} c={p['c']} {p['y']} {p['t'][:70]}")
    print("TPR≥50 and k<3:")
    for p in tpr_not_k3:
        print(f"  tpr={p['tpr']} k={p['k']} in={p['i']} out={p['o']} {p['y']} {p['t'][:70]}")
    print("year-pct≥50 and cites<50 (recent-ish):")
    for p in yp_not_c50[:8]:
        print(f"  p={p['p']} c={p['c']} {p['y']} in={p['i']} out={p['o']} {p['t'][:70]}")
    print("wrote", OUT_JSON, "bytes", OUT_JSON.stat().st_size)


if __name__ == "__main__":
    main()
