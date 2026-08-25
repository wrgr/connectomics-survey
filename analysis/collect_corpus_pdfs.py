#!/usr/bin/env python3
"""Record paper links for the frozen inclusive corpus and download OA PDFs.

Does not mutate checkpoint or work-reconciliation files. The default work set is the
union of the v2 checkpoint inclusive corpus and the v3 full inclusive corpus
(`corpus_full_works.csv`), minus works listed as `out_of_scope` in
`human_review_decisions.csv`. Identifiers come from those rows plus `work_versions.csv`
and canonical works metadata.

Filenames prefer a DOI stem (`doi_10.1038_s41586-026-10735-w.pdf`), then arXiv,
PMID, and `work_<id>` if nothing else is available. Progress is append-only JSONL
so a rerun skips successful downloads and retries the rest.

Drop folders `manual_OA/` and `manual_closed/` hold hand-retrieved PDFs. `--ingest-manual`
copies them into `files/` under the corpus stem, logs `pdf_source=manual_oa` or
`manual_closed`, and rewrites the catalog from the progress stream. Matching uses
the corpus stem, DOI, MDPI article id (`photonics-06-00066`), then title.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html as htmlmod
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from human_review import excluded_work_ids

UA_BASE = "connectomics-survey/pdf-collect"
PROGRESS_FILE = "pdf_progress.jsonl"
CATALOG_FILE = "paper_links.csv"
AUDIT_FILE = "direct_search_audit.csv"
SUMMARY_FILE = "pdf_summary.json"
FILES_DIR = "files"
MANUAL_OA_DIR = "manual_OA"
MANUAL_CLOSED_DIR = "manual_closed"
MANUAL_DROP_DIRS = (
    (MANUAL_OA_DIR, "manual_oa"),
    (MANUAL_CLOSED_DIR, "manual_closed"),
)
TITLE_SIM_FLOOR = 0.92
TITLE_PREFIX_MIN = 32
DOI_IN_TEXT_RE = re.compile(r"10\.\d{4,9}/[^\s<>\"']+", re.I)
MDPI_ARTICLE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]+)-(\d+)-(\d+)$")
WILEY_YEAR_RE = re.compile(r"^\d{4}$")
DOI_STEM_RE = re.compile(r"^doi_(10\.\d{4,9})_(.+)$", re.I)
VENUE_TAIL_RE = re.compile(
    r"\s+(cvprw|cvpr|iccv|eccv|wacv|neurips|nips|icml|aaai)\s+(\d{4})(?:\s+paper)?$",
    re.I,
)
TITLE_TOKEN_MIN = 6
TITLE_PREFIX = re.compile(
    r"^(?:viewpoint|review|perspective(?:\s+chapter)?|tutorial|editorial|commentary|special\s+issue|supplement\s+to|chapter\s+\d+[a-z]?(?:\s*[–—:-].*)?)\s*[:.\-–—]?\s*",
    re.I,
)
OA_SELECT = "id,doi,display_name,title,publication_year,open_access,best_oa_location,primary_location,locations,ids"
ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.(.+)$", re.I)
DOI_PREFIX_RE = re.compile(r"^https?://(?:dx\.)?doi\.org/|^doi:\s*", re.I)
SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
PMID_RE = re.compile(r"^\d+$")
PMC_ARTICLE_RE = re.compile(
    r"https?://(?:www\.)?(?:ncbi\.nlm\.nih\.gov/pmc|pmc\.ncbi\.nlm\.nih\.gov)/articles/(PMC\d+)",
    re.I,
)
EUROPEPMC_ART_RE = re.compile(r"europepmc\.org/articles/(PMC\d+)", re.I)
PMC_BARE_RE = re.compile(r"\bPMC(\d+)\b", re.I)
HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.I)
PMC_SUPPLEMENT_RE = re.compile(r"supplement|/bin/", re.I)
NCBI_TOOL = "connectomics-survey"
PDF_MAGIC = b"%PDF"
DEFAULT_CORPORA = (
    Path("postanalysis/checkpoint/corpus_inclusive.csv"),
    Path("postanalysis/llm_agent_v3/corpus_full_works.csv"),
)
DEFAULT_WORKS_CSV = Path("postanalysis/works/canonical_works.csv")
DEFAULT_SEED_WORKS_CSV = Path("postanalysis/works/manual_seed_works.csv")
CATALOG_FIELDS = [
    "work_id", "canonical_paper_id", "source_group", "decision", "year", "venue", "title",
    "doi", "pmid", "arxiv_id", "stem", "landing_url", "doi_url", "pmid_url", "arxiv_abs_url",
    "semantic_scholar_url", "pdf_url", "pdf_source", "pdf_status", "local_path", "bytes",
    "sha256", "search_match", "match_method", "matched_title", "matched_doi", "title_similarity",
    "search_api", "attempts", "error", "ts",
]
AUDIT_FIELDS = [
    "work_id", "title", "doi", "year", "matched_title", "matched_doi", "title_similarity",
    "match_method", "search_api", "pdf_url", "pdf_status", "local_path", "landing_url",
]


def s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v != v:
        return ""
    t = str(v).strip()
    return "" if t.lower() in {"", "nan", "none", "null"} else t


def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [{k: s(v) for k, v in row.items()} for row in csv.DictReader(fh)]


def union_corpus_rows(corpus_paths: list[Path], works_csv: Path | None = None) -> list[dict[str, str]]:
    """Union work_ids across corpus CSVs; fill DOI/title from canonical works when present."""
    order: list[str] = []
    rows: dict[str, dict[str, str]] = {}
    for path in corpus_paths:
        if not path.exists():
            raise SystemExit(f"missing corpus csv: {path}")
        for row in load_csv(path):
            wid = s(row.get("work_id"))
            if not wid:
                continue
            if wid not in rows:
                order.append(wid)
                rows[wid] = dict(row)
            else:
                for k, v in row.items():
                    if v and not s(rows[wid].get(k)):
                        rows[wid][k] = v
    fill_csvs = []
    if works_csv and Path(works_csv).exists():
        fill_csvs.append(Path(works_csv))
    if DEFAULT_SEED_WORKS_CSV.exists():
        fill_csvs.append(DEFAULT_SEED_WORKS_CSV)
    prefer = {"doi", "canonical_paper_id", "title", "abstract", "authors", "year", "venue", "source_group", "pmid"}
    for fill in fill_csvs:
        for row in load_csv(fill):
            wid = s(row.get("work_id"))
            if wid not in rows:
                continue
            for k, v in row.items():
                if not v:
                    continue
                if k in prefer or not s(rows[wid].get(k)):
                    rows[wid][k] = v
    return [rows[w] for w in order]


def read_progress(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        wid = s(rec.get("work_id"))
        if wid:
            out[wid] = rec
    return out


def emit(fh, rec: dict[str, Any]) -> None:
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    fh.flush()


def norm_doi(v: Any) -> str:
    t = s(v).lower()
    t = DOI_PREFIX_RE.sub("", t)
    return t.strip().strip("/")


def norm_pmid(v: Any) -> str:
    t = s(v)
    if t.endswith(".0") and t[:-2].isdigit():
        t = t[:-2]
    return t if PMID_RE.match(t) else ""


def norm_arxiv(v: Any) -> str:
    t = s(v)
    t = re.sub(r"^arxiv:\s*", "", t, flags=re.I)
    t = t.strip().strip("/")
    t = re.sub(r"v\d+$", "", t)
    return t


def arxiv_from_doi(doi: str) -> str:
    m = ARXIV_DOI_RE.match(doi or "")
    return norm_arxiv(m.group(1)) if m else ""


def safe_stem_part(text: str) -> str:
    return SAFE_RE.sub("_", text).strip("._") or "unknown"


def file_stem(doi: str = "", arxiv: str = "", pmid: str = "", work_id: str = "") -> str:
    if doi:
        return "doi_" + safe_stem_part(doi)
    if arxiv:
        return "arxiv_" + safe_stem_part(arxiv.replace("/", "_"))
    if pmid:
        return "pmid_" + safe_stem_part(pmid)
    wid = safe_stem_part(work_id or "unknown")
    return wid if wid.startswith("work_") else "work_" + wid


def looks_like_pdf_url(url: str) -> bool:
    t = s(url).lower()
    if not t.startswith("http"):
        return False
    path = t.split("?", 1)[0]
    # Wiley /doi/epdf/ is an HTML viewer. The file is /doi/pdfdirect/{doi}?download=true.
    return (
        path.endswith(".pdf")
        or "/pdf/" in path
        or "/pdfdirect/" in path
        or path.endswith("/pdf")
    )


WILEY_DOI_HOSTS = (
    (re.compile(r"^10\.1002/advs\.", re.I), "advanced.onlinelibrary.wiley.com"),
    (re.compile(r"^10\.1002/alz\.", re.I), "alz-journals.onlinelibrary.wiley.com"),
    (re.compile(r"^10\.1096/fasebj", re.I), "faseb.onlinelibrary.wiley.com"),
)


def is_wiley_doi(doi: str) -> bool:
    d = s(doi).lower()
    return d.startswith("10.1002/") or d.startswith("10.1111/") or d.startswith("10.1096/")


def wiley_host(doi: str) -> str:
    d = s(doi)
    for pat, host in WILEY_DOI_HOSTS:
        if pat.search(d):
            return host
    return "onlinelibrary.wiley.com"


def wiley_epdf_url(doi: str) -> str:
    """HTML ePDF viewer. urllib 403s; real Chrome after Cloudflare loads it."""
    d = s(doi)
    if not d or not is_wiley_doi(d):
        return ""
    return f"https://{wiley_host(d)}/doi/epdf/{d}"


def wiley_pdfdirect_url(doi: str) -> str:
    """OA file URL used after a Chrome session on the matching Wiley host."""
    d = s(doi)
    if not d or not is_wiley_doi(d):
        return ""
    return f"https://{wiley_host(d)}/doi/pdfdirect/{d}?download=true"


def pmc_pdf_url(url: str) -> str:
    m = PMC_ARTICLE_RE.search(s(url))
    if not m:
        return ""
    return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{m.group(1)}/pdf/"


def normalize_candidate_url(url: str) -> str:
    t = s(url)
    pmc = pmc_pdf_url(t)
    if pmc:
        return pmc
    return t


def looks_like_pdf(data: bytes) -> bool:
    return bool(data) and data.lstrip().startswith(PDF_MAGIC)


def looks_like_html(data: bytes) -> bool:
    head = data[:256].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def join_ids(values: list[str]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return "|".join(out)


def norm_title(t: Any) -> str:
    text = unicodedata.normalize("NFKC", s(t)).lower()
    text = TITLE_PREFIX.sub("", text)
    text = text.replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([,;:()\[\]])\s*", r"\1", text)
    return text.strip(" .")


def title_sim(a: Any, b: Any) -> float:
    return SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()


def year_ok(y1: Any, y2: Any) -> bool:
    try:
        return abs(int(float(y1)) - int(float(y2))) <= 1
    except (TypeError, ValueError):
        return True


def record_title(rec: dict[str, Any]) -> str:
    if rec.get("display_name"):
        return s(rec.get("display_name"))
    title = rec.get("title")
    if isinstance(title, list):
        return " ".join(s(x) for x in title if s(x))
    return s(title)


def score_match(work: dict[str, str], matched_title: str, matched_doi: str, matched_year: Any) -> dict[str, Any] | None:
    our_doi = norm_doi(work.get("doi"))
    their_doi = norm_doi(matched_doi)
    sim = title_sim(work.get("title"), matched_title)
    doi_hit = bool(our_doi and their_doi and our_doi == their_doi)
    title_hit = bool(matched_title) and sim >= TITLE_SIM_FLOOR and year_ok(work.get("year"), matched_year)
    if not doi_hit and not title_hit:
        return None
    return {
        "search_match": True,
        "match_method": "doi" if doi_hit else "title",
        "matched_title": s(matched_title)[:300],
        "matched_doi": their_doi,
        "title_similarity": round(float(sim), 4),
    }


class Fetcher:
    def __init__(self, *, email: str = "", timeout: int = 60, sleep: float = 0.35, arxiv_sleep: float = 3.0):
        self.email = email
        self.timeout = timeout
        self.sleep = sleep
        self.arxiv_sleep = arxiv_sleep
        self.last_host_ts: dict[str, float] = {}

    def user_agent(self) -> str:
        mail = f" mailto:{self.email}" if self.email else ""
        return f"{UA_BASE} (https://github.com/wrgr/connectomics-survey;{mail})"

    def _pace(self, url: str) -> None:
        host = urllib.parse.urlparse(url).netloc.lower()
        if "ncbi.nlm.nih.gov" in host:
            host = "ncbi.nlm.nih.gov"
        gap = self.arxiv_sleep if "arxiv.org" in host else self.sleep
        last = self.last_host_ts.get(host, 0.0)
        wait = gap - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        self.last_host_ts[host] = time.time()

    def _open(self, url: str, headers: dict[str, str] | None = None):
        self._pace(url)
        h = {"User-Agent": self.user_agent(), "Accept": "*/*"}
        h.update(headers or {})
        req = urllib.request.Request(url, headers=h)
        return urllib.request.urlopen(req, timeout=self.timeout)

    def get_json(self, url: str) -> Any:
        with self._open(url, {"Accept": "application/json"}) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def get_bytes(self, url: str) -> bytes:
        with self._open(url, {"Accept": "application/pdf,*/*"}) as resp:
            return resp.read()


def identifiers_for(work: dict[str, str], versions: list[dict[str, str]]) -> dict[str, str]:
    dois = [norm_doi(work.get("doi"))]
    pmids: list[str] = [norm_pmid(work.get("pmid"))]
    arxivs: list[str] = [norm_arxiv(work.get("arxiv_id"))]
    for row in versions:
        dois.append(norm_doi(row.get("doi")))
        pmids.append(norm_pmid(row.get("pmid")))
        arxivs.append(norm_arxiv(row.get("arxiv_id")))
    dois = [d for d in dois if d]
    for d in list(dois):
        ax = arxiv_from_doi(d)
        if ax:
            arxivs.append(ax)
    doi = dois[0] if dois else ""
    pmid = next((p for p in pmids if p), "")
    arxiv = next((a for a in arxivs if a), "")
    pid = s(work.get("canonical_paper_id"))
    doi_url = f"https://doi.org/{doi}" if doi else ""
    pmid_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
    arxiv_abs = f"https://arxiv.org/abs/{arxiv}" if arxiv else ""
    s2_url = f"https://www.semanticscholar.org/paper/{pid}" if pid else ""
    landing = doi_url or pmid_url or arxiv_abs or s2_url
    return {
        "doi": doi,
        "pmid": pmid,
        "arxiv_id": arxiv,
        "dois": join_ids(dois),
        "pmids": join_ids(pmids),
        "arxiv_ids": join_ids(arxivs),
        "doi_url": doi_url,
        "pmid_url": pmid_url,
        "arxiv_abs_url": arxiv_abs,
        "semantic_scholar_url": s2_url,
        "landing_url": landing,
        "stem": file_stem(doi, arxiv, pmid, s(work.get("work_id"))),
    }


def unique_stems(works: list[dict[str, str]]) -> dict[str, str]:
    used: dict[str, str] = {}
    out: dict[str, str] = {}
    for work in sorted(works, key=lambda r: r["work_id"]):
        stem = work["stem"]
        if stem in used and used[stem] != work["work_id"]:
            stem = f"{stem}__{work['work_id']}"
        used[stem] = work["work_id"]
        out[work["work_id"]] = stem
    return out


def assemble_works(corpus: list[dict[str, str]], versions: list[dict[str, str]]) -> list[dict[str, str]]:
    by_work: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in versions:
        wid = s(row.get("work_id"))
        if wid:
            by_work[wid].append(row)
    works: list[dict[str, str]] = []
    for row in corpus:
        ids = identifiers_for(row, by_work.get(row["work_id"], []))
        merged = dict(row)
        merged.update(ids)
        works.append(merged)
    stems = unique_stems(works)
    for work in works:
        work["stem"] = stems[work["work_id"]]
    works.sort(key=lambda r: r["work_id"])
    return works


def direct_pdf_candidates(ids: dict[str, str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if ids.get("arxiv_id"):
        ax = ids["arxiv_id"]
        out.append((f"https://arxiv.org/pdf/{ax}.pdf", "arxiv"))
    doi = s(ids.get("doi"))
    venue = s(ids.get("venue")).lower()
    if doi and ("medrxiv" in venue):
        out.append((f"https://www.medrxiv.org/content/{doi}.full.pdf", "medrxiv"))
    elif doi and (doi.startswith("10.1101/") or doi.startswith("10.64898/") or "biorxiv" in venue):
        out.append((f"https://www.biorxiv.org/content/{doi}.full.pdf", "biorxiv"))
    return out


def unpaywall_candidates(data: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    locations = []
    best = data.get("best_oa_location") or {}
    if best:
        locations.append(best)
    locations.extend(data.get("oa_locations") or [])
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        for key in ("url_for_pdf", "url"):
            url = normalize_candidate_url(s(loc.get(key)))
            if not url or url in seen:
                continue
            if key == "url" and not looks_like_pdf_url(url):
                continue
            seen.add(url)
            out.append((url, "unpaywall"))
    return out


def openalex_candidates(data: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    blobs = [data.get("best_oa_location"), data.get("primary_location"), data.get("open_access")]
    blobs.extend(data.get("locations") or [])
    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        for key in ("pdf_url", "oa_url"):
            url = normalize_candidate_url(s(blob.get(key)))
            if url and url not in seen and (key == "pdf_url" or looks_like_pdf_url(url)):
                seen.add(url)
                out.append((url, "openalex"))
    return out


def europepmc_candidates(data: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    results = ((data.get("resultList") or {}).get("result") or [])
    if not results:
        return out
    row = results[0]
    pmcid = s(row.get("pmcid"))
    if pmcid:
        out.append((f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/", "pmc"))
    urls = ((row.get("fullTextUrlList") or {}).get("fullTextUrl") or [])
    for item in urls:
        if not isinstance(item, dict):
            continue
        style = s(item.get("documentStyle")).lower()
        url = s(item.get("url"))
        if url and style in {"pdf", ""}:
            out.append((url, "europepmc"))
    return out


def _dedupe_cands(cands: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for url, src in cands:
        if url and url not in seen:
            seen.add(url)
            out.append((url, src))
    return out


def lookup_unpaywall(fetcher: Fetcher, doi: str, attempts: list[str]) -> list[tuple[str, str]]:
    if not doi:
        attempts.append("unpaywall:skip")
        return []
    if not fetcher.email:
        attempts.append("unpaywall:skip_no_email")
        return []
    url = "https://api.unpaywall.org/v2/" + urllib.parse.quote(doi, safe="/") + "?" + urllib.parse.urlencode({"email": fetcher.email})
    try:
        data = fetcher.get_json(url)
        cands = unpaywall_candidates(data if isinstance(data, dict) else {})
        attempts.append("unpaywall:hit" if cands else "unpaywall:no_pdf")
        return cands
    except Exception as e:
        attempts.append(f"unpaywall:error:{type(e).__name__}")
        return []


def lookup_openalex(fetcher: Fetcher, ids: dict[str, str], attempts: list[str]) -> list[tuple[str, str]]:
    keys: list[str] = []
    if ids.get("doi"):
        keys.append("doi:" + ids["doi"])
    if ids.get("pmid"):
        keys.append("pmid:" + ids["pmid"])
    if not keys:
        attempts.append("openalex:skip")
        return []
    params = {"select": "id,doi,ids,open_access,best_oa_location,primary_location,locations"}
    if fetcher.email:
        params["mailto"] = fetcher.email
    qs = urllib.parse.urlencode(params)
    last_cands: list[tuple[str, str]] = []
    for key in keys:
        url = "https://api.openalex.org/works/" + urllib.parse.quote(key, safe=":/") + "?" + qs
        try:
            data = fetcher.get_json(url)
            cands = openalex_candidates(data if isinstance(data, dict) else {})
            attempts.append("openalex:hit" if cands else "openalex:no_pdf")
            if cands:
                return cands
            last_cands = cands
        except Exception as e:
            attempts.append(f"openalex:error:{type(e).__name__}")
    return last_cands


def norm_pmcid(v: Any) -> str:
    t = s(v).upper().replace("PMC", "").strip()
    return f"PMC{t}" if t.isdigit() else ""


def pmc_pdf_from_id(pmcid: str) -> str:
    pid = norm_pmcid(pmcid)
    return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pid}/pdf/" if pid else ""


def pmc_article_url(pmcid: str) -> str:
    pid = norm_pmcid(pmcid)
    return f"https://pmc.ncbi.nlm.nih.gov/articles/{pid}/" if pid else ""


def pmcid_from_text(text: str) -> str:
    t = s(text)
    for rx in (PMC_ARTICLE_RE, EUROPEPMC_ART_RE, PMC_BARE_RE):
        m = rx.search(t)
        if m:
            return norm_pmcid(m.group(1))
    return ""


def pmc_named_pdf_urls_from_html(html: str, pmcid: str) -> list[str]:
    """Absolute NIHMS/article PDF hrefs from a PMC article page. Skips supplements."""
    pid = norm_pmcid(pmcid)
    if not pid or not html:
        return []
    base = pmc_article_url(pid)
    nihms: list[str] = []
    other: list[str] = []
    seen: set[str] = set()
    for raw in HREF_RE.findall(html):
        href = htmlmod.unescape(raw).strip()
        if not href or href.startswith("#"):
            continue
        if PMC_SUPPLEMENT_RE.search(href):
            continue
        path = urllib.parse.urlparse(href).path.lower()
        if not path.endswith(".pdf"):
            continue
        absu = urllib.parse.urljoin(base, href)
        if absu in seen:
            continue
        seen.add(absu)
        if "nihms" in path:
            nihms.append(absu)
        else:
            other.append(absu)
    return nihms + other


def ncbi_params(email: str = "") -> dict[str, str]:
    out = {"tool": NCBI_TOOL}
    if email:
        out["email"] = email
    return out


def pubmed_idconv_url(ids: list[str], email: str = "") -> str:
    params = {"ids": ",".join(ids), "format": "json", **ncbi_params(email)}
    return "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?" + urllib.parse.urlencode(params)


def pubmed_elink_url(pmid: str, email: str = "") -> str:
    params = {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "json", **ncbi_params(email)}
    return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?" + urllib.parse.urlencode(params)


def pubmed_esearch_url(term: str, email: str = "") -> str:
    params = {"db": "pubmed", "term": term, "retmode": "json", "retmax": "5", **ncbi_params(email)}
    return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)


def pubmed_cands_from_pmcids(pmcids: list[str]) -> list[tuple[str, str]]:
    """PMC PDF URLs. Europe PMC render is tried first; NCBI `/pdf/` often returns HTML."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pmcid in pmcids:
        pid = norm_pmcid(pmcid)
        if not pid:
            continue
        urls = [
            f"https://europepmc.org/articles/{pid}?pdf=render",
            f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pid}&blobtype=pdf",
            f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pid}/pdf/",
        ]
        for url in urls:
            if url not in seen:
                seen.add(url)
                out.append((url, "pubmed"))
    return out


