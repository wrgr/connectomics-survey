#!/usr/bin/env python3
"""LLM-first semantic relevance screening of reconciled canonical works.

Input should be IA-008 `canonical_works_enriched.csv`: all originally retained
records plus the 391 recovered role-bridge records have already been reconciled into
work/version groups and subjected to best-effort abstract rescue.

The LLM is a first-pass reviewer only. It never changes source `keep`, derived core,
bridge, or work-link status. Missing abstracts are never excluded from title alone.
"""
from __future__ import annotations
import argparse, hashlib, json, os, random, time, urllib.error, urllib.request
from pathlib import Path
from typing import Any
import pandas as pd

PROMPT_VERSION="IA-007-v2-work-level"
ALLOWED_DECISIONS={"core_relevant","adjacent_relevant","role_bridge","out_of_scope","uncertain","insufficient_abstract"}
ALLOWED_ROLES={"acquisition_preparation","reconstruction_segmentation","synapse_inference","proofreading_qc","infrastructure","network_science","biological_application","structure_function_modeling","alternative_modality","health_translation","training_outreach"}

CRITERIA="""
Scope for this evidence map:
- Core relevance: nanoscale or synaptic-resolution connectomics; direct reconstruction or measurement of individual neurons/synapses; enabling methods or infrastructure specifically used for such connectomics; or downstream analysis/modeling of an established nanoscale/synaptic connectome.
- Core pipeline includes tissue preparation, volume electron microscopy acquisition, alignment/registration, segmentation/agglomeration, proofreading/QC, synapse detection/partner assignment, graph construction, infrastructure, biological analysis and connectome-constrained modeling.
- Adjacent relevance: methods, modality comparisons, network concepts, or other work with a substantive and explicit relationship to nanoscale connectomics, but not itself core.
- Role bridges: health/translation, training/outreach, proofreading/annotation, infrastructure, or network-science work meaningfully connected to the field without itself necessarily being nanoscale-core science.
- Out of scope: diffusion MRI tractography, resting-state/functional connectivity, generic network neuroscience, generic microscopy, generic computer vision/ML, or generic graph theory unless the supplied title/abstract establishes a substantive relationship to nanoscale/synaptic connectomics.
- "training" meaning model optimization is NOT training/outreach/people development.
- Do not use outside knowledge. Judge only supplied title and abstract. If evidence is insufficient, choose uncertain rather than guessing.
""".strip()
SYSTEM="You are a high-recall scientific title/abstract screener for an auditable evidence map. Missing a genuinely relevant work is more costly than passing an ambiguous work to later human review. Be conservative about exclusion. Return JSON only."

def stable_hash(value:Any)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def build_prompt(row:dict[str,Any])->str:
    group={"core_audit":"derived core (audit for false-positive noise)","unresolved":"unresolved retained work","role_bridge":"strict role-bridge work (retained or recovered)"}.get(str(row.get("source_group")),str(row.get("source_group")))
    return f"""{CRITERIA}

CURRENT SOURCE GROUP: {group}
TITLE: {row.get('title') or ''}
ABSTRACT:
{row.get('abstract') or ''}

Return exactly one JSON object with:
- decision: core_relevant, adjacent_relevant, role_bridge, out_of_scope, or uncertain
- roles: array chosen from acquisition_preparation, reconstruction_segmentation, synapse_inference, proofreading_qc, infrastructure, network_science, biological_application, structure_function_modeling, alternative_modality, health_translation, training_outreach
- confidence: 0 to 1
- evidence: concise phrase/sentence grounded only in title/abstract
- reason: concise explanation
- noise_flags: array drawn from generic_machine_learning, generic_network_neuroscience, diffusion_mri_or_tractography, resting_state_or_functional_connectivity, mesoscale_only, generic_health_context, ml_training_not_people_training, ambiguous_connectome_usage, paratext_or_peer_review_record

If plausible relevance exists but the abstract is ambiguous, choose uncertain rather than out_of_scope.
""".strip()

def validate(result:dict[str,Any])->dict[str,Any]:
    decision=str(result.get("decision",""))
    if decision not in ALLOWED_DECISIONS-{"insufficient_abstract"}:raise ValueError(f"invalid decision: {decision}")
    roles=result.get("roles",[])
    if not isinstance(roles,list) or any(str(x) not in ALLOWED_ROLES for x in roles):raise ValueError(f"invalid roles: {roles}")
    confidence=float(result.get("confidence",-1))
    if not 0<=confidence<=1:raise ValueError("invalid confidence")
    return {"decision":decision,"roles":[str(x) for x in roles],"confidence":confidence,"evidence":str(result.get("evidence",""))[:600],"reason":str(result.get("reason",""))[:1200],"noise_flags":[str(x) for x in result.get("noise_flags",[])]}

