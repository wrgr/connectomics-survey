#!/usr/bin/env python3
"""Second-pass abstract recovery for works still missing after IA-008 pass one.

Fixes two pass-one gaps: OpenAlex is queried without an API key (mailto politeness
only), and title-based lookups cover identifier-free works. Also mines the wider
papers_all.csv corpus and supports ingesting web-recovered identifiers.

Never overwrites an existing abstract. Title matches are audited and queued.
"""
from __future__ import annotations
import argparse, html, json, os, re, time, unicodedata, urllib.error, urllib.parse, urllib.request
from difflib import SequenceMatcher
from pathlib import Path
import pandas as pd

UA="connectomics-survey/abstract-rescue-pass2 (mailto:connectomics-survey@example.org)"
MAILTO="connectomics-survey@example.org"
PROGRESS_FILE="pass2_progress.jsonl"
NET_SOURCES=("internal_corpus","openalex","semantic_scholar","europe_pmc","crossref","pubmed","datacite","web_identifier","web_page")
TITLE_PREFIX=re.compile(r"^(?:viewpoint|review|perspective(?:\s+chapter)?|tutorial|editorial|commentary|special\s+issue|supplement\s+to|chapter\s+\d+[a-z]?(?:\s*[–—:-].*)?)\s*[:.\-–—]?\s*",re.I)
TITLE_SIM_FLOOR=0.92

def s(v):return "" if v is None or (isinstance(v,float) and v!=v) else str(v).strip()

def now_ts():return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())

def clean_abstract(x):
    if x is None:return ""
    if isinstance(x,float) and x!=x:return ""
    t=html.unescape(str(x)).strip()
    if t.lower() in ("","nan","none","null","n/a","na"):return ""
    t=re.sub(r"<[^>]+>"," ",t); t=" ".join(t.split())
    return t if len(t)>=40 else ""

def openalex_abstract(inv):
    if not isinstance(inv,dict) or not inv:return ""
    pairs=[]
    for word,positions in inv.items():
        for p in positions or []: pairs.append((int(p),word))
    return " ".join(w for _,w in sorted(pairs))

def norm_title(t):
    t=unicodedata.normalize("NFKC",s(t)).lower()
    t=TITLE_PREFIX.sub("",t)
    t=t.replace("–","-").replace("—","-").replace("’","'").replace("“",'"').replace("”",'"')
    t=re.sub(r"\s+"," ",t); t=re.sub(r"\s*([,;:()\[\]])\s*",r"\1",t); return t.strip(" .")

def title_sim(a,b):return SequenceMatcher(None,norm_title(a),norm_title(b)).ratio()

def nz(v):
    t=s(v).lower(); return t not in ("","nan","none","null")

def year_ok(y1,y2):
    try:a,b=int(float(y1)),int(float(y2)); return abs(a-b)<=1
    except Exception:return True

def get_json(url,headers=None,timeout=45):
    h={"User-Agent":UA,"Accept":"application/json"}; h.update(headers or {})
    req=urllib.request.Request(url,headers=h)
    with urllib.request.urlopen(req,timeout=timeout) as resp: return json.loads(resp.read().decode("utf-8"))

def read_progress(path):
    out={}
    if not Path(path).exists():return out
    for line in Path(path).read_text(encoding="utf-8",errors="replace").splitlines():
        line=line.strip()
        if not line:continue
        try:rec=json.loads(line)
        except Exception:continue
        wid=s(rec.get("work_id"))
        if wid:out[wid]=rec
    return out

def emit(fh,rec):
    fh.write(json.dumps(rec,ensure_ascii=False)+"\n"); fh.flush()

def progress_rec(pos,total,row,source,identifier,abstract,needed,attempts,match_method="",matched_title="",sim=0.0,record_type=""):
    src="still_missing" if source in ("","missing") else source
    return {"ts":now_ts(),"index":int(pos),"total":int(total),"work_id":s(row.get("work_id")),"canonical_paper_id":s(row.get("canonical_paper_id")),"title":s(row.get("title"))[:200],"rescue_source":src,"rescue_identifier":s(identifier),"abstract_chars":len(abstract or ""),"needed_rescue":bool(needed),"attempts":list(attempts or []),"abstract":abstract if src in NET_SOURCES else "","match_method":match_method,"matched_title":s(matched_title)[:200],"title_similarity":float(sim or 0),"record_type":s(record_type)}

