#!/usr/bin/env python3
"""Deterministic checks for the IA-010 pair `analysis/triage_record_types.py` and
`analysis/apply_record_type_partition.py`.

Runs standalone, with no test runner, the same way the IA-009 comparison checks do:

    python analysis/test_triage_record_types.py

Every fixture is synthetic and written to a fresh temp dir. Nothing under
`postanalysis/` is read or written.
"""
from __future__ import annotations
import csv, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
TRIAGE=HERE/"triage_record_types.py"
PARTITION=HERE/"apply_record_type_partition.py"
WORK_COLS=["work_id","canonical_paper_id","source_group","version_count","member_paper_ids","title","abstract","authors","year","venue","doi","publication_types"]
RESULT_COLS=["work_id","canonical_paper_id","source_group","title","model","prompt_version","decision","roles","confidence","evidence","reason","noise_flags","human_review_priority","human_review_reason"]

def load(name:str,path:Path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

T=load("triage_record_types",TRIAGE)

try:
    import pytest
    @pytest.fixture(name="td")
    def _td(tmp_path):return tmp_path
except ImportError:pass

def kind(title,ptypes="",abstract="x"*40):return T.classify(title,ptypes,abstract)

def work(wid,title,*,ptypes="",abstract="An abstract long enough to look real."*3,group="unresolved"):
    return {"work_id":wid,"canonical_paper_id":"P"+wid,"source_group":group,"version_count":1,"member_paper_ids":"P"+wid,
            "title":title,"abstract":abstract,"authors":"A Author","year":2020,"venue":"Venue","doi":"10.1/"+wid,"publication_types":ptypes}

def result(wid,decision,*,group="unresolved",review=False,title=None):
    return {"work_id":wid,"canonical_paper_id":"P"+wid,"source_group":group,"title":title or ("Title "+wid),"model":"agent:x/y",
            "prompt_version":"IA-007-v2-work-level","decision":decision,"roles":"[]","confidence":0.9,"evidence":"e","reason":"r",
            "noise_flags":"[]","human_review_priority":review,"human_review_reason":"uncertain_or_missing_abstract" if review else ""}

def write_csv(path:Path,rows:list[dict],cols:list[str])->Path:
    with path.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=cols); w.writeheader()
        for r in rows:w.writerow({c:r.get(c,"") for c in cols})
    return path

def run_triage(td:Path,rows:list[dict],*,extra=(),out_name="record_types"):
    src=write_csv(td/"canonical_works.csv",rows,WORK_COLS); out=td/out_name
    proc=subprocess.run([sys.executable,str(TRIAGE),"--works-csv",str(src),"--out",str(out),*extra],capture_output=True,text=True)
    assert proc.returncode==0,f"triage failed:\n{proc.stdout}\n{proc.stderr}"
    with (out/"work_record_types.csv").open(encoding="utf-8") as fh:types=list(csv.DictReader(fh))
    with (out/"record_type_review_queue.csv").open(encoding="utf-8") as fh:queue=list(csv.DictReader(fh))
    summary=json.loads((out/"record_type_summary.json").read_text())
    return summary,types,queue,out,src

# --------------------------------------------------------------------------- rules

def test_review_article_publication_types_stay_research_papers():
    for ptypes in ("Review;JournalArticle","JournalArticle;Review","Review","JournalArticle;Conference;Review","Review;JournalArticle;Study"):
        r=kind("Structural connectomics of the mouse cortex: a review",ptypes)
        assert r["record_type"]=="research_paper",(ptypes,r)
        assert r["is_research_paper"]and r["confidence"]=="high"and r["review_queue"]is False,(ptypes,r)

def test_peer_review_report_titles():
    r=kind('Review for "The connectome of the Caenorhabditis elegans pharynx"',"Review",abstract="")
    assert r["record_type"]=="peer_review_report" and r["title_rule"]=="review_for_quoted"
    # Semantic Scholar tagged the referee report `Review`, which contradicts the anchor:
    # the label holds but the record is demoted and queued rather than trusted.
    assert r["signals_conflict"] and r["confidence"]=="medium" and r["review_queue"]
    assert "signal_conflict" in r["review_reasons"] and r["research_publication_types"]=="Review"
    # Same anchor, no contradicting metadata, still only one channel: no metadata at all
    # is weaker than neutral metadata, so the bare-title case lands one level lower.
    assert kind('Review for "X"',"JournalArticle")["confidence"]=="high"
    assert kind('Review for "X"',"")["confidence"]=="medium"
    assert kind("Review for the 2019 workshop",'')["record_type"]=="research_paper"
    assert kind('Review for "X"',"")["record_type"]=="peer_review_report"
    for t in ("Author response: SynEM, automated synapse detection for connectomics",
              "Decision letter: A connectome of the fly",
              "Referee report for a connectomics manuscript",
              "Reviewer comments on the submitted manuscript"):
        assert kind(t,"")["record_type"]=="peer_review_report",t
    # A review ARTICLE is not a referee report even when the word review leads.
    assert kind("Reviewing the evidence for synaptic plasticity","Review")["record_type"]=="research_paper"

