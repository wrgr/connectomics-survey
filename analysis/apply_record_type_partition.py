#!/usr/bin/env python3
"""IA-010 post-hoc partition of an IA-007 screening run by deterministic record type.

The IA-007/IA-009 screen runs against the full 4,136-canonical-work denominator, and
that denominator is deliberately not changed: the screening script, its prompts and
its cache stay exactly as run. This tool partitions a completed
`llm_relevance_results.csv` *after the fact* using `work_record_types.csv`, so the
paper-level result can be reported against a paper denominator while the non-paper
records stay visible, counted and re-joinable.

Nothing is deleted. Every input row appears in exactly one output partition, and the
summary asserts that identity. The human-review queue is reduced by lifting non-paper
records into their own queue rather than dropping them, because a peer-review report
or an erratum still needs a one-line human confirmation of its *type* — just not an
adjudication of its scientific relevance.

Strictly read-only with respect to both inputs; it refuses to write into an input
directory.
"""
from __future__ import annotations
import argparse, collections, json
from pathlib import Path
import pandas as pd

PARTITION_VERSION="IA-010-v1-partition"
JOIN_COLS=("record_type","is_research_paper","confidence","evidence","title_rule","publication_type_signal","signals_conflict","review_queue","review_reasons")
UNCLASSIFIED="unclassified_treated_as_paper"

def s(v)->str:return "" if v is None or (isinstance(v,float) and v!=v) else str(v)

def truthy(v)->bool:return s(v).strip().lower() in {"true","1","yes","y","t"}

def read(path:Path,label:str,required:tuple[str,...])->pd.DataFrame:
    if not path.exists():raise SystemExit(f"{label}: {path} does not exist")
    try:df=pd.read_csv(path,low_memory=False,dtype=str,keep_default_na=False)
    except pd.errors.EmptyDataError:raise SystemExit(f"{label}: {path} is empty") from None
    missing=[c for c in required if c not in df.columns]
    if missing:raise SystemExit(f"{label}: {path} is missing required column(s) {missing}")
    df["work_id"]=df.work_id.astype(str).str.strip()
    return df[df.work_id.ne("")].copy()

def counts(series)->dict:return {k:int(v) for k,v in sorted(collections.Counter(s(x) for x in series).items())}

