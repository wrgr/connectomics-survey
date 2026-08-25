"""View overlay: ultra / connected core / contextual ring / hidden gem / drop.

Does not rewrite frozen IA-007-v3 agent JSON. Contextual quality for papers
from 2020 and earlier uses a 5-cite floor; the 2–4 cite band is hidden_gem.
"""
from __future__ import annotations

import ast
from typing import Any

import pandas as pd

CONN_K = 3
CORE_CITE_OLD = 10
CORE_CITE_2021_22 = 5
NO_GRAPH_CORE_CITES = 50
OLD_YEAR = 2020
CONTEXT_CITES = 5
DROP_CITES = 2
WEAK_MAX_IO = 2

TRANSLATION_ROLES = {"health_translation"}
BRIDGE_ROLES = {"infrastructure", "training_outreach", "proofreading_qc"}


def s(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    t = str(v).strip()
    return "" if t.lower() in {"", "nan", "none", "null"} else t


def parse_roles(v: Any) -> list[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    try:
        parsed = ast.literal_eval(str(v))
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    text = s(v)
    return [text] if text else []


def n(v: Any) -> float:
    x = pd.to_numeric(v, errors="coerce")
    return float(x) if pd.notna(x) else float("nan")


def connected(max_io: float) -> bool:
    if pd.isna(max_io):
        return False
    return float(max_io) >= CONN_K


def cites_ok_core(year: float, cites: float) -> bool:
    c = 0.0 if pd.isna(cites) else float(cites)
    if pd.isna(year) or year <= OLD_YEAR:
        return c >= CORE_CITE_OLD
    if year <= 2022:
        return c >= CORE_CITE_2021_22
    return True


def is_graph_unknown(citation_role: str, graph_status: str) -> bool:
    role = s(citation_role) or "no_graph"
    status = s(graph_status)
    return role == "no_graph" or status in {"no_graph", "rescued_no_graph"}


def proposed_core(
    *,
    decision: str,
    is_ultra: bool,
    is_emergent: bool,
    graph_unknown: bool,
    max_io: float,
    year: float,
    cites: float,
) -> bool:
    if decision != "core_relevant":
        return False
    if is_ultra or is_emergent:
        return True
    if graph_unknown:
        return cites_ok_core(year, cites) and (0.0 if pd.isna(cites) else cites) >= NO_GRAPH_CORE_CITES
    return cites_ok_core(year, cites) and connected(max_io)


def contextual_sublabel(decision: str, roles: list[str]) -> str:
    rs = set(roles or [])
    if rs & TRANSLATION_ROLES:
        return "translation"
    if decision == "role_bridge" or rs & BRIDGE_ROLES:
        return "bridge"
    return "complementary"


def contextual_quality(
    *,
    year: float,
    cites: float,
    max_io: float,
    out_deg: float,
    decision: str,
) -> tuple[str, str]:
    """Return (pass|hidden_gem|drop, reason) for non-ultra, non-core works."""
    c = 0.0 if pd.isna(cites) else float(cites)
    mio = 0.0 if pd.isna(max_io) else float(max_io)
    out = 0.0 if pd.isna(out_deg) else float(out_deg)
    old = (not pd.isna(year)) and year <= OLD_YEAR
    linked = mio >= 1 or out >= 1
    if old and c < CONTEXT_CITES and mio < WEAK_MAX_IO:
        if c >= DROP_CITES:
            return "hidden_gem", "old_cite_band_2_to_4"
        if linked:
            return "hidden_gem", "old_uncited_linked"
        return "drop", "old_uncited_unlinked"
    if (pd.isna(year) or year >= 2021) and c < DROP_CITES and mio < 1:
        if decision == "core_relevant":
            return "hidden_gem", "young_core_thin"
        return "pass", "young_adjacent_thin"
    return "pass", "ok"


def assign_row(row: Any) -> dict[str, Any]:
    decision = s(getattr(row, "decision", ""))
    is_ultra = bool(getattr(row, "is_ultra", False))
    is_emergent = bool(getattr(row, "is_emergent", False))
    year = n(getattr(row, "year_n", getattr(row, "year", float("nan"))))
    cites = n(getattr(row, "cites", getattr(row, "citation_count_work", 0)))
    max_io = n(getattr(row, "max_io", float("nan")))
    out_deg = n(getattr(row, "out_deg", getattr(row, "corpus_out_degree", float("nan"))))
    graph_unknown = bool(getattr(row, "graph_unknown", False))
    roles = getattr(row, "roles", []) or []
    if is_ultra:
        return {"proposed_layer": "ultra", "contextual_sublabel": "", "quality": "pass", "quality_reason": "ultra"}
    if proposed_core(
        decision=decision,
        is_ultra=is_ultra,
        is_emergent=is_emergent,
        graph_unknown=graph_unknown,
        max_io=max_io,
        year=year,
        cites=cites if not pd.isna(cites) else 0.0,
    ):
        return {"proposed_layer": "core", "contextual_sublabel": "", "quality": "pass", "quality_reason": "connected_core"}
    sub = contextual_sublabel(decision, roles if isinstance(roles, list) else parse_roles(roles))
    quality, reason = contextual_quality(
        year=year, cites=cites, max_io=max_io, out_deg=out_deg, decision=decision
    )
    layer = "contextual" if quality == "pass" else quality
    return {
        "proposed_layer": layer,
        "contextual_sublabel": sub,
        "quality": quality,
        "quality_reason": reason,
    }


def annotate_corpus(corpus: pd.DataFrame, *, emergent_ids: set[str], roles_map: dict[str, list[str]]) -> pd.DataFrame:
    out = corpus.copy()
    out["year_n"] = pd.to_numeric(out.year, errors="coerce")
    out["cites"] = pd.to_numeric(out.citation_count_work, errors="coerce").fillna(0)
    out["in_deg"] = pd.to_numeric(out.corpus_in_degree, errors="coerce")
    out["out_deg"] = pd.to_numeric(out.corpus_out_degree, errors="coerce")
    out["max_io"] = out[["in_deg", "out_deg"]].max(axis=1)
    out["is_ultra"] = out.ultra_core.fillna(False).astype(bool)
    out["is_emergent"] = out.work_id.isin(emergent_ids)
    role = out.citation_role.fillna("no_graph") if "citation_role" in out.columns else pd.Series(["no_graph"] * len(out), index=out.index)
    if "graph_status" in out.columns:
        status = out.graph_status.fillna("")
    else:
        status = pd.Series([""] * len(out), index=out.index)
    out["graph_unknown"] = role.eq("no_graph") | status.isin(["no_graph", "rescued_no_graph"])
    out["roles"] = out.work_id.map(lambda w: roles_map.get(str(w), []))
    assigned = [assign_row(row) for row in out.itertuples(index=False)]
    extra = pd.DataFrame(assigned, index=out.index)
    for col in extra.columns:
        out[col] = extra[col]
    return out