def test_erratum_corrigendum_retraction_and_correction_family():
    for t in ("Erratum to: The Developing Human Connectome Project",
              "Erratum: Connectomic reconstruction of the inner plexiform layer",
              "Corrigendum: GRETNA, a graph theoretical network analysis toolbox",
              "Correction to: Graph Matching Based Connectomic Biomarker",
              "Correction: Highly Nonrandom Features of Synaptic Connectivity",
              "Author Correction: The challenge of mapping the human connectome",
              "Publisher Correction: A connectome of the adult fly brain",
              "Addendum: dense reconstruction of cortical tissue"):
        assert kind(t,"")["record_type"]=="erratum_correction",t
    for t in ("Retraction: a flawed connectome","Retracted: synaptic counts in cortex",
              "Withdrawn: preliminary connectome analysis","Expression of Concern: connectome data"):
        assert kind(t,"")["record_type"]=="retraction",t
    # Anchoring is the whole point: `correction` mid-title is ordinary methods language.
    for t in ("An Error Detection and Correction Framework for Connectomics",
              "Image-based correction of continuous non-planar axial distortion in serial section microscopy",
              "Neuronal Subcompartment Classification and Merge Error Correction",
              "Unsupervised Deep Learning for Susceptibility Distortion Correction in Connectome Imaging"):
        r=kind(t,"JournalArticle")
        assert r["record_type"]=="research_paper" and r["review_queue"]is False,t

def test_editorial_reply_and_commentary_detection():
    for t in ("Editorial: Organization of the White Matter Anatomy in the Human Brain",
              "Editorial. Computational connectomics",
              "Editorial for the research topic: information-based methods for neuroimaging",
              "Reply to Castro et al.: Do connectomes possess markers of plasticity?",
              'Reply to: "Historical pursuits of the language pathway hypothesis"',
              "Comment on: a connectome of the fly brain",
              'Commentary "Reinstatement of long-term memory in Aplysia"',
              "Commentary: Developmental connectomics",
              "Correspondence: on synapse counting",
              "Letter to the Editor: connectome nomenclature",
              "News and Views: the fly connectome arrives",
              "In Memoriam: a connectomics pioneer"):
        assert kind(t,"")["record_type"]=="editorial_commentary",t
    assert kind("Connectomics: A pharmacologic viewpoint","Editorial")["record_type"]=="editorial_commentary"
    assert kind("Use citizen science to turbocharge big-data projects","News;JournalArticle")["record_type"]=="editorial_commentary"
    # `Editorial` plus a neutral container type is two-channel agreement.
    high=kind("Editorial: Neurobiology of Drosophila","Editorial;JournalArticle")
    assert high["confidence"]=="high" and high["signal_count"]==2 and high["review_queue"]is False
    # A reply that merely mentions response dynamics is not a reply.
    assert kind("Response properties of neurons in the mouse visual cortex","JournalArticle")["record_type"]=="research_paper"

def test_front_matter_conference_abstract_dataset_and_book_rules():
    for t in ("Table of Contents","Author Index","Front Matter","Masthead","Preface","Editorial Board","Acknowledgment of Reviewers"):
        assert kind(t,"")["record_type"]=="front_back_matter",t
    for t in ("Abstract 70: Rich-Club Behaviour in the Human Brain Connectome",
              "Abstract A124: Simulating Disruption of Large-Scale Functional Networks",
              "Abstracts from the Society for Clinical and Experimental Hypnosis 71st Annual Conference",
              "Meeting Abstracts of the 2019 connectomics symposium"):
        assert kind(t,"")["record_type"]=="conference_abstract",t
    # A conference PAPER is a paper; only abstract stubs are not.
    assert kind("A Multicore Path to Connectomics-on-Demand","Book;JournalArticle;Conference")["record_type"]=="research_paper"
    assert kind("Transformer-GNN Based Graph Representation Learning","Book;Conference")["record_type"]=="research_paper"
    assert kind("Connectomics in NeuroImaging: Third International Workshop, CNI 2019, Proceedings","Book")["record_type"]=="book_or_chapter"
    assert kind("Perspective Chapter: Functional Human Brain Connectome in Deep Brain Stimulation","Review")["record_type"]=="book_or_chapter"
    # A data descriptor article is a peer-reviewed paper; a bare dataset record is not.
    assert kind("An open science resource for reliability in functional connectomics","JournalArticle;Dataset")["record_type"]=="research_paper"
    assert kind("Mouse cortical volume EM dataset","Dataset")["record_type"]=="dataset_or_software"

