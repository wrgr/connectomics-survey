#!/usr/bin/env python3
"""Deterministic checks for the IA-009 offline adjudication path in `analysis/llm_relevance_screen.py`.

Runs standalone (no test runner needed in CI):

    python analysis/test_llm_relevance_screen.py

Every fixture is synthetic and written to a fresh temp dir. Nothing under `postanalysis/`
is read or written, and no test opens a socket: the API path is exercised with a stubbed
`call_model` so the two execution paths can be compared on identical decisions.
"""
from __future__ import annotations
import contextlib, importlib.util, io, json, os, sys, tempfile
from pathlib import Path

import pandas as pd

HERE=Path(__file__).resolve().parent
SCRIPT=HERE/"llm_relevance_screen.py"

def load(name:str,path:Path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

L=load("llm_relevance_screen",SCRIPT)
ADJ="agent:cursor/claude-opus-5-thinking"

try:
    import pytest
    @pytest.fixture(name="td")
    def _td(tmp_path):return tmp_path
except ImportError:pass

WORKS=[
    ("work_a","core_audit","Dense EM reconstruction","Serial-section electron microscopy reconstruction of a cortical volume with synapse-level connectivity."),
    ("work_b","core_audit","Tractography of the human brain","Diffusion MRI tractography of long-range white matter pathways."),
    ("work_c","unresolved","Segmentation benchmark","Flood-filling network segmentation of volume electron microscopy image stacks."),
    ("work_d","unresolved","No abstract here",""),
    ("work_e","unresolved","Generic graph theory","Spectral properties of random graphs with no neuroscience application."),
    ("work_f","role_bridge","Proofreading crowdsourcing","A citizen-science platform for proofreading neuron reconstructions."),
    ("work_g","role_bridge","Another missing abstract",""),
    ("work_h","core_audit","Connectome-constrained model","A model of the fly visual system constrained by an EM connectome."),
]

def works_csv(root:Path)->Path:
    path=root/"canonical_works_enriched.csv"
    pd.DataFrame([{"work_id":w,"canonical_paper_id":"p_"+w,"source_group":g,"version_count":1,"member_paper_ids":"p_"+w,"title":t,"abstract":a,"doi":"","citation_count_work":0} for w,g,t,a in WORKS]).to_csv(path,index=False)
    return path

def run_main(argv:list[str])->None:
    old=sys.argv; sys.argv=["llm_relevance_screen",*argv]
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):L.main()
    finally:sys.argv=old

def expect_exit(argv:list[str],needle:str)->str:
    try:run_main(argv)
    except SystemExit as e:
        assert needle in str(e),f"expected {needle!r} in {e!r}"
        return str(e)
    raise AssertionError(f"expected SystemExit containing {needle!r}")

def export(root:Path,out:Path,*,extra:tuple[str,...]=())->dict:
    run_main(["--works-csv",str(works_csv(root)),"--out",str(out),"--export-prompts",*extra])
    return json.loads((out/"adjudication"/"manifest.json").read_text())

def batch_records(out:Path,batch:str)->list[dict]:
    return [json.loads(x) for x in (out/"adjudication"/"prompts"/f"{batch}.jsonl").read_text().splitlines() if x.strip()]

def decide(work_id:str,manifest:dict,*,decision="core_relevant",conf=0.9,evidence="EM reconstruction of a cortical volume",roles=("reconstruction_segmentation",),noise=(),echo_sha=True)->dict:
    out={"decision":decision,"roles":list(roles),"confidence":conf,"evidence":evidence,"reason":"synthetic fixture decision","noise_flags":list(noise)}
    if echo_sha:out["prompt_sha256"]=manifest["works"][work_id]["prompt_sha256"]
    return out

def write_decisions(out:Path,manifest:dict,batches:dict[str,dict],*,adjudicator:str=ADJ,criteria_sha:str|None=None)->Path:
    d=out/"adjudication"/"decisions"; d.mkdir(parents=True,exist_ok=True)
    for batch,decisions in batches.items():
        (d/f"{batch}.json").write_text(json.dumps({"batch":batch,"adjudicator":adjudicator,"prompt_version":L.PROMPT_VERSION,"criteria_sha256":criteria_sha if criteria_sha is not None else manifest["criteria_sha256"],"decisions":decisions},indent=2)+"\n")
    return d