def pmcids_from_idconv(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    pmcids: list[str] = []
    pmids: list[str] = []
    for rec in data.get("records") or []:
        if not isinstance(rec, dict):
            continue
        if s(rec.get("status")).lower() == "error":
            continue
        pmc = norm_pmcid(rec.get("pmcid"))
        pmid = norm_pmid(rec.get("pmid"))
        if pmc:
            pmcids.append(pmc)
        if pmid:
            pmids.append(pmid)
    return pmcids, pmids


def pmcids_from_elink(data: dict[str, Any]) -> list[str]:
    """PMC full-text deposits only (`pubmed_pmc`). Skip citing-article dumps (`pubmed_pmc_refs`)."""
    out: list[str] = []
    for ls in data.get("linksets") or []:
        if not isinstance(ls, dict):
            continue
        for db in ls.get("linksetdbs") or []:
            if not isinstance(db, dict):
                continue
            if s(db.get("dbto")).lower() != "pmc":
                continue
            linkname = s(db.get("linkname")).lower()
            if linkname and linkname not in {"pubmed_pmc", "pubmed_pmc_local"}:
                continue
            for link in db.get("links") or []:
                pmc = norm_pmcid(link)
                if pmc:
                    out.append(pmc)
    return out


def pmids_from_esearch(data: dict[str, Any]) -> list[str]:
    ids = (data.get("esearchresult") or {}).get("idlist") or []
    return [p for p in (norm_pmid(x) for x in ids) if p]


def lookup_pubmed(
    fetcher: Fetcher,
    ids: dict[str, str],
    attempts: list[str],
    *,
    include_search: bool = False,
) -> list[tuple[str, str]]:
    """NCBI PubMed/PMC: idconv (DOI) and elink (PMID → PMCID), then the PMC PDF URL.

    `include_search` adds DOI/title esearch for works that still lack a PMCID.
    Hits are tagged `pdf_source=pubmed`, not `direct_search`.
    """
    pmcids: list[str] = []
    pmids = [ids["pmid"]] if ids.get("pmid") else []
    email = fetcher.email

    if ids.get("doi"):
        try:
            data = fetcher.get_json(pubmed_idconv_url([ids["doi"]], email))
            got_pmc, got_pmid = pmcids_from_idconv(data if isinstance(data, dict) else {})
            pmcids.extend(got_pmc)
            for p in got_pmid:
                if p not in pmids:
                    pmids.append(p)
            attempts.append("pubmed:idconv:hit" if (got_pmc or got_pmid) else "pubmed:idconv:miss")
        except Exception as e:
            attempts.append(f"pubmed:idconv:error:{type(e).__name__}")

    if not pmcids and pmids:
        try:
            data = fetcher.get_json(pubmed_elink_url(pmids[0], email))
            got = pmcids_from_elink(data if isinstance(data, dict) else {})
            pmcids.extend(got)
            attempts.append("pubmed:elink:hit" if got else "pubmed:elink:miss")
        except Exception as e:
            attempts.append(f"pubmed:elink:error:{type(e).__name__}")

    if include_search and not pmcids:
        terms: list[str] = []
        if ids.get("doi"):
            terms.append(f'{ids["doi"]}[DOI]')
        title = s(ids.get("title"))
        if title:
            terms.append(f'"{title[:180]}"[Title]')
        for term in terms:
            try:
                data = fetcher.get_json(pubmed_esearch_url(term, email))
                found = pmids_from_esearch(data if isinstance(data, dict) else {})
                if not found:
                    attempts.append("pubmed:esearch:miss")
                    continue
                attempts.append("pubmed:esearch:hit")
                for pmid in found:
                    if pmid not in pmids:
                        pmids.append(pmid)
                    data2 = fetcher.get_json(pubmed_elink_url(pmid, email))
                    got = pmcids_from_elink(data2 if isinstance(data2, dict) else {})
                    pmcids.extend(got)
                    if pmcids:
                        attempts.append("pubmed:elink:hit")
                        break
                if pmcids:
                    break
                attempts.append("pubmed:elink:miss")
            except Exception as e:
                attempts.append(f"pubmed:esearch:error:{type(e).__name__}")

    cands = pubmed_cands_from_pmcids(pmcids)
    if cands:
        attempts.append("pubmed:hit")
    elif not any(a.startswith("pubmed:") for a in attempts):
        attempts.append("pubmed:skip")
    else:
        attempts.append("pubmed:no_pdf")
    return cands


def lookup_europepmc(fetcher: Fetcher, ids: dict[str, str], attempts: list[str]) -> list[tuple[str, str]]:
    q = ""
    if ids.get("doi"):
        q = f'DOI:"{ids["doi"]}"'
    elif ids.get("pmid"):
        q = f"EXT_ID:{ids['pmid']} AND SRC:MED"
    if not q:
        attempts.append("europepmc:skip")
        return []
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": q, "format": "json", "resultType": "core", "pageSize": 1}
    )
    try:
        data = fetcher.get_json(url)
        cands = europepmc_candidates(data if isinstance(data, dict) else {})
        attempts.append("europepmc:hit" if cands else "europepmc:no_pdf")
        return cands
    except Exception as e:
        attempts.append(f"europepmc:error:{type(e).__name__}")
        return []