def test_empty_publication_types_fall_back_to_title_at_lower_confidence():
    bare=kind("Erratum: Connectomic reconstruction of the inner plexiform layer","",abstract="")
    supported=kind("Erratum: Connectomic reconstruction of the inner plexiform layer","JournalArticle",abstract="")
    assert bare["record_type"]==supported["record_type"]=="erratum_correction"
    assert bare["signal_count"]==supported["signal_count"]==1
    assert supported["confidence"]=="high" and supported["review_queue"]is False
    assert bare["confidence"]=="medium" and bare["review_queue"]
    assert "unconfirmed_nonpaper_medium_confidence" in bare["review_reasons"]
    assert "title_rule:erratum" in bare["evidence"]
    # A suggestive anchor with no metadata support is weaker still.
    assert kind("Q&A: What is the Open Connectome Project?","")["confidence"]=="low"

def test_conflicting_signals_are_queued_and_never_silently_exclude():
    # publication_types claims a review ARTICLE while also claiming Editorial: the
    # unsupported Editorial signal is vetoed and the work stays in the paper denominator.
    v=kind("What do the mushroom bodies do for the insect brain?","Editorial;Review;JournalArticle")
    assert v["record_type"]=="research_paper" and v["vetoed_publication_type_signals"]=="Editorial"
    assert v["review_queue"] and "vetoed_nonpaper_signal_kept_as_paper" in v["review_reasons"]
    # LettersAndComments alone is unreliable here (it also tags real methods papers), so
    # it never classifies on its own; it only corroborates a title anchor.
    weak=kind("BigDataViewer: visualization and processing for large image data sets","LettersAndComments")
    assert weak["record_type"]=="research_paper" and "weak_nonpaper_signal_kept_as_paper" in weak["review_reasons"]
    corroborated=kind("Commentary: Developmental connectomics","LettersAndComments;JournalArticle")
    assert corroborated["record_type"]=="editorial_commentary" and corroborated["signal_count"]==2 and corroborated["confidence"]=="high"
    # Two channels naming different non-paper types keeps the specific title label but
    # demotes confidence and queues the record.
    mixed=kind("Erratum: something went wrong","Editorial")
    assert mixed["record_type"]=="erratum_correction" and mixed["publication_type_signal"]=="Editorial"
    assert mixed["signals_conflict"] and mixed["confidence"]=="medium" and mixed["review_queue"]
    assert "signal_conflict" in mixed["review_reasons"]

def test_watchlist_flags_without_excluding():
    w=kind("2015 Brainhack Proceedings","")
    assert w["record_type"]=="research_paper" and w["watchlist_titles"]=="proceedings_mention" and w["review_queue"]
    assert kind("Special Issue: The Connectome - Feature Review","Review")["record_type"]=="research_paper"
    assert kind("TUTORIAL: BRAIN CONNECTOME ANALYSIS WITH GRAPH NEURAL NETWORKS","Review")["watchlist_titles"]=="tutorial_or_keynote"
    assert kind("Viewpoint Synaptic Connectivity and Neuronal Morphology","")["record_type"]=="research_paper"
    # A clean paper carries no flags at all.
    clean=kind("Dense reconstruction of a cortical column by serial-section electron microscopy","JournalArticle")
    assert clean["watchlist_titles"]=="" and clean["evidence"]=="no_non_paper_signal" and clean["review_queue"]is False

def test_title_normalization_handles_curly_quotes_and_whitespace():
    assert T.norm_title("  Review   for \u201cX\u201d ")=='Review for "X"'
    assert kind("Review for \u201cThe connectome\u201d","")["record_type"]=="peer_review_report"
    assert T.ptype_tokens("Review;JournalArticle")==["Review","JournalArticle"]
    assert T.ptype_tokens("nan")==[] and T.ptype_tokens(float("nan"))==[] and T.ptype_tokens("")==[]
    assert T.down("high")=="medium" and T.down("medium")=="low" and T.down("low")=="low"

