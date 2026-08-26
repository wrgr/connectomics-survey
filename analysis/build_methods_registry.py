#!/usr/bin/env python3
"""Verify the per-stage methods registry (placeholder v0.1 todo resolution).

Each entry is resolved against Crossref (DOI resolves; title keywords match)
and cross-checked for presence in the frozen pilot corpus. Software without a
paper enters as a software record (repository URL), per protocol v5 §2.
Entries that fail verification are kept with status `verification-failed`
rather than silently guessed.

Output: postanalysis/registry/methods_registry_draft.csv
"""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "postanalysis" / "registry" / "methods_registry_draft.csv"
ENRICHED = REPO / "postanalysis" / "enriched2" / "canonical_works_enriched_pass2.csv"

# (stage, method, group, doi_or_None, repo_url_or_None, title_keywords)
ENTRIES = [
    ("preparation", "Large-volume en-bloc staining (rOTO)", "Hua/Helmstaedter (MPI)", "10.1038/ncomms8923", None, "en bloc staining"),
    ("preparation", "Whole-brain EM staining", "Mikula/Denk (MPI)", "10.1038/nmeth.3361", None, "whole brain staining electron"),
    ("preparation", "ECS-preserving fixation", "Pallotto/Briggman (NIH)", "10.7554/elife.08206", None, "extracellular space preserv"),
    ("sectioning", "SBF-SEM", "Denk & Horstmann (MPI)", "10.1371/journal.pbio.0020329", None, "block face scanning"),
    ("sectioning", "ATUM + WaferMapper", "Hayworth/Lichtman (Harvard)", "10.3389/fncir.2014.00068", None, "wafermapper"),
    ("sectioning", "FIB-SEM for circuits", "Knott (EPFL)", "10.1523/jneurosci.3189-07.2008", None, "focused ion beam"),
    ("sectioning", "Enhanced long-run FIB-SEM", "Xu/Hess (Janelia)", "10.7554/elife.25916", None, "enhanced fib-sem"),
    ("sectioning", "GridTape TEM", "Phelps/Lee (Harvard)", "10.1016/j.cell.2020.12.013", None, "automated transmission electron"),
    ("sectioning", "Hot-knife partitioning", "Hayworth (Janelia)", "10.1038/nmeth.3292", None, "smooth thick partitioning"),
    ("sectioning", "GCIB-SEM", "Hayworth (Janelia)", "10.1038/s41592-019-0641-2", None, "gas cluster ion beam"),
    ("acquisition", "TEMCA camera-array ssTEM", "Bock (Janelia)", "10.1038/nature09802", None, "network anatomy"),
    ("acquisition", "Multibeam SEM", "Eberle (Zeiss)", "10.1111/jmi.12224", None, "multi-beam"),
    ("acquisition", "FAST-EM array tomography", "Kievits/Hoogenboom (Delft)", "10.1515/mim-2024-0005", None, "fast-em array tomography"),
    ("acquisition", "SmartEM ML-guided acquisition", "MIT/Harvard", "10.1038/s41592-025-02929-3", None, "smartem"),
    ("alignment", "Elastic serial-section alignment", "Saalfeld (Janelia)", "10.1038/nmeth.2072", None, "elastic"),
    ("alignment", "SOFIMA flow-based alignment", "Google", None, "https://github.com/google-research/sofima", None),
    ("segmentation", "Flood-filling networks", "Januszewski/Jain (Google)", "10.1038/s41592-018-0049-4", None, "flood-filling"),
    ("segmentation", "SegEM", "Berning/Helmstaedter (MPI)", "10.1016/j.neuron.2015.09.003", None, "segem"),
    ("segmentation", "GALA agglomeration", "Nunez-Iglesias (Janelia)", "10.3389/fninf.2014.00034", None, "gala"),
    ("segmentation", "Structured-loss affinity segmentation", "Funke (Janelia)", "10.1109/tpami.2018.2835450", None, "structured loss"),
    ("segmentation", "CDeep3M cloud segmentation", "Ellisman (NCMIR)", "10.1038/s41592-018-0106-z", None, "cdeep3m"),
    ("proofreading", "CATMAID", "Saalfeld/Cardona", "10.1093/bioinformatics/btp266", None, "catmaid"),
    ("proofreading", "KNOSSOS + RESCOP consensus", "Helmstaedter (MPI)", "10.1038/nn.2868", None, "high-accuracy neurite"),
    ("proofreading", "EyeWire crowd proofreading", "Kim/Seung (MIT/Princeton)", "10.1038/nature13240", None, "space-time wiring"),
    ("proofreading", "webKnossos", "Boergens/Helmstaedter (MPI)", "10.1038/nmeth.4331", None, "webknossos"),
    ("proofreading", "VAST", "Berger/Lichtman (Harvard)", "10.3389/fncir.2018.00088", None, "vast"),
    ("proofreading", "Neuroglancer", "Maitin-Shepard (Google)", None, "https://github.com/google/neuroglancer", None),
    ("proofreading", "CAVE / PyChunkedGraph", "Dorkenwald (Princeton/Allen)", "10.1038/s41592-024-02426-z", None, "connectome annotation versioning"),
    ("synapses", "SynEM", "Staffler/Helmstaedter (MPI)", "10.7554/elife.26414", None, "synem"),
    ("synapses", "Synful partner prediction", "Buhmann/Funke (Janelia)", "10.1038/s41592-021-01183-7", None, "synaptic partners"),
    ("synapses", "ilastik interactive ML", "Berg/Kreshuk (EMBL)", "10.1038/s41592-019-0582-9", None, "ilastik"),
    ("synapses", "SyConn", "Dorkenwald/Kornfeld (MPI)", "10.1038/nmeth.4206", None, "automated synaptic connectivity"),
    ("infrastructure", "BossDB ecosystem", "Vogelstein/Gray Roncal (APL/JHU; COI-0)", "10.1038/s41592-018-0181-1", None, "community-developed"),
    ("infrastructure", "neuPrint", "Plaza (Janelia)", "10.3389/fninf.2022.896292", None, "neuprint"),
    ("infrastructure", "DVID", "Katz/Plaza (Janelia)", "10.3389/fncir.2019.00005", None, "dvid"),
    ("infrastructure", "CloudVolume/Igneous", "Silversmith (Princeton)", None, "https://github.com/seung-lab/cloud-volume", None),
    ("analysis", "natverse", "Bates/Jefferis (Cambridge)", "10.7554/elife.53350", None, "natverse"),
    ("analysis", "Network motifs", "Milo/Alon (Weizmann)", "10.1126/science.298.5594.824", None, "network motifs"),
    ("modeling", "Connectome-constrained visual-system model", "Lappalainen/Turaga (Janelia)", "10.1038/s41586-024-07939-3", None, "connectome-constrained"),
]

