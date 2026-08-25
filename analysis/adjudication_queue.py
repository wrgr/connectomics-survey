#!/usr/bin/env python3
"""Claim/lease open IA-007 adjudication works in fixed-size packs.

Merge-only discipline: never delete existing decision files; claims are exclusive
leases on currently undecided work_ids. New agents must --claim before packing.
"""
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path

ROOT_DEFAULT = Path("postanalysis/llm_agent/adjudication")
ADJUDICATOR = "agent:cursor/claude-opus-5-thinking"
PROMPT_VERSION = "IA-007-v2-work-level"

def s(v):
    return "" if v is None else str(v).strip()

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def load_manifest(root: Path):
    return json.loads((root / "manifest.json").read_text())

def decided_ids(root: Path) -> set[str]:
    out = set()
    ddir = root / "decisions"
    if not ddir.exists():
        return out
    for p in ddir.glob("batch_*.json"):
        try:
            obj = json.loads(p.read_text())
        except Exception:
            continue
        for wid in (obj.get("decisions") or {}):
            out.add(str(wid))
    return out

def active_claims(root: Path) -> list[dict]:
    cdir = root / "queue" / "claims"
    if not cdir.exists():
        return []
    rows = []
    for p in sorted(cdir.glob("claim_*.json")):
        try:
            obj = json.loads(p.read_text())
        except Exception:
            continue
        if obj.get("status") == "active":
            rows.append(obj)
    return rows

def claimed_ids(root: Path) -> set[str]:
    out = set()
    for c in active_claims(root):
        out.update(map(str, c.get("work_ids") or []))
    return out

def manifest_prompt_version(manifest: dict) -> str:
    return str(manifest.get("prompt_version") or "IA-007-v2-work-level")

def extract_abstract(prompt: str) -> str:
    if "ABSTRACT:\n" not in prompt:
        return ""
    tail = prompt.split("ABSTRACT:\n", 1)[1]
    for marker in ("\n\nReturn exactly", "\n\nIf core vs adjacent"):
        if marker in tail:
            return tail.split(marker, 1)[0].strip()
    return tail.strip()

def batch_of_map(manifest: dict) -> dict[str, str]:
    m = {}
    for b, ids in manifest.get("home_batches", {}).items():
        for w in ids:
            m[str(w)] = b
    return m

def open_work_ids(root: Path, manifest: dict) -> list[str]:
    done = decided_ids(root) | claimed_ids(root)
    return [w for w in sorted(manifest["works"]) if w not in done]

def status(root: Path):
    man = load_manifest(root)
    done = decided_ids(root)
    claimed = claimed_ids(root)
    open_ids = open_work_ids(root, man)
    active = active_claims(root)
    print(json.dumps({
        "exported": len(man["works"]),
        "decided": len(done),
        "actively_claimed": len(claimed),
        "open_unclaimed": len(open_ids),
        "active_claims": [{"claim_id": c["claim_id"], "agent": c["agent"], "n": len(c["work_ids"]), "created_at": c.get("created_at")} for c in active],
        "remaining_packs_of_200": (len(open_ids) + 199) // 200,
    }, indent=2))