def crossref_pdf_links(message: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for link in message.get("link") or []:
        if not isinstance(link, dict):
            continue
        url = normalize_candidate_url(s(link.get("URL")))
        ctype = s(link.get("content-type")).lower()
        if url and ("pdf" in ctype or looks_like_pdf_url(url)):
            out.append(url)
    return out


def openalex_search_url(title: str, email: str = "") -> str:
    q = re.sub(r"[,:]", " ", s(title))[:180]
    params = {"filter": "title.search:" + q, "per-page": "5", "select": OA_SELECT}
    if email:
        params["mailto"] = email
    return "https://api.openalex.org/works?" + urllib.parse.urlencode(params)


def crossref_search_url(title: str) -> str:
    return "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": s(title)[:180], "rows": 5})


def crossref_doi_url(doi: str) -> str:
    return "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")


def epmc_search_url(query: str) -> str:
    return "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": query, "format": "json", "resultType": "core", "pageSize": 5}
    )


def _tag_direct(cands: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(url, "direct_search") for url, _ in cands if url]


def search_by_title_doi(fetcher: Fetcher, work: dict[str, str], attempts: list[str]) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    """Bibliographic search by DOI and title. Hits are flagged `direct_search` for audit."""
    title = s(work.get("title"))
    doi = s(work.get("doi"))
    cands: list[tuple[str, str]] = []
    meta: dict[str, Any] = {}

    if doi:
        try:
            data = fetcher.get_json(crossref_doi_url(doi))
            message = data.get("message") if isinstance(data, dict) else {}
            if isinstance(message, dict):
                scored = score_match(work, record_title(message), s(message.get("DOI")), ((message.get("published-print") or message.get("published-online") or {}).get("date-parts") or [[None]])[0][0])
                links = crossref_pdf_links(message)
                if scored:
                    attempts.append("direct_search:crossref_doi:hit")
                    meta = dict(scored)
                    meta["search_api"] = "crossref"
                    cands.extend((u, "direct_search") for u in links)
                else:
                    attempts.append("direct_search:crossref_doi:nomatch")
            else:
                attempts.append("direct_search:crossref_doi:miss")
        except Exception as e:
            attempts.append(f"direct_search:crossref_doi:error:{type(e).__name__}")

    if title:
        try:
            data = fetcher.get_json(openalex_search_url(title, fetcher.email))
            results = (data.get("results") or []) if isinstance(data, dict) else []
            best = None
            best_cands: list[tuple[str, str]] = []
            for rec in results:
                if not isinstance(rec, dict):
                    continue
                scored = score_match(work, record_title(rec), rec.get("doi"), rec.get("publication_year"))
                if not scored:
                    continue
                got = _tag_direct(openalex_candidates(rec))
                if not best or scored["title_similarity"] > best["title_similarity"] or (scored["match_method"] == "doi" and best["match_method"] != "doi"):
                    best, best_cands = scored, got
            if best:
                attempts.append("direct_search:openalex_title:hit")
                if not meta or best["match_method"] == "doi" and meta.get("match_method") != "doi":
                    meta = dict(best)
                    meta["search_api"] = "openalex"
                cands.extend(best_cands)
            else:
                attempts.append("direct_search:openalex_title:miss")
        except Exception as e:
            attempts.append(f"direct_search:openalex_title:error:{type(e).__name__}")

        try:
            data = fetcher.get_json(crossref_search_url(title))
            items = ((data.get("message") or {}).get("items") or []) if isinstance(data, dict) else []
            best = None
            best_links: list[str] = []
            for rec in items:
                if not isinstance(rec, dict):
                    continue
                yr = ((rec.get("published-print") or rec.get("published-online") or {}).get("date-parts") or [[None]])[0][0]
                scored = score_match(work, record_title(rec), rec.get("DOI"), yr)
                if not scored:
                    continue
                links = crossref_pdf_links(rec)
                if not best or scored["title_similarity"] > best["title_similarity"] or (scored["match_method"] == "doi" and best["match_method"] != "doi"):
                    best, best_links = scored, links
            if best:
                attempts.append("direct_search:crossref_title:hit")
                if not meta:
                    meta = dict(best)
                    meta["search_api"] = "crossref"
                cands.extend((u, "direct_search") for u in best_links)
            else:
                attempts.append("direct_search:crossref_title:miss")
        except Exception as e:
            attempts.append(f"direct_search:crossref_title:error:{type(e).__name__}")

        try:
            q = f'TITLE:"{title[:180]}"'
            data = fetcher.get_json(epmc_search_url(q))
            results = ((data.get("resultList") or {}).get("result") or []) if isinstance(data, dict) else []
            best = None
            best_cands: list[tuple[str, str]] = []
            for rec in results:
                if not isinstance(rec, dict):
                    continue
                scored = score_match(work, rec.get("title"), rec.get("doi"), rec.get("pubYear"))
                if not scored:
                    continue
                got = _tag_direct(europepmc_candidates({"resultList": {"result": [rec]}}))
                if not best or scored["title_similarity"] > best["title_similarity"] or (scored["match_method"] == "doi" and best["match_method"] != "doi"):
                    best, best_cands = scored, got
            if best:
                attempts.append("direct_search:europepmc_title:hit")
                if not meta:
                    meta = dict(best)
                    meta["search_api"] = "europepmc"
                cands.extend(best_cands)
            else:
                attempts.append("direct_search:europepmc_title:miss")
        except Exception as e:
            attempts.append(f"direct_search:europepmc_title:error:{type(e).__name__}")

    matched_doi = s(meta.get("matched_doi"))
    if matched_doi and matched_doi != doi:
        extra = lookup_unpaywall(fetcher, matched_doi, attempts)
        cands.extend((url, "direct_search") for url, _ in extra)

    return _dedupe_cands(cands), meta


