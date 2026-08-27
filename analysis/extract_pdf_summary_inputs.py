#!/usr/bin/env python3
"""Extract selected PDF text for journal-club summaries of the visible core.

Does not copy or commit PDFs. Writes compact jsonl shards under
source_artifact/neurotrailblazers_visible_core/summaries/pdf/.
"""
from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "postanalysis/pdfs/files"
SUM_IN = ROOT / "source_artifact/neurotrailblazers_visible_core/summaries"
OUT_DIR = SUM_IN / "pdf"
PAPERS_PER_SHARD = 30
TEXT_CAP = 12_000
# PDFs on disk that are known not to match the catalog row.
PDF_MISMATCH = {
    "work_de90f3f542a40fe0",  # Baker 2019; file is Keijser & Sadeh 2026
}

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


def enrich(row: dict) -> dict:
    stem = Path(row.get("pdf_local") or "").name
    pdf_path = PDF_DIR / stem if stem else None
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
        "pdf_local": row.get("pdf_local"),
        "landing_url": row.get("landing_url"),
        "stages": row.get("stages") or [],
        "datasets": row.get("datasets") or [],
        "organism": row.get("organism") or [],
        "method": row.get("method") or [],
        "axis": row.get("axis"),
        "abstract": row.get("abstract") or "",
        "pdf_trust": "mismatch" if row["work_id"] in PDF_MISMATCH else "ok",
        "pdf_chars_body": 0,
        "pdf_text": "",
    }
    if rec["pdf_trust"] == "mismatch" or not pdf_path or not pdf_path.exists():
        rec["pdf_text"] = rec["abstract"]
        return rec
    raw = pdftotext(pdf_path)
    rec["pdf_text"], rec["pdf_chars_body"] = selected_text(raw)
    if len(rec["pdf_text"]) < 400:
        rec["pdf_text"] = rec["abstract"]
        rec["pdf_trust"] = "thin_extract"
    return rec


def main() -> None:
    rows = load_abstract_inputs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("input_shard_*.jsonl"):
        old.unlink()
    enriched = [None] * len(rows)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(enrich, row): i for i, row in enumerate(rows)}
        for fut in as_completed(futs):
            enriched[futs[fut]] = fut.result()
    n_mismatch = sum(1 for r in enriched if r["pdf_trust"] != "ok")
    n_short = sum(1 for r in enriched if len(r["pdf_text"]) < 1000)
    shard_i = 0
    for start in range(0, len(enriched), PAPERS_PER_SHARD):
        chunk = enriched[start : start + PAPERS_PER_SHARD]
        path = OUT_DIR / f"input_shard_{shard_i:02d}.jsonl"
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
        PAPERS_PER_SHARD,
        "pdf_trust_not_ok",
        n_mismatch,
        "text<1k",
        n_short,
        "median_selected",
        sorted(len(r["pdf_text"]) for r in enriched)[len(enriched) // 2],
    )


if __name__ == "__main__":
    main()
