#!/usr/bin/env python3
"""Deterministic checks for `analysis/human_review.py`.

    python analysis/test_human_review.py
"""
from __future__ import annotations

import csv
import importlib.util
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
H = importlib.util.spec_from_file_location("human_review", HERE / "human_review.py")
mod = importlib.util.module_from_spec(H)
H.loader.exec_module(mod)


def write_decisions(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(mod.FIELDS))
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in mod.FIELDS})
    return path


def test_overlay_and_exclusion(td: Path) -> None:
    decisions = write_decisions(
        td / "human_review_decisions.csv",
        [
            {
                "work_id": "w_keep",
                "title": "Stay in",
                "agent_decision": "adjacent_relevant",
                "human_decision": "core_relevant",
                "reviewer": "human",
                "reviewed_at": "2026-08-24",
                "note": "promote",
            },
            {
                "work_id": "w_drop",
                "title": "Drop me",
                "agent_decision": "adjacent_relevant",
                "human_decision": "out_of_scope",
                "reviewer": "human",
                "reviewed_at": "2026-08-24",
                "note": "exclude",
            },
        ],
    )
    assert mod.excluded_work_ids(decisions) == {"w_drop"}

    rows = [
        {"work_id": "w_keep", "decision": "adjacent_relevant"},
        {"work_id": "w_drop", "decision": "adjacent_relevant"},
        {"work_id": "w_untouched", "decision": "core_relevant"},
    ]
    overlaid = mod.apply_human_decisions_rows(rows, path=decisions)
    by_id = {r["work_id"]: r["decision"] for r in overlaid}
    assert by_id == {
        "w_keep": "core_relevant",
        "w_drop": "out_of_scope",
        "w_untouched": "core_relevant",
    }

    frame = pd.DataFrame(rows)
    out = mod.apply_human_decisions_frame(frame, path=decisions)
    assert list(out.decision) == ["core_relevant", "out_of_scope", "core_relevant"]
    # Frozen agent column is not present; overlay does not invent one.
    assert "agent_decision" not in out.columns


def test_missing_file_is_noop(td: Path) -> None:
    missing = td / "absent.csv"
    assert mod.excluded_work_ids(missing) == set()
    rows = [{"work_id": "w1", "decision": "core_relevant"}]
    assert mod.apply_human_decisions_rows(rows, path=missing) == rows


def main() -> None:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        test_overlay_and_exclusion(td)
        test_missing_file_is_noop(td)
    print("ok")


if __name__ == "__main__":
    main()
