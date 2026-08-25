#!/usr/bin/env python3
"""LLM-first semantic relevance screening of reconciled canonical works.

Input should be IA-008 `canonical_works_enriched.csv`: all originally retained
records plus the 391 recovered role-bridge records have already been reconciled into
work/version groups and subjected to best-effort abstract rescue.

The LLM is a first-pass reviewer only. It never changes source `keep`, derived core,
bridge, or work-link status. Missing abstracts are never excluded from title alone.

Two execution paths produce the same schema (IA-009):

- API mode calls a hosted model directly (`LLM_API_KEY` required);
- offline agent mode exports the exact per-work prompts with `--export-prompts`, has
  them adjudicated out of band, and reads the returned JSON back with
  `--ingest-decisions`. Offline mode never reads `LLM_API_KEY` and opens no socket.

One JSON line per screened work is appended to `llm_screen_progress.jsonl` as each
decision lands, and the partial results CSV is rewritten periodically, so a long run
is observable and a partial run is still usable.
"""
from __future__ import annotations
import argparse, hashlib, json, os, random, re, sys, time, urllib.error, urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import pandas as pd

PROMPT_VERSION="IA-007-v2-work-level"
PROGRESS_FILE="llm_screen_progress.jsonl"
DUMP_EVERY=25
CACHE_SCHEMA="ia007-cache-v2"
ALLOWED_DECISIONS={"core_relevant","adjacent_relevant","role_bridge","out_of_scope","uncertain","insufficient_abstract"}
ALLOWED_ROLES={"acquisition_preparation","reconstruction_segmentation","synapse_inference","proofreading_qc","infrastructure","network_science","biological_application","structure_function_modeling","alternative_modality","health_translation","training_outreach"}
ALLOWED_SCALE={"nanoscale_only","multi_scale_bridging","macro_only","unclear"}
ALLOWED_CORE_GATE={"em_or_synaptic_reconstruction","connectomics_pipeline_tool","analysis_on_wiring_graph","not_applicable"}
NOISE_FLAGS_V2={"generic_machine_learning","generic_network_neuroscience","diffusion_mri_or_tractography","resting_state_or_functional_connectivity","mesoscale_only","generic_health_context","ml_training_not_people_training","ambiguous_connectome_usage","paratext_or_peer_review_record"}
NOISE_FLAGS_V3=NOISE_FLAGS_V2|{"macro_connectome_imaging","human_connectome_project_style","unrelated_developmental_or_cell_biology","molecular_genetics_not_wiring","general_purpose_tool_only","connectome_word_only","analysis_without_wiring_graph"}
INCLUSIVE_DECISIONS={"core_relevant","adjacent_relevant","role_bridge"}
EXCLUSIVE_DECISIONS={"out_of_scope"}
SOURCE_GROUPS=["core_audit","unresolved","role_bridge"]
ADJUDICATOR_RE=re.compile(r"^agent:[0-9A-Za-z][0-9A-Za-z._-]*/[0-9A-Za-z][0-9A-Za-z._-]*(@\d{4}-\d{2}-\d{2})?$")
MANIFEST_FIELDS=("run_mode","model","prompt_version","criteria_sha256","works_csv_sha256")

CRITERIA_V2="""
Scope for this evidence map:
- Core relevance: nanoscale or synaptic-resolution connectomics; direct reconstruction or measurement of individual neurons/synapses; enabling methods or infrastructure specifically used for such connectomics; or downstream analysis/modeling of an established nanoscale/synaptic connectome.
- Core pipeline includes tissue preparation, volume electron microscopy acquisition, alignment/registration, segmentation/agglomeration, proofreading/QC, synapse detection/partner assignment, graph construction, infrastructure, biological analysis and connectome-constrained modeling.
- Adjacent relevance: methods, modality comparisons, network concepts, or other work with a substantive and explicit relationship to nanoscale connectomics, but not itself core.
- Role bridges: health/translation, training/outreach, proofreading/annotation, infrastructure, or network-science work meaningfully connected to the field without itself necessarily being nanoscale-core science.
- Out of scope: diffusion MRI tractography, resting-state/functional connectivity, generic network neuroscience, generic microscopy, generic computer vision/ML, or generic graph theory unless the supplied title/abstract establishes a substantive relationship to nanoscale/synaptic connectomics.
- "training" meaning model optimization is NOT training/outreach/people development.
- Do not use outside knowledge. Judge only supplied title and abstract. If evidence is insufficient, choose uncertain rather than guessing.
""".strip()

SYSTEM_V2="You are a high-recall scientific title/abstract screener for an auditable evidence map. Missing a genuinely relevant work is more costly than passing an ambiguous work to later human review. Be conservative about exclusion. Return JSON only."

