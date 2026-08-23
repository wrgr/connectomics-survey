#!/usr/bin/env python3
"""Best-effort abstract rescue for canonical work records.

Order: existing linked-version abstract; Semantic Scholar (if key available);
Europe PMC; OpenAlex (if key available); Crossref DOI metadata. Existing abstracts
are never replaced. Failures are logged and never make a paper ineligible.
"""
from __future__ import annotations
import argparse, html, json, os, re, time, urllib.parse, urllib.request
from pathlib import Path
import pandas as pd

UA="connectomics-survey/abstract-rescue"

def get_json(url,headers=None,timeout=60):
    h={"User-Agent":UA,"Accept":"application/json"}; h.update(headers or {})
    req=urllib.request.Request(url,headers=h)
    with urllib.request.urlopen(req,timeout=timeout) as resp: return json.loads(resp.read().decode("utf-8"))

def post_json(url,payload,headers=None,timeout=90):
    h={"User-Agent":UA,"Accept":"application/json","Content-Type":"application/json"}; h.update(headers or {})
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers=h,method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as resp: return json.loads(resp.read().decode("utf-8"))

def clean_abstract(x):
    if not x:return ""
    s=html.unescape(str(x)); s=re.sub(r"<[^>]+>"," ",s); return " ".join(s.split())

def openalex_abstract(inv):
    if not isinstance(inv,dict) or not inv:return ""
    pairs=[]
    for word,positions in inv.items():
        for p in positions or []: pairs.append((int(p),word))
    return " ".join(w for _,w in sorted(pairs))

def s2_batch(ids,key):
    if not ids or not key:return {}
    out={}
    for i in range(0,len(ids),500):
        chunk=ids[i:i+500]
        try:
            data=post_json("https://api.semanticscholar.org/graph/v1/paper/batch?fields=title,abstract,externalIds",{"ids":chunk},{"x-api-key":key})
            for pid,row in zip(chunk,data):
                if row and row.get("abstract"):out[pid]=clean_abstract(row["abstract"])
        except Exception: pass
        time.sleep(1.05)
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--works-csv",required=True,type=Path); ap.add_argument("--versions-csv",required=True,type=Path); ap.add_argument("--out",required=True,type=Path); a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    works=pd.read_csv(a.works_csv,low_memory=False); versions=pd.read_csv(a.versions_csv,low_memory=False)
    works["work_id"]=works.work_id.astype(str); versions["work_id"]=versions.work_id.astype(str); versions["paper_id"]=versions.paper_id.astype(str)
    works["abstract_rescue_source"]="existing"; works["abstract_rescue_identifier"]=""
    missing=works.abstract.fillna("").astype(str).str.strip().eq(""); works.loc[missing,"abstract_rescue_source"]="missing"; logs=[]

    key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY","").strip(); missing_ids=set(works.loc[missing,"work_id"]); vmiss=versions[versions.work_id.isin(missing_ids)]
    s2=s2_batch(list(vmiss.paper_id),key)
    for wid,g in vmiss.groupby("work_id"):
        for pid in g.paper_id:
            if pid in s2:
                idx=works.index[works.work_id.eq(wid)]; works.loc[idx,"abstract"]=s2[pid]; works.loc[idx,"abstract_rescue_source"]="semantic_scholar"; works.loc[idx,"abstract_rescue_identifier"]=pid; break

    for idx,r in works.iterrows():
        current=str(r.get("abstract") or "").strip()
        if current and current.lower()!="nan":continue
        doi=str(r.get("doi") or "").strip(); vg=versions[versions.work_id.eq(r.work_id)]; pmid=""
        if "pmid" in vg.columns:
            vals=[str(x).strip().removesuffix(".0") for x in vg.pmid.dropna() if str(x).strip()]; pmid=vals[0] if vals else ""
        found=src=ident=""
        queries=[]
        if pmid:queries.append((f"EXT_ID:{pmid}",pmid))
        if doi:queries.append((f'DOI:"{doi}"',doi))
        for q,ident0 in queries:
            try:
                url="https://www.ebi.ac.uk/europepmc/webservices/rest/search?"+urllib.parse.urlencode({"query":q,"format":"json","resultType":"core","pageSize":1})
                data=get_json(url); results=data.get("resultList",{}).get("result",[])
                if results and results[0].get("abstractText"):found=clean_abstract(results[0]["abstractText"]); src="europe_pmc"; ident=ident0; break
            except Exception as e:logs.append({"work_id":r.work_id,"source":"europe_pmc","identifier":ident0,"error":repr(e)[:500]})
        if not found:
            oak=os.environ.get("OPENALEX_API_KEY","").strip(); oid=("doi:"+doi) if doi else (("pmid:"+pmid) if pmid else "")
            if oak and oid:
                try:
                    url="https://api.openalex.org/works/"+urllib.parse.quote(oid,safe=":/")+"?"+urllib.parse.urlencode({"api_key":oak,"select":"id,abstract_inverted_index"})
                    data=get_json(url); found=openalex_abstract(data.get("abstract_inverted_index")); src="openalex" if found else ""; ident=oid if found else ""
                except Exception as e:logs.append({"work_id":r.work_id,"source":"openalex","identifier":oid,"error":repr(e)[:500]})
        if not found and doi:
            try:
                data=get_json("https://api.crossref.org/works/"+urllib.parse.quote(doi,safe="")); found=clean_abstract(data.get("message",{}).get("abstract")); src="crossref" if found else ""; ident=doi if found else ""
            except Exception as e:logs.append({"work_id":r.work_id,"source":"crossref","identifier":doi,"error":repr(e)[:500]})
        if found:works.at[idx,"abstract"]=found; works.at[idx,"abstract_rescue_source"]=src; works.at[idx,"abstract_rescue_identifier"]=ident
        time.sleep(0.05)

    works.to_csv(a.out/"canonical_works_enriched.csv",index=False); pd.DataFrame(logs).to_csv(a.out/"abstract_rescue_errors.csv",index=False)
    before=int(missing.sum()); after=int(works.abstract.fillna("").astype(str).str.strip().eq("").sum())
    summary={"works":len(works),"missing_before":before,"rescued":before-after,"missing_after":after,"rescue_sources":works.abstract_rescue_source.value_counts().to_dict(),"note":"Best effort only; remaining missing abstracts must stay reviewable and cannot be excluded from title alone."}
    (a.out/"abstract_rescue_summary.json").write_text(json.dumps(summary,indent=2)+"\n"); print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
