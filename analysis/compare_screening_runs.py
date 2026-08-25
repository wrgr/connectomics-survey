#!/usr/bin/env python3
"""Compare two IA-007 screening runs at canonical-work level.

Strictly read-only with respect to both input runs: nothing is written outside
`--out`, and the run being compared is never rewritten. Intended for the IA-009
agent-adjudicated versus API comparison, but any two `llm_relevance_results.csv`
files keyed on `work_id` are accepted. Coverage may legitimately differ between
runs; only the intersection is scored, and coverage gaps are reported separately.

IA-007 is a high-recall first pass, so an `out_of_scope` in one run against
core/adjacent/role_bridge in the other is treated as the costly disagreement and
ranked above uncertain-vs-decided churn.
"""
from __future__ import annotations
import argparse, ast, collections, json, re, statistics
from pathlib import Path
import pandas as pd

INCLUSIVE=("core_relevant","adjacent_relevant","role_bridge")
EXCLUSIVE=("out_of_scope",)
DEFER=("uncertain","insufficient_abstract")
DECISIONS=INCLUSIVE+EXCLUSIVE+DEFER
GROUPS=("core_audit","unresolved","role_bridge")
STAKES={5:"inclusive_vs_out_of_scope",4:"out_of_scope_vs_deferred",3:"inclusive_vs_deferred",2:"inclusive_class_swap",1:"deferred_or_other_swap",0:"agree"}
CONF_BINS=((0.0,0.5),(0.5,0.7),(0.7,0.85),(0.85,0.95),(0.95,1.0001))
OPT_COLS=("canonical_paper_id","source_group","version_count","member_paper_ids","title","model","prompt_version","roles","confidence","evidence","reason","noise_flags","human_review_priority","human_review_reason")
REQ_COLS=("work_id","decision")

def slug(x:str)->str:return re.sub(r"[^0-9a-zA-Z]+","_",str(x)).strip("_").lower() or "run"

def s(v)->str:return "" if v is None or (isinstance(v,float) and v!=v) else str(v)

def truthy(v)->bool:return s(v).strip().lower() in {"true","1","yes","y","t"}

def fnum(v)->float:
    try:return float(s(v).strip())
    except ValueError:return float("nan")

def parse_set(v)->frozenset[str]:
    t=s(v).strip()
    if not t or t.lower() in {"nan","none","[]","set()"}:return frozenset()
    if t[0] in "[({":
        try:
            p=ast.literal_eval(t)
            if isinstance(p,(list,tuple,set,frozenset)):return frozenset(s(x).strip() for x in p if s(x).strip())
        except (ValueError,SyntaxError):pass
    return frozenset(x for x in (y.strip().strip("'\"") for y in re.split(r"[;,|]",t.strip("[]{}() "))) if x)

def jaccard(a:frozenset,b:frozenset)->float:
    if not a and not b:return 1.0
    u=a|b; return len(a&b)/len(u) if u else 1.0

def kind(d:str)->str:return "incl" if d in INCLUSIVE else "excl" if d in EXCLUSIVE else "defer" if d in DEFER else "other"

def tier(da:str,db:str)->int:
    if da==db:return 0
    ks={kind(da),kind(db)}
    if ks=={"incl","excl"}:return 5
    if ks=={"excl","defer"}:return 4
    if ks=={"incl","defer"}:return 3
    if ks=={"incl"}:return 2
    return 1

def kappa(pairs:list[tuple[str,str]])->float|None:
    n=len(pairs)
    if not n:return None
    ca=collections.Counter(a for a,_ in pairs); cb=collections.Counter(b for _,b in pairs)
    po=sum(1 for a,b in pairs if a==b)/n; pe=sum((ca[c]/n)*(cb[c]/n) for c in set(ca)|set(cb))
    return None if abs(1.0-pe)<1e-12 else round((po-pe)/(1.0-pe),6)

def rate(num:int,den:int)->float|None:return None if den<=0 else round(num/den,6)

def stats(vals:list[float])->dict:
    v=[x for x in vals if x==x]
    return {"n":len(v),"mean":round(statistics.fmean(v),6) if v else None,"median":round(statistics.median(v),6) if v else None}

