#!/usr/bin/env python3
"""Prepare IA-007-v3 queue for full agent adjudication.

Removes bootstrap/heuristic decisions from home batches while preserving
decisions already written by completed claim_*.json packs. Archives prior
batch state before modifying.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

ROOT_DEFAULT = Path("postanalysis/llm_agent_v3/adjudication")


def load_agent_decisions(claims_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(claims_dir.glob("claim_*.json")):
        obj = json.loads(p.read_text())
        for wid, dec in (obj.get("decisions") or {}).items():
            out[str(wid)] = dec
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = args.root.resolve()
    man = json.loads((root / "manifest.json").read_text())
    agent = load_agent_decisions(root / "decisions" / "claims")
    if not agent:
        raise SystemExit("no agent decisions found under decisions/claims/claim_*.json")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    archive = root / f"_pre_agent_queue_{stamp}"
    decisions = root / "decisions"
    if not args.dry_run:
        archive.mkdir(parents=True, exist_ok=True)
        for p in sorted(decisions.glob("batch_*.json")):
            shutil.copy2(p, archive / p.name)

    kept = 0
    removed = 0
    for batch in sorted(man.get("home_batches", {})):
        path = decisions / f"{batch}.json"
        if not path.exists():
            continue
        obj = json.loads(path.read_text())
        old = obj.get("decisions") or {}
        new = {}
        for wid, dec in old.items():
            if wid in agent:
                new[wid] = agent[wid]
                kept += 1
            else:
                removed += 1
        if args.dry_run:
            continue
        if new:
            obj["decisions"] = new
            obj["adjudicator"] = obj.get("adjudicator") or "agent:pending"
        else:
            obj["decisions"] = {}
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(obj, indent=2) + "\n")
        tmp.replace(path)

    exported = len(man["works"])
    open_n = exported - len({w for w in man["works"] if w in agent})
    summary = {
        "archived_to": str(archive) if not args.dry_run else None,
        "agent_decisions_loaded": len(agent),
        "batch_decisions_kept": kept,
        "bootstrap_removed": removed,
        "exported": exported,
        "decided_after": len(agent),
        "open_unclaimed_after": open_n,
        "remaining_packs_of_200": (open_n + 199) // 200,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