def resolve_pdf_candidates(fetcher: Fetcher, ids: dict[str, str], attempts: list[str], *, local_ids_only: bool) -> list[tuple[str, str]]:
    cands = direct_pdf_candidates(ids)
    if cands:
        attempts.append("direct:arxiv")
    if local_ids_only:
        return _dedupe_cands(cands)
    cands.extend(lookup_unpaywall(fetcher, ids.get("doi", ""), attempts))
    if not any(looks_like_pdf_url(url) for url, src in cands if src != "arxiv"):
        cands.extend(lookup_openalex(fetcher, ids, attempts))
    if not cands:
        cands.extend(lookup_europepmc(fetcher, ids, attempts))
    if not cands:
        cands.extend(lookup_pubmed(fetcher, ids, attempts, include_search=False))
    return _dedupe_cands(cands)


def existing_pdf(path: Path) -> tuple[bool, int, str]:
    if not path.exists() or not path.is_file():
        return False, 0, ""
    data = path.read_bytes()
    if not looks_like_pdf(data):
        return False, len(data), ""
    return True, len(data), sha256_bytes(data)


def download_first_pdf(fetcher: Fetcher, cands: list[tuple[str, str]], dest: Path, attempts: list[str]) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err = ""
    for url, src in cands:
        try:
            data = fetcher.get_bytes(url)
        except urllib.error.HTTPError as e:
            attempts.append(f"download:{src}:http_{e.code}")
            last_err = f"HTTP {e.code} {url}"
            continue
        except Exception as e:
            attempts.append(f"download:{src}:error")
            last_err = f"{type(e).__name__} {url}"
            continue
        if looks_like_html(data) or not looks_like_pdf(data):
            attempts.append(f"download:{src}:not_pdf")
            last_err = f"not a PDF: {url}"
            continue
        dest.write_bytes(data)
        attempts.append(f"download:{src}:ok")
        return {"ok": True, "pdf_url": url, "pdf_source": src, "bytes": len(data), "sha256": sha256_bytes(data), "error": ""}
    return {"ok": False, "pdf_url": cands[0][0] if cands else "", "pdf_source": cands[0][1] if cands else "", "bytes": 0, "sha256": "", "error": last_err}


