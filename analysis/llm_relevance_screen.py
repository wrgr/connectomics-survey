#!/usr/bin/env python3
"""LLM-first semantic relevance screening for the frozen post-analysis corpus.

Default target: the 2,068 unresolved originally-retained papers plus a noise audit of
the 1,685-paper derived nanoscale core. Strict retained bridges and recovered
keep=False bridges are outside the default screen.

The LLM is a first-pass reviewer only. It never changes source `keep`, derived core,
or bridge status. Outputs are provisional labels and later human-review queues.

Papers without abstracts are never semantically excluded from title alone; they are
routed to `insufficient_abstract` for later human/full-text review.

OpenAI-compatible environment variables:
  LLM_API_KEY       required unless --prepare-only
  LLM_API_BASE      default https://api.openai.com/v1
  LLM_MODEL         default gpt-5.6

The script is resumable: one JSON result is cached per paper/prompt/model hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

PROMPT_VERSION = "IA-007-v1"
ALLOWED_DECISIONS = {
    "core_relevant",
    "adjacent_relevant",
    "role_bridge",
    "out_of_scope",
    "uncertain",
    "insufficient_abstract",
}
ALLOWED_ROLES = {
    "acquisition_preparation",
    "reconstruction_segmentation",
    "synapse_inference",
    "proofreading_qc",
    "infrastructure",
    "network_science",
    "biological_application",
    "structure_function_modeling",
    "alternative_modality",
    "health_translation",
    "training_outreach",
}

CRITERIA = """
Scope for this evidence map:
- Core relevance: nanoscale or synaptic-resolution connectomics; direct reconstruction or measurement of individual neurons/synapses; enabling methods or infrastructure that are specifically used for such connectomics; or downstream analysis/modeling of an established nanoscale/synaptic connectome.
- Core pipeline includes tissue preparation, volume electron microscopy acquisition, alignment/registration, segmentation/agglomeration, proofreading/QC, synapse detection/partner assignment, graph construction, infrastructure, biological analysis and connectome-constrained modeling.
- Adjacent relevance: methods, modality comparisons, network concepts, or other work with a substantive and explicit relationship to nanoscale connectomics, but which is not itself core.
- Role bridges: health/translation, training/outreach, proofreading/annotation, infrastructure, or network-science work that is meaningfully connected to the field without itself necessarily being nanoscale-core science.
- Out of scope: diffusion MRI tractography, resting-state/functional connectivity, generic network neuroscience, generic microscopy, generic computer vision/ML, or generic graph theory unless the supplied title/abstract establishes a substantive relationship to nanoscale/synaptic connectomics.
- "training" meaning model optimization is NOT training/outreach/people development.
- Do not use outside knowledge. Judge only the supplied title and abstract. If evidence is insufficient, return uncertain rather than guessing.
""".strip()

SYSTEM = """You are a high-recall scientific title/abstract screener for an auditable evidence map. Missing a genuinely relevant paper is more costly than passing an ambiguous paper to later human review. Be conservative about exclusion. Return JSON only."""


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def build_prompt(row: dict[str, Any], source_group: str) -> str:
    current = "derived core (audit for false-positive noise)" if source_group == "core_audit" else "unresolved retained paper"
    return f"""{CRITERIA}

CURRENT SOURCE GROUP: {current}
TITLE: {row.get('title') or ''}
ABSTRACT:
{row.get('abstract') or ''}

Classify this record. Return exactly one JSON object with these fields:
- decision: one of core_relevant, adjacent_relevant, role_bridge, out_of_scope, uncertain
- roles: array chosen from acquisition_preparation, reconstruction_segmentation, synapse_inference, proofreading_qc, infrastructure, network_science, biological_application, structure_function_modeling, alternative_modality, health_translation, training_outreach
- confidence: number from 0 to 1
- evidence: concise phrase or sentence grounded only in the supplied title/abstract
- reason: concise explanation
- noise_flags: array of any of generic_machine_learning, generic_network_neuroscience, diffusion_mri_or_tractography, resting_state_or_functional_connectivity, mesoscale_only, generic_health_context, ml_training_not_people_training, ambiguous_connectome_usage

