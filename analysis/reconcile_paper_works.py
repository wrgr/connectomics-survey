#!/usr/bin/env python3
"""Reconcile retained + recovered bridge records into canonical scholarly works.

This is work/version reconciliation, not destructive citation deduplication. Every
source paper record is retained in work_versions.csv. Exact identifiers are linked
first; conservative title/author/year rules then link likely preprint/publication or
metadata-duplicate versions.
"""
from __future__ import annotations
import argparse, hashlib, json, re, unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
import pandas as pd

PREPRINT_DOI_PREFIXES=("10.1101/","10.21203/","10.20944/","10.31219/","10.22541/")
STOP={"a","an","the","of","and","or","for","to","in","on","with","from","by","via","using","toward","towards"}

def norm_text(v):
    if pd.isna(v): return ""
    s=unicodedata.normalize("NFKD",str(v)).encode("ascii","ignore").decode().lower()
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return " ".join(s.split())

def norm_doi(v):
    if pd.isna(v): return ""
    s=str(v).strip().lower()
    s=re.sub(r"^https?://(?:dx\.)?doi\.org/","",s)
    s=re.sub(r"^doi:\s*","",s)
    return s.strip()

def title_tokens(v): return [x for x in norm_text(v).split() if x not in STOP]

def author_surnames(v):
    if pd.isna(v): return set()
    out=set()
    for a in str(v).split(";"):
        toks=norm_text(a).split()
        if toks:
            out.add(toks[-1])
            if len(toks)>=2 and len(toks[-2])>2: out.add(toks[-2]+" "+toks[-1])
    return out

def jaccard(a,b):
    a=set(a); b=set(b)
    return len(a&b)/len(a|b) if a|b else 0.0

def is_preprint(row):
    doi=norm_doi(row.get("doi")); ptypes=str(row.get("publication_types") or "").lower(); venue=str(row.get("venue") or "").lower()
    return bool(row.get("arxiv_id")) or doi.startswith(PREPRINT_DOI_PREFIXES) or "preprint" in ptypes or "biorxiv" in venue or "medrxiv" in venue or "arxiv" in venue

class UnionFind:
    def __init__(self,ids): self.p={x:x for x in ids}
    def find(self,x):
        while self.p[x]!=x:
            self.p[x]=self.p[self.p[x]]; x=self.p[x]
        return x
    def union(self,a,b):
        ra,rb=self.find(a),self.find(b)
        if ra==rb:return
        lo,hi=sorted((ra,rb)); self.p[hi]=lo

def similarity(a,b):
    ta,tb=title_tokens(a.get("title")),title_tokens(b.get("title")); tj=jaccard(ta,tb)
    seq=SequenceMatcher(None,norm_text(a.get("title")),norm_text(b.get("title"))).ratio()
    aa,ab=author_surnames(a.get("authors")),author_surnames(b.get("authors")); aj=jaccard(aa,ab) if aa and ab else None
    ya=pd.to_numeric(a.get("year"),errors="coerce"); yb=pd.to_numeric(b.get("year"),errors="coerce"); yd=abs(float(ya)-float(yb)) if pd.notna(ya) and pd.notna(yb) else None
    return tj,seq,aj,yd

def choose_canonical(g):
    def score(r):
        doi=norm_doi(r.get("doi")); pre=is_preprint(r); ptypes=str(r.get("publication_types") or "").lower()
        abstract=len(str(r.get("abstract") or "")) if pd.notna(r.get("abstract")) else 0
        authors=len(str(r.get("authors") or "")) if pd.notna(r.get("authors")) else 0
        year=pd.to_numeric(r.get("year"),errors="coerce"); year=float(year) if pd.notna(year) else 0
        return (1 if doi and not pre else 0,1 if "journal" in ptypes else 0,abstract>0,authors>0,year,abstract,str(r.get("paper_id")))
    return max(g.to_dict("records"),key=score)

