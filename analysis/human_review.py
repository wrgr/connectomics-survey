"""Apply explicit human screening overrides without mutating frozen agent decisions.

`postanalysis/llm_agent_v3/human_review_decisions.csv` is the source of record.
`human_decision=out_of_scope` removes a work from inclusive corpora and PDF collection.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("postanalysis/llm_agent_v3/human_review_decisions.csv")
EXCLUDED = {"out_of_scope"}
FIELDS = (
    "work_id",
    "title",
    "agent_decision",
    "human_decision",
    "reviewer",
    "reviewed_at",
    "note",
)


def s(v: Any) -> str:
    if v is None:
        return ""
    t = str(v).strip()
    return "" if t.lower() in {"", "nan", "none", "null"} else t


def load_human_decisions(path: Path | None = None) -> dict[str, dict[str, str]]:
    p = Path(path) if path is not None else DEFAULT_PATH
    if not p.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    with p.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            wid = s(row.get("work_id"))
            if wid:
                out[wid] = {k: s(row.get(k)) for k in FIELDS}
    return out


def excluded_work_ids(path: Path | None = None) -> set[str]:
    return {
        wid
        for wid, rec in load_human_decisions(path).items()
        if rec.get("human_decision") in EXCLUDED
    }


def apply_human_decisions_rows(
    rows: list[dict[str, Any]],
    *,
    path: Path | None = None,
    decision_key: str = "decision",
) -> list[dict[str, Any]]:
    overlay = load_human_decisions(path)
    if not overlay:
        return rows
    out: list[dict[str, Any]] = []
    for row in rows:
        rec = dict(row)
        hit = overlay.get(s(rec.get("work_id")))
        if hit and hit.get("human_decision"):
            rec[decision_key] = hit["human_decision"]
        out.append(rec)
    return out


def apply_human_decisions_frame(df, *, path: Path | None = None, decision_col: str = "decision"):
    overlay = load_human_decisions(path)
    if not overlay or df is None or df.empty or "work_id" not in df.columns:
        return df
    mapped = df["work_id"].map(lambda w: overlay.get(s(w), {}).get("human_decision") or None)
    hit = mapped.notna()
    if not bool(hit.any()):
        return df
    out = df.copy()
    out.loc[hit, decision_col] = mapped[hit]
    return out
