#!/usr/bin/env python3
"""Replace wrong PDFs for known catalog mismatches. Patches those catalog rows only.

Does not run --ingest-manual. Does not rebuild the 1,806-work union.
Verifies title/DOI on the first pages before overwriting files/<stem>.pdf.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
import collect_corpus_pdfs as P  # noqa: E402

MISMATCHES = ROOT / "postanalysis/registry/pdf_extract_mismatches.csv"
CATALOG = ROOT / "postanalysis/pdfs/paper_links.csv"
PROGRESS = ROOT / "postanalysis/pdfs/pdf_progress.jsonl"
FILES = ROOT / "postanalysis/pdfs/files"
QUARANTINE = ROOT / "postanalysis/pdfs/mismatch_quarantine"
SUMMARY = ROOT / "postanalysis/pdfs/pdf_summary.json"
CORE = ROOT / "postanalysis/registry/sota_history_core_labeled.csv"
REPORT = ROOT / "postanalysis/registry/pdf_mismatch_repair_report.json"
FOLLOWUP = ROOT / "postanalysis/registry/pdf_mismatch_direct_search_followup.csv"
AUDIT = ROOT / "postanalysis/pdfs/direct_search_audit.csv"

# Same-paper OA/preprint URLs. Catalog pdf_url is often a mismatched Europe PMC render.
# arXiv IDs 2208.0479 / 2608.1929 were truncated (missing a trailing 0).
EXTRA_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "work_de90f3f542a40fe0": [
        ("https://www.biorxiv.org/content/10.1101/372607.full.pdf", "biorxiv_preprint"),
    ],
    "work_791ccba206b1bbdc": [
        ("https://arxiv.org/pdf/2208.04790.pdf", "arxiv_full_id"),
    ],
    "work_020893805fee7188": [
        ("https://arxiv.org/pdf/2608.19290.pdf", "arxiv_full_id"),
    ],
    "work_6cb6b38366a67f63": [
        ("https://arxiv.org/pdf/2405.06110.pdf", "arxiv_preprint"),
    ],
    "work_4f923dc785f0b321": [
        ("https://www.biorxiv.org/content/10.1101/2019.12.13.875971.full.pdf", "biorxiv_preprint"),
    ],
    "work_c6b4755fa98e0894": [
        ("https://www.biorxiv.org/content/10.1101/460618.full.pdf", "biorxiv_preprint"),
    ],
}

DOI_IN_URL_RE = re.compile(r"10\.\d{4,9}/[^\s/?#]+")
STOP = {
    "the", "and", "for", "with", "from", "into", "that", "this", "than",
    "then", "their", "them", "they", "are", "was", "were", "its", "via",
}
SKIP_URL_RE = re.compile(
    r"pdf=render|europepmc\.org/articles/.+\?pdf="
    r"|springer-static/esm|/esm/|supplementary[-_]information",
    re.I,
)
PUBLISHER_HOST_RE = re.compile(
    r"sciencedirect\.com|cell\.com/article/.+/pdf|nature\.com/articles/.+\.pdf|"
    r"science\.org/doi/pdf|onlinelibrary\.wiley\.com",
    re.I,
)
META_PDF_RE = re.compile(
    r'<meta[^>]+(?:name|property)=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:name|property)=["\']citation_pdf_url',
    re.I,
)
REL_PDF_RE = re.compile(
    r'<link[^>]+type=["\']application/pdf["\'][^>]+href=["\']([^"\']+)',
    re.I,
)
HREF_PDF_RE = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)', re.I)
PAYWALL_HINTS = (
    ('id="paywall"', "paywall_id"),
    ("get access", "get_access"),
    ("purchase pdf", "purchase_pdf"),
    ("buy this article", "buy_article"),
    ("subscribe to access", "subscribe"),
    ("this article is locked", "locked"),
    ("institutional access", "institutional"),
)


def extra_dois_for(work_id: str) -> list[str]:
    out: list[str] = []
    for url, _src in EXTRA_CANDIDATES.get(work_id, []):
        m = DOI_IN_URL_RE.search(url.replace(".full.pdf", "").replace(".pdf", ""))
        if m:
            out.append(P.norm_doi(m.group(0)))
    return out


def fold_spaced_letters(text: str) -> str:
    return re.sub(r"\b([A-Za-z]) ([A-Za-z]{2,})\b", r"\1\2", text)


def strip_preprint_header(text: str) -> str:
    t = re.sub(
        r"(?is)bioRxiv preprint doi:.*?license\.",
        " ",
        text,
        count=1,
    )
    t = re.sub(r"(?is)arXiv:\d{4}\.\d{4,5}[^\n]*", " ", t)
    return t


def content_tokens(title: str) -> list[str]:
    return [
        t
        for t in P.title_tokens(title)
        if len(t) > 3 and t not in STOP
    ]


def content_window_hit(title: str, text: str, min_tokens: int = 4) -> bool:
    wt = content_tokens(title)
    gt = P.title_tokens(fold_spaced_letters(text))
    n = min(len(wt), max(min_tokens, 3))
    if len(wt) < 3 or len(gt) < n:
        return False
    needles = [tuple(wt[j : j + n]) for j in range(len(wt) - n + 1)]
    return any(tuple(gt[i : i + n]) in needles for i in range(len(gt) - n + 1))


def token_coverage(title: str, text: str) -> float:
    toks = content_tokens(title)
    if not toks:
        return 0.0
    hay = P.norm_title(fold_spaced_letters(text))
    return sum(1 for t in toks if t in hay) / len(toks)


def verify_pdf(path: Path, title: str, doi: str, extra_dois: list[str] | None = None) -> tuple[bool, str]:
    head = P.pdf_first_page_text(path)
    if re.search(r"(?i)in the format provided by\s+the\s+authors|supplementary materials?:", head[:800]):
        return False, "supplement_not_article"
    folded = fold_spaced_letters(head)
    compact_raw = folded[:2500].lower().replace(" ", "").replace("\n", "")
    extra = [P.norm_doi(d) for d in (extra_dois or []) if d]
    for ed in extra:
        if ed.replace(" ", "") in compact_raw:
            return True, "preprint_doi"
    front = strip_preprint_header(folded)[:2500]
    compact_front = front.lower().replace(" ", "").replace("\n", "")
    nd = P.norm_doi(doi)
    header_block = folded[:1200].lower().replace(" ", "").replace("\n", "")
    doi_in_header = bool(nd and nd.replace(" ", "") in header_block)
    if P.title_token_window_hit(title, front, min_tokens=min(4, max(3, len(P.title_tokens(title))))):
        return True, "token_window"
    if content_window_hit(title, front, min_tokens=4):
        return True, "content_window"
    sim = P.title_sim(title, front[:800])
    if doi_in_header and sim >= 0.25:
        return True, f"doi+sim={sim:.2f}"
    if sim >= 0.55:
        return True, f"sim={sim:.2f}"
    cov = token_coverage(title, front)
    return False, f"no_match cov={cov:.2f} sim={sim:.2f} head={head[:120]!r}"


def skip_url(url: str) -> bool:
    return bool(SKIP_URL_RE.search(url or ""))


def europepmc_doi_cands(fetcher: P.Fetcher, doi: str, title: str) -> list[tuple[str, str]]:
    if not doi:
        return []
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": f'DOI:"{doi}"', "format": "json", "pageSize": "5"}
    )
    try:
        data = fetcher.get_json(url)
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    for row in ((data.get("resultList") or {}).get("result") or []):
        if not isinstance(row, dict):
            continue
        got_doi = P.norm_doi(row.get("doi"))
        got_title = P.record_title(row)
        if got_doi and doi and got_doi != P.norm_doi(doi):
            continue
        if got_title and P.title_sim(title, got_title) < 0.7 and got_doi != P.norm_doi(doi):
            continue
        pmcid = P.s(row.get("pmcid"))
        if pmcid:
            out.append((f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/", "pmc_doi_search"))
        for cand_url, src in P.europepmc_candidates({"resultList": {"result": [row]}}):
            if not skip_url(cand_url):
                out.append((cand_url, src))
    return P._dedupe_cands(out)


def unpaywall_cands(fetcher: P.Fetcher, doi: str) -> list[tuple[str, str]]:
    if not doi or not fetcher.email:
        return []
    url = "https://api.unpaywall.org/v2/" + urllib.parse.quote(doi, safe="/") + "?" + urllib.parse.urlencode(
        {"email": fetcher.email}
    )
    try:
        data = fetcher.get_json(url)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    ranked: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    blobs = []
    if data.get("best_oa_location"):
        blobs.append(data["best_oa_location"])
    blobs.extend(data.get("oa_locations") or [])
    for loc in blobs:
        if not isinstance(loc, dict):
            continue
        host = P.s(loc.get("host_type")).lower()
        rank = {"preprint": 0, "repository": 1}.get(host, 2)
        for key in ("url_for_pdf", "url"):
            cand = P.normalize_candidate_url(P.s(loc.get(key)))
            if not cand or cand in seen or skip_url(cand):
                continue
            if key == "url" and not P.looks_like_pdf_url(cand) and host not in {"repository", "preprint"}:
                continue
            seen.add(cand)
            src = "unpaywall_repo" if host in {"repository", "preprint"} else "unpaywall"
            ranked.append((rank, cand, src))
    ranked.sort(key=lambda r: r[0])
    return [(url, src) for _rank, url, src in ranked]


def openalex_cands(fetcher: P.Fetcher, doi: str) -> list[tuple[str, str]]:
    if not doi:
        return []
    url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi)
    if fetcher.email:
        url += "?" + urllib.parse.urlencode({"mailto": fetcher.email})
    try:
        data = fetcher.get_json(url)
    except Exception:
        return []
    return [(u, s) for u, s in P.openalex_candidates(data if isinstance(data, dict) else {}) if not skip_url(u)]


def arxiv_id_variants(arxiv: str) -> list[str]:
    ax = P.norm_arxiv(arxiv)
    if not ax:
        return []
    out = [ax]
    if re.fullmatch(r"\d{4}\.\d{4}", ax):
        out.append(ax + "0")
    return out


def openalex_title_cands(fetcher: P.Fetcher, title: str, doi: str, year: str) -> list[tuple[str, str]]:
    if not title:
        return []
    params = {"search": title[:180], "per-page": "5"}
    if fetcher.email:
        params["mailto"] = fetcher.email
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    try:
        data = fetcher.get_json(url)
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    our_doi = P.norm_doi(doi)
    for work in data.get("results") or []:
        if not isinstance(work, dict):
            continue
        got_title = P.s(work.get("display_name"))
        got_doi = P.norm_doi((work.get("doi") or "").replace("https://doi.org/", ""))
        sim = P.title_sim(title, got_title)
        doi_hit = bool(our_doi and got_doi and our_doi == got_doi)
        if not doi_hit and sim < P.TITLE_SIM_FLOOR:
            continue
        if not doi_hit and not P.year_ok(year, (work.get("publication_year") or "")):
            continue
        loc = work.get("best_oa_location") or {}
        pdf = P.s(loc.get("pdf_url"))
        if pdf and not skip_url(pdf):
            out.append((pdf, "openalex_title"))
        for loc in work.get("locations") or []:
            if not isinstance(loc, dict):
                continue
            pdf = P.s(loc.get("pdf_url"))
            if pdf and not skip_url(pdf):
                out.append((pdf, "openalex_title"))
    return P._dedupe_cands(out)


def s2_cands(fetcher: P.Fetcher, doi: str, paper_id: str) -> list[tuple[str, str]]:
    keys = []
    if paper_id:
        keys.append(paper_id)
    if doi:
        keys.append("DOI:" + doi)
    out: list[tuple[str, str]] = []
    for key in keys:
        url = "https://api.semanticscholar.org/graph/v1/paper/" + urllib.parse.quote(key) + "?fields=openAccessPdf,title,externalIds"
        try:
            data = fetcher.get_json(url)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        oa = data.get("openAccessPdf") or {}
        pdf = P.s(oa.get("url"))
        if pdf and not skip_url(pdf):
            out.append((pdf, "s2_oa"))
        break
    return P._dedupe_cands(out)


def pmid_pmc_cands(fetcher: P.Fetcher, pmid: str) -> list[tuple[str, str]]:
    if not pmid:
        return []
    url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?" + urllib.parse.urlencode(
        {"ids": pmid, "format": "json"}
    )
    try:
        data = fetcher.get_json(url)
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    for rec in data.get("records") or []:
        pmcid = P.s(rec.get("pmcid"))
        if pmcid:
            out.append((f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/", "pmc_idconv"))
    return out


def candidates_for(row: dict[str, str], fetcher: P.Fetcher) -> list[tuple[str, str]]:
    wid = row["work_id"]
    doi = P.norm_doi(row.get("doi"))
    arxiv = P.norm_arxiv(row.get("arxiv_id"))
    title = row.get("title") or ""
    year = P.s(row.get("year"))
    cands: list[tuple[str, str]] = []
    cands.extend(EXTRA_CANDIDATES.get(wid, []))
    for ax in arxiv_id_variants(arxiv):
        cands.append((f"https://arxiv.org/pdf/{ax}.pdf", "arxiv"))
        cands.append((f"https://export.arxiv.org/pdf/{ax}.pdf", "arxiv_export"))
    if doi.startswith("10.1101/") or doi.startswith("10.64898/"):
        cands.append((f"https://www.biorxiv.org/content/{doi}.full.pdf", "biorxiv"))
    if doi.startswith("10.3389/"):
        cands.append((f"https://www.frontiersin.org/articles/{doi}/pdf", "frontiers"))
    cands.extend(unpaywall_cands(fetcher, doi))
    cands.extend(s2_cands(fetcher, doi, P.s(row.get("canonical_paper_id"))))
    cands.extend(pmid_pmc_cands(fetcher, P.s(row.get("pmid"))))
    cands.extend(openalex_cands(fetcher, doi))
    cands.extend(openalex_title_cands(fetcher, title, doi, year))
    cands.extend(europepmc_doi_cands(fetcher, doi, title))
    return P._dedupe_cands([(u, s) for u, s in cands if u and not skip_url(u)])


def pdf_urls_from_html(data: bytes, base: str) -> list[str]:
    text = data.decode("utf-8", "replace")
    out: list[str] = []
    for m in META_PDF_RE.finditer(text):
        out.append(urllib.parse.urljoin(base, m.group(1) or m.group(2)))
    for m in REL_PDF_RE.finditer(text):
        out.append(urllib.parse.urljoin(base, m.group(1)))
    for m in HREF_PDF_RE.finditer(text):
        out.append(urllib.parse.urljoin(base, m.group(1)))
    return [u for u, _src in P._dedupe_cands([(u, "html") for u in out if u and not skip_url(u)])]


def html_paywall_evidence(data: bytes) -> str:
    text = data.decode("utf-8", "replace")[:24000].lower()
    for needle, label in PAYWALL_HINTS:
        if needle in text:
            return label
    return ""


def publisher_guess_cands(doi: str) -> list[tuple[str, str]]:
    d = P.norm_doi(doi)
    if not d:
        return []
    out: list[tuple[str, str]] = []
    if d.startswith("10.1038/"):
        out.append((f"https://www.nature.com/articles/{d.split('/', 1)[1]}.pdf", "nature_pdf"))
    if d.startswith("10.1126/"):
        out.append((f"https://www.science.org/doi/pdf/{d}", "science_pdf"))
    if d.startswith("10.3389/"):
        out.append((f"https://www.frontiersin.org/articles/{d}/pdf", "frontiers"))
    if d.startswith("10.7554/elife.") or d.startswith("10.7554/eLife."):
        art = d.rsplit(".", 1)[-1]
        out.append((f"https://cdn.elifesciences.org/articles/{art}/elife-{art}-v1.pdf", "elife_cdn"))
    if d:
        out.append((f"https://doi.org/{d}", "doi_landing"))
    return out


def direct_search_candidates(row: dict[str, str], fetcher: P.Fetcher) -> tuple[list[tuple[str, str]], dict]:
    attempts: list[str] = []
    cands, meta = P.search_by_title_doi(fetcher, row, attempts)
    pubmed = P.lookup_pubmed(
        fetcher,
        {
            "doi": P.norm_doi(row.get("doi")),
            "pmid": P.s(row.get("pmid")),
            "title": row.get("title") or "",
        },
        attempts,
        include_search=True,
    )
    cands.extend(pubmed)
    cands.extend(publisher_guess_cands(P.norm_doi(row.get("doi"))))
    meta["attempts"] = attempts
    filtered = [(u, s) for u, s in cands if u and not skip_url(u)]
    return P._dedupe_cands(filtered), meta


def fetch_pdf_bytes(fetcher: P.Fetcher, url: str, src: str) -> tuple[bytes | None, str]:
    tries = 1 if PUBLISHER_HOST_RE.search(url) else 3
    last = f"{src}:no_response"
    for attempt in range(tries):
        try:
            data = fetcher.get_bytes(url)
            return data, ""
        except urllib.error.HTTPError as e:
            last = f"{src}:HTTP{e.code}"
            if e.code in {302, 301, 303, 307, 308, 403, 404, 410}:
                return None, last
            if e.code in {429, 500, 502, 503}:
                time.sleep(2.0 * (attempt + 1))
                continue
            return None, last
        except Exception as e:
            last = f"{src}:{type(e).__name__}"
            time.sleep(1.0 * (attempt + 1))
    return None, last


def accept_pdf(data: bytes, dest: Path, title: str, doi: str, extra_dois: list[str], url: str, src: str) -> dict | None:
    if P.looks_like_html(data) or not P.looks_like_pdf(data):
        return None
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    ok, why = verify_pdf(tmp_path, title, doi, extra_dois)
    tmp_path.unlink(missing_ok=True)
    if not ok:
        return {"error": f"{src}:verify_fail:{why}"}
    dest.write_bytes(data)
    return {
        "ok": True,
        "pdf_url": url,
        "pdf_source": src,
        "bytes": len(data),
        "sha256": P.sha256_bytes(data),
        "verify": why,
        "error": "",
    }


def try_download(
    fetcher: P.Fetcher,
    cands: list[tuple[str, str]],
    dest: Path,
    title: str,
    doi: str,
    extra_dois: list[str],
) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = "no_candidates"
    paywall = ""
    publisher_denied = ""
    pending = list(cands)
    seen: set[str] = set()
    while pending:
        url, src = pending.pop(0)
        if not url or url in seen or skip_url(url):
            continue
        seen.add(url)
        data, err = fetch_pdf_bytes(fetcher, url, src)
        if data is None:
            last = err
            if err.endswith("HTTP403") or err.endswith("HTTP401"):
                publisher_denied = err
            continue
        if P.looks_like_html(data):
            ev = html_paywall_evidence(data)
            if ev:
                paywall = ev
            nested = pdf_urls_from_html(data, url)
            for nurl in nested[:8]:
                if nurl not in seen:
                    pending.insert(0, (nurl, src + "_html"))
            last = f"{src}:html"
            continue
        got = accept_pdf(data, dest, title, doi, extra_dois, url, src)
        if got and got.get("ok"):
            return got
        last = (got or {}).get("error") or f"{src}:not_pdf"
    out = {"ok": False, "error": last}
    if paywall:
        out["paywall_evidence"] = paywall
    if publisher_denied:
        out["publisher_denied"] = publisher_denied
    return out


def patch_catalog_row(rows: list[dict[str, str]], work_id: str, rec: dict) -> None:
    for row in rows:
        if row["work_id"] != work_id:
            continue
        row["pdf_url"] = rec["pdf_url"]
        row["pdf_source"] = rec["pdf_source"]
        row["pdf_status"] = "downloaded"
        row["local_path"] = rec["local_path"]
        row["bytes"] = str(rec["bytes"])
        row["sha256"] = rec["sha256"]
        row["attempts"] = rec.get("attempts", "mismatch_repair")
        row["error"] = ""
        row["ts"] = P.now_ts()
        return


def mark_unresolved(rows: list[dict[str, str]], work_id: str, error: str) -> None:
    for row in rows:
        if row["work_id"] != work_id:
            continue
        row["pdf_status"] = "paywall"
        row["local_path"] = ""
        row["bytes"] = "0"
        row["sha256"] = ""
        row["error"] = error
        row["ts"] = P.now_ts()
        return


def rewrite_summary(catalog_rows: list[dict[str, str]]) -> None:
    statuses = Counter(r.get("pdf_status") or "unprocessed" for r in catalog_rows)
    sources = Counter(r.get("pdf_source") for r in catalog_rows if r.get("pdf_source"))
    summary = {
        "corpus_works": len(catalog_rows),
        "with_landing_url": sum(1 for r in catalog_rows if r.get("landing_url")),
        "with_doi": sum(1 for r in catalog_rows if r.get("doi")),
        "with_pdf_url": sum(1 for r in catalog_rows if r.get("pdf_url")),
        "downloaded": sum(1 for r in catalog_rows if r.get("pdf_status") == "downloaded"),
        "status_counts": dict(sorted(statuses.items())),
        "pdf_sources": dict(sorted(sources.items())),
        "note": "Recomputed from paper_links.csv after targeted mismatch repair. Catalog N unchanged.",
    }
    prior = {}
    if SUMMARY.exists():
        try:
            prior = json.loads(SUMMARY.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prior = {}
    for k in ("title_similarity_floor", "out", "direct_search_audit_rows", "direct_search_matches"):
        if k in prior:
            summary[k] = prior[k]
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def file_stem_name(row: dict[str, str], fallback: str) -> str:
    stem = Path(row.get("stem") or fallback or "").name
    return stem if stem.endswith(".pdf") else f"{stem}.pdf"


def is_resolved(row: dict[str, str]) -> bool:
    if row.get("pdf_status") != "downloaded":
        return False
    return (FILES / file_stem_name(row, "")).exists()


def mismatch_queue(catalog_by_id: dict[str, dict[str, str]]) -> list[str]:
    """Mismatch rows that still need a replacement. Skip already-resolved files."""
    wanted: list[str] = []
    for r in csv.DictReader(MISMATCHES.open()):
        if r.get("repair_status") == "resolved":
            continue
        crow = catalog_by_id.get(r["work_id"]) or {}
        if is_resolved(crow):
            continue
        wanted.append(r["work_id"])
    return wanted


def mark_mismatch_resolved(work_ids: list[str]) -> None:
    if not work_ids:
        return
    done = set(work_ids)
    rows = list(csv.DictReader(MISMATCHES.open()))
    fields = list(rows[0].keys())
    if "repair_status" not in fields:
        fields.append("repair_status")
    for r in rows:
        if r["work_id"] in done:
            r["repair_status"] = "resolved"
        else:
            r.setdefault("repair_status", r.get("repair_status") or "unresolved")
    with MISMATCHES.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def classify_direct_failure(got: dict, n_cands: int) -> str:
    err = got.get("error") or ""
    denied = got.get("publisher_denied") or ""
    blob = f"{denied} {err}"
    if got.get("paywall_evidence") and ("HTTP403" in blob or "HTTP401" in blob):
        return "paywall_confirmed"
    if any(k in blob for k in ("nature_pdf:HTTP403", "science_pdf:HTTP403", "unpaywall:HTTP403")):
        return "paywall_confirmed"
    if got.get("paywall_evidence") and n_cands <= 3:
        return "paywall_confirmed"
    return "parser_miss"


def append_audit(row: dict[str, str], rec: dict, meta: dict) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    exists = AUDIT.exists()
    with AUDIT.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=P.AUDIT_FIELDS)
        if not exists:
            w.writeheader()
        w.writerow({
            "work_id": rec["work_id"],
            "title": (row.get("title") or "")[:200],
            "doi": rec.get("doi") or "",
            "year": row.get("year") or "",
            "matched_title": meta.get("matched_title") or "",
            "matched_doi": meta.get("matched_doi") or "",
            "title_similarity": meta.get("title_similarity") or "",
            "match_method": meta.get("match_method") or "",
            "search_api": meta.get("search_api") or "direct_search",
            "pdf_url": rec.get("pdf_url") or "",
            "pdf_status": rec.get("pdf_status") or "",
            "local_path": rec.get("local_path") or "",
            "landing_url": row.get("landing_url") or row.get("doi_url") or "",
        })


def write_catalog(catalog: list[dict[str, str]]) -> None:
    with CATALOG.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(catalog[0].keys()))
        w.writeheader()
        w.writerows(catalog)


def direct_search_main() -> None:
    email = os.environ.get("CONNECTOMICS_MAILTO") or os.environ.get("UNPAYWALL_EMAIL") or ""
    if not email:
        raise SystemExit("set UNPAYWALL_EMAIL (Unpaywall requires a contact address)")
    fetcher = P.Fetcher(email=email, timeout=60, sleep=0.4, arxiv_sleep=3.0)
    catalog = list(csv.DictReader(CATALOG.open()))
    by_id = {r["work_id"]: r for r in catalog}
    core = {r["work_id"]: r for r in csv.DictReader(CORE.open())}
    wanted = mismatch_queue(by_id)
    downloaded: list[str] = []
    paywall: list[dict] = []
    parser_miss: list[dict] = []
    followup: list[dict] = []
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    with PROGRESS.open("a", encoding="utf-8") as log:
        for i, wid in enumerate(wanted, start=1):
            row = {**(core.get(wid) or {}), **(by_id.get(wid) or {})}
            name = file_stem_name(row, "")
            dest = FILES / name
            title = row.get("title") or ""
            doi = row.get("doi") or ""
            extras = extra_dois_for(wid)
            cands, meta = direct_search_candidates(row, fetcher)
            got = try_download(fetcher, cands, dest, title, doi, extras)
            rec = {
                "ts": P.now_ts(),
                "work_id": wid,
                "title": title[:200],
                "doi": doi,
                "stem": Path(name).stem,
                "pdf_status": "downloaded" if got.get("ok") else "mismatch_unresolved",
                "pdf_url": got.get("pdf_url", ""),
                "pdf_source": got.get("pdf_source", "direct_search"),
                "local_path": dest.as_posix() if got.get("ok") else "",
                "bytes": got.get("bytes", 0),
                "sha256": got.get("sha256", ""),
                "attempts": "mismatch_direct_search",
                "error": got.get("error", ""),
                "verify": got.get("verify", ""),
                "match_method": meta.get("match_method") or "",
                "search_api": meta.get("search_api") or "",
            }
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if got.get("ok"):
                rec["pdf_status"] = "downloaded"
                patch_catalog_row(catalog, wid, rec)
                for crow in catalog:
                    if crow["work_id"] == wid:
                        if meta.get("match_method"):
                            crow["search_match"] = "true"
                            crow["match_method"] = str(meta.get("match_method") or "")
                            crow["matched_title"] = str(meta.get("matched_title") or "")
                            crow["matched_doi"] = str(meta.get("matched_doi") or "")
                            crow["title_similarity"] = str(meta.get("title_similarity") or "")
                            crow["search_api"] = str(meta.get("search_api") or "crossref")
                        break
                downloaded.append(wid)
                outcome = "downloaded"
                print(f"[{i}/{len(wanted)}] {wid} OK {got.get('pdf_source')} {got.get('verify')}", flush=True)
            else:
                outcome = classify_direct_failure(got, len(cands))
                if dest.exists():
                    dest.replace(QUARANTINE / dest.name)
                mark_unresolved(catalog, wid, f"{outcome}:{got.get('error','')}")
                item = {
                    "work_id": wid,
                    "doi": doi,
                    "title": title[:180],
                    "venue": row.get("venue") or "",
                    "outcome": outcome,
                    "evidence": got.get("paywall_evidence") or got.get("publisher_denied") or got.get("error") or "",
                    "n_cands": len(cands),
                    "pdf_url": (cands[0][0] if cands else ""),
                    "landing_url": row.get("landing_url") or row.get("doi_url") or "",
                }
                followup.append(item)
                if outcome == "paywall_confirmed":
                    paywall.append(item)
                else:
                    parser_miss.append(item)
                print(f"[{i}/{len(wanted)}] {wid} {outcome} {item['evidence'][:80]}", flush=True)
            append_audit(row, rec, meta)
    write_catalog(catalog)
    mark_mismatch_resolved(downloaded)
    rewrite_summary(catalog)
    with FOLLOWUP.open("w", newline="", encoding="utf-8") as fh:
        fields = ["work_id", "doi", "title", "venue", "outcome", "evidence", "n_cands", "pdf_url", "landing_url"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(followup)
    (ROOT / "postanalysis/registry/pdf_mismatch_direct_search_report.json").write_text(
        json.dumps({
            "n_tried": len(wanted),
            "n_downloaded": len(downloaded),
            "n_paywall_confirmed": len(paywall),
            "n_parser_miss": len(parser_miss),
            "downloaded": downloaded,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "direct_search tried", len(wanted),
        "downloaded", len(downloaded),
        "paywall_confirmed", len(paywall),
        "parser_miss", len(parser_miss),
    )


def repair_all_main() -> None:
    email = os.environ.get("CONNECTOMICS_MAILTO") or os.environ.get("UNPAYWALL_EMAIL") or ""
    if not email:
        raise SystemExit("set UNPAYWALL_EMAIL (Unpaywall requires a contact address)")
    fetcher = P.Fetcher(email=email, timeout=60, sleep=0.4, arxiv_sleep=3.0)
    catalog = list(csv.DictReader(CATALOG.open()))
    by_id = {r["work_id"]: r for r in catalog}
    wanted = mismatch_queue(by_id)
    core = {r["work_id"]: r for r in csv.DictReader(CORE.open())}
    repaired: list[str] = []
    restored: list[str] = []
    skipped_ok: list[str] = []
    failed: list[tuple[str, str]] = []
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    with PROGRESS.open("a", encoding="utf-8") as log:
        for i, wid in enumerate(wanted, start=1):
            row = by_id.get(wid) or core.get(wid)
            if not row:
                failed.append((wid, "not_in_catalog"))
                continue
            name = file_stem_name(row, core.get(wid, {}).get("stem") or "")
            dest = FILES / name
            qpath = QUARANTINE / name
            title = row.get("title") or core.get(wid, {}).get("title") or ""
            doi = row.get("doi") or core.get(wid, {}).get("doi") or ""
            extras = extra_dois_for(wid)
            if dest.exists():
                ok, why = verify_pdf(dest, title, doi, extras)
                if ok:
                    print(f"[{i}/{len(wanted)}] {wid} SKIP already_matches {why}", flush=True)
                    skipped_ok.append(wid)
                    continue
            if (not dest.exists()) and qpath.exists():
                ok, why = verify_pdf(qpath, title, doi, extras)
                if ok:
                    dest.write_bytes(qpath.read_bytes())
                    rec = {
                        "ts": P.now_ts(),
                        "work_id": wid,
                        "title": title[:200],
                        "doi": doi,
                        "stem": Path(name).stem,
                        "pdf_status": "downloaded",
                        "pdf_url": row.get("pdf_url") or "",
                        "pdf_source": row.get("pdf_source") or "quarantine_restore",
                        "local_path": dest.as_posix(),
                        "bytes": dest.stat().st_size,
                        "sha256": P.sha256_bytes(dest.read_bytes()),
                        "attempts": "mismatch_repair",
                        "error": "",
                        "verify": why,
                    }
                    log.write(json.dumps(rec) + "\n")
                    log.flush()
                    patch_catalog_row(catalog, wid, rec)
                    restored.append(wid)
                    print(f"[{i}/{len(wanted)}] {wid} RESTORE {why}", flush=True)
                    continue
            cands = candidates_for({**core.get(wid, {}), **row}, fetcher)
            got = try_download(fetcher, cands, dest, title, doi, extras)
            rec = {
                "ts": P.now_ts(),
                "work_id": wid,
                "title": title[:200],
                "doi": doi,
                "stem": Path(name).stem,
                "pdf_status": "downloaded" if got.get("ok") else "mismatch_unresolved",
                "pdf_url": got.get("pdf_url", ""),
                "pdf_source": got.get("pdf_source", ""),
                "local_path": dest.as_posix() if got.get("ok") else "",
                "bytes": got.get("bytes", 0),
                "sha256": got.get("sha256", ""),
                "attempts": "mismatch_repair",
                "error": got.get("error", ""),
                "verify": got.get("verify", ""),
            }
            log.write(json.dumps(rec) + "\n")
            log.flush()
            print(f"[{i}/{len(wanted)}] {wid} {'OK' if got.get('ok') else 'FAIL'} {got.get('pdf_source') or got.get('error')}", flush=True)
            if got.get("ok"):
                patch_catalog_row(catalog, wid, rec)
                repaired.append(wid)
            else:
                failed.append((wid, got.get("error", "")))
                if dest.exists():
                    dest.replace(qpath)
                mark_unresolved(catalog, wid, rec.get("error", "mismatch_unresolved"))
    with CATALOG.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(catalog[0].keys()))
        w.writeheader()
        w.writerows(catalog)
    mark_mismatch_resolved(repaired + restored)
    rewrite_summary(catalog)
    report = {
        "repaired": repaired,
        "restored": restored,
        "already_ok": skipped_ok,
        "failed": [{"work_id": w, "error": e} for w, e in failed],
        "n_repaired": len(repaired),
        "n_restored": len(restored),
        "n_already_ok": len(skipped_ok),
        "n_failed": len(failed),
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "repaired", len(repaired),
        "restored", len(restored),
        "already_ok", len(skipped_ok),
        "failed", len(failed),
    )
    for wid, err in failed:
        print(" FAIL", wid, err)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--direct-search",
        action="store_true",
        help="Retry unresolved mismatch rows via Crossref/OpenAlex/EuropePMC/PubMed landing parse.",
    )
    args = ap.parse_args()
    if args.direct_search:
        direct_search_main()
    else:
        repair_all_main()


if __name__ == "__main__":
    main()