def catalog_row(work: dict[str, str], rec: dict[str, Any]) -> dict[str, str]:
    attempts = rec.get("attempts") or []
    if isinstance(attempts, list):
        attempts_s = "|".join(str(x) for x in attempts)
    else:
        attempts_s = s(attempts)
    return {
        "work_id": s(work.get("work_id")),
        "canonical_paper_id": s(work.get("canonical_paper_id")),
        "source_group": s(work.get("source_group")),
        "decision": s(work.get("decision")),
        "year": s(work.get("year")),
        "venue": s(work.get("venue")),
        "title": s(work.get("title")),
        "doi": s(rec.get("doi") or work.get("doi")),
        "pmid": s(rec.get("pmid") or work.get("pmid")),
        "arxiv_id": s(rec.get("arxiv_id") or work.get("arxiv_id")),
        "stem": s(rec.get("stem") or work.get("stem")),
        "landing_url": s(rec.get("landing_url") or work.get("landing_url")),
        "doi_url": s(rec.get("doi_url") or work.get("doi_url")),
        "pmid_url": s(rec.get("pmid_url") or work.get("pmid_url")),
        "arxiv_abs_url": s(rec.get("arxiv_abs_url") or work.get("arxiv_abs_url")),
        "semantic_scholar_url": s(rec.get("semantic_scholar_url") or work.get("semantic_scholar_url")),
        "pdf_url": s(rec.get("pdf_url")),
        "pdf_source": s(rec.get("pdf_source")),
        "pdf_status": s(rec.get("pdf_status")),
        "local_path": s(rec.get("local_path")),
        "bytes": "" if rec.get("bytes") in (None, "") else str(rec.get("bytes")),
        "sha256": s(rec.get("sha256")),
        "search_match": "true" if rec.get("search_match") in (True, "true", "True", 1, "1") else "",
        "match_method": s(rec.get("match_method")),
        "matched_title": s(rec.get("matched_title")),
        "matched_doi": s(rec.get("matched_doi")),
        "title_similarity": "" if rec.get("title_similarity") in (None, "") else str(rec.get("title_similarity")),
        "search_api": s(rec.get("search_api")),
        "attempts": attempts_s,
        "error": s(rec.get("error")),
        "ts": s(rec.get("ts")),
    }