def surname_set(authors):
    out=set()
    for part in re.split(r"[;|]",s(authors)):
        part=part.strip()
        if not part:continue
        tok=re.split(r"\s+",part.replace(",", " "))
        if tok:out.add(tok[-1].lower())
    return out

def build_internal_index(path):
    if not path or not Path(path).exists():return {},{}
    df=pd.read_csv(path,low_memory=False,usecols=lambda c:c in {"paper_id","title","abstract","doi","authors","year"})
    by_doi,by_title={},{}
    for r in df.itertuples(index=False):
        abs_=clean_abstract(getattr(r,"abstract",""))
        if not abs_:continue
        doi=s(getattr(r,"doi","")).lower()
        if doi and doi not in by_doi:by_doi[doi]=(s(getattr(r,"paper_id","")),abs_,s(getattr(r,"title","")),s(getattr(r,"authors","")),s(getattr(r,"year","")))
        nt=norm_title(getattr(r,"title",""))
        if nt and nt not in by_title:by_title[nt]=(s(getattr(r,"paper_id","")),abs_,s(getattr(r,"title","")),s(getattr(r,"authors","")),s(getattr(r,"year","")))
    return by_doi,by_title

def try_internal(row,by_doi,by_title,logs,attempts):
    doi=s(row.get("doi")).lower()
    if doi and doi in by_doi:
        pid,abs_,_,_,_=by_doi[doi]; attempts.append("internal_corpus:hit"); return abs_,"internal_corpus",pid,"identifier","",1.0
    nt=norm_title(row.get("title"))
    if nt and nt in by_title:
        pid,abs_,mt,au,yr=by_title[nt]
        if year_ok(row.get("year"),yr) and (not surname_set(row.get("authors")) or surname_set(row.get("authors"))&surname_set(au) or not surname_set(au)):
            attempts.append("internal_corpus:hit"); return abs_,"internal_corpus",pid,"title_similarity",mt,1.0
        attempts.append("internal_corpus:reject")
    attempts.append("internal_corpus:miss"); return "","","","","",0.0

def try_openalex(row,logs,attempts):
    doi,pmid,title=s(row.get("doi")),s(row.get("pmid")),s(row.get("title"))
    lookups=[]
    if doi:lookups.append(("doi","https://api.openalex.org/works/doi:"+urllib.parse.quote(doi)+"?"+urllib.parse.urlencode({"mailto":MAILTO,"select":"id,doi,title,publication_year,abstract_inverted_index"})))
    if pmid:lookups.append(("pmid","https://api.openalex.org/works/pmid:"+urllib.parse.quote(pmid)+"?"+urllib.parse.urlencode({"mailto":MAILTO,"select":"id,doi,title,publication_year,abstract_inverted_index"})))
    for label,url in lookups:
        try:
            data=get_json(url); abs_=clean_abstract(openalex_abstract(data.get("abstract_inverted_index")))
            if abs_:attempts.append("openalex:hit"); return abs_,"openalex",label+":"+ (doi or pmid),"identifier",s(data.get("title")),1.0
            attempts.append("openalex:miss")
        except Exception as e:logs.append({"work_id":row.get("work_id"),"source":"openalex","identifier":label,"error":repr(e)[:500]}); attempts.append("openalex:error")
    for q in [title,TITLE_PREFIX.sub("",title).strip()]:
        if not q or len(q)<12:continue
        try:
            url="https://api.openalex.org/works?"+urllib.parse.urlencode({"filter":"title.search:"+q[:180],"per-page":3,"mailto":MAILTO,"select":"id,doi,title,publication_year,abstract_inverted_index"})
            results=(get_json(url).get("results") or [])
            best=None
            for r in results:
                sim=title_sim(title,r.get("title")); abs_=clean_abstract(openalex_abstract(r.get("abstract_inverted_index")))
                if abs_ and sim>=TITLE_SIM_FLOOR and year_ok(row.get("year"),r.get("publication_year")):
                    if not best or sim>best[0]:best=(sim,abs_,s(r.get("id")),s(r.get("title")))
            if best:attempts.append("openalex:hit"); return best[1],"openalex",best[2],"title_similarity",best[3],best[0]
            attempts.append("openalex:miss")
        except Exception as e:logs.append({"work_id":row.get("work_id"),"source":"openalex","identifier":"title","error":repr(e)[:500]}); attempts.append("openalex:error")
        break
    return "","","","","",0.0