def load(path:Path,label:str)->tuple[pd.DataFrame,dict]:
    try:df=pd.read_csv(path,low_memory=False,dtype=str,keep_default_na=False)
    except FileNotFoundError:raise SystemExit(f"{label}: {path} does not exist") from None
    except pd.errors.EmptyDataError:raise SystemExit(f"{label}: {path} is empty; expected an IA-007 llm_relevance_results.csv") from None
    present=list(df.columns)
    miss=[c for c in REQ_COLS if c not in present]
    if miss:raise SystemExit(f"{label}: {path} is missing required column(s) {miss}")
    df["work_id"]=df.work_id.astype(str).str.strip(); df=df[df.work_id.ne("")]
    dupes=int(df.work_id.duplicated().sum()); df=df.drop_duplicates("work_id",keep="first").set_index("work_id")
    for c in OPT_COLS:
        if c not in df.columns:df[c]=""
    meta={"path":str(path),"rows":int(len(df))+dupes,"unique_works":int(len(df)),"duplicate_work_ids_dropped":dupes,"missing_optional_columns":[c for c in OPT_COLS if c not in present],"models":sorted({x for x in df.model.map(s) if x}),"prompt_versions":sorted({x for x in df.prompt_version.map(s) if x}),"decision_counts":{k:int(v) for k,v in df.decision.map(s).value_counts().items()},"unknown_decisions":sorted({x for x in df.decision.map(s) if x and x not in DECISIONS})}
    return df,meta

def group_of(ga:str,gb:str)->str:return ga or gb or "unknown"