def write_catalog(path: Path, works: list[dict[str, str]], latest: dict[str, dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CATALOG_FIELDS)
        w.writeheader()
        for work in works:
            rec = latest.get(work["work_id"], {})
            w.writerow(catalog_row(work, rec))


def write_audit(path: Path, works: list[dict[str, str]], latest: dict[str, dict[str, Any]]) -> int:
    rows = []
    for work in works:
        rec = latest.get(work["work_id"], {})
        if rec.get("search_match") not in (True, "true", "True", 1, "1"):
            continue
        rows.append({
            "work_id": s(work.get("work_id")),
            "title": s(work.get("title")),
            "doi": s(rec.get("doi") or work.get("doi")),
            "year": s(work.get("year")),
            "matched_title": s(rec.get("matched_title")),
            "matched_doi": s(rec.get("matched_doi")),
            "title_similarity": "" if rec.get("title_similarity") in (None, "") else str(rec.get("title_similarity")),
            "match_method": s(rec.get("match_method")),
            "search_api": s(rec.get("search_api")),
            "pdf_url": s(rec.get("pdf_url")),
            "pdf_status": s(rec.get("pdf_status")),
            "local_path": s(rec.get("local_path")),
            "landing_url": s(rec.get("landing_url") or work.get("landing_url")),
        })
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=AUDIT_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return len(rows)


def summarize(works: list[dict[str, str]], latest: dict[str, dict[str, Any]]) -> dict[str, Any]:
    statuses: dict[str, int] = defaultdict(int)
    sources: dict[str, int] = defaultdict(int)
    n_landing = n_pdf_url = n_doi = n_file = n_search = 0
    for work in works:
        rec = latest.get(work["work_id"], {})
        statuses[s(rec.get("pdf_status")) or "unprocessed"] += 1
        if s(rec.get("landing_url") or work.get("landing_url")):
            n_landing += 1
        if s(rec.get("pdf_url")):
            n_pdf_url += 1
        if s(rec.get("doi") or work.get("doi")):
            n_doi += 1
        if s(rec.get("local_path")) and s(rec.get("pdf_status")) == "downloaded":
            n_file += 1
        src = s(rec.get("pdf_source"))
        if src:
            sources[src] += 1
        if rec.get("search_match") in (True, "true", "True", 1, "1"):
            n_search += 1
    return {
        "corpus_works": len(works),
        "with_landing_url": n_landing,
        "with_doi": n_doi,
        "with_pdf_url": n_pdf_url,
        "downloaded": n_file,
        "direct_search_matches": n_search,
        "status_counts": dict(sorted(statuses.items())),
        "pdf_sources": dict(sorted(sources.items())),
        "files_dir": FILES_DIR,
        "title_similarity_floor": TITLE_SIM_FLOOR,
        "note": "PDFs are OA/direct only; paywalled works keep landing URLs. Title/DOI search hits are flagged pdf_source=direct_search for audit.",
    }


def doi_from_manual_name(stem: str) -> str:
    m = DOI_STEM_RE.match(stem)
    if m:
        return norm_doi(m.group(1) + "/" + m.group(2).replace("_", "/"))
    found = DOI_IN_TEXT_RE.search(stem.replace("_", "/"))
    return norm_doi(found.group(0).rstrip(".,;)]}")) if found else ""


def mdpi_filename_matches_doi(stem: str, doi: str) -> bool:
    m = MDPI_ARTICLE_RE.match(stem)
    if not m:
        return False
    journal, vol, art = m.group(1).lower(), int(m.group(2)), int(m.group(3))
    suffix = norm_doi(doi).lower().rsplit("/", 1)[-1]
    if not suffix.startswith(journal):
        return False
    rest = suffix[len(journal):]
    vol_s = str(vol)
    if not rest.startswith(vol_s):
        return False
    after = rest[len(vol_s):]
    return after.endswith(f"{art:04d}") and len(after) in {4, 5, 6, 7}


def filename_title_guess(stem: str) -> tuple[str, str]:
    parts = [p.strip() for p in re.split(r"\s+-\s+", stem) if p.strip()]
    if len(parts) >= 4 and WILEY_YEAR_RE.match(parts[1]):
        return parts[-1], parts[1]
    text = stem.replace("_", " ").strip()
    m = VENUE_TAIL_RE.search(text)
    if m:
        return text[: m.start()].strip(), m.group(2)
    text = re.sub(r"\s+paper$", "", text, flags=re.I).strip()
    return text, ""


def title_tokens(t: Any) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", norm_title(t)).split()


def title_token_window_hit(work_title: str, guessed_title: str, min_tokens: int = TITLE_TOKEN_MIN) -> bool:
    wt = title_tokens(work_title)
    gt = title_tokens(guessed_title)
    if len(wt) < min_tokens or len(gt) < len(wt):
        return False
    n = len(wt)
    return any(gt[i : i + n] == wt for i in range(len(gt) - n + 1))


def title_filename_hit(work: dict[str, str], guessed_title: str, guessed_year: str) -> bool:
    if not guessed_title:
        return False
    if guessed_year and not year_ok(work.get("year"), guessed_year):
        return False
    if title_sim(work.get("title"), guessed_title) >= TITLE_SIM_FLOOR:
        return True
    wt = re.sub(r"[^a-z0-9]+", " ", norm_title(work.get("title"))).strip()
    gt = re.sub(r"[^a-z0-9]+", " ", norm_title(guessed_title)).strip()
    if not wt or not gt:
        return False
    shorter, longer = (gt, wt) if len(gt) <= len(wt) else (wt, gt)
    if len(shorter) >= TITLE_PREFIX_MIN and longer.startswith(shorter):
        return True
    return title_token_window_hit(work.get("title") or "", guessed_title)


def clean_extracted_doi(raw: str) -> str:
    t = norm_doi(raw)
    t = t.split(")")[0].split("]")[0].split("<")[0]
    t = t.rstrip(".,;:/")
    return t if t.startswith("10.") else ""


def dois_from_text(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in DOI_IN_TEXT_RE.finditer(text.replace("_", "/")):
        d = clean_extracted_doi(m.group(0))
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def dois_from_pdf_bytes(data: bytes) -> list[str]:
    try:
        text = data.decode("latin-1")
    except Exception:
        return []
    return dois_from_text(text)


def pdf_first_page_text(path: Path) -> str:
    try:
        proc = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "2", str(path), "-"],
            capture_output=True, timeout=20, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""
    if proc.returncode != 0 or not proc.stdout:
        return ""
    return proc.stdout.decode("utf-8", "replace")


def work_for_extracted_dois(dois: list[str], works: list[dict[str, str]]) -> tuple[dict[str, str] | None, str]:
    by_doi = {norm_doi(w.get("doi")): w for w in works if norm_doi(w.get("doi"))}
    uniq = list(dict.fromkeys(d for d in dois if d in by_doi))
    if len(uniq) == 1:
        return by_doi[uniq[0]], "pdf_doi"
    return None, ""


def match_manual_file(
    path: Path,
    works: list[dict[str, str]],
    data: bytes | None = None,
) -> tuple[dict[str, str] | None, str, str]:
    stem = path.stem
    named_doi = doi_from_manual_name(stem)
    id_works: dict[str, tuple[str, dict[str, str]]] = {}
    for work in works:
        method = ""
        if stem == work["stem"]:
            method = "stem"
        elif stem == work["work_id"]:
            method = "work_id"
        elif named_doi and named_doi == norm_doi(work.get("doi")):
            method = "doi"
        elif mdpi_filename_matches_doi(stem, work.get("doi") or ""):
            method = "mdpi_article"
        if method and work["work_id"] not in id_works:
            id_works[work["work_id"]] = (method, work)
    if len(id_works) == 1:
        method, work = next(iter(id_works.values()))
        return work, method, ""
    if len(id_works) > 1:
        return None, "", "ambiguous identifier match: " + ",".join(sorted(id_works))
    guessed, year = filename_title_guess(stem)
    title_hits = [w for w in works if title_filename_hit(w, guessed, year)]
    if len(title_hits) == 1:
        return title_hits[0], "title", ""
    if len(title_hits) > 1:
        return None, "", "ambiguous title match: " + ",".join(w["work_id"] for w in title_hits)
    blob = data if data is not None else path.read_bytes()
    page = pdf_first_page_text(path)
    if page:
        work, method = work_for_extracted_dois(dois_from_text(page), works)
        if work:
            return work, "pdf_text_doi", ""
    work, method = work_for_extracted_dois(dois_from_pdf_bytes(blob), works)
    if work:
        return work, method, ""
    return None, "", "unmatched"


def list_manual_pdfs(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"),
        key=lambda p: p.name.lower(),
    )


def ingest_manual_pdfs(
    works: list[dict[str, str]],
    out: Path,
    prior: dict[str, dict[str, Any]],
    *,
    force: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    files_dir = out / FILES_DIR
    files_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    problems: list[str] = []
    claimed: dict[str, str] = {}
    for dirname, source in MANUAL_DROP_DIRS:
        for path in list_manual_pdfs(out / dirname):
            data = path.read_bytes()
            label = f"{dirname}/{path.name}"
            if not looks_like_pdf(data):
                problems.append(f"{label}: not a PDF")
                continue
            work, method, err = match_manual_file(path, works, data)
            if not work:
                problems.append(f"{label}: {err}")
                continue
            wid = work["work_id"]
            if wid in claimed and claimed[wid] != path.name:
                problems.append(f"{label}: same work already claimed by {claimed[wid]}")
                continue
            claimed[wid] = path.name
            dest = files_dir / f"{work['stem']}.pdf"
            digest = sha256_bytes(data)
            ok, _, existing_digest = existing_pdf(dest)
            latest = prior.get(wid) or {}
            if ok and existing_digest != digest and not force:
                problems.append(f"{label}: dest exists with different bytes ({dest.name})")
                continue
            already = (
                ok and existing_digest == digest
                and s(latest.get("pdf_status")) == "downloaded"
                and s(latest.get("pdf_source")) == source
                and s(latest.get("sha256")) == digest
            )
            if already and not force:
                continue
            copied = False
            if not ok or existing_digest != digest or force:
                dest.write_bytes(data)
                copied = True
            extra: dict[str, Any] = {
                "pdf_url": s(latest.get("pdf_url")),
                "pdf_source": source,
                "local_path": dest.as_posix(),
                "bytes": len(data),
                "sha256": digest,
                "attempts": [f"ingest:{source}:{method}:{'copied' if copied else 'existing'}"],
                "error": "",
                "match_method": method,
            }
            for k in ("search_match", "matched_title", "matched_doi", "title_similarity", "search_api"):
                if latest.get(k) not in (None, ""):
                    extra[k] = latest[k]
            extra["match_method"] = method
            records.append(progress_record(work, "downloaded", extra))
    return records, problems


def write_run_outputs(out: Path, works: list[dict[str, str]], latest: dict[str, dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
    write_catalog(out / CATALOG_FILE, works, latest)
    n_audit = write_audit(out / AUDIT_FILE, works, latest)
    summary = summarize(works, latest)
    summary.update(extra)
    summary["direct_search_audit_rows"] = n_audit
    summary["out"] = str(out)
    (out / SUMMARY_FILE).write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def should_skip(prior: dict[str, Any] | None, dest: Path, *, skip_attempted: bool, force: bool) -> tuple[bool, str]:
    if force:
        return False, ""
    ok, _, _ = existing_pdf(dest)
    if ok:
        return True, "existing_file"
    if skip_attempted and prior and s(prior.get("pdf_status")):
        return True, "skip_attempted"
    return False, ""


def progress_record(work: dict[str, str], status: str, extra: dict[str, Any]) -> dict[str, Any]:
    rec = {
        "ts": now_ts(),
        "index": extra.pop("index", 0),
        "total": extra.pop("total", 0),
        "work_id": work["work_id"],
        "canonical_paper_id": s(work.get("canonical_paper_id")),
        "title": s(work.get("title"))[:200],
        "doi": s(work.get("doi")),
        "pmid": s(work.get("pmid")),
        "arxiv_id": s(work.get("arxiv_id")),
        "stem": s(work.get("stem")),
        "landing_url": s(work.get("landing_url")),
        "doi_url": s(work.get("doi_url")),
        "pmid_url": s(work.get("pmid_url")),
        "arxiv_abs_url": s(work.get("arxiv_abs_url")),
        "semantic_scholar_url": s(work.get("semantic_scholar_url")),
        "pdf_status": status,
    }
    rec.update(extra)
    return rec


def process_work(
    work: dict[str, str],
    dest: Path,
    fetcher: Fetcher,
    prior: dict[str, Any] | None,
    *,
    local_ids_only: bool,
    resolve_only: bool,
    force: bool,
    skip_attempted: bool,
    search_unresolved: bool = False,
    pubmed_only: bool = False,
) -> dict[str, Any]:
    attempts: list[str] = []
    skip, why = should_skip(prior, dest, skip_attempted=skip_attempted, force=force)
    if skip:
        ok, nbytes, digest = existing_pdf(dest)
        status = "downloaded" if ok else s((prior or {}).get("pdf_status")) or "linked"
        attempts.append(f"resume:{why}")
        extra = {
            "pdf_url": s((prior or {}).get("pdf_url")),
            "pdf_source": s((prior or {}).get("pdf_source")),
            "local_path": dest.as_posix() if ok else s((prior or {}).get("local_path")),
            "bytes": nbytes if ok else (prior or {}).get("bytes") or 0,
            "sha256": digest if ok else s((prior or {}).get("sha256")),
            "attempts": attempts,
            "error": "" if ok else s((prior or {}).get("error")),
        }
        if prior:
            for k in ("search_match", "match_method", "matched_title", "matched_doi", "title_similarity", "search_api"):
                if prior.get(k) not in (None, ""):
                    extra[k] = prior[k]
        return progress_record(work, status, extra)

    cands: list[tuple[str, str]] = []
    search_meta: dict[str, Any] = {}
    if pubmed_only:
        cands = lookup_pubmed(fetcher, work, attempts, include_search=True)
        if resolve_only:
            if not cands:
                status = s((prior or {}).get("pdf_status")) or "linked"
                extra = {
                    "pdf_url": s((prior or {}).get("pdf_url")),
                    "pdf_source": s((prior or {}).get("pdf_source")),
                    "local_path": s((prior or {}).get("local_path")),
                    "bytes": (prior or {}).get("bytes") or 0,
                    "sha256": s((prior or {}).get("sha256")),
                    "attempts": attempts,
                    "error": "",
                }
                return progress_record(work, status, extra)
            return progress_record(work, "oa_resolved", {
                "pdf_url": cands[0][0], "pdf_source": cands[0][1], "local_path": "",
                "bytes": 0, "sha256": "", "attempts": attempts, "error": "",
            })
        if cands:
            downloaded = download_first_pdf(fetcher, cands, dest, attempts)
            if downloaded["ok"]:
                return progress_record(work, "downloaded", {
                    "pdf_url": downloaded["pdf_url"], "pdf_source": downloaded["pdf_source"],
                    "local_path": dest.as_posix(), "bytes": downloaded["bytes"],
                    "sha256": downloaded["sha256"], "attempts": attempts, "error": "",
                })
            return progress_record(work, "download_failed", {
                "pdf_url": downloaded["pdf_url"], "pdf_source": downloaded["pdf_source"],
                "local_path": "", "bytes": 0, "sha256": "", "attempts": attempts,
                "error": downloaded["error"],
            })
        status = s((prior or {}).get("pdf_status")) or "paywall"
        extra = {
            "pdf_url": s((prior or {}).get("pdf_url")),
            "pdf_source": s((prior or {}).get("pdf_source")),
            "local_path": s((prior or {}).get("local_path")),
            "bytes": (prior or {}).get("bytes") or 0,
            "sha256": s((prior or {}).get("sha256")),
            "attempts": attempts,
            "error": s((prior or {}).get("error")),
        }
        if prior:
            for k in ("search_match", "match_method", "matched_title", "matched_doi", "title_similarity", "search_api"):
                if prior.get(k) not in (None, ""):
                    extra[k] = prior[k]
        return progress_record(work, status, extra)

    if not search_unresolved:
        if not s(work.get("landing_url")):
            attempts.append("ids:none")
        else:
            cands = resolve_pdf_candidates(fetcher, work, attempts, local_ids_only=local_ids_only)

    need_search = (not local_ids_only) and (search_unresolved or not cands)
    downloaded = None
    if cands and not search_unresolved:
        if resolve_only:
            pdf_url, pdf_source = cands[0]
            attempts.append("resolve_only")
            return progress_record(work, "oa_resolved", {
                "pdf_url": pdf_url, "pdf_source": pdf_source, "local_path": "", "bytes": 0,
                "sha256": "", "attempts": attempts, "error": "",
            })
        downloaded = download_first_pdf(fetcher, cands, dest, attempts)
        if downloaded["ok"]:
            return progress_record(work, "downloaded", {
                "pdf_url": downloaded["pdf_url"], "pdf_source": downloaded["pdf_source"],
                "local_path": dest.as_posix(), "bytes": downloaded["bytes"],
                "sha256": downloaded["sha256"], "attempts": attempts, "error": "",
            })
        need_search = not local_ids_only

    if need_search:
        search_cands, search_meta = search_by_title_doi(fetcher, work, attempts)
        if search_cands:
            if resolve_only:
                attempts.append("resolve_only")
                extra = {
                    "pdf_url": search_cands[0][0], "pdf_source": "direct_search",
                    "local_path": "", "bytes": 0, "sha256": "", "attempts": attempts, "error": "",
                }
                extra.update(search_meta)
                return progress_record(work, "oa_resolved", extra)
            downloaded = download_first_pdf(fetcher, search_cands, dest, attempts)
            extra = {
                "pdf_url": downloaded["pdf_url"], "pdf_source": "direct_search",
                "local_path": dest.as_posix() if downloaded["ok"] else "",
                "bytes": downloaded["bytes"] if downloaded["ok"] else 0,
                "sha256": downloaded["sha256"] if downloaded["ok"] else "",
                "attempts": attempts, "error": "" if downloaded["ok"] else downloaded["error"],
            }
            extra.update(search_meta)
            return progress_record(work, "downloaded" if downloaded["ok"] else "download_failed", extra)
        if search_meta:
            extra = {
                "pdf_url": "", "pdf_source": "direct_search", "local_path": "", "bytes": 0,
                "sha256": "", "attempts": attempts, "error": "",
            }
            extra.update(search_meta)
            return progress_record(work, "search_matched", extra)

    if downloaded and not downloaded["ok"]:
        return progress_record(work, "download_failed", {
            "pdf_url": downloaded["pdf_url"], "pdf_source": downloaded["pdf_source"],
            "local_path": "", "bytes": 0, "sha256": "", "attempts": attempts,
            "error": downloaded["error"],
        })
    status = "linked" if local_ids_only else "paywall"
    return progress_record(work, status, {
        "pdf_url": cands[0][0] if cands else "", "pdf_source": cands[0][1] if cands else "",
        "local_path": "", "bytes": 0, "sha256": "", "attempts": attempts, "error": "",
    })


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-csv", type=Path, action="append", default=None, help="Inclusive corpus CSV. Repeatable; work_ids are unioned. Default: v2 checkpoint + v3 full.")
    ap.add_argument("--works-csv", type=Path, default=DEFAULT_WORKS_CSV, help="Canonical works metadata used to fill DOI/title for union members.")
    ap.add_argument("--versions-csv", type=Path, default=Path("postanalysis/works/work_versions.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/pdfs"))
    ap.add_argument("--email", default=os.environ.get("CONNECTOMICS_MAILTO") or os.environ.get("UNPAYWALL_EMAIL") or "")
    ap.add_argument("--local-ids-only", action="store_true", help="Write landing URLs from identifiers; no OA APIs. Still downloads arXiv PDFs unless --resolve-only.")
    ap.add_argument("--resolve-only", action="store_true", help="Record PDF URLs but do not download bytes.")
    ap.add_argument("--skip-attempted", action="store_true", help="Do not retry works already present in the progress log.")
    ap.add_argument("--force", action="store_true", help="Re-download even when a valid local PDF exists.")
    ap.add_argument("--unresolved-only", action="store_true", help="Skip works that already have a valid local PDF.")
    ap.add_argument("--search-unresolved", action="store_true", help="Title/DOI search fallback for works without a local PDF. Hits are flagged pdf_source=direct_search for audit.")
    ap.add_argument("--pubmed-unresolved", action="store_true", help="Look up remaining works in NCBI PubMed/PMC (idconv, elink, esearch) and download PMC PDFs. Skips existing local files.")
    ap.add_argument("--ingest-manual", action="store_true", help="Copy PDFs from out/manual_OA and out/manual_closed into files/ with corpus stems and log them. No network.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.35)
    ap.add_argument("--arxiv-sleep", type=float, default=3.0)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--expected-works", type=int, default=0)
    args = ap.parse_args()
    download_flags = (args.local_ids_only, args.resolve_only, args.search_unresolved, args.pubmed_unresolved, args.unresolved_only)
    if args.ingest_manual and any(download_flags):
        raise SystemExit("--ingest-manual cannot be combined with download/resolve flags")

    corpus_paths = list(args.corpus_csv) if args.corpus_csv else list(DEFAULT_CORPORA)
    for path in corpus_paths:
        if not path.exists():
            raise SystemExit(f"missing corpus csv: {path}")
    if not args.versions_csv.exists():
        raise SystemExit(f"missing versions csv: {args.versions_csv}")
    out = args.out.resolve()
    input_dirs = {p.resolve().parent for p in corpus_paths}
    input_dirs.add(args.versions_csv.resolve().parent)
    if args.works_csv:
        input_dirs.add(args.works_csv.resolve().parent)
    if out in input_dirs:
        raise SystemExit("refusing to write into an input directory")

    versions = load_csv(args.versions_csv)
    corpus = union_corpus_rows(corpus_paths, args.works_csv)
    all_works = assemble_works(corpus, versions)
    skip = excluded_work_ids()
    if skip:
        all_works = [w for w in all_works if w["work_id"] not in skip]
    if args.expected_works and len(all_works) != args.expected_works:
        raise SystemExit(f"expected {args.expected_works} corpus works, found {len(all_works)}")

    out.mkdir(parents=True, exist_ok=True)
    files_dir = out / FILES_DIR
    files_dir.mkdir(parents=True, exist_ok=True)
    progress_path = out / PROGRESS_FILE

    if args.ingest_manual:
        prior = read_progress(progress_path)
        records, problems = ingest_manual_pdfs(all_works, out, prior, force=args.force)
        with progress_path.open("a", encoding="utf-8") as fh:
            total = len(records)
            for i, rec in enumerate(records, start=1):
                rec["index"] = i
                rec["total"] = total
                emit(fh, rec)
                print(
                    f"[{i}/{total}] {rec['work_id']} {rec['pdf_status']:16s} {s(rec.get('stem'))[:48]:48s} {s(rec.get('pdf_source')) or '-'}",
                    flush=True,
                )
        latest = read_progress(progress_path)
        summary = write_run_outputs(out, all_works, latest, {
            "ingest_manual": True,
            "manual_ingested": len(records),
            "manual_problems": len(problems),
            "email_configured": bool(args.email),
        })
        print(json.dumps({
            k: summary[k] for k in (
                "corpus_works", "downloaded", "manual_ingested", "manual_problems", "status_counts", "pdf_sources"
            ) if k in summary
        }, indent=2), flush=True)
        if problems:
            for item in problems:
                print(item, file=sys.stderr)
            raise SystemExit(
                f"manual ingest finished with {len(problems)} unmatched/conflicted file(s); {len(records)} ingested"
            )
        return

    queue = all_works
    if args.unresolved_only or args.search_unresolved or args.pubmed_unresolved:
        queue = [w for w in queue if not existing_pdf(files_dir / f"{w['stem']}.pdf")[0]]
    if args.limit:
        queue = queue[: args.limit]

    prior = read_progress(progress_path)
    fetcher = Fetcher(email=args.email, timeout=args.timeout, sleep=args.sleep, arxiv_sleep=args.arxiv_sleep)

    latest = dict(prior)
    total = len(queue)
    with progress_path.open("a", encoding="utf-8") as fh:
        for i, work in enumerate(queue, start=1):
            dest = files_dir / f"{work['stem']}.pdf"
            rec = process_work(
                work, dest, fetcher, prior.get(work["work_id"]),
                local_ids_only=args.local_ids_only, resolve_only=args.resolve_only,
                force=args.force, skip_attempted=args.skip_attempted,
                search_unresolved=bool(args.search_unresolved),
                pubmed_only=bool(args.pubmed_unresolved),
            )
            rec["index"] = i
            rec["total"] = total
            emit(fh, rec)
            latest[work["work_id"]] = rec
            print(
                f"[{i}/{total}] {work['work_id']} {rec['pdf_status']:16s} {work['stem'][:48]:48s} {s(rec.get('pdf_source')) or '-'}",
                flush=True,
            )

    summary = write_run_outputs(out, all_works, latest, {
        "local_ids_only": bool(args.local_ids_only),
        "resolve_only": bool(args.resolve_only),
        "search_unresolved": bool(args.search_unresolved),
        "pubmed_unresolved": bool(args.pubmed_unresolved),
        "unresolved_only": bool(args.unresolved_only or args.search_unresolved or args.pubmed_unresolved),
        "email_configured": bool(args.email),
    })
    print(json.dumps({k: summary[k] for k in ("corpus_works", "with_landing_url", "with_pdf_url", "downloaded", "direct_search_matches", "status_counts") if k in summary}, indent=2), flush=True)


if __name__ == "__main__":
    main()
