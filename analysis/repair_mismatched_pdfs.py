#!/usr/bin/env python3
"""Replace wrong PDFs for known catalog mismatches. Patches those catalog rows only.

Does not run --ingest-manual. Does not rebuild the 1,806-work union.
Verifies title/DOI on the first pages before overwriting files/<stem>.pdf.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import tempfile
import time
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
SUMMARY = ROOT / "postanalysis/pdfs/pdf_summary.json"
CORE = ROOT / "postanalysis/registry/sota_history_core_labeled.csv"

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


def token_coverage(title: str, text: str) -> float:
    toks = [t for t in P.title_tokens(title) if len(t) > 3]
    if not toks:
        return 0.0
    hay = P.norm_title(text)
    return sum(1 for t in toks if t in hay) / len(toks)


def verify_pdf(path: Path, title: str, doi: str) -> tuple[bool, str]:
    head = P.pdf_first_page_text(path)
    if not head.strip():
        return False, "empty_extract"
    nd = P.norm_doi(doi)
    compact = head.lower().replace(" ", "").replace("\n", "")
    if nd and nd.replace(" ", "") in compact:
        return True, "doi"
    # Require a consecutive title-token window so shared words like
    # "connectome" / "brain" do not count as a match.
    if P.title_token_window_hit(title, head[:4000], min_tokens=4):
        return True, "token_window"
    toks = [t for t in P.title_tokens(title) if len(t) > 3]
    cov = token_coverage(title, head[:8000])
    if len(toks) >= 5 and cov >= 0.9:
        return True, f"high_cov={cov:.2f}"
    sim = P.title_sim(title, head[:500])
    if sim >= 0.5:
        return True, f"sim={sim:.2f}"
    return False, f"no_match cov={cov:.2f} sim={sim:.2f} head={head[:120]!r}"


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
        out.extend(P.europepmc_candidates({"resultList": {"result": [row]}}))
    return P._dedupe_cands(out)


def unpaywall_cands(fetcher: P.Fetcher, doi: str) -> list[tuple[str, str]]:
    attempts: list[str] = []
    return P.lookup_unpaywall(fetcher, doi, attempts)


def openalex_cands(fetcher: P.Fetcher, doi: str) -> list[tuple[str, str]]:
    if not doi:
        return []
    url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi)
    try:
        data = fetcher.get_json(url)
    except Exception:
        return []
    return P.openalex_candidates(data if isinstance(data, dict) else {})


def arxiv_id_variants(arxiv: str) -> list[str]:
    ax = P.norm_arxiv(arxiv)
    if not ax:
        return []
    out = [ax]
    # New-style ids are YYMM.NNNNN (5 digits). Catalog sometimes dropped a trailing 0.
    if re.fullmatch(r"\d{4}\.\d{4}", ax):
        out.append(ax + "0")
    return out


def openalex_title_cands(fetcher: P.Fetcher, title: str, doi: str, year: str) -> list[tuple[str, str]]:
    if not title:
        return []
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
        {"search": title[:180], "per-page": "5"}
    )
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
        if pdf:
            out.append((pdf, "openalex_title"))
        for loc in work.get("locations") or []:
            if not isinstance(loc, dict):
                continue
            pdf = P.s(loc.get("pdf_url"))
            if pdf:
                out.append((pdf, "openalex_title"))
    return P._dedupe_cands(out)


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
    cands.extend(openalex_cands(fetcher, doi))
    cands.extend(openalex_title_cands(fetcher, title, doi, year))
    cands.extend(europepmc_doi_cands(fetcher, doi, title))
    # Do not reuse the known-wrong catalog URL (usually a mismatched Europe PMC render).
    return P._dedupe_cands(cands)


def try_download(fetcher: P.Fetcher, cands: list[tuple[str, str]], dest: Path, title: str, doi: str) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = "no_candidates"
    for url, src in cands:
        data = None
        for attempt in range(3):
            try:
                data = fetcher.get_bytes(url)
                break
            except Exception as e:
                last = f"{src}:{type(e).__name__}"
                if "HTTP" in type(e).__name__ or "Error" in type(e).__name__:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
        if data is None:
            continue
        if P.looks_like_html(data) or not P.looks_like_pdf(data):
            last = f"{src}:not_pdf"
            continue
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        ok, why = verify_pdf(tmp_path, title, doi)
        if not ok:
            tmp_path.unlink(missing_ok=True)
            last = f"{src}:verify_fail:{why}"
            continue
        dest.write_bytes(data)
        tmp_path.unlink(missing_ok=True)
        return {
            "ok": True,
            "pdf_url": url,
            "pdf_source": src,
            "bytes": len(data),
            "sha256": P.sha256_bytes(data),
            "verify": why,
            "error": "",
        }
    return {"ok": False, "error": last}


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


def main() -> None:
    email = os.environ.get("CONNECTOMICS_MAILTO") or os.environ.get("UNPAYWALL_EMAIL") or ""
    if not email:
        raise SystemExit("set UNPAYWALL_EMAIL (Unpaywall requires a contact address)")
    fetcher = P.Fetcher(email=email, timeout=60, sleep=0.4, arxiv_sleep=3.0)
    wanted = [r["work_id"] for r in csv.DictReader(MISMATCHES.open())]
    catalog = list(csv.DictReader(CATALOG.open()))
    by_id = {r["work_id"]: r for r in catalog}
    core = {r["work_id"]: r for r in csv.DictReader(CORE.open())}
    repaired = []
    skipped_ok = []
    failed = []
    with PROGRESS.open("a", encoding="utf-8") as log:
        for i, wid in enumerate(wanted, start=1):
            row = by_id.get(wid) or core.get(wid)
            if not row:
                failed.append((wid, "not_in_catalog"))
                continue
            stem = Path(row.get("stem") or core.get(wid, {}).get("stem") or "").name
            dest = FILES / f"{stem}.pdf" if not stem.endswith(".pdf") else FILES / stem
            title = row.get("title") or core.get(wid, {}).get("title") or ""
            doi = row.get("doi") or core.get(wid, {}).get("doi") or ""
            if dest.exists():
                ok, why = verify_pdf(dest, title, doi)
                if ok:
                    print(f"[{i}/{len(wanted)}] {wid} SKIP already_matches {why}", flush=True)
                    skipped_ok.append(wid)
                    continue
            cands = candidates_for({**core.get(wid, {}), **row}, fetcher)
            got = try_download(fetcher, cands, dest, title, doi)
            rec = {
                "ts": P.now_ts(),
                "work_id": wid,
                "title": title[:200],
                "doi": doi,
                "stem": stem,
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
                    qdir = FILES.parent / "mismatch_quarantine"
                    qdir.mkdir(parents=True, exist_ok=True)
                    dest.replace(qdir / dest.name)
                    for crow in catalog:
                        if crow["work_id"] == wid:
                            crow["pdf_status"] = "paywall"
                            crow["error"] = rec.get("error", "mismatch_unresolved")
                            crow["ts"] = P.now_ts()
                            break
    with CATALOG.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(catalog[0].keys()))
        w.writeheader()
        w.writerows(catalog)
    rewrite_summary(catalog)
    report = {
        "repaired": repaired,
        "already_ok": skipped_ok,
        "failed": [{"work_id": w, "error": e} for w, e in failed],
        "n_repaired": len(repaired),
        "n_already_ok": len(skipped_ok),
        "n_failed": len(failed),
    }
    (ROOT / "postanalysis/registry/pdf_mismatch_repair_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("repaired", len(repaired), "already_ok", len(skipped_ok), "failed", len(failed))
    for wid, err in failed:
        print(" FAIL", wid, err)


if __name__ == "__main__":
    main()