# ------------------------------------------------------------------- triage script

def test_triage_end_to_end_partitions_and_accounts_for_every_work(td:Path):
    rows=[work("w01","Dense reconstruction of a cortical column",ptypes="",group="core_audit"),
          work("w02",'Review for "The connectome of the C. elegans pharynx"',ptypes="Review",abstract=""),
          work("w03","Erratum to: The Developing Human Connectome Project",abstract=""),
          work("w04","Editorial: Organization of the White Matter Anatomy",ptypes="Editorial",abstract="x"*2000),
          work("w05","An Error Detection and Correction Framework for Connectomics",ptypes="JournalArticle"),
          work("w06","What do the mushroom bodies do?",ptypes="Editorial;Review;JournalArticle"),
          work("w07","Abstract 70: Rich-Club Behaviour in the Human Brain Connectome",ptypes="JournalArticle"),
          work("w08","Connectomics in NeuroImaging: CNI 2019, Proceedings",ptypes="Book",abstract=""),
          work("w09","A review of macroscale connectomics",ptypes="Review;JournalArticle",group="role_bridge"),
          work("w10","Author response: SynEM, automated synapse detection",abstract="")]
    for i,r in enumerate(rows):r["work_id"]=f"w{i+1:02d}"
    summary,types,queue,out,src=run_triage(td,rows,extra=("--expected-works","10"))
    assert len(types)==10 and [r["work_id"] for r in types]==sorted(r["work_id"] for r in types)
    got={r["work_id"]:r["record_type"] for r in types}
    assert got=={"w01":"research_paper","w02":"peer_review_report","w03":"erratum_correction","w04":"editorial_commentary",
                 "w05":"research_paper","w06":"research_paper","w07":"conference_abstract","w08":"book_or_chapter",
                 "w09":"research_paper","w10":"peer_review_report"}
    d=summary["denominators"]
    assert d["canonical_works_original"]==10 and d["revised_paper_denominator"]==4 and d["non_paper_records"]==6
    assert d["revised_paper_denominator"]+d["non_paper_records"]==d["canonical_works_original"]
    assert d["expected_canonical_works"]==10 and d["complete"]is True
    assert "retained, never deleted" in d["note"] and "3,768 retained" in d["note"]
    a=summary["abstract_status"]
    assert a["works_without_abstract"]==4 and a["non_papers_without_abstract"]==4
    assert a["non_paper_types_without_abstract"]=={"book_or_chapter":1,"erratum_correction":1,"peer_review_report":2}
    assert a["research_papers_without_abstract"]==0
    assert summary["counts_by_source_group_and_record_type"]["core_audit"]=={"research_paper":1}
    assert summary["counts_by_source_group_and_record_type"]["role_bridge"]=={"research_paper":1}
    assert summary["signal_provenance"]["works_without_publication_types"]==3
    assert summary["signal_provenance"]["non_papers_from_title_evidence_only"]==4
    assert summary["signal_provenance"]["title_rule_counts"]["review_for_quoted"]==1
    assert summary["signal_provenance"]["vetoed_publication_type_counts"]=={"Editorial":1}
    # The queue is a strict subset of the per-work table and holds the ambiguous middle.
    qids=[r["work_id"] for r in queue]
    assert set(qids)<=set(got) and qids==sorted(qids)
    assert set(qids)=={"w02","w03","w04","w06","w08","w10"}
    assert summary["review_queue"]["rows"]==len(queue)
    assert summary["review_queue"]["papers_flagged_for_a_second_look"]==1
    assert set(p.name for p in out.iterdir())=={"work_record_types.csv","record_type_review_queue.csv","record_type_summary.json"}
    assert summary["input"]["rows"]==10 and summary["triage_version"]==T.TRIAGE_VERSION
    assert summary["input"]["sha256"]==T.sha256_file(src)