Important: if there is plausible nanoscale/connectomics relevance but the abstract is ambiguous, choose uncertain rather than out_of_scope.
""".strip()


def validate(result: dict[str, Any]) -> dict[str, Any]:
    decision = str(result.get("decision", ""))
    if decision not in ALLOWED_DECISIONS - {"insufficient_abstract"}:
        raise ValueError(f"invalid decision: {decision}")
    roles = result.get("roles", [])
    if not isinstance(roles, list) or any(str(x) not in ALLOWED_ROLES for x in roles):
        raise ValueError(f"invalid roles: {roles}")
    confidence = float(result.get("confidence", -1))
    if not (0 <= confidence <= 1):
        raise ValueError(f"invalid confidence: {confidence}")
    return {
        "decision": decision,
        "roles": [str(x) for x in roles],
        "confidence": confidence,
        "evidence": str(result.get("evidence", ""))[:600],
        "reason": str(result.get("reason", ""))[:1200],
        "noise_flags": [str(x) for x in result.get("noise_flags", [])],
    }


def call_model(prompt: str, *, api_base: str, api_key: str, model: str, attempts: int = 5) -> dict[str, Any]:
    # Chat Completions JSON object mode is used for broad OpenAI-compatible support.
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    url = api_base.rstrip("/") + "/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(attempts):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            return validate(json.loads(content))
        except urllib.error.HTTPError as e:
            if e.code not in {429, 500, 502, 503, 504} or attempt == attempts - 1:
                detail = e.read().decode("utf-8", errors="replace")[:1600]
                raise RuntimeError(f"LLM HTTP {e.code}: {detail}") from e
            retry_after = e.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** (attempt + 1)
            time.sleep(min(delay, 60))
        except (urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError):
            if attempt == attempts - 1:
                raise
            time.sleep(min(2 ** (attempt + 1), 60))
    raise RuntimeError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounting-csv", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--prepare-only", action="store_true", help="write screening input without calling an LLM")
    ap.add_argument("--limit", type=int, default=0, help="optional deterministic development limit")
    ap.add_argument("--confidence-review-threshold", type=float, default=0.85)
    ap.add_argument("--exclusion-audit-fraction", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=20260822)
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    cache.mkdir(exist_ok=True)

    df = pd.read_csv(args.accounting_csv, low_memory=False)
    df["paper_id"] = df["paper_id"].astype(str)
    df["source_group"] = "not_screened"
    df.loc[df["canonical_postanalysis_category"].eq("derived_nanoscale_core"), "source_group"] = "core_audit"
    df.loc[df["canonical_postanalysis_category"].str.startswith("unresolved_", na=False), "source_group"] = "unresolved"
    screen = df[df["source_group"].isin(["core_audit", "unresolved"])].copy()
    screen = screen.sort_values("paper_id").reset_index(drop=True)
    if args.limit:
        screen = screen.head(args.limit).copy()

    screen[["paper_id", "source_group", "title", "abstract", "canonical_postanalysis_category"]].to_json(
        out / "llm_screening_input.jsonl", orient="records", lines=True, force_ascii=False
    )

    if args.prepare_only:
        print(json.dumps({"prepared": len(screen), "core_audit": int((screen.source_group == 'core_audit').sum()), "unresolved": int((screen.source_group == 'unresolved').sum())}, indent=2))
        return

    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("LLM_API_KEY is required unless --prepare-only")
    api_base = os.environ.get("LLM_API_BASE", "https://api.openai.com/v1").strip()
    model = os.environ.get("LLM_MODEL", "gpt-5.6").strip()

    rows: list[dict[str, Any]] = []
    for idx, r in screen.iterrows():
        abstract = str(r.get("abstract") or "").strip()
        base = {
            "paper_id": r["paper_id"],
            "source_group": r["source_group"],
            "source_category": r["canonical_postanalysis_category"],
            "title": r.get("title", ""),
            "model": model,
            "prompt_version": PROMPT_VERSION,
        }
        if not abstract or abstract.lower() == "nan":
            result = {
                "decision": "insufficient_abstract",
                "roles": [],
                "confidence": 0.0,
                "evidence": "",
                "reason": "No abstract available; do not exclude from title alone.",
                "noise_flags": [],
            }
        else:
            prompt = build_prompt(r.to_dict(), r["source_group"])
            key = stable_hash({"paper_id": r["paper_id"], "prompt": prompt, "model": model, "version": PROMPT_VERSION})
            path = cache / f"{key}.json"
            if path.exists():
                result = json.loads(path.read_text())
            else:
                result = call_model(prompt, api_base=api_base, api_key=api_key, model=model)
                path.write_text(json.dumps(result, indent=2) + "\n")
        rows.append({**base, **result})
        if (idx + 1) % 25 == 0 or idx + 1 == len(screen):
            print(f"screened {idx + 1}/{len(screen)}", flush=True)

    results = pd.DataFrame(rows)

    # LLM-first workflow: these are provisional labels, never automatic source mutations.
    results["human_review_priority"] = False
    results["human_review_reason"] = ""
    low_conf = results["confidence"] < args.confidence_review_threshold
    uncertain = results["decision"].isin(["uncertain", "insufficient_abstract"])
    core_noise = results["source_group"].eq("core_audit") & results["decision"].isin(["out_of_scope", "uncertain", "insufficient_abstract"])
    results.loc[low_conf, ["human_review_priority", "human_review_reason"]] = [True, "low_confidence"]
    results.loc[uncertain, ["human_review_priority", "human_review_reason"]] = [True, "uncertain_or_missing_abstract"]
    results.loc[core_noise, ["human_review_priority", "human_review_reason"]] = [True, "core_noise_audit"]

    # Deterministic audit sample of high-confidence unresolved exclusions protects sensitivity.
    rng = random.Random(args.seed)
    exclusion_idx = list(results.index[
        results["source_group"].eq("unresolved")
        & results["decision"].eq("out_of_scope")
        & (results["confidence"] >= args.confidence_review_threshold)
    ])
    n_audit = int(round(len(exclusion_idx) * args.exclusion_audit_fraction))
    if exclusion_idx and args.exclusion_audit_fraction > 0:
        n_audit = max(1, n_audit)
        audit_idx = set(rng.sample(exclusion_idx, min(n_audit, len(exclusion_idx))))
        for i in audit_idx:
            results.loc[i, "human_review_priority"] = True
            results.loc[i, "human_review_reason"] = "random_high_confidence_exclusion_audit"

    results.to_csv(out / "llm_relevance_results.csv", index=False)
    results[results["human_review_priority"]].to_csv(out / "human_review_queue.csv", index=False)

    counts = results.groupby(["source_group", "decision"]).size().unstack(fill_value=0).to_dict(orient="index")
    summary = {
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "screened": len(results),
        "source_groups": results["source_group"].value_counts().to_dict(),
        "decision_counts": counts,
        "missing_abstracts": int((results["decision"] == "insufficient_abstract").sum()),
        "human_review_queue": int(results["human_review_priority"].sum()),
        "confidence_review_threshold": args.confidence_review_threshold,
        "high_confidence_exclusion_audit_fraction": args.exclusion_audit_fraction,
        "principle": "LLM first pass only; no source keep/core/bridge status is mutated.",
    }
    (out / "llm_relevance_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
