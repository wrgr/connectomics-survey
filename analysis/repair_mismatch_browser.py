#!/usr/bin/env python3
"""Chrome fetch for unresolved mismatch PDFs only.

Does not run --ingest-manual. Does not rebuild the 1,806-work union.
Verifies title/DOI before writing files/<stem>.pdf. Skips resolved rows.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
import collect_corpus_pdfs as P  # noqa: E402
import repair_mismatched_pdfs as R  # noqa: E402
from collect_pmc_browser_pdfs import fetch_pmc_pdf, load_playwright  # noqa: E402

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
SKIP_HREF = re.compile(r"pdf=render|/esm/|springer-static/esm|supplementary", re.I)
PMC_RE = re.compile(r"PMC\d+", re.I)


async def save_verified(dest: Path, data: bytes, title: str, doi: str, extras: list[str], src: str) -> dict | None:
    if not P.looks_like_pdf(data) or P.looks_like_html(data):
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.pdf")
    tmp.write_bytes(data)
    ok, why = R.verify_pdf(tmp, title, doi, extras)
    if not ok:
        tmp.unlink(missing_ok=True)
        print(f"    reject {src} {why[:80]}", flush=True)
        return None
    tmp.replace(dest)
    return {"ok": True, "pdf_source": src, "bytes": len(data), "sha256": P.sha256_bytes(data), "verify": why}


async def try_page_pdf(page, url: str, dest: Path, title: str, doi: str, extras: list[str], src: str) -> dict | None:
    if not url or R.skip_url(url):
        return None
    pdf_resps = []

    def on_response(resp) -> None:
        try:
            ctype = (resp.headers.get("content-type") or "").lower()
        except Exception:
            return
        if "application/pdf" in ctype:
            pdf_resps.append(resp)

    page.on("response", on_response)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(1200)
        for resp in reversed(pdf_resps):
            if SKIP_HREF.search(resp.url or ""):
                continue
            try:
                data = await resp.body()
            except Exception:
                continue
            got = await save_verified(dest, data, title, doi, extras, src + ":nav")
            if got:
                got["pdf_url"] = resp.url
                return got
        try:
            resp = await page.request.get(url, timeout=45000, fail_on_status_code=False)
            data = await resp.body()
            got = await save_verified(dest, data, title, doi, extras, src + ":req")
            if got:
                got["pdf_url"] = url
                return got
        except Exception:
            pass
        html = await page.content()
        hrefs = []
        for m in re.finditer(r'(?:href|content)=["\']([^"\']+)["\']', html, re.I):
            h = m.group(1)
            if SKIP_HREF.search(h):
                continue
            if ".pdf" in h.lower() or "/pdf" in h.lower() or "bitstream" in h.lower():
                hrefs.append(urljoin(page.url, h))
        seen = set()
        for h in hrefs:
            if h in seen or R.skip_url(h):
                continue
            seen.add(h)
            if len(seen) > 20:
                break
            try:
                resp = await page.request.get(h, timeout=30000, fail_on_status_code=False)
                data = await resp.body()
            except Exception:
                continue
            got = await save_verified(dest, data, title, doi, extras, src + ":href")
            if got:
                got["pdf_url"] = h
                return got
        loc = page.get_by_role("link", name=re.compile(r"PDF|Download PDF|Full text PDF", re.I))
        n = await loc.count()
        for i in range(min(n, 4)):
            try:
                async with page.expect_download(timeout=10000) as di:
                    await loc.nth(i).click()
                dl = await di.value
                data = Path(await dl.path()).read_bytes()
                got = await save_verified(dest, data, title, doi, extras, src + ":click")
                if got:
                    got["pdf_url"] = url
                    return got
            except Exception:
                continue
        return None
    finally:
        page.remove_listener("response", on_response)


async def run(limit: int) -> None:
    email = os.environ.get("CONNECTOMICS_MAILTO") or os.environ.get("UNPAYWALL_EMAIL") or "willgray@gmail.com"
    catalog = list(csv.DictReader(R.CATALOG.open()))
    by_id = {r["work_id"]: r for r in catalog}
    core = {r["work_id"]: r for r in csv.DictReader(R.CORE.open())}
    wanted = R.mismatch_queue(by_id)
    if limit:
        wanted = wanted[:limit]
    print("browser mismatch queue", len(wanted), flush=True)
    fetcher = P.Fetcher(email=email, timeout=45, sleep=0.3, arxiv_sleep=2.0)
    async_playwright = load_playwright()
    downloaded = []
    failed = []
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(
                channel="chrome",
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
            )
        except Exception:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
        context = await browser.new_context(user_agent=UA, accept_downloads=True)
        page = await context.new_page()
        with R.PROGRESS.open("a", encoding="utf-8") as log:
            for i, wid in enumerate(wanted, start=1):
                row = {**(core.get(wid) or {}), **(by_id.get(wid) or {})}
                dest = R.FILES / R.file_stem_name(row, "")
                title = row.get("title") or ""
                doi = row.get("doi") or ""
                extras = R.extra_dois_for(wid)
                print(f"[{i}/{len(wanted)}] {wid} {(title or '')[:60]}", flush=True)
                got = None
                pmc = PMC_RE.search(" ".join([row.get("pdf_url") or "", row.get("landing_url") or "", row.get("pmid_url") or ""]))
                if pmc:
                    attempts: list[str] = []
                    try:
                        data, url = await fetch_pmc_pdf(page, pmc.group(0), 45000, attempts)
                        got = await save_verified(dest, data, title, doi, extras, "pmc_browser")
                        if got:
                            got["pdf_url"] = url
                    except Exception as e:
                        print(f"    pmc {type(e).__name__}", flush=True)
                urls = []
                if doi:
                    urls.append((f"https://doi.org/{doi}", "doi"))
                    if doi.startswith("10.1038/"):
                        urls.append((f"https://www.nature.com/articles/{doi.split('/', 1)[1]}", "nature"))
                    if doi.startswith("10.1126/"):
                        urls.append((f"https://www.science.org/doi/{doi}", "science"))
                attempts: list[str] = []
                search_cands, _meta = P.search_by_title_doi(fetcher, row, attempts)
                for url, src in search_cands:
                    if url and not R.skip_url(url):
                        urls.append((url, src))
                pubmed = P.lookup_pubmed(
                    fetcher,
                    {"doi": P.norm_doi(doi), "pmid": P.s(row.get("pmid")), "title": title},
                    attempts,
                    include_search=True,
                )
                for url, src in pubmed:
                    urls.append((url, src))
                seen = set()
                for url, src in urls:
                    if not url or url in seen or R.skip_url(url):
                        continue
                    seen.add(url)
                    try:
                        got = await try_page_pdf(page, url, dest, title, doi, extras, src)
                    except Exception as e:
                        print(f"    {src} {type(e).__name__}", flush=True)
                        got = None
                    if got:
                        break
                rec = {
                    "ts": P.now_ts(),
                    "work_id": wid,
                    "title": title[:200],
                    "doi": doi,
                    "stem": dest.stem,
                    "attempts": "mismatch_browser",
                    "pdf_status": "downloaded" if got else "mismatch_unresolved",
                    "pdf_url": (got or {}).get("pdf_url", ""),
                    "pdf_source": (got or {}).get("pdf_source", "browser"),
                    "local_path": dest.as_posix() if got else "",
                    "bytes": (got or {}).get("bytes", 0),
                    "sha256": (got or {}).get("sha256", ""),
                    "error": "" if got else "browser_no_verified_pdf",
                    "verify": (got or {}).get("verify", ""),
                }
                log.write(__import__("json").dumps(rec) + "\n")
                log.flush()
                if got:
                    R.patch_catalog_row(catalog, wid, rec)
                    downloaded.append(wid)
                    print(f"    OK {got['pdf_source']} {got['verify']}", flush=True)
                else:
                    failed.append(wid)
                    if dest.exists():
                        dest.replace(R.QUARANTINE / dest.name)
                    R.mark_unresolved(catalog, wid, rec["error"])
                    print("    FAIL", flush=True)
        await browser.close()
    R.write_catalog(catalog)
    R.mark_mismatch_resolved(downloaded)
    R.rewrite_summary(catalog)
    print("browser downloaded", len(downloaded), "failed", len(failed))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    asyncio.run(run(args.limit))


if __name__ == "__main__":
    main()
