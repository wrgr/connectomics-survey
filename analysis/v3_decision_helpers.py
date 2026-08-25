#!/usr/bin/env python3
"""Helpers for IA-007-v3 offline adjudication decision objects."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Import validate() from screening module when run from repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import analysis.llm_relevance_screen as L  # noqa: E402

CORE_GATES = {
    "em_or_synaptic_reconstruction",
    "connectomics_pipeline_tool",
    "analysis_on_wiring_graph",
}


def make_decision(
    decision: str,
    roles: list[str],
    confidence: float,
    evidence: str,
    reason: str,
    noise_flags: list[str] | None = None,
    *,
    scale_relationship: str = "unclear",
    core_gate: str | None = None,
) -> dict:
    """Build and validate one v3 decision dict."""
    L.set_prompt_version("v3")
    if decision == "insufficient_abstract":
        return {
            "decision": "insufficient_abstract",
            "roles": [],
            "confidence": 0.0,
            "evidence": evidence,
            "reason": reason,
            "noise_flags": list(noise_flags or []),
            "scale_relationship": "unclear",
            "core_gate": "not_applicable",
        }
    if decision == "core_relevant":
        gate = core_gate or "em_or_synaptic_reconstruction"
    else:
        gate = "not_applicable"
    obj = {
        "decision": decision,
        "roles": list(roles),
        "confidence": float(confidence),
        "evidence": evidence,
        "reason": reason,
        "noise_flags": list(noise_flags or []),
        "scale_relationship": scale_relationship,
        "core_gate": gate,
    }
    return L.validate(obj)


def write_claim_decisions(
    pack_path: Path,
    decisions: dict[str, dict],
    out_path: Path,
    *,
    adjudicator: str = "agent:cursor/claude-opus-5-thinking",
) -> None:
    pack = json.loads(Path(pack_path).read_text())
    missing = [w["work_id"] for w in pack["works"] if w["work_id"] not in decisions]
    if missing:
        raise SystemExit(f"missing decisions for {len(missing)} works (first: {missing[:3]})")
    L.set_prompt_version("v3")
    validated = {wid: L.validate(dec) for wid, dec in decisions.items()}
    obj = {
        "criteria_sha256": pack["criteria_sha256"],
        "prompt_version": pack.get("prompt_version", L.PROMPT_VERSION),
        "adjudicator": adjudicator,
        "decisions": validated,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(obj, indent=2) + "\n")


def validate_file(path: Path) -> dict:
    obj = json.loads(Path(path).read_text())
    L.set_prompt_version("v3")
    n = 0
    for wid, dec in (obj.get("decisions") or {}).items():
        L.validate(dec)
        n += 1
    return {"works": n, "path": str(path)}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("decisions_json", type=Path)
    args = ap.parse_args()
    print(json.dumps(validate_file(args.decisions_json), indent=2))