CRITERIA_V3="""
TIER DEFINITIONS (apply in order; pick the best-fitting tier; if two fit, prefer the less specific tier)

1) CORE_RELEVANT (strict) — requires explicit title/abstract evidence of at least one:
   - EM or synaptic-resolution reconstruction, segmentation, proofreading, synapse assignment, or release/analysis of a neuronal/synaptic wiring diagram.
   - Methods/software whose stated primary purpose is the connectomics reconstruction pipeline or wiring-graph construction/query.
   - Analysis explicitly performed ON a reconstructed nanoscale/synaptic wiring graph.
   NOT core: general tools "also used by connectomics labs"; macro network studies; developmental/cellular biology about synapses unless wiring-graph work is central; citation count or field fame alone.

2) ADJACENT_RELEVANT — substantive explicit relationship to nanoscale connectomics, including:
   - Multi-scale / cross-level analysis relating nanoscale EM wiring to mesoscale or macro brain organization; comparative connectomics; integrative reviews connecting EM connectomes to broader architecture.
   - Network/graph analysis, topology, or comparative methods motivated by wiring graphs or connectome datasets (including influential network-science work on connectome structure).
   - EM/segmentation/microscopy methods linked to circuit reconstruction but not exclusively connectomics pipeline tools.
   - General-purpose EM visualization or infrastructure widely used by connectomics labs when not framed as connectomics pipeline science.

3) ROLE_BRIDGE — training/outreach, health translation, annotation/metadata standards, infrastructure platforms, or cross-field bridges where connectomics is one meaningful application.

4) UNCERTAIN — plausible relevance but insufficient detail to choose fairly (ambiguous "connectome"/"connectivity"/"circuit" language). Prefer uncertain over guessing core or excluding.

5) OUT_OF_SCOPE (last resort) — clearly unrelated with no fair link to nanoscale connectomics, e.g. macro in vivo imaging connectomes (DTI, fMRI, BOLD, HCP-style cohorts) with no synaptic/EM link; generic neuroscience where connectivity is background; generic ML/CV/graph theory/microscopy with no connectomics relationship.

If macroscale work discusses methods or concepts that could inform how wiring graphs relate to larger brain organization, use adjacent_relevant or uncertain — not out_of_scope.

DISAMBIGUATION
- "Connectome" from macro imaging alone → out_of_scope OR uncertain if vague; NOT core.
- Multi-scale / integrative framing of EM connectomes → adjacent_relevant.
- Network methods on wiring graphs → adjacent_relevant (network_science role).
- General-purpose tools → adjacent or role_bridge, not core.
- Biology papers (microglia, genetics, synaptogenesis) without wiring reconstruction → out_of_scope if clearly unrelated; uncertain if ambiguous.

CONFIDENCE: 0.90+ unambiguous; 0.75–0.89 clear with one inference; 0.55–0.74 borderline (prefer uncertain/adjacent over core); <0.55 weak (uncertain unless clearly out_of_scope).

"training" meaning model optimization is NOT training_outreach.
Do not use outside knowledge. Judge only supplied title and abstract.
""".strip()

SYSTEM_V3="""You are a title/abstract screener for a nanoscale connectomics evidence map.

Classify each work into the tier that BEST FITS the supplied title and abstract.
Do not force unrelated work into the map, but do not exclude generously — when a fair link exists, use adjacent_relevant or role_bridge rather than out_of_scope.

core_relevant is STRICT: synaptic-resolution / nanoscale wiring connectomics only.

When placement is ambiguous, prefer uncertain (for human review) over out_of_scope or core_relevant.

Judge ONLY the supplied title and abstract. Return JSON only."""

ACTIVE_PROMPT="v2"
CRITERIA=CRITERIA_V2
SYSTEM=SYSTEM_V2

def set_prompt_version(version:str)->None:
    global ACTIVE_PROMPT, PROMPT_VERSION, CRITERIA, SYSTEM
    version=version.strip().lower()
    if version in {"v2","ia-007-v2","ia-007-v2-work-level"}:
        ACTIVE_PROMPT="v2"; PROMPT_VERSION="IA-007-v2-work-level"; CRITERIA=CRITERIA_V2; SYSTEM=SYSTEM_V2
    elif version in {"v3","ia-007-v3","ia-007-v3-work-level"}:
        ACTIVE_PROMPT="v3"; PROMPT_VERSION="IA-007-v3-work-level"; CRITERIA=CRITERIA_V3; SYSTEM=SYSTEM_V3
    else:
        raise ValueError(f"unknown prompt version: {version}")

def allowed_noise_flags()->set[str]:
    return NOISE_FLAGS_V3 if ACTIVE_PROMPT=="v3" else NOISE_FLAGS_V2

def stable_hash(value:Any)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def sha256_text(text:str)->str:return hashlib.sha256(text.encode()).hexdigest()

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()

def criteria_text()->str:return SYSTEM+"\n\n"+CRITERIA

def criteria_sha256()->str:return sha256_text(criteria_text())

def s(v:Any)->str:return "" if v is None or (isinstance(v,float) and v!=v) else str(v)

def now_ts()->str:return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())

