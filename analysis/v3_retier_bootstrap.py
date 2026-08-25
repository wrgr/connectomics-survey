#!/usr/bin/env python3
"""Bootstrap v3 labels from v2 using golden-set-calibrated heuristics (preview only)."""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import analysis.llm_relevance_screen as L
from analysis.v3_decision_helpers import make_decision

MACRO_FLAGS = {
    "diffusion_mri_or_tractography",
    "resting_state_or_functional_connectivity",
    "macro_connectome_imaging",
    "human_connectome_project_style",
}
MESO_FLAGS = {"mesoscale_only"}
BIO_ONLY = {
    "unrelated_developmental_or_cell_biology",
    "molecular_genetics_not_wiring",
}

EM_CORE_RE = re.compile(
    r"\b(electron microscop|EM connectome|connectome reconstruction|serial section|"
    r"serial block|FIB-SEM|SBF-SEM|ssEM|volume EM|vEM|synaptic connect|wiring diagram|"
    r"FlyWire|hemibrain|MICrONS|petavoxel|nanoscale resolution|synapse-level|"
    r"whole-brain connectome|images-to-graph|connectomics pipeline|connectomic analysis)\b",
    re.I,
)
PIPELINE_RE = re.compile(
    r"\b(connectomics (?:segmentation|reconstruction|pipeline|community|dataset)|"
    r"neural circuit reconstruction|proofreading.*connectome|connectome assessment|"
    r"DotMotif|CONFIRMS|TrakEM2|FlyWire|images-to-graphs)\b",
    re.I,
)
MACRO_TEXT = re.compile(
    r"\b(fMRI|BOLD|resting[- ]state|diffusion (?:tensor|weighted|MRI)|tractograph|"
    r"Human Connectome Project|HCP[- ]|DTI|functional connectiv|macroscale)\b",
    re.I,
)


def parse_list(v) -> list[str]:
    if v is None or (isinstance(v, float) and v != v):
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    s = str(v).strip()
    if not s or s == "[]":
        return []
    try:
        x = ast.literal_eval(s)
        return [str(i) for i in x] if isinstance(x, list) else []
    except Exception:
        return []


def infer_scale(flags: set[str], title: str, abstract: str) -> str:
    text = f"{title} {abstract}"
    if flags & MACRO_FLAGS or MACRO_TEXT.search(text):
        return "macro_only"
    if flags & MESO_FLAGS or re.search(r"\b(mesoscale|tract-tracing|macro connectome)\b", text, re.I):
        return "multi_scale_bridging" if EM_CORE_RE.search(text) else "macro_only"
    if EM_CORE_RE.search(text):
        return "nanoscale_only"
    return "unclear"


def infer_core_gate(decision: str, roles: list[str], title: str, abstract: str) -> str | None:
    if decision != "core_relevant":
        return None
    text = f"{title} {abstract}"
    if PIPELINE_RE.search(text) or "infrastructure" in roles or "proofreading_qc" in roles:
        return "connectomics_pipeline_tool"
    if re.search(r"\b(reconstruct|reconstruction|segmentation|proofread|EM volume|petavoxel)\b", text, re.I):
        return "em_or_synaptic_reconstruction"
    return "analysis_on_wiring_graph"