def all_home_decisions(manifest:dict,**kw)->dict[str,dict]:
    return {b:{w:decide(w,manifest,**kw) for w in ids} for b,ids in manifest["home_batches"].items()}

def ingest(root:Path,out:Path,*,extra:tuple[str,...]=())->None:
    run_main(["--works-csv",str(works_csv(root)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator",ADJ,*extra])

def test_export_is_deterministic_and_work_id_ordered(td:Path):
    m1=export(td,td/"run1",extra=("--batch-size","3")); m2=export(td,td/"run2",extra=("--batch-size","3"))
    assert m1["exported_prompts"]==6 and m1["auto_insufficient_abstract"]==2
    assert m1["exported_prompts"]+m1["auto_insufficient_abstract"]==m1["prepared_works"]==8
    assert m1["auto_insufficient_abstract_work_ids"]==["work_d","work_g"]
    assert list(m1["home_batches"])==["batch_000","batch_001"]
    assert m1["home_batches"]["batch_000"]==["work_a","work_b","work_c"]
    assert m1["home_batches"]["batch_001"]==["work_e","work_f","work_h"]
    assert m1["exported_source_groups"]=={"core_audit":3,"role_bridge":1,"unresolved":2}
    # Re-exporting the same input reproduces every prompt file byte-for-byte.
    for p in sorted((td/"run1"/"adjudication"/"prompts").glob("*.jsonl")):
        assert p.read_bytes()==(td/"run2"/"adjudication"/"prompts"/p.name).read_bytes(),p.name
    assert (td/"run1"/"adjudication"/"criteria.md").read_bytes()==(td/"run2"/"adjudication"/"criteria.md").read_bytes()
    assert {k:v for k,v in m1.items() if k!="generated_at"}=={k:v for k,v in m2.items() if k!="generated_at"}

def test_every_batch_carries_the_verbatim_criteria_header(td:Path):
    m=export(td,td/"run",extra=("--batch-size","3"))
    for batch in list(m["home_batches"])+[b for r in m["overlap"]["batches"].values() for b in r]:
        recs=batch_records(td/"run",batch)
        head=recs[0]
        assert head=={"record":"criteria","prompt_version":L.PROMPT_VERSION,"criteria_sha256":m["criteria_sha256"],"system":L.SYSTEM,"criteria":L.CRITERIA}
        assert all(r["record"]=="work" and r["batch"]==batch for r in recs[1:])
    recs=batch_records(td/"run","batch_000")
    row=next(r for r in recs[1:] if r["work_id"]=="work_a")
    expected=L.build_prompt({"source_group":"core_audit","title":WORKS[0][2],"abstract":WORKS[0][3]})
    assert row["prompt"]==expected and row["prompt_sha256"]==L.sha256_text(expected)
    assert "work_d" not in {r.get("work_id") for r in recs}

def test_overlap_sample_is_seeded_and_stratified(td:Path):
    m=export(td,td/"run",extra=("--batch-size","3","--overlap-fraction","0.5","--overlap-replicates","2"))
    ov=m["overlap"]["work_ids"]
    assert ov==sorted(ov) and set(ov)<=set(m["works"])
    assert m["overlap"]["by_source_group"]=={"core_audit":2,"role_bridge":1,"unresolved":1}
    assert sorted(m["overlap"]["batches"])==["overlap_r1","overlap_r2"]
    r1=[w for ids in m["overlap"]["batches"]["overlap_r1"].values() for w in ids]
    r2=[w for ids in m["overlap"]["batches"]["overlap_r2"].values() for w in ids]
    assert r1==r2==ov
    again=export(td,td/"run2",extra=("--batch-size","3","--overlap-fraction","0.5","--overlap-replicates","2"))
    assert again["overlap"]["work_ids"]==ov

def test_validate_rejects_malformed_decisions():
    good={"decision":"core_relevant","roles":["infrastructure"],"confidence":0.5,"evidence":"e","reason":"r","noise_flags":[]}
    assert L.validate(good)["decision"]=="core_relevant"
    for bad,needle in [
        ({**good,"decision":"insufficient_abstract"},"invalid decision"),
        ({**good,"decision":"relevant"},"invalid decision"),
        ({**good,"decision":""},"invalid decision"),
        ({**good,"roles":["not_a_role"]},"invalid roles"),
        ({**good,"roles":"infrastructure"},"invalid roles"),
        ({**good,"confidence":1.5},"invalid confidence"),
        ({**good,"confidence":-0.1},"invalid confidence"),
    ]:
        try:L.validate(bad)
        except ValueError as e:assert needle in str(e),(bad,e)
        else:raise AssertionError(f"expected {needle} for {bad}")
    try:L.validate({**good,"confidence":"high"})
    except ValueError:pass
    else:raise AssertionError("expected non-numeric confidence to fail")
    # Truncation and coercion are part of the contract the offline path inherits unchanged.
    long=L.validate({**good,"evidence":"x"*900,"reason":"y"*2000,"noise_flags":["generic_machine_learning"]})
    assert len(long["evidence"])==600 and len(long["reason"])==1200 and long["noise_flags"]==["generic_machine_learning"]

def test_ingest_rejects_bad_batches(td:Path):
    out=td/"run"; m=export(td,out,extra=("--batch-size","3","--overlap-fraction","0"))
    base=all_home_decisions(m)
    def reset(mutate):
        d=out/"adjudication"/"decisions"
        if d.exists():
            for f in d.glob("*.json"):f.unlink()
        batches={b:{w:dict(v) for w,v in dec.items()} for b,dec in base.items()}
        mutate(batches); write_decisions(out,m,batches)
    def mut_unknown(b):b["batch_000"]["work_zzz"]=decide("work_a",m)
    reset(mut_unknown); expect_exit(["--works-csv",str(works_csv(td)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator",ADJ],"unknown work_id work_zzz")
    def mut_insufficient(b):b["batch_000"]["work_a"]["decision"]="insufficient_abstract"
    reset(mut_insufficient); expect_exit(["--works-csv",str(works_csv(td)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator",ADJ],"invalid decision: insufficient_abstract")
    def mut_empty_evidence(b):b["batch_000"]["work_b"].update(decision="out_of_scope",evidence="   ")
    reset(mut_empty_evidence); expect_exit(["--works-csv",str(works_csv(td)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator",ADJ],"out_of_scope requires non-empty evidence")
    def mut_prompt_sha(b):b["batch_000"]["work_a"]["prompt_sha256"]="0"*64
    reset(mut_prompt_sha); expect_exit(["--works-csv",str(works_csv(td)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator",ADJ],"prompt_sha256 does not match")
    def mut_role(b):b["batch_001"]["work_e"]["roles"]=["not_a_role"]
    reset(mut_role); expect_exit(["--works-csv",str(works_csv(td)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator",ADJ],"invalid roles")
    reset(lambda b:None); write_decisions(out,m,{},criteria_sha="deadbeef")
    (out/"adjudication"/"decisions"/"batch_000.json").write_text(json.dumps({"batch":"batch_000","criteria_sha256":"deadbeef","decisions":{}})+"\n")
    expect_exit(["--works-csv",str(works_csv(td)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator",ADJ],"criteria_sha256 deadbeef does not match")

def test_adjudicator_provenance_is_enforced(td:Path):
    out=td/"run"; m=export(td,out,extra=("--batch-size","3","--overlap-fraction","0")); write_decisions(out,m,all_home_decisions(m))
    dec=str(out/"adjudication"/"decisions"); csv=str(works_csv(td))
    for bad in ("","gpt-5.6","agent:cursor","claude-opus-5-thinking","agent:/model"):
        expect_exit(["--works-csv",csv,"--out",str(out),"--ingest-decisions",dec,*(["--adjudicator",bad] if bad else [])],"agent:<vendor>/<model>")
    expect_exit(["--works-csv",csv,"--out",str(out),"--adjudicator",ADJ],"--adjudicator is only valid with --ingest-decisions")
    expect_exit(["--works-csv",csv,"--out",str(out),"--export-prompts","--ingest-decisions",dec,"--adjudicator",ADJ],"mutually exclusive")
    expect_exit(["--works-csv",csv,"--out",str(out),"--prepare-only","--export-prompts"],"cannot be combined")
    assert L.ADJUDICATOR_RE.match(ADJ) and L.ADJUDICATOR_RE.match(ADJ+"@2026-08-22")
    os.environ["LLM_API_KEY"]="unused"; os.environ["LLM_MODEL"]="agent:cursor/claude-opus-5-thinking"
    try:expect_exit(["--works-csv",csv,"--out",str(td/"api")],"API mode rejects an agent: model id")
    finally:os.environ.pop("LLM_API_KEY",None); os.environ.pop("LLM_MODEL",None)

def test_cache_v1_and_v2_do_not_collide(td:Path):
    prompt=L.build_prompt({"source_group":"core_audit","title":"T","abstract":"A"}); psha=L.sha256_text(prompt)
    v1=L.stable_hash({"work_id":"work_a","prompt":prompt,"model":ADJ,"version":L.PROMPT_VERSION})
    v2=L.cache_key("work_a",psha,ADJ,"agent_offline")
    assert v1!=v2
    assert L.cache_key("work_a",psha,ADJ,"agent_offline")!=L.cache_key("work_a",psha,ADJ,"api")
    assert L.cache_key("work_a",psha,"gpt-5.6","api")!=L.cache_key("work_a",psha,ADJ,"api")
    root=td/"cache"
    assert L.cache_path(root,"work_a",psha,ADJ,"agent_offline")==root/"agent_offline"/"agent_cursor_claude-opus-5-thinking"/f"{v2}.json"
    assert L.model_slug("agent:cursor/claude-opus-5-thinking@2026-08-22")=="agent_cursor_claude-opus-5-thinking_2026-08-22"
    # A legacy v1 flat entry must never be read, migrated, or deleted by a v2 run.
    out=td/"run"; m=export(td,out,extra=("--batch-size","3","--overlap-fraction","0"))
    legacy_sha=m["works"]["work_a"]["prompt_sha256"]
    legacy_key=L.stable_hash({"work_id":"work_a","prompt":batch_records(out,"batch_000")[1]["prompt"],"model":ADJ,"version":L.PROMPT_VERSION})
    (out/"cache").mkdir(parents=True,exist_ok=True)
    legacy=out/"cache"/f"{legacy_key}.json"; legacy.write_text(json.dumps({"decision":"out_of_scope","roles":[],"confidence":1.0,"evidence":"stale v1 entry","reason":"stale","noise_flags":[]})+"\n")
    write_decisions(out,m,all_home_decisions(m)); ingest(td,out)
    results=pd.read_csv(out/"llm_relevance_results.csv")
    assert results.set_index("work_id").decision["work_a"]=="core_relevant"
    assert json.loads(legacy.read_text())["decision"]=="out_of_scope",'the v1 entry must be left untouched'
    v2path=out/"cache"/"agent_offline"/L.model_slug(ADJ)/f"{L.cache_key('work_a',legacy_sha,ADJ,'agent_offline')}.json"
    assert v2path.exists() and json.loads(v2path.read_text())["key"]["schema"]==L.CACHE_SCHEMA

def test_resume_from_partial_decisions(td:Path):
    out=td/"run"; m=export(td,out,extra=("--batch-size","3","--overlap-fraction","0"))
    home=all_home_decisions(m)
    write_decisions(out,m,{"batch_000":home["batch_000"]})
    ingest(td,out)
    partial=pd.read_csv(out/"llm_relevance_results.csv"); summary=json.loads((out/"llm_relevance_summary.json").read_text())
    assert set(partial.work_id)=={"work_a","work_b","work_c","work_d","work_g"}
    assert summary["undecided_works"]==3 and summary["screened_works"]==5
    expect_exit(["--works-csv",str(works_csv(td)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator",ADJ,"--require-complete"],"have no home-batch decision")
    write_decisions(out,m,home); ingest(td,out,extra=("--require-complete",))
    full=pd.read_csv(out/"llm_relevance_results.csv")
    assert len(full)==8 and set(full.work_id)=={w for w,_,_,_ in WORKS}
    assert json.loads((out/"llm_relevance_summary.json").read_text())["undecided_works"]==0
    prog=[json.loads(x) for x in (out/L.PROGRESS_FILE).read_text().splitlines() if x.strip()]
    tail=prog[-8:]
    assert [r["index"] for r in tail]==list(range(1,9)) and {r["total"] for r in tail}=={8}
    # The second pass re-reads the namespaced cache rather than treating ingest as fresh work.
    assert sum(1 for r in tail if r["cache_hit"]) >= 3
    # A conflicting home decision for the same work is a hard error, not a silent last-writer-wins.
    (out/"adjudication"/"decisions"/"batch_000_retry.json").write_text(json.dumps({"batch":"batch_000_retry","decisions":{"work_a":decide("work_a",m,decision="uncertain",evidence="",roles=())}})+"\n")
    expect_exit(["--works-csv",str(works_csv(td)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator",ADJ],"conflicting home decisions")

def test_ingested_run_matches_the_api_path_schema(td:Path):
    fixed={"decision":"core_relevant","roles":["reconstruction_segmentation"],"confidence":0.9,"evidence":"EM reconstruction of a cortical volume","reason":"synthetic fixture decision","noise_flags":[]}
    api=td/"api"; original=L.call_model
    L.call_model=lambda prompt,**kw:dict(fixed)
    os.environ["LLM_API_KEY"]="stub"; os.environ["LLM_MODEL"]="gpt-5.6"
    try:run_main(["--works-csv",str(works_csv(td)),"--out",str(api)])
    finally:
        L.call_model=original; os.environ.pop("LLM_API_KEY",None); os.environ.pop("LLM_MODEL",None)
    off=td/"agent"; m=export(td,off,extra=("--batch-size","3","--overlap-fraction","0"))
    write_decisions(off,m,all_home_decisions(m)); ingest(td,off,extra=("--require-complete",))
    a=pd.read_csv(api/"llm_relevance_results.csv"); b=pd.read_csv(off/"llm_relevance_results.csv")
    assert list(a.columns)==list(b.columns)
    assert "run_mode" in a.columns and "prompt_sha256" in a.columns and "adjudication_batch" in a.columns
    assert set(a.run_mode)=={"api"} and set(b.run_mode)=={"agent_offline"}
    assert set(a.model)=={"gpt-5.6"} and set(b.model)=={ADJ}
    assert a.adjudication_batch.fillna("").eq("").all() and set(b.adjudication_batch.dropna())=={"batch_000","batch_001"}
    prov=["model","run_mode","adjudication_batch"]
    assert a.drop(columns=prov).to_csv(index=False).encode()==b.drop(columns=prov).to_csv(index=False).encode()
    assert list(a.prompt_sha256.fillna(""))==list(b.prompt_sha256.fillna(""))
    for run in (api,off):
        man=json.loads((run/"run_manifest.json").read_text())
        assert man["prompt_version"]==L.PROMPT_VERSION and man["criteria_sha256"]==L.criteria_sha256()
        assert set(L.MANIFEST_FIELDS)<=set(man) and man["cache_schema"]==L.CACHE_SCHEMA
    qa=pd.read_csv(api/"human_review_queue.csv"); qb=pd.read_csv(off/"human_review_queue.csv")
    assert set(qa.work_id)==set(qb.work_id) and {"work_d","work_g"}<=set(qb.work_id)

def test_replicate_conflict_forces_human_review(td:Path):
    out=td/"run"; m=export(td,out,extra=("--batch-size","3","--overlap-fraction","0.5","--overlap-replicates","2"))
    ov=m["overlap"]["work_ids"]; flip=ov[0]
    batches=all_home_decisions(m)
    for rep in ("overlap_r1","overlap_r2"):
        for batch,ids in m["overlap"]["batches"][rep].items():
            batches[batch]={w:decide(w,m,decision="out_of_scope",evidence="no nanoscale connectomics content in the abstract",roles=()) if (w==flip and rep=="overlap_r1") else decide(w,m) for w in ids}
    write_decisions(out,m,batches); ingest(td,out,extra=("--require-complete",))
    results=pd.read_csv(out/"llm_relevance_results.csv").set_index("work_id")
    assert results.decision[flip]=="core_relevant",'the home decision stays the run of record'
    assert bool(results.human_review_priority[flip]) and results.human_review_reason[flip]=="internal_replicate_conflict"
    audit=json.loads((out/"agent_adjudication_audit.json").read_text())
    assert sorted(audit["replicates"])==["r1","r2"]
    assert audit["replicates"]["r1"]["relevant_vs_out_of_scope_conflicts"]==1
    assert audit["replicates"]["r1"]["conflict_work_ids"]==[flip]
    assert audit["replicates"]["r2"]["relevant_vs_out_of_scope_conflicts"]==0
    assert audit["replicates"]["r2"]["agreement_rate"]==1.0
    assert audit["replicates"]["r1"]["overlap_works"]==len(ov)
    assert audit["internal_replicate_conflict_work_ids"]==[flip]
    rep=pd.read_csv(out/"overlap_replicate_r1"/"llm_relevance_results.csv")
    assert set(rep.work_id)==set(ov) and set(rep.run_mode)=={"agent_offline"}
    queue=pd.read_csv(out/"human_review_queue.csv")
    assert flip in set(queue.work_id)

def test_run_manifest_refuses_a_conflicting_run(td:Path):
    out=td/"run"; m=export(td,out,extra=("--batch-size","3","--overlap-fraction","0"))
    write_decisions(out,m,all_home_decisions(m)); ingest(td,out,extra=("--require-complete",))
    expect_exit(["--works-csv",str(works_csv(td)),"--out",str(out),"--ingest-decisions",str(out/"adjudication"/"decisions"),"--adjudicator","agent:other/model"],"disagrees with this run")
    man=json.loads((out/"run_manifest.json").read_text())
    assert man["model"]==ADJ and man["run_mode"]=="agent_offline" and man["screened_works"]==8
    assert man["works_csv_sha256"]==L.sha256_file(works_csv(td)) and "completed_at" in man and "started_at" in man

def test_offline_mode_needs_no_api_key(td:Path):
    out=td/"run"; m=export(td,out,extra=("--batch-size","3","--overlap-fraction","0")); write_decisions(out,m,all_home_decisions(m))
    os.environ.pop("LLM_API_KEY",None)
    ingest(td,out,extra=("--require-complete",))
    summary=json.loads((out/"llm_relevance_summary.json").read_text())
    assert summary["run_mode"]=="agent_offline" and summary["adjudicator"]==ADJ
    assert summary["screened_works"]==8 and summary["missing_abstracts"]==2
    assert summary["criteria_sha256"]==L.criteria_sha256() and summary["batch_count"]==2
    assert summary["source_groups"]=={"core_audit":3,"unresolved":3,"role_bridge":2}

def test_helpers():
    assert L.rel_kind("core_relevant")=="incl" and L.rel_kind("out_of_scope")=="excl" and L.rel_kind("uncertain")=="defer"
    assert L.rel_kind("insufficient_abstract")=="defer" and L.rel_kind("role_bridge")=="incl"
    assert L.kappa([("a","a"),("a","b"),("b","a"),("b","b")])==0.0
    assert L.kappa([])is None and L.kappa([("a","a")]*3)is None
    assert L.chunk_batches(["w1","w2","w3"],2,"batch")==[("batch_000",["w1","w2"]),("batch_001",["w3"])]
    assert L.chunk_batches([],2,"batch")==[]
    assert L.overlap_sample({"g":["a","b","c","d"]},0.0,1)==[]
    assert len(L.overlap_sample({"g":["a","b","c","d"]},0.01,1))==1
    assert L.overlap_sample({"g":list("abcd")},0.5,7)==L.overlap_sample({"g":list("dcba")},0.5,7)
    assert L.criteria_sha256()==L.sha256_text(L.SYSTEM+"\n\n"+L.CRITERIA)

def main():
    tests=[(n,f) for n,f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name,fn in tests:
        if fn.__code__.co_argcount>0:
            with tempfile.TemporaryDirectory() as td:fn(Path(td))
        else:fn()
        print(f"ok  {name}",flush=True)
    print(f"\n{len(tests)} llm_relevance_screen checks passed")

if __name__=="__main__":main()