def screen_record(pos:int,total:int,base:dict[str,Any],result:dict[str,Any],cache_hit:bool)->dict[str,Any]:
    return {"ts":now_ts(),"index":int(pos),"total":int(total),"work_id":s(base.get("work_id")),"canonical_paper_id":s(base.get("canonical_paper_id")),"source_group":s(base.get("source_group")),"title":s(base.get("title"))[:200],"decision":result["decision"],"confidence":float(result["confidence"]),"roles":list(result["roles"]),"noise_flags":list(result["noise_flags"]),"evidence":s(result.get("evidence")),"reason":s(result.get("reason")),"cache_hit":bool(cache_hit),"model":s(base.get("model")),"prompt_version":s(base.get("prompt_version"))}

def emit(fh,rec:dict[str,Any])->None:
    fh.write(json.dumps(rec,ensure_ascii=False)+"\n"); fh.flush()

def annotate(results:pd.DataFrame,threshold:float,fraction:float,seed:int)->pd.DataFrame:
    results=results.copy(); results["human_review_priority"]=False; results["human_review_reason"]=""
    low=results.confidence<threshold; uncertain=results.decision.isin(["uncertain","insufficient_abstract"]); core_noise=results.source_group.eq("core_audit")&results.decision.isin(["out_of_scope","uncertain","insufficient_abstract"])
    results.loc[low,["human_review_priority","human_review_reason"]]=[True,"low_confidence"]; results.loc[uncertain,["human_review_priority","human_review_reason"]]=[True,"uncertain_or_missing_abstract"]; results.loc[core_noise,["human_review_priority","human_review_reason"]]=[True,"core_noise_audit"]
    rng=random.Random(seed); ex=list(results.index[results.source_group.isin(["unresolved","role_bridge"])&results.decision.eq("out_of_scope")&(results.confidence>=threshold)]); n=int(round(len(ex)*fraction))
    if ex and fraction>0:
        for i in rng.sample(ex,min(max(1,n),len(ex))):results.loc[i,"human_review_priority"]=True; results.loc[i,"human_review_reason"]="random_high_confidence_exclusion_audit"
    return results

def build_prompt(row:dict[str,Any])->str:
    group={"core_audit":"derived core (audit for false-positive noise)","unresolved":"unresolved retained work","role_bridge":"strict role-bridge work (retained or recovered)"}.get(str(row.get("source_group")),str(row.get("source_group")))
    noise=sorted(allowed_noise_flags())
    footer_v2=f"""Return exactly one JSON object with:
- decision: core_relevant, adjacent_relevant, role_bridge, out_of_scope, or uncertain
- roles: array chosen from acquisition_preparation, reconstruction_segmentation, synapse_inference, proofreading_qc, infrastructure, network_science, biological_application, structure_function_modeling, alternative_modality, health_translation, training_outreach
- confidence: 0 to 1
- evidence: concise phrase/sentence grounded only in title/abstract
- reason: concise explanation
- noise_flags: array drawn from {", ".join(noise)}

If plausible relevance exists but the abstract is ambiguous, choose uncertain rather than out_of_scope."""
    footer_v3=f"""Return exactly one JSON object with:
- decision: core_relevant, adjacent_relevant, role_bridge, out_of_scope, or uncertain
- roles: array chosen from acquisition_preparation, reconstruction_segmentation, synapse_inference, proofreading_qc, infrastructure, network_science, biological_application, structure_function_modeling, alternative_modality, health_translation, training_outreach
- confidence: 0 to 1 (use calibration in criteria)
- evidence: concise phrase/sentence grounded only in title/abstract
- reason: one sentence naming WHY this tier (especially core vs adjacent)
- noise_flags: array drawn from {", ".join(noise)}
- scale_relationship: one of nanoscale_only, multi_scale_bridging, macro_only, unclear
- core_gate: if decision is core_relevant, one of em_or_synaptic_reconstruction, connectomics_pipeline_tool, analysis_on_wiring_graph; else not_applicable

If core vs adjacent is unclear, choose adjacent_relevant or uncertain — NOT core_relevant.
If any connectomics-relevant phrase exists but modality/scale is unclear, prefer uncertain over out_of_scope."""
    footer=footer_v3 if ACTIVE_PROMPT=="v3" else footer_v2
    return f"""{CRITERIA}

CURRENT SOURCE GROUP: {group}
TITLE: {row.get('title') or ''}
ABSTRACT:
{row.get('abstract') or ''}

{footer}""".strip()

def validate(result:dict[str,Any])->dict[str,Any]:
    decision=str(result.get("decision",""))
    if decision not in ALLOWED_DECISIONS-{"insufficient_abstract"}:raise ValueError(f"invalid decision: {decision}")
    roles=result.get("roles",[])
    if not isinstance(roles,list) or any(str(x) not in ALLOWED_ROLES for x in roles):raise ValueError(f"invalid roles: {roles}")
    confidence=float(result.get("confidence",-1))
    if not 0<=confidence<=1:raise ValueError("invalid confidence")
    flags={str(x) for x in result.get("noise_flags",[])}
    bad=flags-allowed_noise_flags()
    if bad:raise ValueError(f"invalid noise_flags: {sorted(bad)}")
    out={"decision":decision,"roles":[str(x) for x in roles],"confidence":confidence,"evidence":str(result.get("evidence",""))[:600],"reason":str(result.get("reason",""))[:1200],"noise_flags":sorted(flags)}
    if ACTIVE_PROMPT=="v3":
        scale=str(result.get("scale_relationship",""))
        gate=str(result.get("core_gate",""))
        if scale not in ALLOWED_SCALE:raise ValueError(f"invalid scale_relationship: {scale}")
        if gate not in ALLOWED_CORE_GATE:raise ValueError(f"invalid core_gate: {gate}")
        if decision=="core_relevant" and gate=="not_applicable":raise ValueError("core_relevant requires a specific core_gate")
        if decision!="core_relevant" and gate!="not_applicable":raise ValueError(f"{decision} requires core_gate not_applicable")
        out["scale_relationship"]=scale
        out["core_gate"]=gate
    return out

