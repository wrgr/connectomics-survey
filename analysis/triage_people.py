#!/usr/bin/env python3
"""Build an evidence matrix for people contributing to the derived nanoscale core.

This is deliberately a TRIAGE layer, not an evaluative ranking. It preserves
separate dimensions and empirical distributions before any A/B/C/D thresholds
are chosen.

Inputs are outputs from the frozen retrieval plus reconcile_cleanup.py. If a
reviewed alias table is supplied, canonical IDs are used; otherwise raw author
IDs are retained and the output is explicitly marked unreconciled.

Literature-grounded design principles:
* disambiguate before individual-level bibliometrics;
* use multiple bibliographic/network/topic dimensions, not publication count alone;
* treat coauthorship as a proxy rather than complete contribution evidence;
* quantify hyperauthorship sensitivity instead of silently treating every byline
  appearance as equivalent;
* derive thresholds from observed distributions / validation rather than asserting
  universal cutoffs.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd


def q(v, p):
    s = pd.to_numeric(v, errors="coerce").dropna()
    return float(s.quantile(p)) if len(s) else None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", required=True, type=Path)
    ap.add_argument("--cleanup-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--aliases", type=Path, default=None,
                    help="Optional reviewed alias CSV with source_author_id,canonical_person_id")
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)

    papers=pd.read_csv(args.cleanup_dir/"derived_nanoscale_core.csv",low_memory=False)
    pa=pd.read_csv(args.outputs_dir/"paper_author_edges.csv",low_memory=False)
    people=pd.read_csv(args.outputs_dir/"people.csv",low_memory=False)
    co=pd.read_csv(args.outputs_dir/"coauthor_edges.csv",low_memory=False)
    papers["paper_id"]=papers.paper_id.astype(str); pa["paper_id"]=pa.paper_id.astype(str)
    pa["author_id"]=pa.author_id.astype(str); people["author_id"]=people.author_id.astype(str)
    core=set(papers.paper_id)
    x=pa[pa.paper_id.isin(core)].copy()

    aliases={}
    reconciled=False
    if args.aliases and args.aliases.exists():
        a=pd.read_csv(args.aliases,dtype=str)
        aliases=dict(zip(a.source_author_id,a.canonical_person_id)); reconciled=True
    x["person_id"]=x.author_id.map(lambda z:aliases.get(z,z))

    # Paper team size is observed, not thresholded. Hyperauthorship is defined
    # empirically as an upper-tail outlier for sensitivity analysis, not exclusion.
    team=x.groupby("paper_id").author_id.nunique().rename("team_size")
    team_log=np.log1p(team)
    q1,q3=team_log.quantile(.25),team_log.quantile(.75)
    hyper_cut=int(math.ceil(np.expm1(q3+1.5*(q3-q1))))
    hyper_cut=max(hyper_cut,int(team.quantile(.95)))
    x=x.merge(team,on="paper_id",how="left")
    x["hyperauthored"]=x.team_size>=hyper_cut
    x["fractional_credit"]=1/x.team_size

    # Merge paper attributes onto authorship events.
    pcols=[c for c in ["paper_id","year","tier","evidence_score","cleanup_bucket","axes","lexical_axes"] if c in papers]
    x=x.merge(papers[pcols],on="paper_id",how="left")
    axiscol="axes" if "axes" in x else ("lexical_axes" if "lexical_axes" in x else None)

    def n_axes(s):
        vals=set()
        for z in s.dropna().astype(str): vals.update(v.strip() for v in z.split(";") if v.strip())
        return len(vals)

    rows=[]
    for pid,g in x.groupby("person_id"):
        yrs=pd.to_numeric(g.year,errors="coerce").dropna() if "year" in g else pd.Series(dtype=float)
        nonhyper=g[~g.hyperauthored]
        row={
          "person_id":pid,
          "source_author_ids":";".join(sorted(set(g.author_id))),
          "core_papers":int(g.paper_id.nunique()),
          "fractional_core_credit":float(g.drop_duplicates(["paper_id"]).fractional_credit.sum()),
          "nonhyper_core_papers":int(nonhyper.paper_id.nunique()),
          "hyperauthored_core_papers":int(g.loc[g.hyperauthored,"paper_id"].nunique()),
          "hyperauthorship_dependence":float(g.loc[g.hyperauthored,"paper_id"].nunique()/g.paper_id.nunique()),
          "first_core_year":int(yrs.min()) if len(yrs) else None,
          "last_core_year":int(yrs.max()) if len(yrs) else None,
          "active_span_years":int(yrs.max()-yrs.min()+1) if len(yrs) else 0,
          "distinct_core_years":int(yrs.nunique()),
          "axis_breadth":n_axes(g[axiscol]) if axiscol else 0,
          "core_candidate_papers":int(g.loc[g.tier.eq("core_candidate"),"paper_id"].nunique()) if "tier" in g else 0,
          "supported_papers":int(g.loc[g.tier.eq("supported"),"paper_id"].nunique()) if "tier" in g else 0,
          "mean_evidence_score":float(pd.to_numeric(g.evidence_score,errors="coerce").mean()) if "evidence_score" in g else None,
        }
        rows.append(row)
    ev=pd.DataFrame(rows)

    # Attach display names conservatively; canonical groups may contain variants.
    names=people.set_index("author_id").name.to_dict()
    ev["name_variants"]=ev.source_author_ids.map(lambda s:";".join(sorted({str(names.get(i,"")) for i in s.split(";") if names.get(i,"")})))
    ev["display_name"]=ev.name_variants.map(lambda s:sorted(s.split(";"),key=lambda z:(len(z),z))[0] if s else "")

    # Network dimension: recompute a core-only canonical coauthor graph. Fractional
    # collaboration strength discounts large teams without deleting them.
    pair_rows=[]
    for paper_id,g in x.groupby("paper_id"):
        ids=sorted(set(g.person_id)); n=len(ids)
        if n<2: continue
        w=1/(n-1)
        for i in range(n):
            for j in range(i+1,n): pair_rows.append((ids[i],ids[j],w))
    if pair_rows:
        ce=pd.DataFrame(pair_rows,columns=["a","b","w"]).groupby(["a","b"],as_index=False).w.sum()
        degree=pd.concat([ce[["a","w"]].rename(columns={"a":"person_id"}),ce[["b","w"]].rename(columns={"b":"person_id"})]).groupby("person_id").w.sum()
        neigh={}
        for r in ce.itertuples(index=False): neigh.setdefault(r.a,set()).add(r.b); neigh.setdefault(r.b,set()).add(r.a)
        ev["fractional_coauthor_strength"]=ev.person_id.map(degree).fillna(0.0)
        ev["distinct_core_coauthors"]=ev.person_id.map(lambda z:len(neigh.get(z,set())))
        ce.to_csv(args.out/"core_canonical_coauthor_edges_fractional.csv",index=False)
    else:
        ev["fractional_coauthor_strength"]=0.; ev["distinct_core_coauthors"]=0

    # Do NOT make a composite score. Add empirical percentile columns so natural
    # breaks can be inspected and validated before tiers are frozen.
    metric_cols=["core_papers","fractional_core_credit","nonhyper_core_papers","distinct_core_years","active_span_years","axis_breadth","core_candidate_papers","fractional_coauthor_strength","distinct_core_coauthors"]
    for c in metric_cols: ev[c+"_pct"]=ev[c].rank(pct=True,method="average")

    # Practical review strata are descriptive intersections, not final tiers.
    ev["repeat_core_author"]=ev.core_papers>=2
    ev["persistent_core_author"]=ev.distinct_core_years>=3
    ev["multi_axis_author"]=ev.axis_breadth>=2
    ev["robust_to_hyperauthorship"]=ev.nonhyper_core_papers>=2
    ev=ev.sort_values(["core_papers","fractional_core_credit","distinct_core_years","axis_breadth"],ascending=False)
    ev.to_csv(args.out/"people_evidence_matrix.csv",index=False)

    dist={c:{"p50":q(ev[c],.5),"p75":q(ev[c],.75),"p90":q(ev[c],.9),"p95":q(ev[c],.95),"p99":q(ev[c],.99),"max":float(ev[c].max())} for c in metric_cols}
    summary={
      "status":"reconciled" if reconciled else "UNRECONCILED: rerun after reviewed aliases",
      "derived_core_papers":len(core),"people_touching_core":len(ev),
      "one_core_paper":int((ev.core_papers==1).sum()),"repeat_core_authors":int(ev.repeat_core_author.sum()),
      "persistent_3plus_core_years":int(ev.persistent_core_author.sum()),
      "multi_axis_authors":int(ev.multi_axis_author.sum()),
      "robust_repeat_nonhyper":int(ev.robust_to_hyperauthorship.sum()),
      "hyperauthorship_team_size_cutoff_empirical":hyper_cut,
      "metric_distributions":dist,
      "warning":"No A/B/C/D tiers or composite importance score are assigned. Inspect distributions and validate strata first."
    }
    (args.out/"people_triage_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
