#!/usr/bin/env python3
"""Union key papers *within* each charting facet so low-cite streams still show.

Global cites / k-core favor biology over education and methods. This does not
equalize mass. It keeps the SOTA+history core, then adds the cell champion
(best paper in that slice) for every non-empty (facet × era) cell.

Rank inside the cell, never against the whole catalog:
  history eras: In, k-core, year-cites percentile, cites
  SOTA eras:    Out, In, k-core
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WS = ROOT / "postanalysis/registry/working_set_labeled.csv"
CORE = ROOT / "postanalysis/registry/sota_history_core_labeled.csv"
OUT_UNION = ROOT / "postanalysis/registry/sota_history_stratum_union.csv"
OUT_CELLS = ROOT / "postanalysis/registry/stratum_cell_champions.csv"
OUT_JSON = ROOT / "postanalysis/llm_agent_v3/stratum_key_union.json"

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


def tokens(raw: str) -> list[str]:
    return [p.strip() for p in str(raw or "").split(";") if p.strip()]


def era_of(y) -> tuple[str, str]:
    try:
        y = int(float(y))
    except (TypeError, ValueError):
        return "", ""
    for label, role, lo, hi in TIME_BINS:
        if lo <= y <= hi:
            return label, role
    return ("pre-2005", "history") if y < 2005 else ("2026", "sota")


def sort_key(row: dict, role: str) -> tuple:
    inn = int(row.get("in_degree") or 0)
    out = int(row.get("out_degree") or 0)
    k = int(row.get("k_core") or 0)
    p = int(row.get("year_cites_percentile") or 0)
    c = int(row.get("cites") or 0)
    if role == "sota":
        return (out, inn, k, p, c)
    return (inn, k, p, c, out)


def champion(rows: list[dict], role: str) -> dict | None:
    if not rows:
        return None
    return max(rows, key=lambda r: sort_key(r, role))


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ws = load_csv(WS)
    core_ids = {r["work_id"] for r in load_csv(CORE)}
    for r in ws:
        era, role = era_of(r.get("year"))
        r["_era"] = era or (r.get("era") or "")
        r["_role"] = role or ("sota" if str(r.get("year")) in {"2024", "2025", "2026"} else "history")

    by_era: dict[str, list[dict]] = defaultdict(list)
    for r in ws:
        if r["_era"]:
            by_era[r["_era"]].append(r)

    cells: list[dict] = []
    champ_ids: dict[str, list[str]] = defaultdict(list)

    def add_cell(kind: str, value: str, era: str, role: str, pool: list[dict]) -> None:
        if not pool:
            return
        ch = champion(pool, role)
        assert ch is not None
        in_core = ch["work_id"] in core_ids
        n_core = sum(1 for p in pool if p["work_id"] in core_ids)
        cells.append(
            {
                "facet": kind,
                "value": value,
                "era": era,
                "time_role": role,
                "n_working_set": len(pool),
                "n_global_core": n_core,
                "champion_work_id": ch["work_id"],
                "champion_doi": ch.get("doi") or "",
                "champion_title": ch.get("title") or "",
                "champion_year": ch.get("year") or "",
                "champion_in_global_core": "yes" if in_core else "",
                "in": ch.get("in_degree") or 0,
                "out": ch.get("out_degree") or 0,
                "k_core": ch.get("k_core") or 0,
                "year_cites_percentile": ch.get("year_cites_percentile") or 0,
            }
        )
        champ_ids[ch["work_id"]].append(f"{kind}:{value}|{era}")

    for label, role, _lo, _hi in TIME_BINS:
        pool_e = by_era.get(label, [])
        axes: dict[str, list[dict]] = defaultdict(list)
        stages: dict[str, list[dict]] = defaultdict(list)
        orgs: dict[str, list[dict]] = defaultdict(list)
        dss: dict[str, list[dict]] = defaultdict(list)
        methods: dict[str, list[dict]] = defaultdict(list)
        for r in pool_e:
            ax = (r.get("axis") or "").strip() or "untagged"
            axes[ax].append(r)
            for s in tokens(r.get("stages") or ""):
                stages[s].append(r)
            for o in tokens(r.get("organism") or ""):
                orgs[o].append(r)
            for d in tokens(r.get("datasets") or ""):
                dss[d].append(r)
            for m in tokens(r.get("method") or ""):
                methods[m].append(r)
        for v, rows in axes.items():
            add_cell("axis", v, label, role, rows)
        for v, rows in stages.items():
            add_cell("stage", v, label, role, rows)
        for v, rows in orgs.items():
            add_cell("organism", v, label, role, rows)
        for v, rows in dss.items():
            add_cell("dataset", v, label, role, rows)
        # Methods: skip the generic catch-all so FIB-SEM/CAVE etc. actually surface.
        for v, rows in methods.items():
            if v.lower() in {"electron microscopy", "volume em", "em"}:
                continue
            add_cell("method", v, label, role, rows)

    added_ids = {wid for wid, _ in champ_ids.items() if wid not in core_ids}
    union_ids = core_ids | set(champ_ids)

    by_id = {r["work_id"]: r for r in ws}
    union_rows = []
    for wid in sorted(union_ids, key=lambda i: (-int(by_id[i].get("k_core") or 0), i)):
        r = dict(by_id[wid])
        r.pop("_era", None)
        r.pop("_role", None)
        r["in_global_core"] = "yes" if wid in core_ids else ""
        r["stratum_champion_cells"] = ";".join(champ_ids.get(wid, []))
        r["added_for_coverage"] = "yes" if wid in added_ids else ""
        union_rows.append(r)

    fields = list(union_rows[0].keys())
    with OUT_UNION.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(union_rows)
    with OUT_CELLS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cells[0].keys()))
        w.writeheader()
        w.writerows(cells)

    n_cells = len(cells)
    n_empty_core = sum(1 for c in cells if int(c["n_global_core"]) == 0)
    n_champ_outside = sum(1 for c in cells if not c["champion_in_global_core"])
    added_examples = [
        {
            "year": by_id[wid].get("year"),
            "axis": by_id[wid].get("axis"),
            "title": (by_id[wid].get("title") or "")[:96],
            "doi": by_id[wid].get("doi") or "",
            "cells": champ_ids[wid][:4],
        }
        for wid in sorted(added_ids, key=lambda i: by_id[i].get("axis") or "")
    ][:24]

    stats = {
        "n_working_set": len(ws),
        "n_global_core": len(core_ids),
        "n_union": len(union_ids),
        "n_added_for_coverage": len(added_ids),
        "n_cells": n_cells,
        "n_cells_empty_in_global_core": n_empty_core,
        "n_cells_champion_outside_core": n_champ_outside,
        "rule": (
            "Union of (1) global SOTA+history core with (2) the within-cell champion "
            "of every non-empty facet×era cell. Ranked inside the cell: history by "
            "In/k-core/year-percentile; SOTA by Out/In/k-core. Generic 'electron "
            "microscopy' method cells skipped."
        ),
        "added_examples": added_examples,
        "axis_added": {},
    }
    from collections import Counter

    ax_add = Counter((by_id[i].get("axis") or "untagged") for i in added_ids)
    stats["axis_added"] = dict(ax_add)

    OUT_JSON.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")

    print("working set", len(ws), "global core", len(core_ids), "union", len(union_ids))
    print("added for coverage", len(added_ids))
    print("cells", n_cells, "empty in global core", n_empty_core, "champion outside core", n_champ_outside)
    print("added by axis", dict(ax_add))
    print("wrote", OUT_UNION)
    print("wrote", OUT_CELLS)
    print("wrote", OUT_JSON)
    print("example adds:")
    for ex in added_examples[:12]:
        print(f"  {ex['year']} [{ex['axis']}] {ex['title'][:70]}")


if __name__ == "__main__":
    main()
