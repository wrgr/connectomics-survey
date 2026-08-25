#!/usr/bin/env python3
"""Overlay completed claim_*.json decisions onto home batch files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT_DEFAULT = Path("postanalysis/llm_agent_v3/adjudication")


def batch_of_map(manifest: dict) -> dict[str, str]:
    m = {}
    for b, ids in manifest.get("home_batches", {}).items():
        for w in ids:
            m[str(w)] = b
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    ap.add_argument("--claim", action="append", default=[], help="claim id(s), default all in decisions/claims/")
    args = ap.parse_args()
    root = args.root.resolve()
    man = json.loads((root / "manifest.json").read_text())
    bmap = batch_of_map(man)
    claims_dir = root / "decisions" / "claims"
    claim_paths = [claims_dir / f"{c}.json" for c in args.claim] if args.claim else sorted(claims_dir.glob("claim_*.json"))
    updated = 0
    written = 0
    for cp in claim_paths:
        if not cp.exists():
            raise SystemExit(f"missing {cp}")
        obj = json.loads(cp.read_text())
        adj = obj.get("adjudicator") or "agent:cursor/claude-opus-5-thinking"
        csha = obj["criteria_sha256"]
        pver = obj.get("prompt_version", man.get("prompt_version"))
        by_batch: dict[str, dict[str, dict]] = {}
        for wid, dec in (obj.get("decisions") or {}).items():
            b = bmap.get(str(wid))
            if not b:
                raise SystemExit(f"{wid} not in manifest home_batches")
            by_batch.setdefault(b, {})[str(wid)] = dec
        for b, chunk in by_batch.items():
            path = root / "decisions" / f"{b}.json"
            if path.exists():
                batch = json.loads(path.read_text())
                existing = batch.setdefault("decisions", {})
            else:
                batch = {"batch": b, "adjudicator": adj, "prompt_version": pver, "criteria_sha256": csha, "decisions": {}}
                existing = batch["decisions"]
            for wid, dec in chunk.items():
                if existing.get(wid) != dec:
                    existing[wid] = dec
                    updated += 1
                written += 1
            batch["adjudicator"] = adj
            batch["prompt_version"] = pver
            batch["criteria_sha256"] = csha
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(batch, indent=2) + "\n")
            tmp.replace(path)
    print(json.dumps({"claims": len(claim_paths), "decisions_touched": written, "field_updates": updated}, indent=2))


if __name__ == "__main__":
    main()
