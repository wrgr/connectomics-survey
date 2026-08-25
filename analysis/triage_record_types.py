#!/usr/bin/env python3
"""IA-010 deterministic record-type triage over IA-008 canonical works.

Some records in the semantic-analysis universe are not research papers: peer-review
reports, errata, editorials, replies, meeting-abstract stubs, whole book/proceedings
volumes. IA-007 currently routes every abstract-less work to `insufficient_abstract`
and into the human queue, which spends human attention adjudicating the "relevance"
of an erratum and inflates the paper denominator.

This tool classifies each canonical work from `publication_types` plus conservative
*anchored* title patterns, writes the firing signal per record so every label is
auditable, and routes single-signal or conflicting classifications to a human queue.

It is strictly non-destructive. It never deletes a record, never mutates `keep`,
core, bridge, work-link or abstract status, never rewrites its input, and writes
nothing outside `--out`. Non-paper records are *labelled*, not removed: the frozen
retrieval provenance (3,768 retained, 391 recovered, 4,159 universe, 4,136 canonical
works) is untouched, and only the reported *paper* denominator changes.

The costly error is calling a real paper a non-paper, so every rule is anchored and
every weak or contradicted signal resolves toward `research_paper` plus review.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, re, unicodedata
from pathlib import Path
import pandas as pd

TRIAGE_VERSION="IA-010-v1-record-type"
LONG_ABSTRACT_CHARS=1500
LEVELS=("high","medium","low")
TYPES=("research_paper","peer_review_report","erratum_correction","retraction","editorial_commentary","front_back_matter","dataset_or_software","book_or_chapter","conference_abstract","unknown_non_paper")
QUOTES=str.maketrans({"\u201c":'"',"\u201d":'"',"\u201e":'"',"\u201f":'"',"\u2018":"'","\u2019":"'","\u201a":"'","\u201b":"'","\u00ab":'"',"\u00bb":'"'})

# Anchored title rules, first match wins. `unambiguous` means the anchored phrase has
# no plausible reading as the title of a research paper; `suggestive` means it usually
# but not always marks a non-paper, and so never reaches high confidence alone.
# Ordering matters only where one anchor is a prefix of another (editorial board before
# editorial; erratum before correction), so specific forms are listed first.
TITLE_RULES=(
    ("review_for_quoted","peer_review_report","unambiguous",r"^review\s+for\s+[\"']"),
    ("author_response","peer_review_report","unambiguous",r"^author\s+response\s*[:\u2013\u2014-]"),
    ("decision_letter","peer_review_report","unambiguous",r"^(?:decision\s+letter|editor'?s?\s+decision\s+letter)\b"),
    ("peer_review_report","peer_review_report","unambiguous",r"^(?:peer\s+review(?:\s+report)?|referee\s+report|reviewer'?s?\s+report|review\s+report)\b"),
    ("reviewer_comments","peer_review_report","unambiguous",r"^reviewer'?s?\s+comments\b"),
    ("erratum","erratum_correction","unambiguous",r"^erratum\b"),
    ("corrigendum","erratum_correction","unambiguous",r"^corrigendum\b"),
    ("named_correction","erratum_correction","unambiguous",r"^(?:author|publisher|editorial)\s+correction\b"),
    ("correction_to","erratum_correction","unambiguous",r"^correction\s+to\b"),
    ("correction_prefix","erratum_correction","unambiguous",r"^correction\s*[:\u2013\u2014-]"),
    ("addendum","erratum_correction","unambiguous",r"^addendum\b"),
    ("retraction","retraction","unambiguous",r"^retract(?:ion|ed)\b"),
    ("withdrawn","retraction","unambiguous",r"^withdrawn\b"),
    ("expression_of_concern","retraction","unambiguous",r"^expression\s+of\s+concern\b"),
    ("editorial_board","front_back_matter","unambiguous",r"^editorial\s+board\b"),
    ("table_of_contents","front_back_matter","unambiguous",r"^(?:table\s+of\s+contents|contents)\s*$|^table\s+of\s+contents\b"),
    ("index_matter","front_back_matter","unambiguous",r"^(?:author|subject|keyword|name)\s+index\b|^index\s*$"),
    ("front_back_matter","front_back_matter","unambiguous",r"^(?:front|back)\s+matter\b|^proceedings\s+front\s+matter\b"),
    ("masthead","front_back_matter","unambiguous",r"^masthead\b"),
    ("preface","front_back_matter","unambiguous",r"^(?:preface|foreword)\b"),
    ("list_of_contributors","front_back_matter","unambiguous",r"^(?:list\s+of\s+(?:contributors|reviewers|referees)|acknowledge?ment\s+of\s+reviewers|title\s+page)\b"),
    ("editorial_prefix","editorial_commentary","unambiguous",r"^editorial\b"),
    ("reply_to","editorial_commentary","unambiguous",r"^(?:reply|response)\s*(?:to|on)?\s*[:\u2013\u2014-]|^(?:reply|response)\s+to\b"),
    ("comment_on","editorial_commentary","unambiguous",r"^comment(?:ary)?\s+(?:on|to)\b"),
    ("commentary_prefix","editorial_commentary","unambiguous",r"^commentary\s*[:\u2013\u2014\"'-]"),
    ("correspondence","editorial_commentary","unambiguous",r"^correspondence\b|^letter\s+to\s+the\s+editor\b"),
    ("news_and_views","editorial_commentary","unambiguous",r"^news\s+(?:and|&)\s+views\b"),
    ("obituary","editorial_commentary","unambiguous",r"^(?:obituary|in\s+memoriam)\b"),
    ("qa_interview","editorial_commentary","suggestive",r"^q\s*&\s*a\b"),
    ("numbered_abstract","conference_abstract","unambiguous",r"^abstract\s+[a-z]{0,3}-?\d+\s*[:.\u2013\u2014-]"),
    ("abstract_collection","conference_abstract","unambiguous",r"^abstracts\b"),
    ("meeting_abstract","conference_abstract","unambiguous",r"^(?:meeting|conference|poster)\s+abstracts?\b"),
    ("perspective_chapter","book_or_chapter","suggestive",r"^perspective\s+chapter\b"),
    ("numbered_chapter","book_or_chapter","suggestive",r"^chapter\s+\d+\b"),
)

# Watchlist patterns never classify. They only mark a record for human eyes, and are
# evaluated only when no anchored rule fired, so they add no noise to real matches.
WATCHLIST=(
    ("proceedings_mention",r"\bproceedings\b"),
    ("special_issue",r"^(?:special\s+issue|this\s+issue)\b"),
    ("issue_introduction",r"^introduction\s+to\s+(?:the|this)\b"),
    ("tutorial_or_keynote",r"^(?:tutorial|keynote|invited\s+(?:talk|lecture)|panel\s+discussion)\b"),
    ("viewpoint_prefix",r"^viewpoint\b"),
    ("book_review",r"\bbook\s+review\b"),
    ("unanchored_correction_mention",r"\b(?:erratum|corrigendum|retraction|author\s+correction|publisher\s+correction)\b"),
    ("supplement",r"^supplement\b|\bsupplemental\s+issue\b"),
)

# Semantic Scholar `publicationTypes` values observed in this corpus. `JournalArticle`
# is a container, not a claim about content: an erratum is also a JournalArticle. The
# research types below are genuine claims that the item is a research article, which is
# why `Review;JournalArticle` (a review ARTICLE) can never become a peer-review report.
PTYPE_RESEARCH=("Review","Study","MetaAnalysis","ClinicalTrial","CaseReport","Conference")
PTYPE_NEUTRAL=("JournalArticle",)
PTYPE_STRONG={"Editorial":"editorial_commentary","News":"editorial_commentary"}
PTYPE_WEAK={"LettersAndComments":"editorial_commentary"}
# Conditional signals fire only when nothing in the blocker set is also present: an
# LNCS/ACM proceedings paper is tagged Book;JournalArticle;Conference, and a data
# descriptor article is tagged JournalArticle;Dataset. Both are papers.
PTYPE_CONDITIONAL={"Dataset":("dataset_or_software",("JournalArticle","Conference","Review","Study","Book","BookSection","MetaAnalysis","ClinicalTrial","CaseReport")),
                   "Book":("book_or_chapter",("JournalArticle","Conference")),
                   "BookSection":("book_or_chapter",("JournalArticle","Conference"))}
PTYPE_ORDER=("Editorial","News","Dataset","Book","BookSection","LettersAndComments")

COMPILED_TITLE=tuple((n,t,st,re.compile(p,re.I)) for n,t,st,p in TITLE_RULES)
COMPILED_WATCH=tuple((n,re.compile(p,re.I)) for n,p in WATCHLIST)
COLS=("work_id","canonical_paper_id","source_group","year","venue","doi","title","publication_types","has_abstract","abstract_chars","record_type","is_research_paper","confidence","signal_count","evidence","title_rule","title_rule_type","title_rule_strength","title_match","publication_type_signal","publication_type_signal_type","publication_type_signal_strength","vetoed_publication_type_signals","research_publication_types","signals_conflict","watchlist_titles","review_queue","review_reasons")

def s(v)->str:return "" if v is None or (isinstance(v,float) and v!=v) else str(v)

def norm_title(v)->str:
    t=unicodedata.normalize("NFKC",s(v)).translate(QUOTES)
    return re.sub(r"\s+"," ",t).strip()

def ptype_tokens(v)->list[str]:
    return [x.strip() for x in s(v).replace(",",";").split(";") if x.strip() and x.strip().lower()!="nan"]

def down(level:str)->str:return LEVELS[min(LEVELS.index(level)+1,len(LEVELS)-1)]

def match_title(title:str):
    for name,rtype,strength,rx in COMPILED_TITLE:
        m=rx.search(title)
        if m:return name,rtype,strength,m.group(0)
    return None

def classify(title,publication_types,abstract="",*,long_abstract_chars:int=LONG_ABSTRACT_CHARS)->dict:
    """Classify one work. Pure and deterministic; the only input is this record."""
    t=norm_title(title); toks=ptype_tokens(publication_types)
    abstract_chars=len(s(abstract).strip()); research=[x for x in toks if x in PTYPE_RESEARCH]
    hit=match_title(t); watch=[] if hit else [n for n,rx in COMPILED_WATCH if rx.search(t)]

    ptype_sig=ptype_strength=None; weak_sig=None
    for tok in PTYPE_ORDER:
        if tok not in toks:continue
        if tok in PTYPE_STRONG and ptype_sig is None:ptype_sig=(tok,PTYPE_STRONG[tok]); ptype_strength="strong"
        elif tok in PTYPE_CONDITIONAL and ptype_sig is None:
            rtype,blockers=PTYPE_CONDITIONAL[tok]
            if not any(b in toks for b in blockers):ptype_sig=(tok,rtype); ptype_strength="conditional"
        elif tok in PTYPE_WEAK and weak_sig is None:weak_sig=(tok,PTYPE_WEAK[tok])

    # A publication-type signal with no title support loses to an explicit research
    # article type in the same metadata string: Editorial;Review stays a paper.
    vetoed=[]
    if ptype_sig and research and not (hit and hit[1]==ptype_sig[1]):
        vetoed.append(ptype_sig[0]); ptype_sig=None; ptype_strength=None

    corroborated=bool(ptype_sig and hit and ptype_sig[1]==hit[1]) or bool(weak_sig and hit and weak_sig[1]==hit[1])
    if hit:
        name,rtype,strength,matched=hit
        confidence="high" if (corroborated or strength=="unambiguous") else "medium"
        signal_count=2 if corroborated else 1
    elif ptype_sig:
        name=matched=""; strength=""; rtype=ptype_sig[1]; confidence="medium"; signal_count=1
    else:
        name=matched=""; strength=""; rtype="research_paper"; signal_count=0
        confidence="medium" if (weak_sig or vetoed or watch) else "high"

    conflict=bool(vetoed) or bool(hit and ptype_sig and hit[1]!=ptype_sig[1]) or bool(rtype!="research_paper" and research)
    if rtype!="research_paper":
        if conflict:confidence=down(confidence)
        # Title evidence stands alone when publication_types is empty, but 661 works
        # have no publication_types at all, so unsupported title evidence is not high.
        if hit and not toks:confidence=down(confidence)

    reasons=[]
    if rtype!="research_paper":
        if confidence!="high":reasons.append(f"unconfirmed_nonpaper_{confidence}_confidence")
        if conflict:reasons.append("signal_conflict")
        if abstract_chars>=long_abstract_chars:reasons.append("nonpaper_with_substantial_abstract")
    else:
        if vetoed:reasons.append("vetoed_nonpaper_signal_kept_as_paper")
        if weak_sig:reasons.append("weak_nonpaper_signal_kept_as_paper")
    if watch:reasons.append("watchlist_title")

    evidence=[]
    if hit:evidence.append(f"title_rule:{name}={matched!r}")
    if ptype_sig:evidence.append(f"publication_type:{ptype_sig[0]}({ptype_strength})")
    if weak_sig:evidence.append(f"weak_publication_type:{weak_sig[0]}")
    if vetoed:evidence.append("vetoed_publication_type:"+",".join(vetoed))
    if research:evidence.append("research_publication_type:"+",".join(research))
    if watch:evidence.append("watchlist_title:"+",".join(watch))
    if not evidence:evidence.append("no_non_paper_signal")

    return {"record_type":rtype,"is_research_paper":rtype=="research_paper","confidence":confidence,"signal_count":signal_count,
            "evidence":"; ".join(evidence),"title_rule":name,"title_rule_type":hit[1] if hit else "","title_rule_strength":strength,
            "title_match":matched,"publication_type_signal":ptype_sig[0] if ptype_sig else "","publication_type_signal_type":ptype_sig[1] if ptype_sig else "",
            "publication_type_signal_strength":ptype_strength or "","vetoed_publication_type_signals":";".join(vetoed),
            "research_publication_types":";".join(research),"signals_conflict":conflict,"watchlist_titles":";".join(watch),
            "review_queue":bool(reasons),"review_reasons":";".join(reasons),"abstract_chars":abstract_chars,"has_abstract":abstract_chars>0}

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description="IA-010 deterministic record-type triage of canonical works.")
    ap.add_argument("--works-csv",required=True,type=Path); ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--long-abstract-chars",type=int,default=LONG_ABSTRACT_CHARS)
    ap.add_argument("--expected-works",type=int,default=0)
    a=ap.parse_args(); src=a.works_csv; out=a.out.resolve()
    if not src.exists():raise SystemExit(f"{src} does not exist")
    if out==src.resolve().parent or out in src.resolve().parents:raise SystemExit(f"refusing to write into an input directory: {src} lives under --out {out}")
    try:df=pd.read_csv(src,low_memory=False)
    except pd.errors.EmptyDataError:raise SystemExit(f"{src} is empty; expected an IA-008 canonical_works.csv") from None
    missing=[c for c in ("work_id","title") if c not in df.columns]
    if missing:raise SystemExit(f"{src} is missing required column(s) {missing}")
    before=sha256_file(src); out.mkdir(parents=True,exist_ok=True)
    for c in ("canonical_paper_id","source_group","year","venue","doi","publication_types","abstract"):
        if c not in df.columns:df[c]=""
    df["work_id"]=df.work_id.astype(str)

    rows=[]
    for r in df.to_dict("records"):
        res=classify(r.get("title"),r.get("publication_types"),r.get("abstract"),long_abstract_chars=a.long_abstract_chars)
        rows.append({"work_id":s(r.get("work_id")),"canonical_paper_id":s(r.get("canonical_paper_id")),"source_group":s(r.get("source_group")),
                     "year":s(r.get("year")),"venue":s(r.get("venue")),"doi":s(r.get("doi")),"title":s(r.get("title")),
                     "publication_types":s(r.get("publication_types")),**res})
    types=pd.DataFrame(rows,columns=list(COLS)).sort_values("work_id",kind="stable").reset_index(drop=True)
    for c in ("is_research_paper","has_abstract","signals_conflict","review_queue"):types[c]=types[c].astype(bool)
    queue=types[types.review_queue].copy()
    types.to_csv(out/"work_record_types.csv",index=False); queue.to_csv(out/"record_type_review_queue.csv",index=False)

    nonpaper=types[~types.is_research_paper]; noabs=types[~types.has_abstract]
    by_group={}
    for g,gd in types.groupby("source_group",dropna=False):
        by_group[s(g) or "unknown"]={k:int(v) for k,v in sorted(gd.record_type.value_counts().items())}
    reasons=collections.Counter(x for v in queue.review_reasons for x in v.split(";") if x)
    summary={"triage_version":TRIAGE_VERSION,"input":{"path":str(src),"sha256":before,"rows":int(len(df))},
             "counts_by_record_type":{t:int((types.record_type==t).sum()) for t in TYPES if int((types.record_type==t).sum())},
             "counts_by_source_group_and_record_type":by_group,
             "confidence_by_record_type":{t:{c:int(((types.record_type==t)&(types.confidence==c)).sum()) for c in LEVELS if int(((types.record_type==t)&(types.confidence==c)).sum())} for t in TYPES if int((types.record_type==t).sum())},
             "signal_provenance":{"title_rule_counts":{k:int(v) for k,v in sorted(collections.Counter(x for x in types.title_rule if x).items())},
                                  "publication_type_signal_counts":{k:int(v) for k,v in sorted(collections.Counter(x for x in types.publication_type_signal if x).items())},
                                  "vetoed_publication_type_counts":{k:int(v) for k,v in sorted(collections.Counter(x for v in types.vetoed_publication_type_signals for x in v.split(";") if x).items())},
                                  "watchlist_counts":{k:int(v) for k,v in sorted(collections.Counter(x for v in types.watchlist_titles for x in v.split(";") if x).items())},
                                  "works_without_publication_types":int(types.publication_types.map(lambda x:not ptype_tokens(x)).sum()),
                                  "non_papers_from_title_evidence_only":int((nonpaper.title_rule.ne("")&nonpaper.publication_type_signal.eq("")).sum())},
             "abstract_status":{"works_without_abstract":int(len(noabs)),"non_papers_without_abstract":int((~noabs.is_research_paper).sum()),
                                "non_paper_types_without_abstract":{k:int(v) for k,v in sorted(collections.Counter(noabs.loc[~noabs.is_research_paper,"record_type"]).items())},
                                "research_papers_without_abstract":int(noabs.is_research_paper.sum())},
             "denominators":{"canonical_works_original":int(len(types)),"non_paper_records":int(len(nonpaper)),
                             "revised_paper_denominator":int(types.is_research_paper.sum()),
                             "invariant":f"{len(types)} canonical works = {int(types.is_research_paper.sum())} research papers + {len(nonpaper)} non-paper records",
                             "note":"Non-paper records are labelled and retained, never deleted. Frozen retrieval provenance (3,768 retained, 391 recovered, 4,159 record universe, 4,136 canonical works) is unchanged; only the reported paper denominator differs."},
             "review_queue":{"rows":int(len(queue)),"non_papers_awaiting_confirmation":int((~queue.is_research_paper).sum()),
                             "papers_flagged_for_a_second_look":int(queue.is_research_paper.sum()),
                             "reasons":{k:int(v) for k,v in sorted(reasons.items())}},
             "principle":"Deterministic, high-precision in the non-paper direction. Anchored title patterns only; a contradicted or weak signal resolves to research_paper plus human review rather than exclusion. No keep, core, bridge, work-link or abstract status is mutated."}
    if a.expected_works:summary["denominators"]["expected_canonical_works"]=a.expected_works; summary["denominators"]["complete"]=len(types)==a.expected_works
    (out/"record_type_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    after=sha256_file(src)
    if after!=before:raise SystemExit("input canonical works CSV changed during triage")
    print(json.dumps({k:summary[k] for k in ("counts_by_record_type","counts_by_source_group_and_record_type","abstract_status","denominators","review_queue")},indent=2))
if __name__=="__main__":main()
