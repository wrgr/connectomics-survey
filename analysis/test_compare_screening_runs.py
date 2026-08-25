#!/usr/bin/env python3
"""Deterministic checks for `analysis/compare_screening_runs.py`.

Runs standalone (`python analysis/compare_screening_runs.py` needs no test runner in CI):

    python analysis/test_compare_screening_runs.py

Every fixture is synthetic and written to a fresh temp dir. Nothing under `postanalysis/`
is read or written.
"""
from __future__ import annotations
import csv, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
SCRIPT=HERE/"compare_screening_runs.py"
COLS=["work_id","canonical_paper_id","source_group","version_count","member_paper_ids","title","model","prompt_version","decision","roles","confidence","evidence","reason","noise_flags","human_review_priority","human_review_reason"]

def load(name:str,path:Path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

C=load("compare_screening_runs",SCRIPT)

try:
    import pytest
    @pytest.fixture(name="td")
    def _td(tmp_path):return tmp_path
except ImportError:pass

def rec(wid,decision,*,group="unresolved",conf=0.9,roles=(),noise=(),title=None,model="m",review=False,reason="r",evidence="e",roles_raw=None,noise_raw=None):
    return {"work_id":wid,"canonical_paper_id":"P"+wid,"source_group":group,"version_count":1,"member_paper_ids":"P"+wid,"title":title if title is not None else "Title "+wid,"model":model,"prompt_version":"IA-007-v2-work-level","decision":decision,"roles":roles_raw if roles_raw is not None else str(list(roles)),"confidence":conf,"evidence":evidence,"reason":reason,"noise_flags":noise_raw if noise_raw is not None else str(list(noise)),"human_review_priority":review,"human_review_reason":"low_confidence" if review else ""}

def write_run(path:Path,rows:list[dict],cols:list[str]|None=None)->Path:
    fields=cols or COLS
    with path.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader()
        for r in rows:w.writerow({c:r.get(c,"") for c in fields})
    return path

def run_compare(td:Path,rows_a,rows_b,*,la="agent",lb="api",cols_a=None,cols_b=None,extra=()):
    a=write_run(td/"a.csv",rows_a,cols_a); b=write_run(td/"b.csv",rows_b,cols_b); out=td/"cmp"
    proc=subprocess.run([sys.executable,str(SCRIPT),"--run-a",str(a),"--run-b",str(b),"--label-a",la,"--label-b",lb,"--out",str(out),*extra],capture_output=True,text=True)
    assert proc.returncode==0,f"comparison failed:\n{proc.stdout}\n{proc.stderr}"
    summary=json.loads((out/"screening_comparison_summary.json").read_text())
    with (out/"screening_decision_disagreements.csv").open(encoding="utf-8") as fh:dis=list(csv.DictReader(fh))
    report=(out/"screening_comparison_report.md").read_text()
    return summary,dis,report,out,a,b

def test_kappa_hand_computed():
    # A=[c,c,c,o] B=[c,c,o,o]: po=3/4, pe=(3/4)(2/4)+(1/4)(2/4)=1/2, kappa=(0.75-0.5)/0.5=0.5
    pairs=[("core_relevant","core_relevant"),("core_relevant","core_relevant"),("core_relevant","out_of_scope"),("out_of_scope","out_of_scope")]
    assert C.kappa(pairs)==0.5
    # balanced 2x2 with zero observed agreement is the kappa=-1 floor
    assert C.kappa([("core_relevant","out_of_scope"),("core_relevant","out_of_scope"),("out_of_scope","core_relevant"),("out_of_scope","core_relevant")])==-1.0
    # chance-level agreement
    assert C.kappa([("core_relevant","core_relevant"),("core_relevant","out_of_scope"),("out_of_scope","core_relevant"),("out_of_scope","out_of_scope")])==0.0
    assert C.kappa([])is None
    # single category on both sides leaves kappa undefined rather than 1.0
    assert C.kappa([("core_relevant","core_relevant")]*3)is None

def test_kappa_matches_hand_computation_end_to_end(td:Path):
    a=[rec("W1","core_relevant"),rec("W2","core_relevant"),rec("W3","core_relevant"),rec("W4","out_of_scope")]
    b=[rec("W1","core_relevant"),rec("W2","core_relevant"),rec("W3","out_of_scope"),rec("W4","out_of_scope")]
    summary,dis,_,_,_,_=run_compare(td,a,b)
    assert summary["agreement"]["agreement_rate"]==0.75
    assert summary["agreement"]["cohens_kappa"]==0.5
    assert len(dis)==1 and dis[0]["work_id"]=="W3"

def test_perfect_agreement(td:Path):
    rows=[rec("W1","core_relevant",group="core_audit",roles=["reconstruction_segmentation"],conf=0.95),
          rec("W2","adjacent_relevant",roles=["network_science"],noise=["generic_network_neuroscience"],conf=0.7),
          rec("W3","out_of_scope",conf=0.9,noise=["diffusion_mri_or_tractography"]),
          rec("W4","role_bridge",group="role_bridge",roles=["training_outreach"],conf=0.8,review=True),
          rec("W5","uncertain",conf=0.4,review=True)]
    summary,dis,report,_,_,_=run_compare(td,rows,[dict(r) for r in rows])
    ag=summary["agreement"]
    assert ag["scored_works"]==5 and ag["agreements"]==5 and ag["agreement_rate"]==1.0 and ag["cohens_kappa"]==1.0
    assert dis==[] and summary["disagreement_rows_written"]==0
    assert summary["sensitivity"]["high_stakes_exclusion_conflicts"]==0
    assert summary["sensitivity"]["exclusion_vs_deferral"]==0 and summary["sensitivity"]["benign_deferral_churn"]==0
    assert summary["roles"]["mean_jaccard"]==1.0 and summary["roles"]["exact_set_match_rate"]==1.0
    assert summary["noise_flags"]["mean_jaccard"]==1.0
    assert summary["human_review"]["jaccard"]==1.0 and summary["human_review"]["flag_agreement_rate"]==1.0
    assert summary["coverage"]["only_in_agent"]==0 and summary["coverage"]["only_in_api"]==0
    assert "None: the two runs agree on every jointly covered work." in report
    for g in ("core_audit","unresolved","role_bridge"):assert ag["by_source_group"][g]["agreement_rate"]==1.0

def test_total_disagreement(td:Path):
    a=[rec("W1","core_relevant"),rec("W2","core_relevant"),rec("W3","out_of_scope"),rec("W4","out_of_scope")]
    b=[rec("W1","out_of_scope"),rec("W2","out_of_scope"),rec("W3","core_relevant"),rec("W4","core_relevant")]
    summary,dis,_,_,_,_=run_compare(td,a,b)
    assert summary["agreement"]["agreements"]==0 and summary["agreement"]["agreement_rate"]==0.0
    assert summary["agreement"]["cohens_kappa"]==-1.0
    assert len(dis)==4 and {r["stake"] for r in dis}=={"inclusive_vs_out_of_scope"}
    assert summary["sensitivity"]["high_stakes_exclusion_conflicts"]==4
    assert summary["sensitivity"]["agent"]["would_exclude"]==2 and summary["sensitivity"]["agent"]["excluded_here_but_included_by_api"]==2
    assert summary["sensitivity"]["api"]["excluded_here_but_included_by_agent"]==2
    assert summary["sensitivity"]["both_exclude"]==0
    assert summary["roles"]["mean_jaccard"]==1.0

def test_partial_coverage_scores_only_the_intersection(td:Path):
    a=[rec("W1","core_relevant"),rec("W2","out_of_scope"),rec("W3","uncertain",conf=0.3)]
    b=[rec("W2","out_of_scope"),rec("W3","uncertain",conf=0.3),rec("W9","core_relevant"),rec("W8","adjacent_relevant")]
    summary,dis,report,out,_,_=run_compare(td,a,b,extra=("--expected-works","4"))
    cov=summary["coverage"]
    assert cov["works_agent"]==3 and cov["works_api"]==4
    assert cov["in_both"]==2 and cov["only_in_agent"]==1 and cov["only_in_api"]==2 and cov["union"]==5
    assert cov["coverage_jaccard"]==0.4
    assert cov["expected_works"]==4 and cov["complete_agent"]is False and cov["complete_api"]is True
    assert summary["agreement"]["scored_works"]==2 and summary["agreement"]["agreement_rate"]==1.0
    assert dis==[]
    assert (out/"screening_coverage_only_agent.txt").read_text().split()==["W1"]
    assert (out/"screening_coverage_only_api.txt").read_text().split()==["W8","W9"]
    assert "only in `api`: 2" in report

def test_high_stakes_exclusions_are_identified_and_ranked_first(td:Path):
    a=[rec("H1","out_of_scope",conf=0.99),                      # tier 5, most confident
       rec("H2","core_relevant",conf=0.60),                     # tier 5, less confident
       rec("E1","out_of_scope",conf=0.95),                      # tier 4
       rec("D1","core_relevant",conf=0.90),                     # tier 3 benign churn
       rec("S1","core_relevant",conf=0.90),                     # tier 2 class swap
       rec("U1","uncertain",conf=0.20),                         # tier 1
       rec("A1","out_of_scope",conf=0.90)]                      # agreed exclusion
    b=[rec("H1","adjacent_relevant",conf=0.70),
       rec("H2","out_of_scope",conf=0.55),
       rec("E1","uncertain",conf=0.30),
       rec("D1","uncertain",conf=0.40),
       rec("S1","adjacent_relevant",conf=0.80),
       rec("U1","insufficient_abstract",conf=0.0),
       rec("A1","out_of_scope",conf=0.85)]
    summary,dis,report,_,_,_=run_compare(td,a,b)
    s=summary["sensitivity"]
    assert s["high_stakes_exclusion_conflicts"]==2
    assert s["exclusion_vs_deferral"]==1 and s["benign_deferral_churn"]==1 and s["inclusive_class_swaps"]==1 and s["other_swaps"]==1
    assert s["both_exclude"]==1
    assert s["agent"]["would_exclude"]==3 and s["agent"]["excluded_here_but_included_by_api"]==1
    assert s["agent"]["conflict_by_other_decision"]=={"adjacent_relevant":1}
    assert s["agent"]["excluded_here_but_deferred_by_api"]==1
    assert s["api"]["would_exclude"]==2 and s["api"]["excluded_here_but_included_by_agent"]==1
    assert s["recall_relevant_union"]==4 and s["recall_relevant_intersection"]==1
    assert [r["work_id"] for r in dis]==["H1","H2","E1","D1","S1","U1"]
    assert [int(r["stake_tier"]) for r in dis]==[5,5,4,3,2,1]
    assert dis[0]["decision_agent"]=="out_of_scope" and dis[0]["decision_api"]=="adjacent_relevant"
    assert dis[0]["confidence_agent"]=="0.99" and dis[0]["confidence_api"]=="0.7"
    assert dis[0]["reason_agent"]=="r" and dis[0]["reason_api"]=="r"
    assert dis[0]["title"]=="Title H1" and dis[0]["source_group"]=="unresolved"
    assert "high-stakes exclusion conflicts (one run excludes, other calls relevant): 2" in report

def test_per_source_group_agreement_and_kappa(td:Path):
    a=[rec("C1","core_relevant",group="core_audit"),rec("C2","core_relevant",group="core_audit"),
       rec("C3","core_relevant",group="core_audit"),rec("C4","out_of_scope",group="core_audit"),
       rec("U1","core_relevant"),rec("U2","out_of_scope"),
       rec("B1","role_bridge",group="role_bridge")]
    b=[rec("C1","core_relevant",group="core_audit"),rec("C2","core_relevant",group="core_audit"),
       rec("C3","out_of_scope",group="core_audit"),rec("C4","out_of_scope",group="core_audit"),
       rec("U1","out_of_scope"),rec("U2","core_relevant"),
       rec("B1","role_bridge",group="role_bridge")]
    summary,_,_,_,_,_=run_compare(td,a,b)
    g=summary["agreement"]["by_source_group"]
    assert g["core_audit"]["works"]==4 and g["core_audit"]["agreement_rate"]==0.75 and g["core_audit"]["cohens_kappa"]==0.5
    assert g["unresolved"]["works"]==2 and g["unresolved"]["agreement_rate"]==0.0 and g["unresolved"]["cohens_kappa"]==-1.0
    assert g["role_bridge"]["works"]==1 and g["role_bridge"]["cohens_kappa"]is None
    assert summary["agreement"]["source_group_mismatches"]==0

def test_source_group_mismatch_is_reported(td:Path):
    a=[rec("W1","core_relevant",group="core_audit"),rec("W2","core_relevant",group="unresolved")]
    b=[rec("W1","core_relevant",group="unresolved"),rec("W2","core_relevant",group="unresolved")]
    summary,_,_,_,_,_=run_compare(td,a,b)
    assert summary["agreement"]["source_group_mismatches"]==1
    assert summary["agreement"]["source_group_mismatch_work_ids"]==["W1"]

def test_confusion_matrix_is_complete(td:Path):
    a=[rec("W1","core_relevant"),rec("W2","core_relevant"),rec("W3","out_of_scope"),rec("W4","uncertain")]
    b=[rec("W1","core_relevant"),rec("W2","out_of_scope"),rec("W3","out_of_scope"),rec("W4","core_relevant")]
    summary,_,_,_,_,_=run_compare(td,a,b)
    m=summary["confusion_matrix"]
    assert sorted(m)==sorted({"core_relevant","out_of_scope","uncertain"})
    assert all(sorted(row)==sorted(m) for row in m.values())
    assert sum(v for row in m.values() for v in row.values())==4
    assert m["core_relevant"]["core_relevant"]==1 and m["core_relevant"]["out_of_scope"]==1
    assert m["out_of_scope"]["out_of_scope"]==1 and m["uncertain"]["core_relevant"]==1

def test_stringified_and_delimited_label_sets_parse_equivalently(td:Path):
    a=[rec("W1","core_relevant",roles_raw="['synapse_inference', 'infrastructure']",noise_raw="['generic_machine_learning']"),
       rec("W2","core_relevant",roles_raw="[]",noise_raw=""),
       rec("W3","adjacent_relevant",roles_raw='["network_science"]',noise_raw="nan")]
    b=[rec("W1","core_relevant",roles_raw="infrastructure;synapse_inference",noise_raw="generic_machine_learning"),
       rec("W2","core_relevant",roles_raw="",noise_raw="[]"),
       rec("W3","adjacent_relevant",roles_raw="network_science, biological_application",noise_raw="")]
    summary,_,_,_,_,_=run_compare(td,a,b)
    assert summary["roles"]["exact_set_match_rate"]==round(2/3,6)
    assert summary["roles"]["mean_jaccard"]==round((1.0+1.0+0.5)/3,6)
    assert summary["roles"]["both_empty"]==1
    assert summary["roles"]["per_label"]["synapse_inference"]=={"agent":1,"api":1,"both":1,"jaccard":1.0}
    assert summary["roles"]["per_label"]["biological_application"]["agent"]==0
    assert summary["noise_flags"]["mean_jaccard"]==1.0
    assert C.parse_set("['a', 'b']")==C.parse_set("a;b")==C.parse_set("b, a")==frozenset({"a","b"})
    assert C.parse_set("")==C.parse_set("nan")==C.parse_set("[]")==frozenset()

def test_missing_optional_columns_are_tolerated(td:Path):
    lean=["work_id","decision"]
    a=[rec("W1","core_relevant",conf=0.4),rec("W2","out_of_scope",conf=0.95),rec("W3","uncertain",conf=0.5)]
    b=[{"work_id":"W1","decision":"core_relevant"},{"work_id":"W2","decision":"adjacent_relevant"},{"work_id":"W3","decision":"uncertain"}]
    summary,dis,_,_,_,_=run_compare(td,a,b,cols_b=lean)
    assert summary["runs"]["api"]["missing_optional_columns"]==[c for c in C.OPT_COLS]
    assert summary["runs"]["agent"]["missing_optional_columns"]==[]
    assert summary["agreement"]["agreement_rate"]==round(2/3,6)
    assert summary["sensitivity"]["high_stakes_exclusion_conflicts"]==1
    assert summary["confidence"]["api"]["overall"]["n"]==0 and summary["confidence"]["api"]["overall"]["mean"]is None
    assert summary["confidence"]["agent"]["overall"]["n"]==3
    assert summary["human_review"]["source_api"]=="unavailable" and summary["human_review"]["flagged_api"]==0
    assert summary["agreement"]["by_source_group"]["unresolved"]["works"]==3
    assert dis[0]["work_id"]=="W2" and dis[0]["confidence_api"]==""
    # with neither run carrying source_group, everything falls back to a single bucket
    lean_both,_,_,_,_,_=run_compare(td,a,b,cols_a=lean,cols_b=lean)
    assert lean_both["agreement"]["by_source_group"]["unknown"]["works"]==3

def test_confidence_calibration_and_low_confidence_concentration(td:Path):
    a=[rec("W1","core_relevant",conf=0.95),rec("W2","core_relevant",conf=0.99),rec("W3","out_of_scope",conf=0.30),rec("W4","out_of_scope",conf=0.50)]
    b=[rec("W1","core_relevant",conf=0.90),rec("W2","core_relevant",conf=0.98),rec("W3","core_relevant",conf=0.40),rec("W4","uncertain",conf=0.60)]
    summary,_,_,_,_,_=run_compare(td,a,b,extra=("--low-confidence-threshold","0.85"))
    c=summary["confidence"]
    assert c["agent"]["by_decision"]["core_relevant"]=={"n":2,"mean":0.97,"median":0.97}
    assert c["agent"]["by_decision"]["out_of_scope"]=={"n":2,"mean":0.4,"median":0.4}
    assert c["agreeing_works"]["agent"]["mean"]==0.97 and c["disagreeing_works"]["agent"]["mean"]==0.4
    assert c["low_confidence_threshold"]==0.85
    assert c["disagreements_below_threshold"]==2 and c["share_of_disagreements_below_threshold"]==1.0
    assert c["min_confidence_below_threshold"]==2 and c["share_of_works_below_threshold"]==0.5
    assert c["disagreements_concentrate_at_low_confidence"]is True
    bins=c["disagreement_rate_by_min_confidence_bin"]
    assert bins["0.00-0.50"]=={"works":1,"disagreements":1,"disagreement_rate":1.0}
    assert bins["0.50-0.70"]=={"works":1,"disagreements":1,"disagreement_rate":1.0}
    assert bins["0.85-0.95"]["works"]==1 and bins["0.85-0.95"]["disagreement_rate"]==0.0
    assert bins["0.95-1.00"]["works"]==1 and bins["0.95-1.00"]["disagreements"]==0

def test_human_review_queue_overlap_from_column_and_from_queue_csv(td:Path):
    a=[rec("W1","uncertain",conf=0.3,review=True),rec("W2","out_of_scope",conf=0.5,review=True),rec("W3","core_relevant",conf=0.95),rec("W4","core_relevant",conf=0.95)]
    b=[rec("W1","uncertain",conf=0.3,review=True),rec("W2","out_of_scope",conf=0.95),rec("W3","uncertain",conf=0.4,review=True),rec("W4","core_relevant",conf=0.95)]
    summary,_,_,_,_,_=run_compare(td,a,b)
    q=summary["human_review"]
    assert q["source_agent"]=="results_column" and q["source_api"]=="results_column"
    assert q["flagged_agent"]==2 and q["flagged_api"]==2
    assert q["flagged_in_both_runs"]==1 and q["only_agent"]==1 and q["only_api"]==1
    assert q["jaccard"]==round(1/3,6) and q["flag_agreement_rate"]==0.5 and q["flagged_by_either"]==3

    with tempfile.TemporaryDirectory() as raw:
        qtd=Path(raw)
        qa=write_run(qtd/"qa.csv",[r for r in a if r["human_review_priority"]])
        qb=write_run(qtd/"qb.csv",[r for r in b if r["human_review_priority"]]+[rec("W4","core_relevant",review=True)])
        summary2,_,_,_,_,_=run_compare(qtd,a,b,extra=("--queue-a",str(qa),"--queue-b",str(qb)))
        q2=summary2["human_review"]
        assert q2["source_agent"]=="queue_csv" and q2["source_api"]=="queue_csv"
        assert q2["flagged_api"]==3 and q2["flagged_in_both_runs"]==1 and q2["only_api"]==2

def test_provenance_distinguishes_agent_from_api(td:Path):
    a=[rec("W1","core_relevant",model="agent:cursor/claude-opus-5-thinking@2026-08-22"),rec("W2","out_of_scope",model="agent:cursor/claude-opus-5-thinking@2026-08-22")]
    b=[rec("W1","core_relevant",model="gpt-5.6"),rec("W2","out_of_scope",model="gpt-5.6")]
    summary,_,_,_,_,_=run_compare(td,a,b)
    p=summary["provenance"]
    assert p["agent"]["models"]==["agent:cursor/claude-opus-5-thinking@2026-08-22"] and p["api"]["models"]==["gpt-5.6"]
    assert p["same_model"]is False and p["same_prompt_version"]is True and p["model_provenance_recorded"]is True
    assert p["models_union"]==["agent:cursor/claude-opus-5-thinking@2026-08-22","gpt-5.6"]

def test_inputs_are_never_modified(td:Path):
    pa=write_run(td/"a.csv",[rec("W1","core_relevant"),rec("W2","out_of_scope")])
    pb=write_run(td/"b.csv",[rec("W1","out_of_scope"),rec("W2","core_relevant")])
    digest_a,digest_b=pa.read_bytes(),pb.read_bytes(); out=td/"cmp"
    proc=subprocess.run([sys.executable,str(SCRIPT),"--run-a",str(pa),"--run-b",str(pb),"--label-a","agent","--label-b","api","--out",str(out)],capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    assert pa.read_bytes()==digest_a and pb.read_bytes()==digest_b
    assert {p.name for p in td.iterdir()}=={"a.csv","b.csv","cmp"}
    assert {p.name for p in out.iterdir()}=={"screening_comparison_summary.json","screening_decision_disagreements.csv","screening_comparison_report.md"}

def test_writing_into_an_input_directory_is_refused(td:Path):
    a=write_run(td/"a.csv",[rec("W1","core_relevant")]); b=write_run(td/"b.csv",[rec("W1","core_relevant")])
    proc=subprocess.run([sys.executable,str(SCRIPT),"--run-a",str(a),"--run-b",str(b),"--label-a","x","--label-b","y","--out",str(td)],capture_output=True,text=True)
    assert proc.returncode!=0 and "refusing to write into an input directory" in proc.stderr

def test_empty_and_absent_inputs_are_clean_errors(td:Path):
    good=write_run(td/"b.csv",[rec("W1","core_relevant")])
    (td/"empty.csv").write_bytes(b"")
    for bad in (td/"empty.csv",td/"nope.csv"):
        proc=subprocess.run([sys.executable,str(SCRIPT),"--run-a",str(bad),"--run-b",str(good),"--label-a","x","--label-b","y","--out",str(td/"cmp")],capture_output=True,text=True)
        assert proc.returncode!=0 and "Traceback" not in proc.stderr,proc.stderr
        assert ("is empty" in proc.stderr) or ("does not exist" in proc.stderr),proc.stderr

def test_missing_required_column_is_a_clean_error(td:Path):
    a=write_run(td/"a.csv",[{"work_id":"W1","verdict":"core_relevant"}],["work_id","verdict"])
    b=write_run(td/"b.csv",[rec("W1","core_relevant")])
    proc=subprocess.run([sys.executable,str(SCRIPT),"--run-a",str(a),"--run-b",str(b),"--label-a","x","--label-b","y","--out",str(td/"cmp")],capture_output=True,text=True)
    assert proc.returncode!=0 and "missing required column(s) ['decision']" in proc.stderr

def test_duplicate_work_ids_are_collapsed_and_counted(td:Path):
    a=[rec("W1","core_relevant"),rec("W1","out_of_scope"),rec("W2","core_relevant")]
    b=[rec("W1","core_relevant"),rec("W2","core_relevant")]
    summary,dis,_,_,_,_=run_compare(td,a,b)
    assert summary["runs"]["agent"]["rows"]==3 and summary["runs"]["agent"]["unique_works"]==2
    assert summary["runs"]["agent"]["duplicate_work_ids_dropped"]==1
    assert summary["agreement"]["scored_works"]==2 and dis==[]

def test_disjoint_runs_do_not_crash(td:Path):
    summary,dis,report,_,_,_=run_compare(td,[rec("W1","core_relevant")],[rec("W2","core_relevant")])
    assert summary["coverage"]["in_both"]==0
    assert summary["agreement"]["agreement_rate"]is None and summary["agreement"]["cohens_kappa"]is None
    assert summary["roles"]["mean_jaccard"]is None and dis==[]
    assert "scored in both: **0**" in report

def test_helpers():
    assert C.tier("core_relevant","out_of_scope")==5
    assert C.tier("out_of_scope","uncertain")==4 and C.tier("out_of_scope","insufficient_abstract")==4
    assert C.tier("core_relevant","uncertain")==3
    assert C.tier("core_relevant","adjacent_relevant")==2 and C.tier("role_bridge","core_relevant")==2
    assert C.tier("uncertain","insufficient_abstract")==1
    assert C.tier("core_relevant","core_relevant")==0
    assert C.jaccard(frozenset(),frozenset())==1.0
    assert C.jaccard(frozenset({"a"}),frozenset())==0.0
    assert abs(C.jaccard(frozenset({"a","b"}),frozenset({"b","c"}))-1/3)<1e-12
    assert C.slug("agent:cursor/claude-opus-5-thinking@2026-08-22")=="agent_cursor_claude_opus_5_thinking_2026_08_22"
    assert C.truthy("True") and C.truthy("1") and not C.truthy("") and not C.truthy("False")
    assert C.fnum("0.5")==0.5 and C.fnum("")!=C.fnum("")
    assert set(C.INCLUSIVE)=={"core_relevant","adjacent_relevant","role_bridge"}
    assert C.EXCLUSIVE==("out_of_scope",) and set(C.DEFER)=={"uncertain","insufficient_abstract"}

def main():
    tests=[(n,f) for n,f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name,fn in tests:
        needs_td=fn.__code__.co_argcount>0
        if needs_td:
            with tempfile.TemporaryDirectory() as td:fn(Path(td))
        else:fn()
        print(f"ok  {name}",flush=True)
    print(f"\n{len(tests)} compare_screening_runs checks passed")

if __name__=="__main__":main()