def retier(row: pd.Series) -> dict:
    v2 = str(row.decision)
    roles = parse_list(row.roles)
    flags = set(parse_list(row.noise_flags))
    title = str(row.get("title") or "")
    abstract = str(row.get("abstract") or "")
    text = f"{title} {abstract}"
    conf = float(row.confidence) if pd.notna(row.confidence) else 0.7
    scale = infer_scale(flags, title, abstract)

    if v2 == "insufficient_abstract":
        return make_decision("insufficient_abstract", [], 0.0, "", row.get("reason") or "No abstract.", [], scale_relationship="unclear")

    decision = v2
    reason = str(row.get("reason") or "")

    if v2 == "core_relevant":
        if flags & MACRO_FLAGS or (MACRO_TEXT.search(text) and not EM_CORE_RE.search(text)):
            decision = "out_of_scope"
            reason = "v3: macro imaging connectome without nanoscale wiring evidence."
        elif re.search(r"\b(microglia|GAD|glutamic acid decarboxylase|synaptogenesis|synaptic pruning)\b", text, re.I) and not EM_CORE_RE.search(text):
            decision = "out_of_scope"
            reason = "v3: synaptic/cellular biology without wiring reconstruction."
        elif re.search(r"\bannotation standards|FAIR practices\b", text, re.I):
            decision = "role_bridge"
            reason = "v3: metadata/annotation standards infrastructure."
        elif re.search(r"\bIMOD\b", text) and not re.search(r"\bconnectomics\b", text, re.I):
            decision = "adjacent_relevant"
            reason = "v3: general EM visualization tool, not connectomics-specific pipeline."
        elif re.search(r"\bComparative Connectomics\b", title, re.I):
            decision = "adjacent_relevant"
            reason = "v3: comparative connectomics network-science framing."
        elif re.search(r"\bVolume electron microscopy for neuronal circuit reconstruction\b", title, re.I):
            decision = "adjacent_relevant"
            reason = "v3: methods review, not primary connectomics dataset/tool."
        elif re.search(r"\bfunctional inhibitory connectome\b", text, re.I) and "electrophysiol" in text.lower():
            decision = "adjacent_relevant"
            reason = "v3: electrophysiological circuit mapping, not EM wiring reconstruction."
        elif flags & MESO_FLAGS and not EM_CORE_RE.search(text):
            decision = "adjacent_relevant"
            reason = "v3: mesoscale connectivity, not nanoscale core."

    elif v2 == "out_of_scope":
        if flags & {"ambiguous_connectome_usage"} and re.search(r"\b(EM|electron microscop|synaptic resolution|volume EM)\b", text, re.I):
            decision = "uncertain"
            reason = "v3: ambiguous but possible nanoscale link — defer."

    gate = infer_core_gate(decision, roles, title, abstract)
    allowed = L.allowed_noise_flags()
    flags = sorted(f for f in flags if f in allowed)
    return make_decision(
        decision,
        roles,
        conf,
        str(row.get("evidence") or "")[:600],
        reason[:1200],
        sorted(flags),
        scale_relationship=scale,
        core_gate=gate,
    )


def main() -> None:
    v2_path = Path("postanalysis/llm_agent/llm_relevance_results.csv")
    enriched = Path("postanalysis/enriched/canonical_works_enriched.csv")
    out = Path("postanalysis/llm_agent_v3/llm_relevance_results_bootstrap.csv")
    L.set_prompt_version("v3")
    v2 = pd.read_csv(v2_path, low_memory=False)
    v2["work_id"] = v2.work_id.astype(str)
    meta = pd.read_csv(enriched, low_memory=False, usecols=["work_id", "abstract"])
    meta["work_id"] = meta.work_id.astype(str)
    df = v2.merge(meta, on="work_id", how="left", suffixes=("", "_enriched"))
    if "abstract_enriched" in df.columns:
        df["abstract"] = df.abstract.fillna(df.abstract_enriched)
    rows = []
    for r in df.itertuples(index=False):
        d = retier(pd.Series(r._asdict()))
        rows.append({**r._asdict(), **d, "prompt_version": L.PROMPT_VERSION, "bootstrap": True})
    out_df = pd.DataFrame(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out, index=False)
    summary = {
        "works": len(out_df),
        "v2_decisions": dict(Counter(v2.decision)),
        "v3_bootstrap_decisions": dict(Counter(out_df.decision)),
        "core_v2": int((v2.decision == "core_relevant").sum()),
        "core_v3": int((out_df.decision == "core_relevant").sum()),
        "tier_changes": int((v2.decision != out_df.decision).sum()),
    }
    (out.parent / "v3_bootstrap_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