def build_pack(root: Path, work_ids: list[str], manifest: dict) -> dict:
    bmap = batch_of_map(manifest)
    # criteria from any prompt file
    sample = next(iter(manifest["home_batches"]))
    with (root / "prompts" / f"{sample}.jsonl").open() as fh:
        header = json.loads(fh.readline())
    by_id = {}
    # load only needed batches
    needed = sorted({bmap[w] for w in work_ids})
    for b in needed:
        for line in (root / "prompts" / f"{b}.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("record") != "work":
                continue
            by_id[r["work_id"]] = r
    works = []
    for wid in work_ids:
        r = by_id[wid]
        prompt = r["prompt"]
        abs_ = extract_abstract(prompt)
        works.append({
            "work_id": wid,
            "batch": r["batch"],
            "source_group": r["source_group"],
            "title": r["title"],
            "abstract": abs_,
            "prompt_sha256": r["prompt_sha256"],
        })
    return {
        "criteria_sha256": header["criteria_sha256"],
        "system": header["system"],
        "criteria": header["criteria"],
        "prompt_version": manifest_prompt_version(manifest),
        "works": works,
    }

def claim(root: Path, agent: str, size: int) -> dict:
    qdir = root / "queue" / "claims"
    pdir = root / "queue" / "packs"
    qdir.mkdir(parents=True, exist_ok=True)
    pdir.mkdir(parents=True, exist_ok=True)
    lock = root / "queue" / ".claim.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    # exclusive lock via O_EXCL retry
    for _ in range(200):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{agent} {now()}\n".encode())
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(0.05)
    else:
        raise SystemExit("could not acquire claim lock")
    try:
        man = load_manifest(root)
        open_ids = open_work_ids(root, man)
        if not open_ids:
            return {"claim_id": None, "n": 0, "message": "queue empty"}
        take = open_ids[:size]
        # Avoid reuse of released/archived claim IDs so stale workers cannot merge into a new lease.
        seen = set()
        for folder in (qdir, root / "queue" / "released_archive"):
            if not folder.exists():
                continue
            for p in folder.glob("claim_*.json"):
                try:
                    seen.add(int(p.stem.split("_", 1)[1]))
                except Exception:
                    continue
        n = (max(seen) + 1) if seen else 0
        claim_id = f"claim_{n:04d}"
        pack = build_pack(root, take, man)
        pack_path = pdir / f"{claim_id}.json"
        pack_path.write_text(json.dumps(pack, ensure_ascii=False))
        rec = {
            "claim_id": claim_id,
            "agent": agent,
            "status": "active",
            "created_at": now(),
            "size_requested": size,
            "work_ids": take,
            "pack_path": str(pack_path),
            "home_batches": sorted({w["batch"] for w in pack["works"]}),
        }
        (qdir / f"{claim_id}.json").write_text(json.dumps(rec, indent=2) + "\n")
        return {"claim_id": claim_id, "n": len(take), "pack_path": str(pack_path), "home_batches": rec["home_batches"], "open_remaining_after": len(open_ids) - len(take)}
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass

def merge_decisions(root: Path, decisions: dict, criteria_sha: str, prompt_version: str | None = None) -> dict:
    """Merge decisions into home batch_*.json files. Never wipe; skip work_ids already present."""
    man = load_manifest(root)
    pver = prompt_version or manifest_prompt_version(man)
    bmap = batch_of_map(man)
    (root / "decisions").mkdir(parents=True, exist_ok=True)
    by_batch = {}
    skipped = []
    written = []
    for wid, dec in decisions.items():
        wid = str(wid)
        b = bmap.get(wid)
        if not b:
            raise SystemExit(f"unknown work_id {wid}")
        by_batch.setdefault(b, {})[wid] = dec
    summary = {}
    for b, chunk in sorted(by_batch.items()):
        path = root / "decisions" / f"{b}.json"
        if path.exists():
            obj = json.loads(path.read_text())
            existing = obj.setdefault("decisions", {})
        else:
            obj = {"batch": b, "adjudicator": ADJUDICATOR, "prompt_version": pver, "criteria_sha256": criteria_sha, "decisions": {}}
            existing = obj["decisions"]
        added = 0
        for wid, dec in chunk.items():
            if wid in existing:
                skipped.append(wid)
                continue
            existing[wid] = dec
            written.append(wid)
            added += 1
        obj["adjudicator"] = ADJUDICATOR
        obj["prompt_version"] = pver
        obj["criteria_sha256"] = criteria_sha
        # atomic write
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(obj, indent=2) + "\n")
        tmp.replace(path)
        summary[b] = {"total": len(existing), "added": added}
    return {"batches": summary, "written": len(written), "skipped_already_present": len(skipped)}

def complete(root: Path, claim_id: str, decisions_path: Path, agent: str | None = None):
    cpath = root / "queue" / "claims" / f"{claim_id}.json"
    if not cpath.exists():
        raise SystemExit(f"missing claim {claim_id}")
    claim = json.loads(cpath.read_text())
    if claim.get("status") != "active":
        raise SystemExit(f"{claim_id}: status is {claim.get('status')!r}, not active — refusing merge (stale/released claim)")
    if agent is not None and claim.get("agent") != agent:
        raise SystemExit(f"{claim_id}: agent mismatch (claim={claim.get('agent')!r}, provided={agent!r})")
    obj = json.loads(Path(decisions_path).read_text())
    decisions = obj.get("decisions") or {}
    # ensure only claimed ids
    unexpected = [w for w in decisions if w not in set(claim["work_ids"])]
    if unexpected:
        raise SystemExit(f"decisions contain unclaimed work_ids: {unexpected[:5]}")
    missing = [w for w in claim["work_ids"] if w not in decisions]
    pack = json.loads(Path(claim["pack_path"]).read_text())
    merge = merge_decisions(root, decisions, pack["criteria_sha256"], pack.get("prompt_version"))
    claim["status"] = "completed"
    claim["completed_at"] = now()
    claim["missing_at_complete"] = missing
    claim["merge"] = merge
    cpath.write_text(json.dumps(claim, indent=2) + "\n")
    # also keep a copy under decisions/claims/
    out = root / "decisions" / "claims"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{claim_id}.json").write_text(json.dumps(obj, indent=2) + "\n")
    print(json.dumps({"claim_id": claim_id, "status": "completed", "decisions": len(decisions), "missing": len(missing), "merge": merge}, indent=2))

def release(root: Path, claim_id: str):
    cpath = root / "queue" / "claims" / f"{claim_id}.json"
    claim = json.loads(cpath.read_text())
    claim["status"] = "released"
    claim["released_at"] = now()
    cpath.write_text(json.dumps(claim, indent=2) + "\n")
    print(json.dumps({"claim_id": claim_id, "status": "released", "n": len(claim.get("work_ids") or [])}, indent=2))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT_DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    c = sub.add_parser("claim")
    c.add_argument("--agent", required=True)
    c.add_argument("--size", type=int, default=200)
    p = sub.add_parser("complete")
    p.add_argument("--claim-id", required=True)
    p.add_argument("--decisions", type=Path, required=True)
    p.add_argument("--agent", required=True, help="must match the agent that claimed this lease")
    r = sub.add_parser("release")
    r.add_argument("--claim-id", required=True)
    a = ap.parse_args()
    root = a.root.resolve()
    if a.cmd == "status":
        status(root)
    elif a.cmd == "claim":
        print(json.dumps(claim(root, a.agent, a.size), indent=2))
    elif a.cmd == "complete":
        complete(root, a.claim_id, a.decisions, agent=a.agent)
    elif a.cmd == "release":
        release(root, a.claim_id)

if __name__ == "__main__":
    main()
