#!/usr/bin/env python3
"""Read-only per-work feed for rescue, screening, and PDF-collection progress streams.

Reads `abstract_rescue_progress.jsonl`, `llm_screen_progress.jsonl`, or
`pdf_progress.jsonl` and prints one line per canonical work plus a running
summary. It never writes, truncates or moves any file, so it is safe to run
against an in-flight pipeline.
"""
from __future__ import annotations
import argparse, json, sys, time
from collections import Counter
from pathlib import Path

def kind_of(rec):
    if "pdf_status" in rec: return "pdf"
    if "decision" in rec: return "llm"
    if "rescue_source" in rec: return "rescue"
    return "unknown"

def fmt(rec):
    pos=rec.get("index") or "?"; total=rec.get("total") or "?"; wid=str(rec.get("work_id") or "")[:20]; title=" ".join(str(rec.get("title") or "").split())[:78]
    kind=kind_of(rec)
    if kind=="llm":
        roles=",".join(rec.get("roles") or []) or "-"; flags=",".join(rec.get("noise_flags") or [])
        return f"[{pos}/{total}] {wid:20s} {str(rec.get('source_group') or ''):11s} {str(rec.get('decision') or ''):20s} conf={float(rec.get('confidence') or 0):.2f} {'cache' if rec.get('cache_hit') else 'live '} roles={roles}{' flags='+flags if flags else ''} | {title}"
    if kind=="pdf":
        tried=",".join(rec.get("attempts") or []) or "-"
        return f"[{pos}/{total}] {wid:20s} {str(rec.get('pdf_status') or ''):16s} {str(rec.get('stem') or '')[:36]:36s} src={str(rec.get('pdf_source') or '-')[:12]:12s} tried={tried} | {title}"
    tried=",".join(rec.get("attempts") or []) or "-"
    return f"[{pos}/{total}] {wid:20s} {str(rec.get('rescue_source') or ''):16s} chars={int(rec.get('abstract_chars') or 0):<6d} id={str(rec.get('rescue_identifier') or '')[:32]:32s} tried={tried} | {title}"

def summarize(recs):
    latest={}
    for rec in recs:
        wid=str(rec.get("work_id") or "")
        if wid:latest[wid]=rec
    vals=list(latest.values()); kinds={kind_of(r) for r in vals}; lines=[f"-- {len(vals)} works seen (kind={'/'.join(sorted(kinds)) or 'none'})"]
    if "llm" in kinds:
        dec=Counter(str(r.get("decision") or "") for r in vals if kind_of(r)=="llm"); grp=Counter(str(r.get("source_group") or "") for r in vals if kind_of(r)=="llm")
        hits=sum(1 for r in vals if kind_of(r)=="llm" and r.get("cache_hit")); prio=Counter(f"{r.get('source_group')}/{r.get('decision')}" for r in vals if kind_of(r)=="llm")
        lines.append("   decisions: "+", ".join(f"{k}={v}" for k,v in sorted(dec.items())))
        lines.append("   groups:    "+", ".join(f"{k}={v}" for k,v in sorted(grp.items())))
        lines.append("   by group:  "+", ".join(f"{k}={v}" for k,v in sorted(prio.items())))
        lines.append(f"   cache hits: {hits}")
    if "rescue" in kinds:
        src=Counter(str(r.get("rescue_source") or "") for r in vals if kind_of(r)=="rescue"); needed=sum(1 for r in vals if kind_of(r)=="rescue" and r.get("needed_rescue"))
        rescued=sum(1 for r in vals if kind_of(r)=="rescue" and r.get("needed_rescue") and str(r.get("rescue_source")) not in ("still_missing",""))
        lines.append("   sources:   "+", ".join(f"{k}={v}" for k,v in sorted(src.items())))
        lines.append(f"   needed rescue: {needed}; rescued so far: {rescued}; still missing: {needed-rescued}")
    if "pdf" in kinds:
        st=Counter(str(r.get("pdf_status") or "") for r in vals if kind_of(r)=="pdf")
        src=Counter(str(r.get("pdf_source") or "-") for r in vals if kind_of(r)=="pdf" and r.get("pdf_source"))
        got=sum(1 for r in vals if kind_of(r)=="pdf" and str(r.get("pdf_status"))=="downloaded")
        linked=sum(1 for r in vals if kind_of(r)=="pdf" and r.get("landing_url"))
        lines.append("   statuses:  "+", ".join(f"{k}={v}" for k,v in sorted(st.items())))
        if src: lines.append("   sources:   "+", ".join(f"{k}={v}" for k,v in sorted(src.items())))
        lines.append(f"   downloaded: {got}; with landing url: {linked}")
    tot=next((r.get("total") for r in reversed(vals) if r.get("total")),None)
    if tot:lines.append(f"   progress:  {len(vals)}/{tot} ({100.0*len(vals)/float(tot):.1f}%)")
    return "\n".join(lines)

def read_lines(path,offset):
    with Path(path).open("rb") as fh:
        fh.seek(offset); data=fh.read(); return data.decode("utf-8",errors="replace"),fh.tell()

def parse(line):
    line=line.strip()
    if not line:return None
    try:return json.loads(line)
    except Exception:return None

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("path",type=Path); ap.add_argument("--follow","-f",action="store_true"); ap.add_argument("--interval",type=float,default=2.0); ap.add_argument("--summary-every",type=int,default=25); ap.add_argument("--tail",type=int,default=0); ap.add_argument("--summary-only",action="store_true"); a=ap.parse_args()
    seen=[]; offset=0; buf=""; every=max(1,a.summary_every)
    if not a.path.exists() and not a.follow:print(f"no progress file yet: {a.path}",file=sys.stderr); return 1
    try:
        while True:
            if a.path.exists():
                if a.path.stat().st_size<offset:offset=0; buf=""; seen=[]
                text,offset=read_lines(a.path,offset); buf+=text; parts=buf.split("\n"); buf=parts.pop()
                fresh=[r for r in (parse(x) for x in parts) if r]
                if fresh:
                    first=not seen; seen.extend(fresh); show=fresh[-a.tail:] if first and a.tail else fresh
                    if not a.summary_only:
                        for rec in show:print(fmt(rec),flush=True)
                    if a.follow and (first or len(seen)//every!=(len(seen)-len(fresh))//every):print(summarize(seen),flush=True)
            if not a.follow:break
            time.sleep(a.interval)
    except KeyboardInterrupt:print("",flush=True)
    print(summarize(seen),flush=True); return 0
if __name__=="__main__":sys.exit(main())
