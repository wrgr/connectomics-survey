#!/usr/bin/env python3
"""Extract selected PDF text for journal-club summaries of the visible core.

Does not copy or commit PDFs. Writes compact jsonl shards under
source_artifact/neurotrailblazers_visible_core/summaries/pdf/.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "postanalysis/pdfs/files"
SUM_IN = ROOT / "source_artifact/neurotrailblazers_visible_core/summaries"
OUT_DIR = SUM_IN / "pdf"
CATALOG = ROOT / "postanalysis/pdfs/paper_links.csv"
PAPERS_PER_SHARD = 30
TEXT_CAP = 12_000

REF_RE = re.compile(
    r"\n\s*(References|Bibliography|Literature Cited|Works Cited|"
    r"REFERENCES|BIBLIOGRAPHY|Literature cited)\b",
    re.I,
)
DISC_RE = re.compile(
    r"\n\s*(Discussion|DISCUSSION|Conclusions?|CONCLUSIONS?|"
    r"Future work|Outlook|Limitations|Concluding remarks)\b",
    re.I,
)


def pdftotext(path: Path) -> str:
    r = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.stdout or ""


def selected_text(raw: str, cap: int = TEXT_CAP) -> tuple[str, int]:
    text = re.sub(r"\n{3,}", "\n\n", (raw or "").replace("\x00", ""))
    m = REF_RE.search(text)
    body = text[: m.start()] if m else text
    front = body[:5000]
    disc = ""
    hits = list(DISC_RE.finditer(body))
    if hits:
        start = hits[-1].start()
        disc = body[start : start + 4500]
    elif len(body) > 8000:
        disc = body[-3500:]
    if disc and disc not in front:
        combo = front.rstrip() + "\n\n[...]\n\n" + disc.lstrip()
    else:
        combo = front
    if len(combo) > cap:
        combo = combo[:cap]
    return combo.strip(), len(body)


def load_abstract_inputs() -> list[dict]:
    rows = []
    for path in sorted(SUM_IN.glob("input_shard_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def downloaded_work_ids() -> set[str]:
    if not CATALOG.exists():
        return set()
    return {
        r["work_id"]
        for r in csv.DictReader(CATALOG.open())
        if r.get("pdf_status") == "downloaded"
    }


def enrich(row: dict, downloaded: set[str]) -> dict:
    stem = Path(row.get("pdf_local") or "").name
    pdf_path = PDF_DIR / stem if stem else None
    trusted = row["work_id"] in downloaded and bool(pdf_path and pdf_path.exists())
    rec = {
        "work_id": row["work_id"],
        "uuid": row["uuid"],
        "id": row["id"],
        "title": row["title"],
        "authors": row["authors"],
        "year": row["year"],
        "journal": row["journal"],
        "doi": row.get("doi"),
        "dimension": row.get("dimension"),
        "role": row.get("role"),
        "in": row.get("in"),
        "out": row.get("out"),
        "k_core": row.get("k_core"),
        "cites": row.get("cites"),
        "pdf_url": row.get("pdf_url"),
        "pdf_local": row.get("pdf_local") if trusted else "",
        "landing_url": row.get("landing_url"),
        "stages": row.get("stages") or [],
        "datasets": row.get("datasets") or [],
        "organism": row.get("organism") or [],
        "method": row.get("method") or [],
        "axis": row.get("axis"),
        "abstract": row.get("abstract") or "",
        "pdf_trust": "ok" if trusted else "mismatch",
        "pdf_chars_body": 0,
        "pdf_text": "",
    }
    if not trusted:
        rec["pdf_text"] = rec["abstract"]
        return rec
    raw = pdftotext(pdf_path)
    rec["pdf_text"], rec["pdf_chars_body"] = selected_text(raw)
    if len(rec["pdf_text"]) < 400:
        rec["pdf_text"] = rec["abstract"]
        rec["pdf_trust"] = "thin_extract"
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-ids-file", type=Path)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--papers-per-shard", type=int, default=PAPERS_PER_SHARD)
    args = ap.parse_args()
    rows = load_abstract_inputs()
    if args.work_ids_file:
        wanted = {ln.strip() for ln in args.work_ids_file.read_text().splitlines() if ln.strip()}
        rows = [r for r in rows if r["work_id"] in wanted]
    out_dir = args.out_dir or OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("input_shard_*.jsonl"):
        old.unlink()
    downloaded = downloaded_work_ids()
    enriched = [None] * len(rows)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(enrich, row, downloaded): i for i, row in enumerate(rows)}
        for fut in as_completed(futs):
            enriched[futs[fut]] = fut.result()
    n_mismatch = sum(1 for r in enriched if r["pdf_trust"] != "ok")
    n_short = sum(1 for r in enriched if len(r["pdf_text"]) < 1000)
    per = args.papers_per_shard
    shard_i = 0
    for start in range(0, len(enriched), per):
        chunk = enriched[start : start + per]
        path = out_dir / f"input_shard_{shard_i:02d}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for rec in chunk:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        shard_i += 1
    print(
        "papers",
        len(enriched),
        "shards",
        shard_i,
        "per_shard",
        per,
        "pdf_trust_not_ok",
        n_mismatch,
        "text<1k",
        n_short,
        "median_selected",
        sorted(len(r["pdf_text"]) for r in enriched)[len(enriched) // 2] if enriched else 0,
    )


if __name__ == "__main__":
    main()