def model_slug(model:str)->str:return re.sub(r"[^0-9a-z_-]+","_",str(model).lower()).strip("_") or "model"

def cache_key(work_id:str,prompt_sha:str,model:str,mode:str)->str:
    return stable_hash({"schema":CACHE_SCHEMA,"work_id":work_id,"prompt_sha256":prompt_sha,"prompt_version":PROMPT_VERSION,"run_mode":mode,"model":model})

def cache_path(cache_root:Path,work_id:str,prompt_sha:str,model:str,mode:str)->Path:
    return cache_root/mode/model_slug(model)/f"{cache_key(work_id,prompt_sha,model,mode)}.json"

def cache_read(path:Path)->dict[str,Any]|None:
    if not path.exists():return None
    try:payload=json.loads(path.read_text())
    except json.JSONDecodeError:return None
    result=payload.get("result") if isinstance(payload,dict) else None
    return result if isinstance(result,dict) and "decision" in result else None

def cache_write(path:Path,work_id:str,prompt_sha:str,model:str,mode:str,result:dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"key":{"schema":CACHE_SCHEMA,"work_id":work_id,"prompt_sha256":prompt_sha,"prompt_version":PROMPT_VERSION,"run_mode":mode,"model":model},"result":result},indent=2)+"\n")

def base_row(r:Any,model:str,run_mode:str,prompt_sha:str,batch_id:str)->dict[str,Any]:
    return {"work_id":r.work_id,"canonical_paper_id":r.get("canonical_paper_id",""),"source_group":r.source_group,"version_count":r.get("version_count",1),"member_paper_ids":r.get("member_paper_ids",""),"title":r.get("title",""),"model":model,"prompt_version":PROMPT_VERSION,"run_mode":run_mode,"prompt_sha256":prompt_sha,"adjudication_batch":batch_id}

def rel_kind(decision:str)->str:
    return "incl" if decision in INCLUSIVE_DECISIONS else "excl" if decision in EXCLUSIVE_DECISIONS else "defer"

def kappa(pairs:list[tuple[str,str]])->float|None:
    n=len(pairs)
    if not n:return None
    ca=Counter(a for a,_ in pairs); cb=Counter(b for _,b in pairs)
    po=sum(1 for a,b in pairs if a==b)/n; pe=sum((ca[c]/n)*(cb[c]/n) for c in set(ca)|set(cb))
    return None if abs(1.0-pe)<1e-12 else round((po-pe)/(1.0-pe),6)

def chunk_batches(work_ids:list[str],size:int,prefix:str)->list[tuple[str,list[str]]]:
    return [(f"{prefix}_{i//size:03d}",work_ids[i:i+size]) for i in range(0,len(work_ids),size)]

def overlap_sample(groups:dict[str,list[str]],fraction:float,seed:int)->list[str]:
    if fraction<=0:return []
    picked:list[str]=[]
    for g in sorted(groups):
        ids=sorted(groups[g])
        if not ids:continue
        n=min(max(1,int(round(len(ids)*fraction))),len(ids))
        picked+=random.Random(f"{seed}:{g}").sample(ids,n)
    return sorted(picked)