_last = {"t": 0.0}


def _get(url):
    wait = 1.0 - (time.time() - _last["t"])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": "connectomics-survey-registry"})
    _last["t"] = time.time()
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower())


def main():
    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    corpus_dois = set()
    with ENRICHED.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = (row.get("doi") or "").strip().lower()
            if d:
                corpus_dois.add(d)

    out = []
    for stage, method, group, doi, repo, kw in ENTRIES:
        rec = dict(stage=stage, method=method, group=group, doi=doi or "", repo=repo or "",
                   verified_title="", year="", status="", in_pilot_corpus="")
        if repo and not doi:
            rec["status"] = "software-record (v5 §2: repository suffices)"
        elif doi:
            try:
                m = _get("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]
                title = (m.get("title") or [""])[0]
                yr = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
                rec["verified_title"], rec["year"] = title, yr or ""
                ok = (not kw) or all(w in norm(title) for w in norm(kw).split()) or norm(kw) in norm(title)
                rec["status"] = "verified" if ok else "verification-failed (title mismatch)"
            except Exception as e:
                rec["status"] = f"verification-failed ({type(e).__name__})"
        else:
            # bibliographic resolution for entries without a pinned DOI
            try:
                q = urllib.parse.quote(f"{method} {kw or ''}")
                items = _get(f"https://api.crossref.org/works?rows=3&query.bibliographic={q}&select=DOI,title,issued")["message"]["items"]
                hit = next((it for it in items if kw and norm(kw) in norm((it.get("title") or [""])[0])), None)
                if hit:
                    rec["doi"] = hit["DOI"].lower()
                    rec["verified_title"] = (hit.get("title") or [""])[0]
                    rec["year"] = (hit.get("issued", {}).get("date-parts") or [[None]])[0][0] or ""
                    rec["status"] = "verified (bibliographic resolution)"
                else:
                    rec["status"] = "needs_verification (no confident match)"
            except Exception as e:
                rec["status"] = f"verification-failed ({type(e).__name__})"
        rec["in_pilot_corpus"] = "yes" if rec["doi"].lower() in corpus_dois else ""
        out.append(rec)
        print(f"{rec['status']:45s} | {stage:14s} | {method[:38]:38s} | {rec['doi']}")

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    good = sum(1 for r in out if r["status"].startswith(("verified", "software")))
    print(f"\n{good}/{len(out)} verified or software-record; written {OUT} ({run_ts})")


if __name__ == "__main__":
    main()
