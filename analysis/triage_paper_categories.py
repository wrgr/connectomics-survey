#!/usr/bin/env python3
"""Triage non-core paper categories using proximity to the derived nanoscale core.

Post-analysis only: never mutates the preregistered corpus.

Design principle: lexical role signals (health, training/outreach, proofreading,
infrastructure/methods, network science) nominate a role; proximity to the derived
nanoscale core supplies field-specific evidence. Citation proximity is not treated
as proof of scope. Directed citations, bibliographic coupling, co-citation-like
shared neighborhoods, and core-community breadth are emitted separately so later
validation can determine category-specific thresholds.
"""
from __future__ import annotations
import argparse, collections, json, re
from pathlib import Path
import pandas as pd

ROLE_PATTERNS = {
    "health": [r"\bdisease\b", r"\bdisorder\b", r"\bpatholog(?:y|ical)\b", r"\bclinical\b", r"\bpatient", r"\btherap", r"\bdiagnos", r"\bneurodegener", r"\btrauma\b"],
    "training_outreach": [r"\beducat", r"\bcurricul", r"\btraining program\b", r"\bworkshop\b", r"\bsummer school\b", r"\boutreach\b", r"\bcitizen science\b", r"\bcommunity engagement\b", r"\bworkforce\b"],
    "proofreading_annotation": [r"\bproofread", r"\bannotation\b", r"\bannotat(?:e|ed|ing|or|ors)\b", r"\bmanual correction\b", r"\bhuman[- ]in[- ]the[- ]loop\b"],
    "infrastructure_methods": [r"\bsegmentation\b", r"\bagglomerat", r"\balignment\b", r"\bregistration\b", r"\bdata infrastructure\b", r"\bdata system\b", r"\bvisualization\b", r"\bimage processing\b", r"\bsynapse detection\b"],
    "network_science": [r"\bnetwork analys", r"\bgraph analys", r"\bmotif", r"\bcentrality\b", r"\bcommunity detection\b", r"\bsubgraph\b", r"\bgraph quer"],
}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--outputs-dir",required=True,type=Path); ap.add_argument("--cleanup-dir",required=True,type=Path); ap.add_argument("--out",required=True,type=Path); a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(a.cleanup_dir/"paper_cleanup_review_queue.csv",low_memory=False); e=pd.read_csv(a.outputs_dir/"paper_graph_edges.csv",low_memory=False)
    p["paper_id"]=p.paper_id.astype(str); e["source"]=e.source.astype(str); e["target"]=e.target.astype(str)
    core=set(p.loc[p.derived_nanoscale_core,"paper_id"]); ids=set(p.paper_id)
    e=e[e.source.isin(ids)&e.target.isin(ids)].copy()
    outnbr=collections.defaultdict(set); innbr=collections.defaultdict(set)
    for r in e.itertuples(index=False): outnbr[r.source].add(r.target); innbr[r.target].add(r.source)
    # Core references and core citers are directional evidence; shared-reference overlap is a coupling proxy.
    core_refs={x: outnbr[x] for x in core}; core_citers={x: innbr[x] for x in core}
    def metrics(pid):
        refs=outnbr[pid]; citers=innbr[pid]
        cited_core=refs&core; citing_core=citers&core
        coupled=set(); cocited=set()
        for c in core:
            if refs and core_refs[c] and refs & core_refs[c]: coupled.add(c)
            if citers and core_citers[c] and citers & core_citers[c]: cocited.add(c)
        return len(cited_core),len(citing_core),len(coupled),len(cocited)
    vals=[metrics(x) for x in p.paper_id]
    p[["core_refs_cited","core_citers","core_bibcoupled","core_cocited"]]=pd.DataFrame(vals,index=p.index)
    p["core_direct_proximity"]=p.core_refs_cited+p.core_citers
    p["core_hybrid_proximity"]=p.core_direct_proximity+p.core_bibcoupled+p.core_cocited
    text=(p.title.fillna("")+" "+p.abstract.fillna("")).str.lower()
    for role,pats in ROLE_PATTERNS.items():
        p[f"role_{role}"]=False
        for pat in pats: p[f"role_{role}"] |= text.str.contains(pat,regex=True,na=False)
    # Preserve existing discovery tags as nomination evidence, not sufficient inclusion evidence.
    p["role_health"] |= p.health_flag.fillna(False)
    p["role_training_outreach"] |= p.training_outreach_flag.fillna(False)
    rolecols=[f"role_{r}" for r in ROLE_PATTERNS]
    p["role_count"]=p[rolecols].sum(axis=1)
    # No universal proximity cutoff: stratify for review. Strong means >=2 direct core links OR >=5 hybrid links;
    # these are queue-prioritization heuristics and are explicitly not automatic inclusion rules.
    p["proximity_stratum"]="weak_or_none"
    p.loc[(p.core_direct_proximity>=1)|(p.core_hybrid_proximity>=2),"proximity_stratum"]="moderate"
    p.loc[(p.core_direct_proximity>=2)|(p.core_hybrid_proximity>=5),"proximity_stratum"]="strong"
    def action(r):
        if r.derived_nanoscale_core: return "retain_core"
        if r.proximity_stratum=="strong" and r.role_count>0: return "priority_adjacent_review"
        if r.proximity_stratum in {"strong","moderate"}: return "adjacent_review"
        if r.role_count>0: return "role_bridge_review"
        return "low_priority_review"
    p["triage_action"]=p.apply(action,axis=1)
    p.to_csv(a.out/"paper_category_proximity_triage.csv",index=False)
    for role in ROLE_PATTERNS:
        p[p[f"role_{role}"]].sort_values(["core_hybrid_proximity","evidence_score"],ascending=False).to_csv(a.out/f"role_{role}_review.csv",index=False)
    stats={"papers":len(p),"core":int(p.derived_nanoscale_core.sum()),"actions":p.triage_action.value_counts().to_dict(),"proximity":p.proximity_stratum.value_counts().to_dict(),"roles":{r:int(p[f'role_{r}'].sum()) for r in ROLE_PATTERNS}}
    (a.out/"paper_category_triage_stats.json").write_text(json.dumps(stats,indent=2)+"\n")
    print(json.dumps(stats,indent=2))
if __name__=="__main__": main()