def export_prompts(out:Path,screen:pd.DataFrame,*,batch_size:int,fraction:float,replicates:int,seed:int,works_csv:Path,prepared:dict[str,Any])->dict[str,Any]:
    adj=out/"adjudication"; prompts=adj/"prompts"; prompts.mkdir(parents=True,exist_ok=True); (adj/"decisions").mkdir(parents=True,exist_ok=True)
    csha=criteria_sha256()
    (adj/"criteria.md").write_text(f"# IA-007 adjudication criteria\n\n- `prompt_version`: `{PROMPT_VERSION}`\n- `criteria_sha256`: `{csha}` (SHA-256 of SYSTEM + \"\\n\\n\" + CRITERIA)\n\n## SYSTEM\n\n{SYSTEM}\n\n## CRITERIA\n\n{CRITERIA}\n")
    header={"record":"criteria","prompt_version":PROMPT_VERSION,"criteria_sha256":csha,"system":SYSTEM,"criteria":CRITERIA}
    works:dict[str,dict[str,Any]]={}; order:list[str]=[]; skipped=[]
    for _,r in screen.iterrows():
        abstract=str(r.get("abstract") or "").strip()
        if not abstract or abstract.lower()=="nan":skipped.append(str(r.work_id)); continue
        prompt=build_prompt(r.to_dict()); wid=str(r.work_id); order.append(wid)
        vc=r.get("version_count",1)
        works[wid]={"record":"work","batch":"","work_id":wid,"canonical_paper_id":s(r.get("canonical_paper_id")),"source_group":s(r.source_group),"version_count":int(vc) if s(vc).strip() not in {"","nan"} else 1,"member_paper_ids":s(r.get("member_paper_ids")),"title":s(r.get("title")),"prompt_sha256":sha256_text(prompt),"prompt":prompt}
    home=chunk_batches(order,batch_size,"batch")
    groups=defaultdict(list)
    for wid in order:groups[works[wid]["source_group"]].append(wid)
    overlap=overlap_sample(dict(groups),fraction,seed)
    replicate_batches=[(f"overlap_r{i}",chunk_batches(overlap,batch_size,f"overlap_r{i}")) for i in range(1,replicates+1)] if overlap else []
    for stale in list(prompts.glob("batch_*.jsonl"))+list(prompts.glob("overlap_r*.jsonl")):stale.unlink()
    def write_batch(batch_id:str,ids:list[str])->None:
        lines=[json.dumps(header,ensure_ascii=False)]+[json.dumps({**works[w],"batch":batch_id},ensure_ascii=False) for w in ids]
        (prompts/f"{batch_id}.jsonl").write_text("\n".join(lines)+"\n")
    for batch_id,ids in home:write_batch(batch_id,ids)
    for _,batches in replicate_batches:
        for batch_id,ids in batches:write_batch(batch_id,ids)
    manifest={"generated_at":now_ts(),"prompt_version":PROMPT_VERSION,"criteria_sha256":csha,"works_csv":str(works_csv),"works_csv_sha256":sha256_file(works_csv),"batch_size":batch_size,"prepared_works":prepared["prepared_works"],"source_groups":prepared["source_groups"],"exported_prompts":len(order),"auto_insufficient_abstract":len(skipped),"exported_source_groups":{g:len(v) for g,v in sorted(groups.items())},"home_batches":{b:ids for b,ids in home},"overlap":{"fraction":fraction,"seed":seed,"replicates":replicates,"work_ids":overlap,"by_source_group":{g:sum(1 for w in overlap if works[w]["source_group"]==g) for g in sorted(groups)},"batches":{name:{b:ids for b,ids in batches} for name,batches in replicate_batches}},"works":{w:{"source_group":works[w]["source_group"],"prompt_sha256":works[w]["prompt_sha256"]} for w in order},"auto_insufficient_abstract_work_ids":skipped}
    home_ids=[w for _,ids in home for w in ids]
    if len(home_ids)!=len(set(home_ids)) or set(home_ids)!=set(order):raise RuntimeError("home batches do not partition the exported works")
    if len(order)+len(skipped)!=prepared["prepared_works"]:raise RuntimeError(f"exported {len(order)} + insufficient {len(skipped)} != prepared {prepared['prepared_works']}")
    (adj/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest

def load_manifest(out:Path)->dict[str,Any]:
    path=out/"adjudication"/"manifest.json"
    if not path.exists():raise SystemExit(f"{path} does not exist; run --export-prompts first")
    return json.loads(path.read_text())

def home_batch_map(manifest:dict[str,Any])->dict[str,str]:
    return {w:b for b,ids in manifest["home_batches"].items() for w in ids}

def read_decision_files(path:Path)->list[tuple[str,dict[str,Any]]]:
    if path.is_dir():files=sorted(path.glob("*.json"))
    elif path.exists():files=[path]
    else:raise SystemExit(f"--ingest-decisions path does not exist: {path}")
    out=[]
    for f in files:
        try:obj=json.loads(f.read_text())
        except json.JSONDecodeError as e:raise SystemExit(f"{f}: not valid JSON ({e})") from None
        if not isinstance(obj,dict):raise SystemExit(f"{f}: expected a JSON object")
        out.append((f.stem,obj))
    return out

def load_decisions(path:Path,manifest:dict[str,Any])->tuple[dict[str,dict[str,Any]],dict[str,dict[str,dict[str,Any]]],dict[str,Any]]:
    """Read adjudicator JSON into home decisions, per-replicate decisions, and file metadata.

    Every object goes through the unmodified `validate()`. Ingest-side checks that are
    deliberately not in `validate()` (IA-009): known `work_id`, prompt/criteria hash echoes,
    and a non-empty `evidence` on any `out_of_scope`.
    """
    known=manifest["works"]; csha=manifest["criteria_sha256"]
    home:dict[str,dict[str,Any]]={}; home_src:dict[str,str]={}; reps:dict[str,dict[str,dict[str,Any]]]=defaultdict(dict); meta=[]
    for stem,obj in read_decision_files(path):
        batch=str(obj.get("batch") or stem)
        rep=re.match(r"^overlap_(r\d+)_\d+$",batch)
        decisions=obj.get("decisions") if isinstance(obj.get("decisions"),dict) else obj
        if not isinstance(decisions,dict):raise SystemExit(f"{batch}: no decisions object")
        got=obj.get("criteria_sha256")
        if got and str(got)!=csha:raise SystemExit(f"{batch}: criteria_sha256 {got} does not match the export {csha}")
        got=obj.get("prompt_version")
        if got and str(got)!=PROMPT_VERSION:raise SystemExit(f"{batch}: prompt_version {got} does not match {PROMPT_VERSION}")
        n=0
        for wid,raw in decisions.items():
            wid=str(wid)
            if wid in {"batch","adjudicator","prompt_version","criteria_sha256"}:continue
            if wid not in known:raise SystemExit(f"{batch}: unknown work_id {wid}")
            if not isinstance(raw,dict):raise SystemExit(f"{batch}/{wid}: decision must be an object")
            got=raw.get("prompt_sha256")
            if got and str(got)!=known[wid]["prompt_sha256"]:raise SystemExit(f"{batch}/{wid}: prompt_sha256 does not match the export")
            try:result=validate(raw)
            except (ValueError,TypeError) as e:raise SystemExit(f"{batch}/{wid}: {e}") from None
            if result["decision"] in EXCLUSIVE_DECISIONS and not result["evidence"].strip():raise SystemExit(f"{batch}/{wid}: out_of_scope requires non-empty evidence")
            if rep:reps[rep.group(1)][wid]=result
            else:
                if wid in home and home[wid]!=result:raise SystemExit(f"{wid}: conflicting home decisions in {home_src[wid]} and {batch}")
                home[wid]=result; home_src[wid]=batch
            n+=1
        meta.append({"batch":batch,"file":stem,"replicate":rep.group(1) if rep else "","adjudicator":s(obj.get("adjudicator")),"decisions":n})
    return home,{k:dict(v) for k,v in reps.items()},{"files":meta,"home_decisions":len(home),"replicate_decisions":{k:len(v) for k,v in sorted(reps.items())}}

def sync_run_manifest(out:Path,fields:dict[str,Any],extra:dict[str,Any])->None:
    path=out/"run_manifest.json"
    if path.exists():
        prior=json.loads(path.read_text())
        clash={k:(prior.get(k),fields[k]) for k in MANIFEST_FIELDS if k in prior and prior.get(k)!=fields[k]}
        if clash:raise SystemExit(f"{path} disagrees with this run: {clash}; use a separate --out directory per run")
        extra={**{k:v for k,v in prior.items() if k not in fields and k not in extra},**extra}
    path.write_text(json.dumps({**fields,**extra},indent=2)+"\n")

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

def replicate_views(out:Path,results:pd.DataFrame,reps:dict[str,dict[str,dict[str,Any]]],model:str,batch_of:dict[str,str],prompt_sha:dict[str,str],args:Any)->tuple[dict[str,Any],set[str]]:
    """Write each replicate as its own comparison-tool-shaped results CSV.

    The home decision is the run of record; replicates are never merged into it. Works whose
    replicate flips relevant-versus-excluded are forced into the human queue.
    """
    home={str(r.work_id):r for r in results.itertuples()}; audit={}; conflicts:set[str]=set()
    for rep in sorted(reps):
        rows=[]
        for wid,result in sorted(reps[rep].items()):
            h=home.get(wid)
            if h is None:continue
            rows.append({"work_id":wid,"canonical_paper_id":h.canonical_paper_id,"source_group":h.source_group,"version_count":h.version_count,"member_paper_ids":h.member_paper_ids,"title":h.title,"model":model,"prompt_version":PROMPT_VERSION,"run_mode":"agent_offline","prompt_sha256":prompt_sha.get(wid,""),"adjudication_batch":batch_of.get(wid,""),**result})
        if not rows:continue
        view=annotate(pd.DataFrame(rows),args.confidence_review_threshold,args.exclusion_audit_fraction,args.seed)
        d=out/f"overlap_replicate_{rep}"; d.mkdir(parents=True,exist_ok=True); view.to_csv(d/"llm_relevance_results.csv",index=False)
        scored=[w for w in sorted(reps[rep]) if w in home]; pairs=[(home[w].decision,reps[rep][w]["decision"]) for w in scored]
        flips=[w for w in scored if {rel_kind(home[w].decision),rel_kind(reps[rep][w]["decision"])}=={"incl","excl"}]
        conflicts|=set(flips)
        by_group={}
        for g in SOURCE_GROUPS:
            ws=[w for w in sorted(reps[rep]) if w in home and home[w].source_group==g]
            if not ws:continue
            ag=sum(1 for w in ws if home[w].decision==reps[rep][w]["decision"])
            by_group[g]={"works":len(ws),"agreements":ag,"agreement_rate":round(ag/len(ws),6),"cohens_kappa":kappa([(home[w].decision,reps[rep][w]["decision"]) for w in ws])}
        agree=sum(1 for a,b in pairs if a==b)
        audit[rep]={"overlap_works":len(pairs),"agreements":agree,"agreement_rate":round(agree/len(pairs),6) if pairs else None,"cohens_kappa":kappa(pairs),"by_source_group":by_group,"relevant_vs_out_of_scope_conflicts":len(flips),"conflict_work_ids":flips,"results_csv":str((d/"llm_relevance_results.csv").relative_to(out))}
    return audit,conflicts

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--works-csv",required=True,type=Path); ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--prepare-only",action="store_true"); ap.add_argument("--limit",type=int,default=0)
    ap.add_argument("--confidence-review-threshold",type=float,default=0.85); ap.add_argument("--exclusion-audit-fraction",type=float,default=0.10); ap.add_argument("--seed",type=int,default=20260822)
    ap.add_argument("--prompt-version",default="v2",choices=["v2","v3"],help="IA-007 prompt profile (v3 = fair placement, strict core)")
    ap.add_argument("--export-prompts",action="store_true"); ap.add_argument("--batch-size",type=int,default=100)
    ap.add_argument("--overlap-fraction",type=float,default=0.03); ap.add_argument("--overlap-replicates",type=int,default=2); ap.add_argument("--overlap-seed",type=int,default=20260822)
    ap.add_argument("--ingest-decisions",type=Path,default=None); ap.add_argument("--adjudicator",default=""); ap.add_argument("--require-complete",action="store_true")
    args=ap.parse_args()
    set_prompt_version(args.prompt_version)
    offline=args.ingest_decisions is not None
    if args.export_prompts and offline:raise SystemExit("--export-prompts and --ingest-decisions are mutually exclusive")
    if args.prepare_only and (args.export_prompts or offline):raise SystemExit("--prepare-only cannot be combined with --export-prompts or --ingest-decisions")
    if args.adjudicator and not offline:raise SystemExit("--adjudicator is only valid with --ingest-decisions")
    if offline and not ADJUDICATOR_RE.match(args.adjudicator.strip()):raise SystemExit("--ingest-decisions requires --adjudicator matching agent:<vendor>/<model>[@<date>]")
    if args.batch_size<1:raise SystemExit("--batch-size must be >= 1")
    out=args.out.resolve(); out.mkdir(parents=True,exist_ok=True); cache=out/"cache"; cache.mkdir(exist_ok=True)
    df=pd.read_csv(args.works_csv,low_memory=False); df["work_id"]=df.work_id.astype(str)
    screen=df[df.source_group.isin(SOURCE_GROUPS)].sort_values("work_id").reset_index(drop=True)
    if args.limit:screen=screen.head(args.limit).copy()
    cols=[c for c in ["work_id","canonical_paper_id","source_group","version_count","member_paper_ids","title","abstract","doi","citation_count_work"] if c in screen.columns]
    screen[cols].to_json(out/"llm_screening_input.jsonl",orient="records",lines=True,force_ascii=False)
    prepared={"prepared_works":len(screen),"source_groups":screen.source_group.value_counts().to_dict(),"missing_abstracts":int(screen.abstract.fillna("").astype(str).str.strip().eq("").sum())}
    if args.prepare_only:(out/"llm_prepare_summary.json").write_text(json.dumps(prepared,indent=2)+"\n"); print(json.dumps(prepared,indent=2)); return
    if args.export_prompts:
        manifest=export_prompts(out,screen,batch_size=args.batch_size,fraction=args.overlap_fraction,replicates=args.overlap_replicates,seed=args.overlap_seed,works_csv=args.works_csv,prepared=prepared)
        print(json.dumps({k:manifest[k] for k in ("prepared_works","source_groups","exported_prompts","auto_insufficient_abstract","exported_source_groups","batch_size","criteria_sha256")}|{"home_batches":len(manifest["home_batches"]),"overlap_works":len(manifest["overlap"]["work_ids"]),"overlap_by_source_group":manifest["overlap"]["by_source_group"]},indent=2))
        return
    ingested:dict[str,dict[str,Any]]={}; reps:dict[str,dict[str,dict[str,Any]]]={}; ingest_meta:dict[str,Any]={}; batch_of:dict[str,str]={}; manifest:dict[str,Any]={}
    if offline:
        run_mode="agent_offline"; model=args.adjudicator.strip(); manifest=load_manifest(out)
        if manifest["criteria_sha256"]!=criteria_sha256():raise SystemExit("criteria text changed since export; re-export prompts and bump prompt_version if the change is intentional")
        batch_of=home_batch_map(manifest); ingested,reps,ingest_meta=load_decisions(args.ingest_decisions.resolve(),manifest)
        if args.require_complete:
            missing=[w for w in manifest["works"] if w not in ingested]
            if missing:raise SystemExit(f"--require-complete: {len(missing)} exported works have no home-batch decision (first: {missing[:5]})")
        api_base=api_key=""
    else:
        run_mode="api"; api_key=os.environ.get("LLM_API_KEY","").strip()
        if not api_key:raise RuntimeError("LLM_API_KEY required unless --prepare-only")
        api_base=os.environ.get("LLM_API_BASE","https://api.openai.com/v1").strip(); model=os.environ.get("LLM_MODEL","gpt-5.6").strip()
        if model.startswith("agent:"):raise SystemExit("API mode rejects an agent: model id; use --ingest-decisions for an offline agent run")
    sync_run_manifest(out,{"run_mode":run_mode,"model":model,"prompt_version":PROMPT_VERSION,"criteria_sha256":criteria_sha256(),"works_csv_sha256":sha256_file(args.works_csv)},{"works_csv":str(args.works_csv),"started_at":now_ts(),"adjudicator_date":time.strftime("%Y-%m-%d",time.gmtime()),"batch_size":args.batch_size,"limit":args.limit,"cache_schema":CACHE_SCHEMA})
    rows=[]; tally=Counter(); prompt_sha:dict[str,str]={}; undecided=[]; pf=(out/PROGRESS_FILE).open("a",encoding="utf-8")
    for idx,r in screen.iterrows():
        abstract=str(r.get("abstract") or "").strip(); wid=str(r.work_id); hit=False
        if not abstract or abstract.lower()=="nan":
            base=base_row(r,model,run_mode,"",""); result={"decision":"insufficient_abstract","roles":[],"confidence":0.0,"evidence":"","reason":"No abstract after best-effort rescue; do not exclude from title alone.","noise_flags":[]}
            if ACTIVE_PROMPT=="v3":result.update({"scale_relationship":"unclear","core_gate":"not_applicable"})
        else:
            prompt=build_prompt(r.to_dict()); psha=sha256_text(prompt); prompt_sha[wid]=psha; base=base_row(r,model,run_mode,psha,batch_of.get(wid,""))
            path=cache_path(cache,wid,psha,model,run_mode); cached=cache_read(path)
            if offline:
                result=ingested.get(wid) or cached
                if result is None:undecided.append(wid); continue
                hit=cached is not None and cached==result
                if not hit:cache_write(path,wid,psha,model,run_mode,result)
            elif cached is not None:result=cached; hit=True
            else:result=call_model(prompt,api_base=api_base,api_key=api_key,model=model); cache_write(path,wid,psha,model,run_mode,result)
        rows.append({**base,**result}); tally[result["decision"]]+=1; emit(pf,screen_record(len(rows),len(screen),base,result,hit))
        if len(rows)%DUMP_EVERY==0 or idx+1==len(screen):
            annotate(pd.DataFrame(rows),args.confidence_review_threshold,args.exclusion_audit_fraction,args.seed).to_csv(out/"llm_relevance_results.csv",index=False)
            print(f"screened {len(rows)}/{len(screen)} "+json.dumps(dict(sorted(tally.items()))),flush=True)
    pf.close()
    if not rows:raise SystemExit("no works were screened")
    results=annotate(pd.DataFrame(rows),args.confidence_review_threshold,args.exclusion_audit_fraction,args.seed)
    audit:dict[str,Any]={}; conflicts:set[str]=set()
    if offline and reps:
        audit,conflicts=replicate_views(out,results,reps,model,batch_of,prompt_sha,args)
        if conflicts:
            mask=results.work_id.astype(str).isin(conflicts); results.loc[mask,["human_review_priority","human_review_reason"]]=[True,"internal_replicate_conflict"]
    results.to_csv(out/"llm_relevance_results.csv",index=False); results[results.human_review_priority].to_csv(out/"human_review_queue.csv",index=False)
    summary={"prompt_version":PROMPT_VERSION,"model":model,"run_mode":run_mode,"adjudicator":model if offline else "","criteria_sha256":criteria_sha256(),"screened_works":len(results),"prepared_works":len(screen),"undecided_works":len(undecided),"source_groups":results.source_group.value_counts().to_dict(),"decision_counts":results.groupby(["source_group","decision"]).size().unstack(fill_value=0).to_dict(orient="index"),"missing_abstracts":int(results.decision.eq("insufficient_abstract").sum()),"human_review_queue":int(results.human_review_priority.sum()),"human_review_reasons":{k:int(v) for k,v in results[results.human_review_priority].human_review_reason.value_counts().items()},"exclusion_rate_by_source_group":{g:round(float(sub.decision.eq("out_of_scope").mean()),6) for g,sub in results.groupby("source_group")},"batch_count":len(manifest.get("home_batches",{})),"overlap_works":len(manifest.get("overlap",{}).get("work_ids",[])),"internal_replicate_conflicts":len(conflicts),"principle":"LLM first pass at canonical-work level; no source keep/core/bridge/work-link status is mutated."}
    (out/"llm_relevance_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    if offline:(out/"agent_adjudication_audit.json").write_text(json.dumps({"adjudicator":model,"prompt_version":PROMPT_VERSION,"criteria_sha256":criteria_sha256(),"ingest":ingest_meta,"undecided_works":undecided,"replicates":audit,"internal_replicate_conflict_work_ids":sorted(conflicts),"principle":"Home-batch decisions are the run of record; replicates measure internal consistency and are never averaged into a consensus label."},indent=2)+"\n")
    sync_run_manifest(out,{"run_mode":run_mode,"model":model,"prompt_version":PROMPT_VERSION,"criteria_sha256":criteria_sha256(),"works_csv_sha256":sha256_file(args.works_csv)},{"completed_at":now_ts(),"screened_works":len(results),"undecided_works":len(undecided)})
    if undecided:print(f"WARNING: {len(undecided)} works have no decision yet (partial run)",file=sys.stderr)
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