def main():
    ap=argparse.ArgumentParser(description="Compare two IA-007 llm_relevance_results.csv runs at work level.")
    ap.add_argument("--run-a",required=True,type=Path); ap.add_argument("--run-b",required=True,type=Path)
    ap.add_argument("--label-a",default="run_a"); ap.add_argument("--label-b",default="run_b")
    ap.add_argument("--queue-a",type=Path,default=None); ap.add_argument("--queue-b",type=Path,default=None)
    ap.add_argument("--out",required=True,type=Path); ap.add_argument("--low-confidence-threshold",type=float,default=0.85)
    ap.add_argument("--expected-works",type=int,default=0); ap.add_argument("--max-disagreement-rows",type=int,default=0)
    a=ap.parse_args(); out=a.out.resolve(); la,lb=a.label_a,a.label_b; ka,kb=slug(la),slug(lb)
    if ka==kb:raise SystemExit(f"--label-a and --label-b must differ after normalization (both -> {ka!r})")
    for p in (a.run_a,a.run_b,a.queue_a,a.queue_b):
        if p and (out==p.resolve().parent or out in p.resolve().parents):raise SystemExit(f"refusing to write into an input directory: {p} lives under --out {out}")
    out.mkdir(parents=True,exist_ok=True)
    A,ma=load(a.run_a,la); B,mb=load(a.run_b,lb)

    ida,idb=set(A.index),set(B.index); both=sorted(ida&idb)
    coverage={"works_"+ka:len(ida),"works_"+kb:len(idb),"in_both":len(both),"only_in_"+ka:len(ida-idb),"only_in_"+kb:len(idb-ida),"union":len(ida|idb),"coverage_jaccard":round(jaccard(frozenset(ida),frozenset(idb)),6)}
    if a.expected_works:coverage["expected_works"]=a.expected_works; coverage["complete_"+ka]=len(ida)==a.expected_works; coverage["complete_"+kb]=len(idb)==a.expected_works
    for lbl,gap in ((ka,ida-idb),(kb,idb-ida)):
        if gap:(out/("screening_coverage_only_"+lbl+".txt")).write_text("\n".join(sorted(gap))+"\n"); coverage["only_in_"+lbl+"_listing"]="screening_coverage_only_"+lbl+".txt"

    da={w:s(A.decision[w]) for w in both}; db={w:s(B.decision[w]) for w in both}
    ga={w:s(A.source_group[w]).strip() for w in both}; gb={w:s(B.source_group[w]).strip() for w in both}
    grp={w:group_of(ga[w],gb[w]) for w in both}; gmis=sorted(w for w in both if ga[w] and gb[w] and ga[w]!=gb[w])
    ca={w:fnum(A.confidence[w]) for w in both}; cb={w:fnum(B.confidence[w]) for w in both}
    ra={w:parse_set(A.roles[w]) for w in both}; rb={w:parse_set(B.roles[w]) for w in both}
    na={w:parse_set(A.noise_flags[w]) for w in both}; nb={w:parse_set(B.noise_flags[w]) for w in both}
    pairs=[(da[w],db[w]) for w in both]; agree=[w for w in both if da[w]==db[w]]; disagree=[w for w in both if da[w]!=db[w]]

    seen=sorted({d for d in list(da.values())+list(db.values())},key=lambda d:(DECISIONS.index(d) if d in DECISIONS else len(DECISIONS),d))
    confusion={x:{y:0 for y in seen} for x in seen}
    for w in both:confusion[da[w]][db[w]]+=1
    per_group={}
    for g in sorted({grp[w] for w in both}|set(GROUPS)):
        ws=[w for w in both if grp[w]==g]
        per_group[g]={"works":len(ws),"agreements":sum(1 for w in ws if da[w]==db[w]),"agreement_rate":rate(sum(1 for w in ws if da[w]==db[w]),len(ws)),"cohens_kappa":kappa([(da[w],db[w]) for w in ws])}
    agreement={"scored_works":len(both),"agreements":len(agree),"agreement_rate":rate(len(agree),len(both)),"cohens_kappa":kappa(pairs),"by_source_group":per_group,"source_group_mismatches":len(gmis),"source_group_mismatch_work_ids":gmis[:50]}

    def sens(dx,dy,ly):
        ex=[w for w in both if dx[w] in EXCLUSIVE]; conflict=[w for w in ex if dy[w] in INCLUSIVE]
        return {"would_exclude":len(ex),"exclusive_share":rate(len(ex),len(both)),"excluded_here_but_included_by_"+ly:len(conflict),"conflict_share_of_own_exclusions":rate(len(conflict),len(ex)),"conflict_by_other_decision":{k:int(v) for k,v in sorted(collections.Counter(dy[w] for w in conflict).items())},"conflict_by_source_group":{k:int(v) for k,v in sorted(collections.Counter(grp[w] for w in conflict).items())},"excluded_here_but_deferred_by_"+ly:sum(1 for w in ex if dy[w] in DEFER)}
    tiers=collections.Counter(tier(da[w],db[w]) for w in disagree)
    sensitivity={ka:sens(da,db,lb),kb:sens(db,da,la),"both_exclude":sum(1 for w in both if da[w] in EXCLUSIVE and db[w] in EXCLUSIVE),"high_stakes_exclusion_conflicts":int(tiers.get(5,0)),"exclusion_vs_deferral":int(tiers.get(4,0)),"benign_deferral_churn":int(tiers.get(3,0)),"inclusive_class_swaps":int(tiers.get(2,0)),"other_swaps":int(tiers.get(1,0)),"disagreements_by_stake":{STAKES[t]:int(tiers.get(t,0)) for t in (5,4,3,2,1)},"recall_relevant_union":sum(1 for w in both if da[w] in INCLUSIVE or db[w] in INCLUSIVE),"recall_relevant_intersection":sum(1 for w in both if da[w] in INCLUSIVE and db[w] in INCLUSIVE)}

    def setcmp(xa,xb):
        js=[jaccard(xa[w],xb[w]) for w in both]; labels=sorted({*(l for w in both for l in xa[w]),*(l for w in both for l in xb[w])})
        per={}
        for l in labels:
            ia=sum(1 for w in both if l in xa[w]); ib=sum(1 for w in both if l in xb[w]); ib_=sum(1 for w in both if l in xa[w] and l in xb[w])
            per[l]={ka:ia,kb:ib,"both":ib_,"jaccard":rate(ib_,ia+ib-ib_)}
        return {"mean_jaccard":round(statistics.fmean(js),6) if js else None,"exact_set_match_rate":rate(sum(1 for w in both if xa[w]==xb[w]),len(both)),"both_empty":sum(1 for w in both if not xa[w] and not xb[w]),"nonempty_"+ka:sum(1 for w in both if xa[w]),"nonempty_"+kb:sum(1 for w in both if xb[w]),"mean_jaccard_when_either_nonempty":round(statistics.fmean([jaccard(xa[w],xb[w]) for w in both if xa[w] or xb[w]]),6) if any(xa[w] or xb[w] for w in both) else None,"per_label":per}

    def calib(dx,cx):
        return {"overall":stats([cx[w] for w in both]),"by_decision":{d:stats([cx[w] for w in both if dx[w]==d]) for d in seen}}
    lo=a.low_confidence_threshold; minc={w:min([x for x in (ca[w],cb[w]) if x==x],default=float("nan")) for w in both}
    bins={}
    for b0,b1 in CONF_BINS:
        ws=[w for w in both if minc[w]==minc[w] and b0<=minc[w]<b1]; dcount=sum(1 for w in ws if da[w]!=db[w])
        bins[f"{b0:.2f}-{min(b1,1.0):.2f}"]={"works":len(ws),"disagreements":dcount,"disagreement_rate":rate(dcount,len(ws))}
    dis_lo=sum(1 for w in disagree if minc[w]==minc[w] and minc[w]<lo); all_lo=sum(1 for w in both if minc[w]==minc[w] and minc[w]<lo)
    confidence={ka:calib(da,ca),kb:calib(db,cb),"agreeing_works":{ka:stats([ca[w] for w in agree]),kb:stats([cb[w] for w in agree])},"disagreeing_works":{ka:stats([ca[w] for w in disagree]),kb:stats([cb[w] for w in disagree])},"low_confidence_threshold":lo,"min_confidence_below_threshold":all_lo,"disagreements_below_threshold":dis_lo,"share_of_disagreements_below_threshold":rate(dis_lo,len(disagree)),"share_of_works_below_threshold":rate(all_lo,len(both)),"disagreement_rate_by_min_confidence_bin":bins,"disagreements_concentrate_at_low_confidence":bool(rate(dis_lo,len(disagree)) is not None and rate(all_lo,len(both)) is not None and rate(dis_lo,len(disagree))>rate(all_lo,len(both)))}

    def queue(df:pd.DataFrame,path:Path|None)->tuple[set,str]:
        if path is not None:
            q=pd.read_csv(path,low_memory=False,dtype=str,keep_default_na=False)
            if "work_id" not in q.columns:raise SystemExit(f"{path} is missing work_id")
            return {s(x).strip() for x in q.work_id if s(x).strip()},"queue_csv"
        if df.human_review_priority.map(s).str.strip().ne("").any():return {w for w in df.index if truthy(df.human_review_priority[w])},"results_column"
        return set(),"unavailable"
    qa,sa_=queue(A,a.queue_a); qb,sb_=queue(B,a.queue_b); qai,qbi=qa&ida,qb&idb; qab,qbb=qai&set(both),qbi&set(both)
    review={"source_"+ka:sa_,"source_"+kb:sb_,"flagged_"+ka:len(qai),"flagged_"+kb:len(qbi),"flagged_in_both_runs":len(qab&qbb),"only_"+ka:len(qab-qbb),"only_"+kb:len(qbb-qab),"jaccard":round(jaccard(frozenset(qab),frozenset(qbb)),6),"flag_agreement_rate":rate(sum(1 for w in both if (w in qab)==(w in qbb)),len(both)),"flagged_by_either":len(qab|qbb),"reason_pairs":{f"{x or 'none'}|{y or 'none'}":int(v) for (x,y),v in sorted(collections.Counter((s(A.human_review_reason[w]),s(B.human_review_reason[w])) for w in both).items(),key=lambda kv:-kv[1])[:20]}}

    rows=[]
    for w in disagree:
        t=tier(da[w],db[w]); cmax=max([x for x in (ca[w],cb[w]) if x==x],default=float("nan"))
        rows.append({"work_id":w,"stake_tier":t,"stake":STAKES[t],"source_group":grp[w],"source_group_"+ka:ga[w],"source_group_"+kb:gb[w],"title":s(A.title[w]) or s(B.title[w]),"decision_"+ka:da[w],"decision_"+kb:db[w],"confidence_"+ka:ca[w],"confidence_"+kb:cb[w],"confidence_max":cmax,"roles_"+ka:";".join(sorted(ra[w])),"roles_"+kb:";".join(sorted(rb[w])),"role_jaccard":round(jaccard(ra[w],rb[w]),6),"noise_flags_"+ka:";".join(sorted(na[w])),"noise_flags_"+kb:";".join(sorted(nb[w])),"noise_jaccard":round(jaccard(na[w],nb[w]),6),"human_review_"+ka:w in qab,"human_review_"+kb:w in qbb,"reason_"+ka:s(A.reason[w]),"reason_"+kb:s(B.reason[w]),"model_"+ka:s(A.model[w]),"model_"+kb:s(B.model[w])})
    dis=pd.DataFrame(rows,columns=["work_id","stake_tier","stake","source_group","source_group_"+ka,"source_group_"+kb,"title","decision_"+ka,"decision_"+kb,"confidence_"+ka,"confidence_"+kb,"confidence_max","roles_"+ka,"roles_"+kb,"role_jaccard","noise_flags_"+ka,"noise_flags_"+kb,"noise_jaccard","human_review_"+ka,"human_review_"+kb,"reason_"+ka,"reason_"+kb,"model_"+ka,"model_"+kb])
    if len(dis):dis=dis.sort_values(["stake_tier","confidence_max","work_id"],ascending=[False,False,True],na_position="last").reset_index(drop=True)
    if a.max_disagreement_rows:dis=dis.head(a.max_disagreement_rows)
    dis.to_csv(out/"screening_decision_disagreements.csv",index=False)

    summary={"comparison":{"label_"+ka:la,"label_"+kb:lb,"key":"work_id","scored_on":"intersection of work_id"},"runs":{ka:ma,kb:mb},"provenance":{ka:{"models":ma["models"],"prompt_versions":ma["prompt_versions"]},kb:{"models":mb["models"],"prompt_versions":mb["prompt_versions"]},"models_union":sorted(set(ma["models"])|set(mb["models"])),"same_model":set(ma["models"])==set(mb["models"]),"same_prompt_version":set(ma["prompt_versions"])==set(mb["prompt_versions"]),"model_provenance_recorded":bool(ma["models"] and mb["models"])},"coverage":coverage,"agreement":agreement,"confusion_matrix":confusion,"sensitivity":sensitivity,"roles":setcmp(ra,rb),"noise_flags":setcmp(na,nb),"confidence":confidence,"human_review":review,"disagreement_rows_written":int(len(dis)),"principle":"IA-007 is a high-recall provisional first pass; neither run is a gold standard and this comparison mutates no screening output."}
    (out/"screening_comparison_summary.json").write_text(json.dumps(summary,indent=2)+"\n")

    def pct(x):return "n/a" if x is None else f"{100*x:.1f}%"
    def num(x):return "n/a" if x is None or x!=x else f"{x:.4f}"
    hdr=["| decision ("+la+" \\ "+lb+") | "+" | ".join(seen)+" |","|"+"---|"*(len(seen)+1)]
    mat=hdr+["| "+x+" | "+" | ".join(str(confusion[x][y]) for y in seen)+" |" for x in seen]
    top=dis.head(15).to_dict(orient="records")
    lines=[f"# IA-007 screening run comparison: {la} vs {lb}","",f"- `{la}`: {a.run_a} ({ma['unique_works']:,} works, models {ma['models'] or ['unrecorded']}, prompt {ma['prompt_versions'] or ['unrecorded']})",f"- `{lb}`: {a.run_b} ({mb['unique_works']:,} works, models {mb['models'] or ['unrecorded']}, prompt {mb['prompt_versions'] or ['unrecorded']})","","## Coverage","",f"- scored in both: **{coverage['in_both']:,}**",f"- only in `{la}`: {coverage['only_in_'+ka]:,}",f"- only in `{lb}`: {coverage['only_in_'+kb]:,}",f"- coverage Jaccard: {num(coverage['coverage_jaccard'])}"]
    if a.expected_works:lines.append(f"- expected denominator {a.expected_works:,}: `{la}` {'complete' if coverage['complete_'+ka] else 'INCOMPLETE'}, `{lb}` {'complete' if coverage['complete_'+kb] else 'INCOMPLETE'}")
    lines+=["","## Decision agreement","",f"- overall agreement: **{pct(agreement['agreement_rate'])}** ({agreement['agreements']:,}/{agreement['scored_works']:,})",f"- Cohen's kappa: **{num(agreement['cohens_kappa'])}**",""]
    lines+=["| source_group | works | agreement | kappa |","|---|---|---|---|"]+[f"| {g} | {v['works']:,} | {pct(v['agreement_rate'])} | {num(v['cohens_kappa'])} |" for g,v in per_group.items()]
    lines+=["","## Confusion matrix",""]+mat
    lines+=["","## Sensitivity (high-recall contract)","",f"- **high-stakes exclusion conflicts (one run excludes, other calls relevant): {sensitivity['high_stakes_exclusion_conflicts']:,}**",f"  - `{la}` excludes / `{lb}` relevant: {sensitivity[ka]['excluded_here_but_included_by_'+lb]:,} of {sensitivity[ka]['would_exclude']:,} own exclusions",f"  - `{lb}` excludes / `{la}` relevant: {sensitivity[kb]['excluded_here_but_included_by_'+la]:,} of {sensitivity[kb]['would_exclude']:,} own exclusions",f"- exclusion vs deferral (one excludes, other defers to human): {sensitivity['exclusion_vs_deferral']:,}",f"- benign deferral churn (relevant vs uncertain/insufficient_abstract): {sensitivity['benign_deferral_churn']:,}",f"- relevance-class swaps within core/adjacent/bridge: {sensitivity['inclusive_class_swaps']:,}",f"- works either run calls relevant: {sensitivity['recall_relevant_union']:,}; both: {sensitivity['recall_relevant_intersection']:,}"]
    lines+=["","## Roles and noise flags","",f"- role set mean Jaccard: {num(summary['roles']['mean_jaccard'])}; exact set match {pct(summary['roles']['exact_set_match_rate'])}",f"- noise flag mean Jaccard: {num(summary['noise_flags']['mean_jaccard'])}; exact set match {pct(summary['noise_flags']['exact_set_match_rate'])}"]
    lines+=["","## Confidence calibration","",f"- mean confidence on agreeing works: `{la}` {num(confidence['agreeing_works'][ka]['mean'])}, `{lb}` {num(confidence['agreeing_works'][kb]['mean'])}",f"- mean confidence on disagreeing works: `{la}` {num(confidence['disagreeing_works'][ka]['mean'])}, `{lb}` {num(confidence['disagreeing_works'][kb]['mean'])}",f"- disagreements with min confidence < {lo}: {pct(confidence['share_of_disagreements_below_threshold'])} vs {pct(confidence['share_of_works_below_threshold'])} of all scored works",f"- disagreements concentrate at low confidence: **{confidence['disagreements_concentrate_at_low_confidence']}**","","| min-confidence bin | works | disagreements | rate |","|---|---|---|---|"]+[f"| {k} | {v['works']:,} | {v['disagreements']:,} | {pct(v['disagreement_rate'])} |" for k,v in bins.items()]
    lines+=["","## Human review queue overlap","",f"- flagged by `{la}`: {review['flagged_'+ka]:,} (source: {review['source_'+ka]})",f"- flagged by `{lb}`: {review['flagged_'+kb]:,} (source: {review['source_'+kb]})",f"- flagged by both: {review['flagged_in_both_runs']:,}; only `{la}`: {review['only_'+ka]:,}; only `{lb}`: {review['only_'+kb]:,}",f"- queue Jaccard: {num(review['jaccard'])}; flag agreement rate: {pct(review['flag_agreement_rate'])}"]
    lines+=["","## Highest-stakes disagreements",""]
    if top:
        lines+=["| work_id | stake | group | "+la+" | "+lb+" | conf | title |","|---|---|---|---|---|---|---|"]+[f"| {r['work_id']} | {r['stake']} | {r['source_group']} | {r['decision_'+ka]} | {r['decision_'+kb]} | {num(r['confidence_max'])} | {s(r['title'])[:80].replace('|','/')} |" for r in top]
        lines+=["",f"Full list: `screening_decision_disagreements.csv` ({len(dis):,} rows, highest stake first)."]
    else:lines.append("None: the two runs agree on every jointly covered work.")
    lines+=["","## Interpretation","","Neither run is a gold standard. IA-007 exclusions are provisional, so treat the high-stakes exclusion conflicts above as the human-adjudication queue for this comparison, not as errors attributable to either run. Agreement between an agent-adjudicated run and a single-model API run is not evidence that either matches human screening.",""]
    (out/"screening_comparison_report.md").write_text("\n".join(lines))
    print(json.dumps({k:summary[k] for k in ("coverage","agreement","sensitivity","human_review")},indent=2))
if __name__=="__main__":main()