def try_s2(row,key,logs,attempts):
    if not key:attempts.append("semantic_scholar:skip"); return "","","","","",0.0
    doi,title=s(row.get("doi")),s(row.get("title")); headers={"x-api-key":key}
    if doi:
        try:
            data=get_json("https://api.semanticscholar.org/graph/v1/paper/DOI:"+urllib.parse.quote(doi)+"?fields=title,abstract,externalIds",headers)
            abs_=clean_abstract(data.get("abstract"))
            if abs_:attempts.append("semantic_scholar:hit"); return abs_,"semantic_scholar","DOI:"+doi,"identifier",s(data.get("title")),1.0
            attempts.append("semantic_scholar:miss")
        except Exception as e:logs.append({"work_id":row.get("work_id"),"source":"semantic_scholar","identifier":doi,"error":repr(e)[:500]}); attempts.append("semantic_scholar:error")
    if title:
        try:
            url="https://api.semanticscholar.org/graph/v1/paper/search?"+urllib.parse.urlencode({"query":title[:180],"limit":3,"fields":"title,abstract,year,externalIds"})
            results=(get_json(url,headers).get("data") or [])
            best=None
            for r in results:
                sim=title_sim(title,r.get("title")); abs_=clean_abstract(r.get("abstract"))
                if abs_ and sim>=TITLE_SIM_FLOOR and year_ok(row.get("year"),r.get("year")):
                    if not best or sim>best[0]:best=(sim,abs_,s(r.get("paperId")),s(r.get("title")))
            if best:attempts.append("semantic_scholar:hit"); return best[1],"semantic_scholar",best[2],"title_similarity",best[3],best[0]
            attempts.append("semantic_scholar:miss")
        except Exception as e:logs.append({"work_id":row.get("work_id"),"source":"semantic_scholar","identifier":"title","error":repr(e)[:500]}); attempts.append("semantic_scholar:error")
    return "","","","","",0.0

def try_epmc_title(row,logs,attempts):
    title=s(row.get("title"))
    if not title:attempts.append("europe_pmc:skip"); return "","","","","",0.0
    for q in [title,TITLE_PREFIX.sub("",title).strip()]:
        if not q:continue
        try:
            url="https://www.ebi.ac.uk/europepmc/webservices/rest/search?"+urllib.parse.urlencode({"query":f'TITLE:"{q[:180]}"',"format":"json","resultType":"core","pageSize":3})
            results=(get_json(url).get("resultList",{}) or {}).get("result",[]) or []
            best=None
            for r in results:
                sim=title_sim(title,r.get("title")); abs_=clean_abstract(r.get("abstractText"))
                if abs_ and sim>=TITLE_SIM_FLOOR and year_ok(row.get("year"),r.get("pubYear")):
                    if not best or sim>best[0]:best=(sim,abs_,s(r.get("pmid") or r.get("doi") or r.get("id")),s(r.get("title")))
            if best:attempts.append("europe_pmc:hit"); return best[1],"europe_pmc",best[2],"title_similarity",best[3],best[0]
            attempts.append("europe_pmc:miss")
        except Exception as e:logs.append({"work_id":row.get("work_id"),"source":"europe_pmc","identifier":"title","error":repr(e)[:500]}); attempts.append("europe_pmc:error")
        break
    return "","","","","",0.0