def test_triage_is_idempotent_and_leaves_the_input_untouched(td:Path):
    rows=[work("w1","Erratum: something",abstract=""),work("w2","A real connectomics paper",ptypes="JournalArticle"),
          work("w3","Editorial: a topic",ptypes="Editorial")]
    src=write_csv(td/"canonical_works.csv",rows,WORK_COLS); digest=src.read_bytes(); out=td/"rt"
    first=None
    for _ in range(2):
        proc=subprocess.run([sys.executable,str(TRIAGE),"--works-csv",str(src),"--out",str(out)],capture_output=True,text=True)
        assert proc.returncode==0,proc.stderr
        snapshot={p.name:p.read_bytes() for p in sorted(out.iterdir())}
        if first is None:first=snapshot
        else:assert snapshot==first,"triage output is not byte-identical on rerun"
    assert src.read_bytes()==digest
    assert {p.name for p in td.iterdir()}=={"canonical_works.csv","rt"}

def test_triage_refuses_to_write_into_its_input_directory_and_errors_cleanly(td:Path):
    src=write_csv(td/"canonical_works.csv",[work("w1","A paper")],WORK_COLS)
    proc=subprocess.run([sys.executable,str(TRIAGE),"--works-csv",str(src),"--out",str(td)],capture_output=True,text=True)
    assert proc.returncode!=0 and "refusing to write into an input directory" in proc.stderr
    (td/"empty.csv").write_bytes(b"")
    for bad,msg in ((td/"empty.csv","is empty"),(td/"nope.csv","does not exist")):
        proc=subprocess.run([sys.executable,str(TRIAGE),"--works-csv",str(bad),"--out",str(td/"rt")],capture_output=True,text=True)
        assert proc.returncode!=0 and "Traceback" not in proc.stderr and msg in proc.stderr,proc.stderr
    lean=write_csv(td/"lean.csv",[{"work_id":"w1"}],["work_id"])
    proc=subprocess.run([sys.executable,str(TRIAGE),"--works-csv",str(lean),"--out",str(td/"rt")],capture_output=True,text=True)
    assert proc.returncode!=0 and "missing required column(s) ['title']" in proc.stderr

# ---------------------------------------------------------------- partition script