def load_manual_links(path, by_id, uf, links):
    """Apply audited manual same-work links from CSV (columns: a, b; optional reason, notes)."""
    if not path.exists():
        return 0
    manual = pd.read_csv(path, low_memory=False)
    if manual.empty or "a" not in manual.columns or "b" not in manual.columns:
        return 0
    applied = 0
    for row in manual.itertuples(index=False):
        aid, bid = str(getattr(row, "a", "")).strip(), str(getattr(row, "b", "")).strip()
        if not aid or not bid or aid == bid:
            continue
        if aid not in by_id or bid not in by_id:
            raise SystemExit(f"manual link references unknown paper_id: {aid} <-> {bid}")
        if uf.find(aid) == uf.find(bid):
            continue
        ar, br = by_id[aid], by_id[bid]
        tj, seq, aj, yd = similarity(ar, br)
        reason = str(getattr(row, "reason", "") or "manual_review").strip() or "manual_review"
        uf.union(aid, bid)
        links.append({
            "a": aid,
            "b": bid,
            "link": "same_work",
            "reason": reason,
            "title_jaccard": round(tj, 4),
            "title_sequence": round(seq, 4),
            "author_jaccard": None if aj is None else round(aj, 4),
            "year_diff": yd,
        })
        applied += 1
    return applied

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--outputs-dir",required=True,type=Path); ap.add_argument("--bridges-dir",required=True,type=Path); ap.add_argument("--accounting-csv",required=True,type=Path); ap.add_argument("--out",required=True,type=Path); ap.add_argument("--manual-links-csv",type=Path,default=None,help="Optional CSV of manual same-work links (default: <out>/manual_work_links.csv if present)"); a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    allp=pd.read_csv(a.outputs_dir/"papers_all.csv",low_memory=False); ret=pd.read_csv(a.outputs_dir/"papers_retained.csv",low_memory=False); bridge=pd.read_csv(a.bridges_dir/"all_role_bridges_final.csv",low_memory=False); acct=pd.read_csv(a.accounting_csv,low_memory=False)
    for df in (allp,ret,bridge,acct): df["paper_id"]=df["paper_id"].astype(str)
    recovered_ids=set(bridge.loc[bridge.bridge_origin.eq("recovered_keep_false"),"paper_id"]); rec=allp[allp.paper_id.isin(recovered_ids)].copy()
    ret["analysis_origin"]="originally_retained"; rec["analysis_origin"]="recovered_role_bridge"
    u=pd.concat([ret,rec],ignore_index=True,sort=False).drop_duplicates("paper_id")
    cat=dict(zip(acct.paper_id,acct.canonical_postanalysis_category)); u["source_category"]=u.paper_id.map(cat).fillna("recovered_role_bridge")
    u["doi_norm"]=u.doi.map(norm_doi); u["title_norm"]=u.title.map(norm_text)
    ids=list(u.paper_id); uf=UnionFind(ids); links=[]; recs=u.to_dict("records"); by_id={r["paper_id"]:r for r in recs}

    for field in ("doi_norm","pmid","arxiv_id"):
        x=u.copy(); x[field]=x[field].fillna("").astype(str).str.strip().str.lower()
        for key,g in x[x[field].ne("")].groupby(field):
            members=list(g.paper_id)
            for p in members[1:]: uf.union(members[0],p); links.append({"a":members[0],"b":p,"link":"exact_identifier","field":field,"value":key})

    candidate_pairs=set()
    for _,g in u[u.title_norm.ne("")].groupby("title_norm"):
        mids=list(g.paper_id)
        for i in range(len(mids)):
            for j in range(i+1,len(mids)): candidate_pairs.add(tuple(sorted((mids[i],mids[j]))))
    surname_index=defaultdict(list)
    for r in recs:
        for sname in author_surnames(r.get("authors")): surname_index[sname].append(r["paper_id"])
    for _,mids in surname_index.items():
        if len(mids)>150: continue
        for i in range(len(mids)):
            for j in range(i+1,len(mids)): candidate_pairs.add(tuple(sorted((mids[i],mids[j]))))

    for aid,bid in sorted(candidate_pairs):
        ar,br=by_id[aid],by_id[bid]
        if uf.find(aid)==uf.find(bid): continue
        ya=pd.to_numeric(ar.get("year"),errors="coerce"); yb=pd.to_numeric(br.get("year"),errors="coerce")
        if pd.notna(ya) and pd.notna(yb) and abs(float(ya)-float(yb))>5: continue
        ta,tb=set(title_tokens(ar.get("title"))),set(title_tokens(br.get("title"))); exact=norm_text(ar.get("title"))==norm_text(br.get("title"))
        if not exact and len(ta&tb)<3: continue
        tj,seq,aj,yd=similarity(ar,br); pre_pair=is_preprint(ar)!=is_preprint(br); authors_missing=not author_surnames(ar.get("authors")) or not author_surnames(br.get("authors"))
        strong=False; reason=""
        if exact and aj is not None and aj>=0.50 and (yd is None or yd<=5): strong=True; reason="exact_title_author_overlap"
        elif exact and authors_missing and pre_pair and (yd is None or yd<=5): strong=True; reason="exact_title_preprint_published_authors_missing"
        elif pre_pair and tj>=0.88 and seq>=0.90 and aj is not None and aj>=0.50 and (yd is None or yd<=5): strong=True; reason="preprint_publication_high_similarity"
        elif tj>=0.94 and seq>=0.95 and aj is not None and aj>=0.70 and (yd is None or yd<=3): strong=True; reason="near_exact_title_author_overlap"
        if strong:
            uf.union(aid,bid); links.append({"a":aid,"b":bid,"link":"same_work","reason":reason,"title_jaccard":round(tj,4),"title_sequence":round(seq,4),"author_jaccard":None if aj is None else round(aj,4),"year_diff":yd})

    manual_path=a.manual_links_csv or (a.out/"manual_work_links.csv")
    manual_applied=load_manual_links(manual_path, by_id, uf, links)

    comps=defaultdict(list)
    for pid in ids: comps[uf.find(pid)].append(pid)
    work_rows=[]; version_rows=[]
    for _,members in sorted(comps.items()):
        g=u[u.paper_id.isin(members)].copy(); can=choose_canonical(g); wid="work_"+hashlib.sha256("|".join(sorted(members)).encode()).hexdigest()[:16]
        cats=set(g.source_category.astype(str))
        if "derived_nanoscale_core" in cats: group="core_audit"
        elif any(x.startswith("unresolved_") for x in cats): group="unresolved"
        else: group="role_bridge"
        abstracts=[str(x) for x in g.abstract.dropna() if str(x).strip() and str(x).lower()!="nan"]; best_abs=max(abstracts,key=len) if abstracts else ""
        citations=pd.to_numeric(g.citation_count,errors="coerce").fillna(0)
        work_rows.append({"work_id":wid,"canonical_paper_id":can["paper_id"],"source_group":group,"version_count":len(g),"member_paper_ids":";".join(sorted(members)),"member_dois":";".join(sorted(set(x for x in g.doi_norm if x))),"title":can.get("title"),"abstract":best_abs,"authors":can.get("authors"),"year":can.get("year"),"venue":can.get("venue"),"doi":can.get("doi"),"publication_types":can.get("publication_types"),"citation_count_work":int(citations.max()),"citation_count_sum_versions":int(citations.sum()),"citation_aggregation_note":"max used as conservative work count; sum retained as upper-bound because citing works may overlap across versions","has_recovered_bridge_version":bool((g.analysis_origin=="recovered_role_bridge").any()),"has_retained_version":bool((g.analysis_origin=="originally_retained").any())})
        for _,r in g.iterrows(): version_rows.append({"work_id":wid,"canonical_paper_id":can["paper_id"],"paper_id":r.paper_id,"analysis_origin":r.analysis_origin,"source_category":r.source_category,"doi":r.get("doi"),"pmid":r.get("pmid"),"arxiv_id":r.get("arxiv_id"),"title":r.get("title"),"abstract":r.get("abstract"),"authors":r.get("authors"),"year":r.get("year"),"citation_count":r.get("citation_count"),"publication_types":r.get("publication_types")})
    works=pd.DataFrame(work_rows); versions=pd.DataFrame(version_rows); linkdf=pd.DataFrame(links)
    works.to_csv(a.out/"canonical_works.csv",index=False); versions.to_csv(a.out/"work_versions.csv",index=False); linkdf.to_csv(a.out/"work_link_evidence.csv",index=False)
    summary={"analysis_records":len(u),"originally_retained":len(ret),"recovered_bridge_records":len(rec),"canonical_works":len(works),"multi_version_works":int((works.version_count>1).sum()),"records_collapsed":len(u)-len(works),"manual_links_applied":manual_applied,"source_groups":works.source_group.value_counts().to_dict(),"missing_abstract_works":int(works.abstract.fillna("").astype(str).str.strip().eq("").sum())}
    (a.out/"work_reconciliation_summary.json").write_text(json.dumps(summary,indent=2)+"\n"); print(json.dumps(summary,indent=2))
if __name__=="__main__": main()
