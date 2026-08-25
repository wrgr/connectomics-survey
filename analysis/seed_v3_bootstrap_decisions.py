#!/usr/bin/env python3
"""Write v3 home-batch decision JSON from bootstrap CSV (preview seeding)."""
from __future__ import annotations

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import analysis.llm_relevance_screen as L  # noqa: E402

ADJ = "agent:cursor/claude-opus-5-thinking@2026-08-24"
BOOT = ROOT / "postanalysis/llm_agent_v3/llm_relevance_results_bootstrap.csv"
MANIFEST = ROOT / "postanalysis/llm_agent_v3/adjudication/manifest.json"
OUT = ROOT / "postanalysis/llm_agent_v3/adjudication/decisions"


def parse_list(v):
    if v is None or (isinstance(v, float) and v != v):
        return []
    if isinstance(v, list):
        return list(v)
    s = str(v).strip()
    if not s or s == "[]":
        return []
    try:
        x = ast.literal_eval(s)
        return list(x) if isinstance(x, list) else []
    except Exception:
        return []


def main() -> None:
    L.set_prompt_version("v3")
    man = json.loads(MANIFEST.read_text())
    csha = man["criteria_sha256"]
    bmap = {}
    for b, ids in man["home_batches"].items():
        for w in ids:
            bmap[str(w)] = b
    df = pd.read_csv(BOOT, low_memory=False)
    df["work_id"] = df.work_id.astype(str)
    by_batch: dict[str, dict] = defaultdict(dict)
    for r in df.itertuples(index=False):
        wid = str(r.work_id)
        b = bmap.get(wid)
        if not b:
            continue
        dec = {
            "decision": str(r.decision),
            "roles": parse_list(getattr(r, "roles", [])),
            "confidence": float(r.confidence),
            "evidence": str(getattr(r, "evidence", "") or "")[:600],
            "reason": str(getattr(r, "reason", "") or "")[:1200],
            "noise_flags": parse_list(getattr(r, "noise_flags", [])),
            "scale_relationship": str(getattr(r, "scale_relationship", "unclear")),
            "core_gate": str(getattr(r, "core_gate", "not_applicable")),
        }
        if dec["decision"] != "insufficient_abstract":
            L.validate(dec)
        by_batch[b][wid] = dec
    OUT.mkdir(parents=True, exist_ok=True)
    for b, decisions in sorted(by_batch.items()):
        obj = {
            "batch": b,
            "adjudicator": ADJ,
            "prompt_version": L.PROMPT_VERSION,
            "criteria_sha256": csha,
            "decisions": decisions,
        }
        (OUT / f"{b}.json").write_text(json.dumps(obj, indent=2) + "\n")
    print(json.dumps({"batches": len(by_batch), "decisions": sum(len(v) for v in by_batch.values())}, indent=2))


if __name__ == "__main__":
    main()