def run_partition(td:Path,results_rows,types_rows,*,extra=(),out_name="partition"):
    res=write_csv(td/"llm_relevance_results.csv",results_rows,RESULT_COLS)
    src=write_csv(td/"canonical_works.csv",types_rows,WORK_COLS); rt=td/"rt"
    proc=subprocess.run([sys.executable,str(TRIAGE),"--works-csv",str(src),"--out",str(rt)],capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    out=td/out_name
    proc=subprocess.run([sys.executable,str(PARTITION),"--results-csv",str(res),"--record-types-csv",str(rt/"work_record_types.csv"),
                         "--out",str(out),"--label","agent",*extra],capture_output=True,text=True)
    assert proc.returncode==0,f"partition failed:\n{proc.stdout}\n{proc.stderr}"
    def rd(name):
        with (out/name).open(encoding="utf-8") as fh:return list(csv.DictReader(fh))
    return json.loads((out/"record_type_partition_summary.json").read_text()),rd,out,res

def test_partition_preserves_rows_and_reports_both_denominators(td:Path):
    types_rows=[work("w1","Dense reconstruction of a cortical column",ptypes="JournalArticle"),
                work("w2",'Review for "The connectome"',ptypes="Review",abstract=""),
                work("w3","Erratum to: something",abstract=""),
                work("w4","A review of connectomics",ptypes="Review;JournalArticle"),
                work("w5","Editorial: a research topic",ptypes="Editorial")]
    results_rows=[result("w1","core_relevant"),result("w2","insufficient_abstract",review=True),
                  result("w3","insufficient_abstract",review=True),result("w4","adjacent_relevant"),
                  result("w5","out_of_scope",review=True)]
    summary,rd,out,res=run_partition(td,results_rows,types_rows)
    papers=rd("llm_relevance_results_papers.csv"); non=rd("llm_relevance_results_nonpapers.csv")
    assert len(papers)+len(non)==len(results_rows)==5
    assert [r["work_id"] for r in papers]==["w1","w4"] and [r["work_id"] for r in non]==["w2","w3","w5"]
    d=summary["denominators"]
    assert d["screened_works_as_run"]==5 and d["paper_denominator"]==2 and d["non_paper_records"]==3
    assert d["invariant"]=="5 screened works = 2 papers + 3 non-paper records"
    assert "not deleted" in d["note"] and "not re-run" in d["note"]
    assert summary["non_paper_types"]=={"editorial_commentary":1,"erratum_correction":1,"peer_review_report":1}
    assert summary["decisions_all"]=={"adjacent_relevant":1,"core_relevant":1,"insufficient_abstract":2,"out_of_scope":1}
    assert summary["decisions_papers"]=={"adjacent_relevant":1,"core_relevant":1}
    assert summary["insufficient_abstract"]=={"all":2,"papers":0,"non_papers":2,"note":summary["insufficient_abstract"]["note"]}
    h=summary["human_review"]
    assert h["source"]=="results_column" and h["queue_as_run"]==3 and h["queue_papers"]==0 and h["queue_non_papers_lifted_out"]==3
    assert rd("human_review_queue_papers.csv")==[]
    assert [r["work_id"] for r in rd("human_review_queue_nonpapers.csv")]==["w2","w3","w5"]
    assert set(non[0])>=set(RESULT_COLS)|{"record_type","record_type_confidence","record_type_evidence","record_type_partition"}
    assert non[0]["record_type"]=="peer_review_report" and non[0]["record_type_partition"]=="non_paper"
    report=(out/"record_type_partition_report.md").read_text()
    assert "## Two denominators" in report and d["invariant"] in report
    assert "screened works as run: **5**" in report and "research papers: **2**" in report
    assert res.read_text().startswith("work_id,")

def test_partition_treats_unknown_works_as_papers_and_is_idempotent(td:Path):
    types_rows=[work("w1","A connectomics paper",ptypes="JournalArticle"),work("w2","Erratum: oops",abstract="")]
    results_rows=[result("w1","core_relevant"),result("w2","insufficient_abstract"),result("w9","uncertain")]
    summary,rd,out,_=run_partition(td,results_rows,types_rows)
    d=summary["denominators"]
    assert d["screened_works_as_run"]==3 and d["paper_denominator"]==2 and d["works_without_a_record_type"]==1
    assert [r["work_id"] for r in rd("llm_relevance_results_papers.csv")]==["w1","w9"]
    assert rd("llm_relevance_results_papers.csv")[1]["record_type"]=="unclassified_treated_as_paper"
    assert (out/"partition_unclassified_work_ids.txt").read_text().split()==["w9"]
    first={p.name:p.read_bytes() for p in sorted(out.iterdir())}
    proc=subprocess.run([sys.executable,str(PARTITION),"--results-csv",str(td/"llm_relevance_results.csv"),
                         "--record-types-csv",str(td/"rt"/"work_record_types.csv"),"--out",str(out),"--label","agent"],capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    assert {p.name:p.read_bytes() for p in sorted(out.iterdir())}==first,"partition output is not byte-identical on rerun"

def test_partition_accepts_an_explicit_queue_and_refuses_input_directories(td:Path):
    types_rows=[work("w1","A connectomics paper",ptypes="JournalArticle"),work("w2","Erratum: oops",abstract=""),
                work("w3","Editorial: a topic",ptypes="Editorial")]
    results_rows=[result("w1","uncertain",review=True),result("w2","insufficient_abstract",review=True),result("w3","out_of_scope",review=True)]
    q=write_csv(td/"human_review_queue.csv",[results_rows[0],results_rows[1]],RESULT_COLS)
    summary,rd,out,res=run_partition(td,results_rows,types_rows,extra=("--queue-csv",str(q)))
    h=summary["human_review"]
    assert h["source"]=="queue_csv" and h["queue_as_run"]==2 and h["queue_papers"]==1 and h["queue_non_papers_lifted_out"]==1
    assert [r["work_id"] for r in rd("human_review_queue_papers.csv")]==["w1"]
    assert h["non_paper_queue_types"]=={"erratum_correction":1}
    proc=subprocess.run([sys.executable,str(PARTITION),"--results-csv",str(res),"--record-types-csv",str(td/"rt"/"work_record_types.csv"),
                         "--out",str(td)],capture_output=True,text=True)
    assert proc.returncode!=0 and "refusing to write into an input directory" in proc.stderr
    proc=subprocess.run([sys.executable,str(PARTITION),"--results-csv",str(td/"nope.csv"),
                         "--record-types-csv",str(td/"rt"/"work_record_types.csv"),"--out",str(td/"p2")],capture_output=True,text=True)
    assert proc.returncode!=0 and "does not exist" in proc.stderr and "Traceback" not in proc.stderr

def main():
    tests=[(n,f) for n,f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name,fn in tests:
        if fn.__code__.co_argcount>0:
            with tempfile.TemporaryDirectory() as td:fn(Path(td))
        else:fn()
        print(f"ok  {name}",flush=True)
    print(f"\n{len(tests)} record-type triage checks passed")

if __name__=="__main__":main()