def main():
    ap=argparse.ArgumentParser(description="Partition an IA-007 screening run into paper and non-paper views using IA-010 record types.")
    ap.add_argument("--results-csv",required=True,type=Path); ap.add_argument("--record-types-csv",required=True,type=Path)
    ap.add_argument("--queue-csv",type=Path,default=None); ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--label",default="run")
    a=ap.parse_args(); out=a.out.resolve()
    for p in (a.results_csv,a.record_types_csv,a.queue_csv):
        if p and (out==p.resolve().parent or out in p.resolve().parents):raise SystemExit(f"refusing to write into an input directory: {p} lives under --out {out}")
    results=read(a.results_csv,"results",("work_id","decision"))
    types=read(a.record_types_csv,"record types",("work_id","record_type"))
    dupes=int(types.work_id.duplicated().sum()); types=types.drop_duplicates("work_id",keep="first")
    for c in JOIN_COLS:
        if c not in types.columns:types[c]=""
    out.mkdir(parents=True,exist_ok=True)

    lut=types.set_index("work_id")
    known=set(lut.index)
    merged=results.copy()
    for c in JOIN_COLS:merged["record_type_"+c if c!="record_type" else c]=merged.work_id.map(lut[c]).fillna("")
    merged["record_type"]=merged.record_type.where(merged.work_id.isin(known),UNCLASSIFIED)
    # An unclassified work is treated as a paper: this partition may only remove a work
    # from the paper denominator on positive, recorded record-type evidence.
    merged["record_type_is_research_paper"]=[True if w not in known else truthy(lut.is_research_paper[w]) for w in merged.work_id]
    merged["record_type_partition"]=merged.record_type_is_research_paper.map({True:"paper",False:"non_paper"})

    papers=merged[merged.record_type_is_research_paper].copy(); nonpapers=merged[~merged.record_type_is_research_paper].copy()
    if len(papers)+len(nonpapers)!=len(merged):raise SystemExit("partition lost rows")
    papers.to_csv(out/"llm_relevance_results_papers.csv",index=False)
    nonpapers.to_csv(out/"llm_relevance_results_nonpapers.csv",index=False)

    if a.queue_csv is not None:
        q=read(a.queue_csv,"queue",("work_id",)); queue_ids=set(q.work_id); queue_source="queue_csv"
    elif "human_review_priority" in merged.columns and merged.human_review_priority.map(s).str.strip().ne("").any():
        queue_ids={w for w,v in zip(merged.work_id,merged.human_review_priority) if truthy(v)}; queue_source="results_column"
    else:queue_ids=set(); queue_source="unavailable"
    qpap=papers[papers.work_id.isin(queue_ids)].copy(); qnon=nonpapers[nonpapers.work_id.isin(queue_ids)].copy()
    qpap.to_csv(out/"human_review_queue_papers.csv",index=False); qnon.to_csv(out/"human_review_queue_nonpapers.csv",index=False)

    unclassified=sorted(merged.loc[~merged.work_id.isin(known),"work_id"])
    if unclassified:(out/"partition_unclassified_work_ids.txt").write_text("\n".join(unclassified)+"\n")
    not_screened=sorted(known-set(merged.work_id))
    if not_screened:(out/"partition_record_types_not_in_run.txt").write_text("\n".join(not_screened)+"\n")

    summary={"partition_version":PARTITION_VERSION,"label":a.label,
             "inputs":{"results_csv":str(a.results_csv),"record_types_csv":str(a.record_types_csv),"queue_csv":str(a.queue_csv) if a.queue_csv else None,
                       "results_rows":int(len(results)),"record_type_rows":int(len(types)+dupes),"duplicate_record_type_rows_dropped":dupes},
             "denominators":{"screened_works_as_run":int(len(merged)),"paper_denominator":int(len(papers)),"non_paper_records":int(len(nonpapers)),
                             "works_without_a_record_type":len(unclassified),"record_typed_works_not_in_this_run":len(not_screened),
                             "invariant":f"{len(merged)} screened works = {len(papers)} papers + {len(nonpapers)} non-paper records",
                             "note":"Both denominators are reported. The screening run itself was executed against the as-run denominator and is not re-run, re-scored or rewritten; non-paper records are identified deterministically by IA-010 and retained here, not deleted."},
             "non_paper_types":counts(nonpapers.record_type),
             "non_paper_confidence":counts(nonpapers.record_type_confidence),
             "decisions_all":counts(merged.decision),"decisions_papers":counts(papers.decision),"decisions_non_papers":counts(nonpapers.decision),
             "paper_decisions_by_source_group":{g:counts(gd.decision) for g,gd in papers.groupby(papers.source_group.map(s) if "source_group" in papers.columns else pd.Series(["unknown"]*len(papers),index=papers.index),dropna=False)},
             "insufficient_abstract":{"all":int((merged.decision=="insufficient_abstract").sum()),"papers":int((papers.decision=="insufficient_abstract").sum()),
                                      "non_papers":int((nonpapers.decision=="insufficient_abstract").sum()),
                                      "note":"IA-007 assigns insufficient_abstract to every abstract-less work. Non-paper records counted here were never candidates for relevance adjudication in the first place."},
             "human_review":{"source":queue_source,"queue_as_run":len(queue_ids&set(merged.work_id)),"queue_papers":int(len(qpap)),
                             "queue_non_papers_lifted_out":int(len(qnon)),"reduction":int(len(qnon)),
                             "non_paper_queue_types":counts(qnon.record_type)},
             "principle":"IA-010 is a deterministic record-type label applied after the fact. It changes the reported paper denominator only; it mutates no screening decision, no keep/core/bridge/work-link status, and no retrieval provenance."}
    (out/"record_type_partition_summary.json").write_text(json.dumps(summary,indent=2)+"\n")

    d=summary["denominators"]
    lines=[f"# IA-010 record-type partition of `{a.label}`","",
           f"- screening run: `{a.results_csv}`",f"- record types: `{a.record_types_csv}`","",
           "## Two denominators","",
           f"- screened works as run: **{d['screened_works_as_run']:,}**",
           f"- research papers: **{d['paper_denominator']:,}**",
           f"- non-paper records identified deterministically: **{d['non_paper_records']:,}**",
           f"- works with no record-type row (kept as papers): {d['works_without_a_record_type']:,}","",
           f"`{d['invariant']}`","",d["note"],"",
           "## Non-paper records by type","","| record type | records | insufficient_abstract |","|---|---|---|"]
    for t,n in sorted(summary["non_paper_types"].items(),key=lambda kv:(-kv[1],kv[0])):
        lines.append(f"| {t} | {n:,} | {int(((nonpapers.record_type==t)&(nonpapers.decision=='insufficient_abstract')).sum()):,} |")
    lines+=["","## Decisions","","| decision | all | papers | non-papers |","|---|---|---|---|"]
    for dec in sorted(set(summary["decisions_all"])|set(summary["decisions_non_papers"])):
        lines.append(f"| {dec} | {summary['decisions_all'].get(dec,0):,} | {summary['decisions_papers'].get(dec,0):,} | {summary['decisions_non_papers'].get(dec,0):,} |")
    h=summary["human_review"]
    lines+=["","## Human review queue","",f"- queue as run ({h['source']}): **{h['queue_as_run']:,}**",
            f"- paper-level queue after partition: **{h['queue_papers']:,}**",
            f"- non-paper records lifted into their own queue: **{h['queue_non_papers_lifted_out']:,}**","",
            "Lifted records are written to `human_review_queue_nonpapers.csv`. They are not discarded: a human still confirms the *record type*, which is a one-line check, instead of adjudicating the scientific relevance of an erratum or a referee report.","",
            "## Interpretation","",
            "The record-type label is deterministic and auditable, not a model output. Anything classified non-paper on a single or contradicted signal was already routed to `record_type_review_queue.csv` by IA-010, so this partition is provisional in exactly the same way the screen is.",""]
    (out/"record_type_partition_report.md").write_text("\n".join(lines))
    print(json.dumps({k:summary[k] for k in ("denominators","non_paper_types","decisions_papers","decisions_non_papers","human_review")},indent=2))
if __name__=="__main__":main()
