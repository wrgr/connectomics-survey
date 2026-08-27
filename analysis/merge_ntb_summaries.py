#!/usr/bin/env python3
"""Merge summary shards into collection.json and ntb_export/journal_papers.yml."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from build_ntb_visible_core import dump_yaml_papers  # noqa: E402

SUM = ROOT / "source_artifact/neurotrailblazers_visible_core/summaries"
COLL = ROOT / "source_artifact/neurotrailblazers_visible_core/collection.json"
YML = ROOT / "source_artifact/neurotrailblazers_visible_core/ntb_export/journal_papers.yml"


def shard_paths() -> list[Path]:
    pdf = sorted((SUM / "pdf").glob("output_shard_*.jsonl"))
    abstract = sorted(SUM.glob("output_shard_*.jsonl"))
    # PDF shards overwrite abstract cards for the same work_id.
    return abstract + pdf


def main() -> None:
    papers = json.loads(COLL.read_text(encoding="utf-8"))
    by_id = {p["work_id"]: p for p in papers}
    n_in = 0
    missing = []
    for path in shard_paths():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            wid = rec["work_id"]
            if wid not in by_id:
                missing.append(wid)
                continue
            p = by_id[wid]
            p["ocar"] = rec["ocar"]
            p["summaries"] = rec["summaries"]
            p["plain_language_summary"] = rec.get("plain_language_summary") or rec["summaries"]["beginner"]
            if rec.get("tags"):
                p["tags"] = rec["tags"]
            p["annotation_status"] = rec.get("annotation_status", "generated_from_title_abstract")
            n_in += 1
    COLL.write_text(json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")
    dump_yaml_papers(papers, YML)
    n_gen = sum(1 for p in papers if p.get("annotation_status") == "generated_from_title_abstract")
    print("merged", n_in, "into", len(papers), "generated_from_title_abstract", n_gen, "unknown ids", len(missing))


if __name__ == "__main__":
    main()