def try_crossref_title(row,logs,attempts):
    title=s(row.get("title"))
    if not title:attempts.append("crossref:skip"); return "","","","","",0.0
    try:
        url="https://api.crossref.org/works?"+urllib.parse.urlencode({"query.bibliographic":title[:180],"rows":3})
        items=(get_json(url).get("message",{}) or {}).get("items",[]) or []
        best=None
        for r in items:
            mt=" ".join(r.get("title") or []); sim=title_sim(title,mt); abs_=clean_abstract(r.get("abstract"))
            yr=((r.get("published-print") or r.get("published-online") or {}).get("date-parts") or [[None]])[0][0]
            if abs_ and sim>=TITLE_SIM_FLOOR and year_ok(row.get("year"),yr):
                if not best or sim>best[0]:best=(sim,abs_,s(r.get("DOI")),mt)
        if best:attempts.append("crossref:hit"); return best[1],"crossref",best[2],"title_similarity",best[3],best[0]
        attempts.append("crossref:miss")
    except Exception as e:logs.append({"work_id":row.get("work_id"),"source":"crossref","identifier":"title","error":repr(e)[:500]}); attempts.append("crossref:error")
    return "","","","","",0.0

def try_pubmed(row,logs,attempts):
    pmid=s(row.get("pmid")).removesuffix(".0")
    if not pmid:attempts.append("pubmed:skip"); return "","","","","",0.0
    try:
        url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"+urllib.parse.urlencode({"db":"pubmed","id":pmid,"retmode":"xml"})
        req=urllib.request.Request(url,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=45) as resp:xml=resp.read().decode("utf-8","replace")
        m=re.search(r"<AbstractText[^>]*>(.*?)</AbstractText>",xml,re.S)
        abs_=clean_abstract(m.group(1) if m else "")
        if abs_:attempts.append("pubmed:hit"); return abs_,"pubmed",pmid,"identifier","",1.0
        attempts.append("pubmed:miss")
    except Exception as e:logs.append({"work_id":row.get("work_id"),"source":"pubmed","identifier":pmid,"error":repr(e)[:500]}); attempts.append("pubmed:error")
    return "","","","","",0.0

def try_datacite(row,logs,attempts):
    doi=s(row.get("doi"))
    if not doi:attempts.append("datacite:skip"); return "","","","","",0.0
    try:
        data=get_json("https://api.datacite.org/dois/"+urllib.parse.quote(doi))
        attrs=(data.get("data") or {}).get("attributes") or {}
        desc=""
        for d in attrs.get("descriptions") or []:
            if s(d.get("description")):desc=clean_abstract(d.get("description")); break
        if desc:attempts.append("datacite:hit"); return desc,"datacite",doi,"identifier",s((attrs.get("titles") or [{}])[0].get("title")),1.0
        attempts.append("datacite:miss")
    except Exception as e:logs.append({"work_id":row.get("work_id"),"source":"datacite","identifier":doi,"error":repr(e)[:500]}); attempts.append("datacite:error")
    return "","","","","",0.0

def try_web_findings(row,findings,logs,attempts):
    wid=s(row.get("work_id")); f=findings.get(wid) or {}
    if not f:return "","","","","",0.0
    doi,pmid=s(f.get("doi")),s(f.get("pmid")).removesuffix(".0")
    if doi or pmid:
        probe={"work_id":wid,"doi":doi or s(row.get("doi")),"pmid":pmid or s(row.get("pmid")),"title":s(row.get("title")),"year":row.get("year"),"authors":row.get("authors")}
        for fn in (try_openalex,try_epmc_title,try_pubmed):
            abs_,src,ident,method,mt,sim=fn(probe,logs,attempts) if fn is not try_pubmed else try_pubmed(probe,logs,attempts)
            if abs_:attempts.append("web_identifier:hit"); return abs_,"web_identifier",ident or doi or pmid,"web_identifier",mt or s(f.get("matched_title")),sim or 1.0
    abs_=clean_abstract(f.get("abstract"))
    if abs_:attempts.append("web_page:hit"); return abs_,"web_page",s(f.get("url")),"web_page",s(f.get("matched_title")),float(f.get("title_similarity") or 0)
    attempts.append("web_findings:miss"); return "","","","","",0.0