def call_model(prompt:str,*,api_base:str,api_key:str,model:str,attempts:int=5)->dict[str,Any]:
    payload={"model":model,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],"response_format":{"type":"json_object"}}
    headers={"Content-Type":"application/json","Authorization":f"Bearer {api_key}"}; url=api_base.rstrip("/")+"/chat/completions"; data=json.dumps(payload).encode()
    for attempt in range(attempts):
        req=urllib.request.Request(url,data=data,headers=headers,method="POST")
        try:
            with urllib.request.urlopen(req,timeout=180) as resp:body=json.loads(resp.read().decode())
            return validate(json.loads(body["choices"][0]["message"]["content"]))
        except urllib.error.HTTPError as e:
            if e.code not in {429,500,502,503,504} or attempt==attempts-1:raise RuntimeError(f"LLM HTTP {e.code}: {e.read().decode(errors='replace')[:1600]}") from e
            ra=e.headers.get("Retry-After"); time.sleep(min(float(ra) if ra and ra.isdigit() else 2**(attempt+1),60))
        except (urllib.error.URLError,ValueError,KeyError,json.JSONDecodeError):
            if attempt==attempts-1:raise
            time.sleep(min(2**(attempt+1),60))
    raise RuntimeError("unreachable")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--works-csv",required=True,type=Path); ap.add_argument("--out",required=True,type=Path); ap.add_argument("--prepare-only",action="store_true"); ap.add_argument("--limit",type=int,default=0); ap.add_argument("--confidence-review-threshold",type=float,default=0.85); ap.add_argument("--exclusion-audit-fraction",type=float,default=0.10); ap.add_argument("--seed",type=int,default=20260822); args=ap.parse_args()
    out=args.out.resolve(); out.mkdir(parents=True,exist_ok=True); cache=out/"cache"; cache.mkdir(exist_ok=True)
    df=pd.read_csv(args.works_csv,low_memory=False); df["work_id"]=df.work_id.astype(str)
    screen=df[df.source_group.isin(["core_audit","unresolved","role_bridge"])].sort_values("work_id").reset_index(drop=True)
    if args.limit:screen=screen.head(args.limit).copy()
    cols=[c for c in ["work_id","canonical_paper_id","source_group","version_count","member_paper_ids","title","abstract","doi","citation_count_work"] if c in screen.columns]
    screen[cols].to_json(out/"llm_screening_input.jsonl",orient="records",lines=True,force_ascii=False)
    prepared={"prepared_works":len(screen),"source_groups":screen.source_group.value_counts().to_dict(),"missing_abstracts":int(screen.abstract.fillna("").astype(str).str.strip().eq("").sum())}
    if args.prepare_only:(out/"llm_prepare_summary.json").write_text(json.dumps(prepared,indent=2)+"\n"); print(json.dumps(prepared,indent=2)); return
    key=os.environ.get("LLM_API_KEY","").strip()
    if not key:raise RuntimeError("LLM_API_KEY required unless --prepare-only")
    api_base=os.environ.get("LLM_API_BASE","https://api.openai.com/v1").strip(); model=os.environ.get("LLM_MODEL","gpt-5.6").strip(); rows=[]
    for idx,r in screen.iterrows():
        abstract=str(r.get("abstract") or "").strip(); base={"work_id":r.work_id,"canonical_paper_id":r.get("canonical_paper_id",""),"source_group":r.source_group,"version_count":r.get("version_count",1),"member_paper_ids":r.get("member_paper_ids",""),"title":r.get("title",""),"model":model,"prompt_version":PROMPT_VERSION}
        if not abstract or abstract.lower()=="nan":result={"decision":"insufficient_abstract","roles":[],"confidence":0.0,"evidence":"","reason":"No abstract after best-effort rescue; do not exclude from title alone.","noise_flags":[]}
        else:
            prompt=build_prompt(r.to_dict()); h=stable_hash({"work_id":r.work_id,"prompt":prompt,"model":model,"version":PROMPT_VERSION}); path=cache/f"{h}.json"
            if path.exists():result=json.loads(path.read_text())
            else:result=call_model(prompt,api_base=api_base,api_key=key,model=model); path.write_text(json.dumps(result,indent=2)+"\n")
        rows.append({**base,**result})
        if (idx+1)%25==0 or idx+1==len(screen):print(f"screened {idx+1}/{len(screen)}",flush=True)
    results=pd.DataFrame(rows); results["human_review_priority"]=False; results["human_review_reason"]=""
    low=results.confidence<args.confidence_review_threshold; uncertain=results.decision.isin(["uncertain","insufficient_abstract"]); core_noise=results.source_group.eq("core_audit")&results.decision.isin(["out_of_scope","uncertain","insufficient_abstract"])
    results.loc[low,["human_review_priority","human_review_reason"]]=[True,"low_confidence"]; results.loc[uncertain,["human_review_priority","human_review_reason"]]=[True,"uncertain_or_missing_abstract"]; results.loc[core_noise,["human_review_priority","human_review_reason"]]=[True,"core_noise_audit"]
    rng=random.Random(args.seed); ex=list(results.index[results.source_group.isin(["unresolved","role_bridge"])&results.decision.eq("out_of_scope")&(results.confidence>=args.confidence_review_threshold)]); n=int(round(len(ex)*args.exclusion_audit_fraction))
    if ex and args.exclusion_audit_fraction>0:
        for i in rng.sample(ex,min(max(1,n),len(ex))):results.loc[i,"human_review_priority"]=True; results.loc[i,"human_review_reason"]="random_high_confidence_exclusion_audit"
    results.to_csv(out/"llm_relevance_results.csv",index=False); results[results.human_review_priority].to_csv(out/"human_review_queue.csv",index=False)
    summary={"prompt_version":PROMPT_VERSION,"model":model,"screened_works":len(results),"source_groups":results.source_group.value_counts().to_dict(),"decision_counts":results.groupby(["source_group","decision"]).size().unstack(fill_value=0).to_dict(orient="index"),"missing_abstracts":int(results.decision.eq("insufficient_abstract").sum()),"human_review_queue":int(results.human_review_priority.sum()),"principle":"LLM first pass at canonical-work level; no source keep/core/bridge/work-link status is mutated."}
    (out/"llm_relevance_summary.json").write_text(json.dumps(summary,indent=2)+"\n"); print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
