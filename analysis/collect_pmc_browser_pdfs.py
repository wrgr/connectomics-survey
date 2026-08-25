#!/usr/bin/env python3
"""Download PMC author-manuscript PDFs in Chrome (NCBI proof-of-work cookie).

urllib hits a "Preparing to download" HTML interstitial on NIHMS PDF URLs.
A real Chrome session runs the silent JS challenge, then the named
`pdf/nihms….pdf` file is a normal PDF. This pass visits the article page,
scrapes that href, and fetches it with the browser cookie jar.

`--workers` runs that many isolated Chrome contexts in one browser. Existing
valid PDFs are skipped (`--unresolved-only`), so a rerun resumes. Progress is
append-only JSONL; the catalog is rewritten once when the pass finishes.

Does not mutate checkpoint files. Default work set is the same v2∪v3 union as
`collect_corpus_pdfs.py`.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("collect_corpus_pdfs", HERE / "collect_corpus_pdfs.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def load_playwright():
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise SystemExit(
            "playwright is required for PMC browser downloads: python3 -m pip install playwright"
        ) from e
    return async_playwright


def pmcid_for(work: dict[str, str], prior: dict[str, Any] | None, fetcher: P.Fetcher, attempts: list[str]) -> str:
    blobs = [
        P.s((prior or {}).get("pdf_url")),
        P.s((prior or {}).get("attempts")),
        P.s(work.get("pdf_url")),
        P.s(work.get("landing_url")),
        P.s(work.get("pmid_url")),
        P.s(work.get("error")),
    ]
    for blob in blobs:
        pid = P.pmcid_from_text(blob)
        if pid:
            attempts.append("pmcid:catalog")
            return pid
    cands = P.lookup_pubmed(fetcher, work, attempts, include_search=True)
    for url, _ in cands:
        pid = P.pmcid_from_text(url)
        if pid:
            attempts.append("pmcid:pubmed")
            return pid
    attempts.append("pmcid:none")
    return ""


async def wait_for_pow_cookie(page, timeout_ms: int) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        names = {c.get("name") for c in await page.context.cookies()}
        if "cloudpmc-viewer-pow" in names:
            return True
        await page.wait_for_timeout(250)
    return False


async def _pdf_from_responses(responses: list) -> bytes:
    for resp in reversed(responses):
        try:
            ctype = (resp.headers.get("content-type") or "").lower()
            if "application/pdf" not in ctype:
                continue
            data = await resp.body()
        except Exception:
            continue
        if P.looks_like_pdf(data):
            return data
    return b""


async def fetch_pmc_pdf(page, pmcid: str, timeout_ms: int, attempts: list[str]) -> tuple[bytes, str]:
    article = P.pmc_article_url(pmcid)
    await page.goto(article, wait_until="domcontentloaded", timeout=timeout_ms)
    await page.wait_for_timeout(500)
    html = await page.content()
    hrefs = P.pmc_named_pdf_urls_from_html(html, pmcid)
    if not hrefs:
        loc = page.get_by_role("link", name=re.compile(r"PDF", re.I))
        n = await loc.count()
        for i in range(min(n, 4)):
            href = (await loc.nth(i).get_attribute("href")) or ""
            if href and "supplement" not in href.lower():
                hrefs.append(urllib.parse.urljoin(article, href))
    if not hrefs:
        hrefs.append(urllib.parse.urljoin(article, "pdf/"))
        attempts.append("pmc_browser:fallback_pdf_dir")
    else:
        attempts.append(f"pmc_browser:hrefs:{len(hrefs)}")

    pdf_resps: list = []

    def on_response(resp) -> None:
        try:
            ctype = (resp.headers.get("content-type") or "").lower()
        except Exception:
            return
        if "application/pdf" in ctype:
            pdf_resps.append(resp)

    page.on("response", on_response)
    try:
        for url in hrefs:
            pdf_resps.clear()
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if await wait_for_pow_cookie(page, min(12000, timeout_ms)):
                attempts.append("pmc_browser:pow_cookie")
            else:
                attempts.append("pmc_browser:pow_cookie_miss")
                await page.wait_for_timeout(2500)
            data = await _pdf_from_responses(pdf_resps)
            if data:
                attempts.append("pmc_browser:ok")
                return data, url
            await page.goto(url, wait_until="load", timeout=timeout_ms)
            await page.wait_for_timeout(1000)
            data = await _pdf_from_responses(pdf_resps)
            if data:
                attempts.append("pmc_browser:ok_retry")
                return data, url
            try:
                resp = await page.request.get(url, timeout=timeout_ms, fail_on_status_code=False)
                data = await resp.body()
            except Exception:
                attempts.append("pmc_browser:get_error")
                continue
            if P.looks_like_pdf(data):
                attempts.append("pmc_browser:ok_request")
                return data, url
            attempts.append("pmc_browser:not_pdf")
        return b"", hrefs[0] if hrefs else article
    finally:
        page.remove_listener("response", on_response)


async def process_work(
    work: dict[str, str],
    dest: Path,
    page,
    fetcher: P.Fetcher,
    prior: dict[str, Any] | None,
    *,
    timeout_ms: int,
    force: bool,
) -> dict[str, Any]:
    attempts: list[str] = []
    skip, why = P.should_skip(prior, dest, skip_attempted=False, force=force)
    if skip:
        ok, nbytes, digest = P.existing_pdf(dest)
        extra = {
            "pdf_url": P.s((prior or {}).get("pdf_url")),
            "pdf_source": P.s((prior or {}).get("pdf_source")),
            "local_path": dest.as_posix() if ok else P.s((prior or {}).get("local_path")),
            "bytes": nbytes if ok else (prior or {}).get("bytes") or 0,
            "sha256": digest if ok else P.s((prior or {}).get("sha256")),
            "attempts": [f"resume:{why}"],
            "error": "",
        }
        return P.progress_record(work, "downloaded" if ok else P.s((prior or {}).get("pdf_status")) or "linked", extra)

    pmcid = await asyncio.to_thread(pmcid_for, work, prior, fetcher, attempts)
    if not pmcid:
        status = P.s((prior or {}).get("pdf_status")) or "paywall"
        extra = {
            "pdf_url": P.s((prior or {}).get("pdf_url")),
            "pdf_source": P.s((prior or {}).get("pdf_source")),
            "local_path": "", "bytes": 0, "sha256": "",
            "attempts": attempts, "error": P.s((prior or {}).get("error")),
        }
        return P.progress_record(work, status, extra)

    data, url = await fetch_pmc_pdf(page, pmcid, timeout_ms, attempts)
    if P.looks_like_pdf(data):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return P.progress_record(work, "downloaded", {
            "pdf_url": url, "pdf_source": "pmc_browser",
            "local_path": dest.as_posix(), "bytes": len(data),
            "sha256": P.sha256_bytes(data), "attempts": attempts, "error": "",
        })
    status = P.s((prior or {}).get("pdf_status")) or "download_failed"
    extra = {
        "pdf_url": url, "pdf_source": "pmc_browser",
        "local_path": "", "bytes": 0, "sha256": "",
        "attempts": attempts,
        "error": "not a PDF after Chrome PMC fetch",
    }
    if prior:
        for k in ("search_match", "match_method", "matched_title", "matched_doi", "title_similarity", "search_api"):
            if prior.get(k) not in (None, ""):
                extra[k] = prior[k]
    return P.progress_record(work, status, extra)


async def run(args: argparse.Namespace) -> None:
    corpus_paths = list(args.corpus_csv) if args.corpus_csv else list(P.DEFAULT_CORPORA)
    out = args.out.resolve()
    input_dirs = {p.resolve().parent for p in corpus_paths}
    input_dirs.add(args.versions_csv.resolve().parent)
    if args.works_csv:
        input_dirs.add(args.works_csv.resolve().parent)
    if out in input_dirs:
        raise SystemExit("refusing to write into an input directory")

    versions = P.load_csv(args.versions_csv)
    corpus = P.union_corpus_rows(corpus_paths, args.works_csv)
    all_works = P.assemble_works(corpus, versions)
    skip = P.excluded_work_ids()
    if skip:
        all_works = [w for w in all_works if w["work_id"] not in skip]
    if args.expected_works and len(all_works) != args.expected_works:
        raise SystemExit(f"expected {args.expected_works} corpus works, found {len(all_works)}")

    files_dir = out / P.FILES_DIR
    files_dir.mkdir(parents=True, exist_ok=True)
    queue_works = all_works
    if args.unresolved_only:
        queue_works = [w for w in queue_works if not P.existing_pdf(files_dir / f"{w['stem']}.pdf")[0]]
    if args.work_id:
        want = set(args.work_id)
        queue_works = [w for w in queue_works if w["work_id"] in want]
        missing = want - {w["work_id"] for w in queue_works}
        if missing:
            raise SystemExit(f"work_id not in corpus: {sorted(missing)}")
    if args.limit:
        queue_works = queue_works[: args.limit]

    progress_path = out / P.PROGRESS_FILE
    prior = P.read_progress(progress_path)
    timeout_ms = args.timeout * 1000
    n_workers = max(1, args.workers)

    async_playwright = load_playwright()
    latest = dict(prior)
    total = len(queue_works)
    done = 0
    write_lock = asyncio.Lock()

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(
                channel=args.channel,
                headless=not args.headed,
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
            )
        except Exception as e:
            raise SystemExit(f"failed to launch Chrome ({args.channel}): {e}") from e

        work_q: asyncio.Queue = asyncio.Queue()
        for work in queue_works:
            work_q.put_nowait(work)

        fh = progress_path.open("a", encoding="utf-8")
        contexts = []
        pages = []
        try:
            async def worker(slot: int) -> None:
                nonlocal done
                fetcher = P.Fetcher(email=args.email, timeout=args.timeout, sleep=0.35, arxiv_sleep=3.0)
                context = await browser.new_context(
                    accept_downloads=False,
                    locale="en-US",
                    user_agent=UA,
                    viewport={"width": 1280, "height": 900},
                )
                page = await context.new_page()
                contexts.append(context)
                pages.append(page)
                while True:
                    try:
                        work = work_q.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    dest = files_dir / f"{work['stem']}.pdf"
                    try:
                        rec = await asyncio.wait_for(
                            process_work(
                                work, dest, page, fetcher, prior.get(work["work_id"]),
                                timeout_ms=timeout_ms, force=args.force,
                            ),
                            timeout=(args.timeout + 25),
                        )
                    except asyncio.TimeoutError:
                        rec = P.progress_record(work, "download_failed", {
                            "pdf_url": P.s((prior.get(work["work_id"]) or {}).get("pdf_url")),
                            "pdf_source": "pmc_browser",
                            "local_path": "", "bytes": 0, "sha256": "",
                            "attempts": ["pmc_browser:error:TimeoutError"],
                            "error": f"timed out after {args.timeout + 25}s",
                        })
                    except Exception as e:
                        rec = P.progress_record(work, "download_failed", {
                            "pdf_url": P.s((prior.get(work["work_id"]) or {}).get("pdf_url")),
                            "pdf_source": "pmc_browser",
                            "local_path": "", "bytes": 0, "sha256": "",
                            "attempts": [f"pmc_browser:error:{type(e).__name__}"],
                            "error": str(e)[:300],
                        })
                    async with write_lock:
                        done += 1
                        rec["index"] = done
                        rec["total"] = total
                        rec["worker"] = slot
                        P.emit(fh, rec)
                        latest[work["work_id"]] = rec
                        print(
                            f"[{done}/{total} w{slot}] {work['work_id']} {rec['pdf_status']:16s} "
                            f"{work['stem'][:48]:48s} {P.s(rec.get('pdf_source')) or '-'}",
                            flush=True,
                        )
                    if args.sleep:
                        await asyncio.sleep(args.sleep)

            await asyncio.gather(*(worker(i) for i in range(n_workers)))
        finally:
            fh.close()
            for page in pages:
                await page.close()
            for context in contexts:
                await context.close()
            await browser.close()

    P.write_catalog(out / P.CATALOG_FILE, all_works, latest)
    n_audit = P.write_audit(out / P.AUDIT_FILE, all_works, latest)
    summary = P.summarize(all_works, latest)
    summary.update({
        "pmc_browser": True,
        "pmc_browser_workers": n_workers,
        "unresolved_only": bool(args.unresolved_only),
        "direct_search_audit_rows": n_audit,
        "email_configured": bool(args.email),
        "out": str(out),
    })
    (out / P.SUMMARY_FILE).write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({
        k: summary[k] for k in (
            "corpus_works", "with_pdf_url", "downloaded", "status_counts", "pdf_sources"
        ) if k in summary
    }, indent=2), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-csv", type=Path, action="append", default=None)
    ap.add_argument("--works-csv", type=Path, default=P.DEFAULT_WORKS_CSV)
    ap.add_argument("--versions-csv", type=Path, default=Path("postanalysis/works/work_versions.csv"))
    ap.add_argument("--out", type=Path, default=Path("postanalysis/pdfs"))
    ap.add_argument("--email", default=os.environ.get("CONNECTOMICS_MAILTO") or os.environ.get("UNPAYWALL_EMAIL") or "")
    ap.add_argument("--unresolved-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--work-id", action="append", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4, help="Parallel Chrome contexts (default 4).")
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--expected-works", type=int, default=0)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--channel", default="chrome", help="Playwright browser channel (chrome).")
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