def load_findings(path):
    if not path or not Path(path).exists():return {}
    data=json.loads(Path(path).read_text())
    if isinstance(data,dict):return {s(k):v for k,v in data.items()}
    return {s(r.get("work_id")):r for r in data if s(r.get("work_id"))}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--works-csv",required=True,type=Path); ap.add_argument("--versions-csv",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path); ap.add_argument("--papers-all",type=Path,default=Path("source_artifact/connectomics_deterministic_pipeline/outputs/papers_all.csv"))
    ap.add_argument("--record-types-csv",type=Path,default=Path("postanalysis/record_types/work_record_types.csv"))
    ap.add_argument("--web-findings",type=Path,default=None); ap.add_argument("--skip-non-papers",action="store_true"); ap.add_argument("--limit",type=int,default=0)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    works=pd.read_csv(a.works_csv,low_memory=False); versions=pd.read_csv(a.versions_csv,low_memory=False)
    works["work_id"]=works.work_id.astype(str); versions["work_id"]=versions.work_id.astype(str)
    if "pmid" not in works.columns and "pmid" in versions.columns:
        pm=versions.groupby("work_id")["pmid"].apply(lambda s: next((str(x).strip().removesuffix(".0") for x in s if nz(x)),"")).reset_index()
        works=works.merge(pm,on="work_id",how="left")
    rtypes={}
    if a.record_types_csv.exists():
        rt=pd.read_csv(a.record_types_csv,low_memory=False); rt["work_id"]=rt.work_id.astype(str)
        rtypes=dict(zip(rt.work_id,rt.record_type.astype(str)))
        works["record_type"]=works.work_id.map(lambda x:rtypes.get(x,"research_paper"))
    else:works["record_type"]="research_paper"
    if "pass2_rescue_source" not in works.columns:works["pass2_rescue_source"]=""; works["pass2_rescue_identifier"]=""; works["pass2_match_method"]=""; works["pass2_matched_title"]=""; works["pass2_title_similarity"]=0.0

    miss_mask=works.abstract.fillna("").astype(str).str.strip().eq("")
    targets=works[miss_mask].copy()
    if a.skip_non_papers:targets=targets[targets.record_type.eq("research_paper")]
    if a.limit:targets=targets.head(a.limit)
    prior=read_progress(a.out/PROGRESS_FILE); findings=load_findings(a.web_findings); by_doi,by_title=build_internal_index(a.papers_all)
    key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY","").strip(); logs=[]; review=[]; webq=[]; resumed=0
    for idx in targets.index:
        wid=works.at[idx,"work_id"]; rec=prior.get(wid)
        if not rec:continue
        src=s(rec.get("rescue_source")); txt=s(rec.get("abstract"))
        if src in NET_SOURCES and txt:
            works.at[idx,"abstract"]=txt; works.at[idx,"pass2_rescue_source"]=src; works.at[idx,"pass2_rescue_identifier"]=s(rec.get("rescue_identifier"))
            works.at[idx,"pass2_match_method"]=s(rec.get("match_method")); works.at[idx,"pass2_matched_title"]=s(rec.get("matched_title")); works.at[idx,"pass2_title_similarity"]=float(rec.get("title_similarity") or 0); resumed+=1
    print(json.dumps({"targets":len(targets),"prior":len(prior),"resumed":resumed,"internal_doi_index":len(by_doi),"internal_title_index":len(by_title),"web_findings":len(findings)}),flush=True)

    total=len(targets); pf=(a.out/PROGRESS_FILE).open("a",encoding="utf-8")
    for pos,(_,r) in enumerate(targets.iterrows(),start=1):
        idx=works.index[works.work_id.eq(r.work_id)][0]; wid=str(r.work_id); rtype=s(works.at[idx,"record_type"])
        current=s(works.at[idx,"abstract"]); attempts=[]
        if current and current.lower()!="nan":
            emit(pf,progress_rec(pos,total,r,s(works.at[idx,"pass2_rescue_source"]) or "existing",s(works.at[idx,"pass2_rescue_identifier"]),current,True,["resume:reused"],s(works.at[idx,"pass2_match_method"]),s(works.at[idx,"pass2_matched_title"]),float(works.at[idx,"pass2_title_similarity"] or 0),rtype)); continue
        if prior.get(wid) and s(prior[wid].get("rescue_source"))=="still_missing" and not findings.get(wid):
            # still retry unless web findings provide a new lead; fall through
            pass
        row=works.loc[idx].to_dict(); found=src=ident=method=mt=""; sim=0.0
        for fn in (
            lambda: try_internal(row,by_doi,by_title,logs,attempts),
            lambda: try_web_findings(row,findings,logs,attempts),
            lambda: try_openalex(row,logs,attempts),
            lambda: try_s2(row,key,logs,attempts),
            lambda: try_epmc_title(row,logs,attempts),
            lambda: try_crossref_title(row,logs,attempts),
            lambda: try_pubmed(row,logs,attempts),
            lambda: try_datacite(row,logs,attempts),
        ):
            found,src,ident,method,mt,sim=fn()
            if found:break
            time.sleep(0.08)
        if found:
            works.at[idx,"abstract"]=found; works.at[idx,"pass2_rescue_source"]=src; works.at[idx,"pass2_rescue_identifier"]=ident
            works.at[idx,"pass2_match_method"]=method; works.at[idx,"pass2_matched_title"]=mt; works.at[idx,"pass2_title_similarity"]=sim
            if method in ("title_similarity","web_page","web_identifier"):
                review.append({"work_id":wid,"record_type":rtype,"title":s(row.get("title")),"matched_title":mt,"source":src,"identifier":ident,"match_method":method,"title_similarity":sim,"abstract_chars":len(found)})
        else:
            webq.append({"work_id":wid,"record_type":rtype,"title":s(row.get("title")),"year":s(row.get("year")),"doi":s(row.get("doi")),"pmid":s(row.get("pmid")),"authors":s(row.get("authors"))[:200],"venue":s(row.get("venue"))})
        emit(pf,progress_rec(pos,total,r,src if found else "still_missing",ident,found,True,attempts,method,mt,sim,rtype))
        if pos%10==0 or pos==total:print(f"pass2 {pos}/{total}",flush=True)
        time.sleep(0.05)
    pf.close()

    out_csv=a.out/"canonical_works_enriched_pass2.csv"; works.to_csv(out_csv,index=False)
    pd.DataFrame(logs).to_csv(a.out/"pass2_errors.csv",index=False)
    pd.DataFrame(review).to_csv(a.out/"title_match_review_queue.csv",index=False)
    pd.DataFrame(webq).to_csv(a.out/"web_search_queue.csv",index=False)
    after_mask=works.abstract.fillna("").astype(str).str.strip().eq("")
    still=works[after_mask]
    rescued_ids=set(targets.work_id)-set(still.work_id)
    rescued=works[works.work_id.isin(rescued_ids)]
    summary={
        "works":len(works),"targets":len(targets),"rescued":int(len(rescued_ids)),"missing_after":int(after_mask.sum()),
        "rescued_by_source":rescued.pass2_rescue_source.value_counts().to_dict() if len(rescued) else {},
        "rescued_by_match_method":rescued.pass2_match_method.value_counts().to_dict() if len(rescued) else {},
        "rescued_by_record_type":rescued.record_type.value_counts().to_dict() if len(rescued) else {},
        "still_missing_by_record_type":still.record_type.value_counts().to_dict() if len(still) else {},
        "title_match_review_queue":len(review),"web_search_queue":len(webq),
        "title_similarity_floor":TITLE_SIM_FLOOR,
        "note":"Pass-2 only; does not mutate postanalysis/enriched/. Wrong title matches are worse than gaps — review queue is authoritative for title/web fills.",
    }
    (a.out/"pass2_summary.json").write_text(json.dumps(summary,indent=2)+"\n"); print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
