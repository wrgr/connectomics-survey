#!/usr/bin/env python3
"""IA-015 Step 1+2: build the review pool and freeze the probe/attestation panel.

Resolves each registered work against Crossref (identifier verification,
title/year/venue consistency, retraction check) and Semantic Scholar
(paper IDs + author IDs, matching the frozen pipeline's primary backend),
attempts OpenAlex enrichment (gracefully skipped when the shared daily
budget is exhausted), cross-references the frozen corpus, and writes:

  postanalysis/review_pool/review_pool.json
  postanalysis/review_pool/probe_panel_frozen.json (+ .sha256 sidecar)
  postanalysis/review_pool/resolution_log.json

Re-running refreshes review_pool.json; probe_panel_frozen.json is a freeze
artifact and the script refuses to overwrite it unless --refreeze is given
(a refreeze is a logged deviation per IA-015).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "postanalysis" / "review_pool"
RETAINED_CSV = (
    REPO
    / "source_artifact"
    / "connectomics_deterministic_pipeline"
    / "outputs"
    / "papers_retained.csv"
)
ENRICHED_CSV = REPO / "postanalysis" / "enriched2" / "canonical_works_enriched_pass2.csv"
SCREENING_LOG = (
    REPO
    / "source_artifact"
    / "connectomics_deterministic_pipeline"
    / "outputs"
    / "screening_log.csv"
)

USER_AGENT = "connectomics-survey-IA015"
S2_BASE = "https://api.semanticscholar.org/graph/v1"
MIN_INTERVAL_S = 1.3
# Key is read from the environment only; never printed, serialized, or logged.
S2_API_KEY = __import__("os").environ.get("SEMANTIC_SCHOLAR_API_KEY")

# ---------------------------------------------------------------------------
# Registry. DOIs are pinned from: the execution spec (given explicitly), the
# frozen corpus record (resolve-from-pool-record), or a logged one-time
# Crossref bibliographic resolution (Ware 1975; Litwin-Kumar & Turaga 2019).
# Do not edit identifiers without logging a deviation in IA-015.
# ---------------------------------------------------------------------------

REGISTRY = [
    # --- STEP 1 gap-fill additions -------------------------------------
    dict(
        pool_id="G1",
        doi="10.1016/s0074-7696(08)60956-0",
        citation="Ware RW, LoPresti V (1975). Three-dimensional reconstruction from serial sections. Int. Rev. Cytol. 40:325-440",
        expected_title="Three-Dimensional Reconstruction from Serial Sections",
        expected_year=1975,
        expected_venue="International Review of Cytology",
        stratum="Reconstruction / era-1",
        route="targeted-title-search (gap-fill)",
        route_family="a",
        rationale="Era-1 anchor vocabulary source; the pre-dormancy methods review.",
        identifier_resolution=(
            "Spec-marked UNRESOLVED; resolved 2026-08-25 via Crossref "
            "query.bibliographic (title+container); DOI exists in Elsevier "
            "backfile, so the works-without-DOI path was not needed. "
            "Pages 325-440 and author set match the spec citation."
        ),
    ),
    dict(
        pool_id="G2",
        doi="10.1111/j.1365-2818.2005.01466.x",
        citation="Fiala JC (2005). Reconstruct: a free editor for serial section microscopy. J. Microscopy 218:52-61",
        expected_title="Reconstruct: a free editor for serial section microscopy",
        expected_year=2005,
        expected_venue="Journal of Microscopy",
        stratum="Reconstruction tooling / era-1->2 boundary",
        route="targeted-title-search (gap-fill)",
        route_family="a",
        rationale="Tool paper, not review; enters as software-linked teaching/reference. Vocabulary: manual tracing terminology.",
    ),
    dict(
        pool_id="G3",
        doi="10.1146/annurev-cellbio-100818-125444",
        citation="Scheffer LK, Meinertzhagen IA (2019). The Fly Brain Atlas. Annu. Rev. Cell Dev. Biol. 35:637-653",
        expected_title="The Fly Brain Atlas",
        expected_year=2019,
        expected_venue="Annual Review of Cell and Developmental Biology",
        stratum="Organism (Drosophila) / era-3",
        route="targeted-title-search (gap-fill)",
        route_family="a",
        rationale="Low-cited relative to importance; canonical organism review.",
    ),
    dict(
        pool_id="G4",
        doi="10.1038/s43586-022-00131-9",
        citation="Peddie CJ, Genoud C, Kreshuk A, ..., Collinson LM (2022). Volume electron microscopy. Nat. Rev. Methods Primers 2:51",
        expected_title="Volume electron microscopy",
        expected_year=2022,
        expected_venue="Nature Reviews Methods Primers",
        stratum="Acquisition + preparation / era-3",
        route="targeted-title-search (gap-fill)",
        route_family="a",
        rationale="Systematic vEM nomenclature source.",
    ),
    dict(
        pool_id="G5",
        doi="10.1038/s41592-018-0219-4",
        citation="Wassie AT, Zhao Y, Boyden ES (2019). Expansion microscopy: principles and uses in biological research. Nat. Methods 16:33-41",
        expected_title="Expansion microscopy: principles and uses in biological research",
        expected_year=2019,
        expected_venue="Nature Methods",
        stratum="Alternative modality (ExM) / era-3",
        route="targeted-title-search (gap-fill)",
        route_family="a",
        rationale="Tag alternative-modality; substantive-use test applies at corpus time.",
    ),
    dict(
        pool_id="G6",
        doi="10.1038/s41592-018-0185-x",
        citation="Kebschull JM, Zador AM (2018). Cellular barcoding: lineage tracing, screening and beyond. Nat. Methods 15:871-879",
        expected_title="Cellular barcoding: lineage tracing, screening and beyond",
        expected_year=2018,
        expected_venue="Nature Methods",
        stratum="Alternative modality (sequencing) / era-3",
        route="targeted-title-search (gap-fill)",
        route_family="a",
        rationale="Alternative-modality handling as G5; MAPseq/BARseq vocabulary.",
    ),
    dict(
        pool_id="G7",
        doi="10.1038/s41592-018-0181-1",
        citation="Vogelstein JT, Perlman E, Falk B, et al. (2018). A community-developed open-source computational ecosystem for big neuro data. Nat. Methods 15:846-847",
        expected_title="A community-developed open-source computational ecosystem for big neuro data",
        expected_year=2018,
        expected_venue="Nature Methods",
        stratum="Infrastructure / era-3",
        route="targeted-title-search (gap-fill)",
        route_family="a",
        rationale="Infrastructure stratum coverage.",
        coi="COI-0 (screener is author)",
        flags=["self-tagged"],
        special_handling=(
            "Role-tag evidence must come from third-party sources only; "
            "always in the human reliability sample."
        ),
    ),
    dict(
        pool_id="G8",
        doi="10.1111/jmi.13134",
        citation="Kievits AJ, Lane R, Carroll EC, Hoogenboom JP (2022). How innovations in methodology offer new prospects for volume electron microscopy. J. Microscopy 287:114-137",
        expected_title="How innovations in methodology offer new prospects for volume electron microscopy",
        expected_year=2022,
        expected_venue="Journal of Microscopy",
        stratum="Preparation & throughput / era-3",
        route="targeted-title-search (gap-fill)",
        route_family="a",
        rationale="Only genuine review in an otherwise empty stratum; non-consortium (Delft) attestation base.",
    ),
    dict(
        pool_id="G9",
        doi="10.1111/cgf.14574",
        citation="Beyer J, et al. (2022). A Survey of Visualization and Analysis in High-Resolution Connectomics. Comput. Graph. Forum 41:573-607",
        expected_title="A Survey of Visualization and Analysis in High-Resolution Connectomics",
        expected_year=2022,
        expected_venue="Computer Graphics Forum",
        stratum="Infrastructure & visualization / era-3",
        route="targeted-title-search (gap-fill)",
        route_family="a",
        rationale="Systematic survey; only comprehensive reference list for the software stratum.",
        identifier_resolution=(
            "Spec said resolve by exact-title search; DOI taken from the "
            "frozen corpus record (exact title match in "
            "canonical_works_enriched_pass2.csv), verified against Crossref."
        ),
    ),
    # --- Panel members not among the Step-1 additions -------------------
    dict(
        pool_id="R1",
        doi="10.1038/s41583-025-00998-z",
        citation="Helmstaedter M (2025). Synaptic-resolution connectomics: towards large brains and connectomic screening. Nat. Rev. Neurosci.",
        expected_title="Synaptic-resolution connectomics: towards large brains and connectomic screening",
        expected_year=2025,
        expected_venue="Nature Reviews Neuroscience",
        stratum="Field synthesis / era-3",
        route="WGR-nominated",
        route_family="a",
        rationale="Era-3 anchor review; already the source of the IA-014 manual-seed coverage holes.",
        provenance_note="Route per execution spec ('already logged'); external audit record is source of the original log entry.",
    ),
    dict(
        pool_id="R2",
        doi="10.1016/j.conb.2019.04.001",
        citation="Lee K, Turner N, Macrina T, et al. (2019). Convolutional nets for reconstructing neural circuits from brain images acquired by serial section electron microscopy. Curr. Opin. Neurobiol. 55:188-198",
        expected_title="Convolutional nets for reconstructing neural circuits from brain images acquired by serial section electron microscopy",
        expected_year=2019,
        expected_venue="Current Opinion in Neurobiology",
        stratum="Reconstruction / era-3",
        route="external-pool-member (reconstructed)",
        route_family=None,
        rationale="Panel member P3; DOI resolved from the frozen corpus record per spec.",
        provenance_note="Original discovery route lives in the external protocol audit record (out of sync with this repo).",
    ),
    dict(
        pool_id="R3",
        doi="10.1016/j.cois.2022.100968",
        citation="Galili DS, Jefferis GSXE, et al. (2022). Connectomics and the neural basis of behaviour. Curr. Opin. Insect Sci.",
        expected_title="Connectomics and the neural basis of behaviour",
        expected_year=2022,
        expected_venue="Current Opinion in Insect Science",
        stratum="Fly analysis / era-3",
        route="external-pool-member (reconstructed)",
        route_family=None,
        rationale="Panel member P5; DOI resolved from the frozen corpus record per spec.",
        provenance_note="Original discovery route lives in the external protocol audit record.",
    ),
    dict(
        pool_id="R4",
        doi="10.1016/j.conb.2019.07.007",
        citation="Litwin-Kumar A, Turaga SC (2019). Constraining computational models using electron microscopy wiring diagrams. Curr. Opin. Neurobiol. 58:94-100",
        expected_title="Constraining computational models using electron microscopy wiring diagrams",
        expected_year=2019,
        expected_venue="Current Opinion in Neurobiology",
        stratum="Theory & NeuroAI / era-3",
        route="external-pool-member (reconstructed)",
        route_family=None,
        rationale="Panel member P7; DOI resolved from the frozen corpus record.",
        provenance_note=(
            "TITLE CORRECTION: the execution spec cites this as 'Constraining "
            "computation with connectomics'; the published title differs. "
            "Author set (Litwin-Kumar, Turaga), venue, and year uniquely match; "
            "no other Litwin-Kumar/Turaga 2019 Curr. Opin. Neurobiol. review exists."
        ),
    ),
    dict(
        pool_id="R5",
        doi="10.1016/j.crmeth.2025.100988",
        citation="Collins LT, Huffman T, Koene RA (2025). Comparative prospects of imaging methods for whole-brain mammalian connectomics. Cell Rep. Methods",
        expected_title="Comparative prospects of imaging methods for whole-brain mammalian connectomics",
        expected_year=2025,
        expected_venue="Cell Reports Methods",
        stratum="Alternative modalities & emulation / era-3",
        route="external-pool-member (reconstructed)",
        route_family=None,
        rationale="Panel member P8; published DOI resolved from the frozen corpus record; reconcile with arXiv:2405.10488.",
        preprint_of="arXiv:2405.10488",
    ),
    dict(
        pool_id="R6",
        doi="10.1016/j.cell.2020.08.010",
        citation="Abbott LF, et al. (2020). The Mind of a Mouse. Cell 182:1372-1376",
        expected_title="The Mind of a Mouse",
        expected_year=2020,
        expected_venue="Cell",
        stratum="Cross-cluster consensus / era-3",
        route="external-pool-member (reconstructed)",
        route_family=None,
        rationale="Panel member P9; DOI resolved from the frozen corpus record.",
    ),
]

# Panel definition: pool_id -> (panel_id, cluster, probe_mode, notes)
PANEL = [
    ("R1", "P1", "MPI-Frankfurt / mammalian cortex", "probe", "Era-3 anchor; route WGR-nominated already logged."),
    ("G4", "P2", "Crick-EMBL / cell-biology vEM", "probe", "Acquisition + preparation coverage."),
    ("R2", "P3", "Princeton-Seung / reconstruction", "probe", "Segmentation/agglomeration lineage."),
    ("G3", "P4", "Janelia-FlyEM / fly datasets", "probe", ""),
    ("R3", "P5", "Cambridge-natverse / fly analysis", "probe", ""),
    ("G9", "P6", "Harvard-Pfister / visualization & infrastructure", "probe", "The infrastructure probe; citation metrics under-retrieve here."),
    ("R4", "P7", "Columbia-Janelia / theory & NeuroAI", "probe", ""),
    ("R5", "P8", "Outside-field / emulation & alternative modalities", "probe", "Maximally distant from EM-consortium clusters."),
    ("R6", "P9", "Cross-cluster consensus (25 authors)", "confirmation-only", "Short reference list; each citation ~ consensus attestation. Never counts toward discovery convergence; used to corroborate."),
]

PANEL_EXCLUSION = {
    "work": "Kornfeld & Denk 2018",
    "status": "in corpus, NOT on the panel",
    "rationale": (
        "same intellectual lineage as P1 (Denk trained Helmstaedter); its "
        "reference list is a second draw from the MPI distribution, not an "
        "independent probe."
    ),
}

PANEL_GAPS = [
    "proofreading/QC stratum has no probe: no comprehensive review exists.",
    "alignment/registration stratum has no probe: no comprehensive review exists.",
    "Plaza et al. 2014 remains corpus-member and attestation-eligible but is a "
    "perspective, not a systematic probe; do not present it as stratum coverage.",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_last_call = {"t": 0.0}


def _get(url: str, tries: int = 8, backoff: float = 20.0) -> dict | None:
    """Rate-limited GET with patient backoff (shared unkeyed API pools)."""
    for attempt in range(tries):
        wait = MIN_INTERVAL_S - (time.time() - _last_call["t"])
        if wait > 0:
            time.sleep(wait)
        headers = {"User-Agent": USER_AGENT}
        if S2_API_KEY and url.startswith(S2_BASE):
            headers["x-api-key"] = S2_API_KEY
        req = urllib.request.Request(url, headers=headers)
        _last_call["t"] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                sleep_s = backoff * (1.4**attempt)
                print(f"    HTTP {e.code}; retrying in {sleep_s:.0f}s", flush=True)
                time.sleep(sleep_s)
                continue
            if e.code == 404:
                return None
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < tries - 1:
                time.sleep(backoff)
                continue
            raise
    return None


def _norm_title(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t or "")  # Crossref titles can embed markup
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def fetch_crossref(doi: str) -> dict:
    data = _get(
        "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    )
    if not data:
        return {"resolved": False}
    m = data["message"]
    return {
        "resolved": True,
        "title": (m.get("title") or [""])[0],
        "container": (m.get("container-title") or [""])[0],
        "year": (m.get("issued", {}).get("date-parts") or [[None]])[0][0],
        "authors": [
            {
                "family": a.get("family"),
                "given": a.get("given"),
                "orcid": a.get("ORCID"),
            }
            for a in m.get("author", [])
        ],
        "reference_count": m.get("reference-count"),
    }


def fetch_retraction_notices(doi: str) -> list[dict]:
    """Crossref: notices (retraction/correction/erratum) updating this DOI."""
    data = _get(
        "https://api.crossref.org/works?filter=updates:"
        + urllib.parse.quote(doi)
        + "&select=DOI,title,update-to&rows=10"
    )
    notices = []
    for it in (data or {}).get("message", {}).get("items", []):
        for upd in it.get("update-to", []):
            if upd.get("DOI", "").lower() == doi.lower():
                notices.append(
                    {
                        "notice_doi": it.get("DOI"),
                        "type": upd.get("type"),
                        "label": upd.get("label"),
                    }
                )
    return notices


def fetch_s2(doi: str) -> dict:
    fields = "paperId,externalIds,title,year,venue,referenceCount,citationCount,isOpenAccess,authors.name,authors.authorId"
    data = _get(f"{S2_BASE}/paper/DOI:{urllib.parse.quote(doi)}?fields={fields}")
    if not data:
        return {"resolved": False}
    return {
        "resolved": True,
        "paper_id": data.get("paperId"),
        "corpus_id": (data.get("externalIds") or {}).get("CorpusId"),
        "title": data.get("title"),
        "year": data.get("year"),
        "venue": data.get("venue"),
        "reference_count": data.get("referenceCount"),
        "citation_count": data.get("citationCount"),
        "authors": [
            {"author_id": a.get("authorId"), "name": a.get("name")}
            for a in data.get("authors", [])
        ],
    }


def fetch_openalex(doi: str) -> dict:
    try:
        data = _get(
            "https://api.openalex.org/works/doi:"
            + urllib.parse.quote(doi)
            + "?select=id,doi,title,publication_year,is_retracted,cited_by_count,authorships",
            tries=1,
        )
    except urllib.error.HTTPError as e:
        return {"resolved": False, "status": f"HTTP {e.code} (likely shared daily budget exhausted); backfill per IA-015"}
    if not data or "id" not in data:
        return {"resolved": False, "status": "no record"}
    return {
        "resolved": True,
        "openalex_id": data["id"].rsplit("/", 1)[-1],
        "is_retracted": data.get("is_retracted"),
        "cited_by_count": data.get("cited_by_count"),
        "authors": [
            {
                "openalex_author_id": (a.get("author") or {}).get("id", "").rsplit("/", 1)[-1] or None,
                "name": (a.get("author") or {}).get("display_name"),
                "orcid": (a.get("author") or {}).get("orcid"),
            }
            for a in data.get("authorships", [])
        ],
    }


def load_corpus_indexes():
    retained = {}
    with RETAINED_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = (row.get("doi") or "").strip().lower()
            if d:
                retained[d] = {"paper_id": row["paper_id"], "keep": row.get("keep")}
    works = {}
    with ENRICHED_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = (row.get("doi") or "").strip().lower()
            if d:
                works[d] = {"work_id": row["work_id"], "source_group": row.get("source_group")}
    screened_titles = {}
    with SCREENING_LOG.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            screened_titles.setdefault(_norm_title(row.get("title", "")), row["paper_id"])
    return retained, works, screened_titles


def verify(entry: dict, cr: dict, s2: dict) -> dict:
    checks = {}
    checks["identifier_resolves"] = bool(cr.get("resolved"))
    exp_t = _norm_title(entry["expected_title"])
    got_t = _norm_title(cr.get("title", ""))
    checks["title_consistent"] = bool(got_t) and (exp_t in got_t or got_t in exp_t)
    year = cr.get("year")
    checks["year_consistent"] = year is not None and abs(int(year) - entry["expected_year"]) <= 1
    checks["venue_consistent"] = _norm_title(entry["expected_venue"]) in _norm_title(cr.get("container", "")) or _norm_title(cr.get("container", "")) in _norm_title(entry["expected_venue"])
    if s2.get("resolved"):
        checks["s2_title_consistent"] = exp_t in _norm_title(s2.get("title", "")) or _norm_title(s2.get("title", "")) in exp_t
    return checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refreeze", action="store_true", help="allow overwriting probe_panel_frozen.json (logged deviation)")
    ap.add_argument("--skip-openalex", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = OUT_DIR / "probe_panel_frozen.json"
    if panel_path.exists() and not args.refreeze:
        print("probe_panel_frozen.json already exists; refusing to refreeze without --refreeze")
        return 1

    run_ts = _now()
    retained, works, screened_titles = load_corpus_indexes()
    print(f"corpus indexes: {len(retained)} retained DOIs, {len(works)} work DOIs, {len(screened_titles)} screened titles")

    pool_entries = []
    log = {"run_timestamp": run_ts, "entries": []}

    for entry in REGISTRY:
        doi = entry["doi"]
        print(f"[{entry['pool_id']}] {doi}", flush=True)
        cr = fetch_crossref(doi)
        notices = fetch_retraction_notices(doi)
        s2 = fetch_s2(doi)
        oa = {"resolved": False, "status": "skipped"} if args.skip_openalex else fetch_openalex(doi)
        checks = verify(entry, cr, s2)
        retracted = any(n["type"] == "retraction" for n in notices) or bool(oa.get("is_retracted"))

        nt = _norm_title(entry["expected_title"])
        rec = {
            "pool_id": entry["pool_id"],
            "doi": doi,
            "citation": entry["citation"],
            "stratum_era": entry["stratum"],
            "route": entry["route"],
            "route_family": entry.get("route_family"),
            "rationale": entry["rationale"],
            "coi": entry.get("coi", "none declared (frozen COI artifact not in this repo; tagging deferred to sync)"),
            "flags": entry.get("flags", []),
            "special_handling": entry.get("special_handling"),
            "identifier_resolution": entry.get("identifier_resolution"),
            "provenance_note": entry.get("provenance_note"),
            "preprint_of": entry.get("preprint_of"),
            "verification": {
                "checked_at": run_ts,
                "checks": checks,
                "retraction_notices": notices,
                "retracted": retracted,
            },
            "crossref": cr,
            "semantic_scholar": s2,
            "openalex": oa,
            "corpus_crossref": {
                "in_frozen_retained": retained.get(doi.lower()),
                "in_canonical_works": works.get(doi.lower()),
                "in_frozen_discovery_by_title": screened_titles.get(nt),
            },
            "added_at": run_ts,
        }
        pool_entries.append(rec)
        log["entries"].append(
            {
                "pool_id": entry["pool_id"],
                "doi": doi,
                "checks": checks,
                "retracted": retracted,
                "s2_paper_id": s2.get("paper_id"),
                "openalex_status": oa.get("status", "ok" if oa.get("resolved") else "unresolved"),
            }
        )
        bad = [k for k, v in checks.items() if v is False]
        if bad:
            print(f"    !! failed checks: {bad}")
        if retracted:
            print("    !! RETRACTION NOTICE FOUND")

    pool = {
        "artifact": "review_pool.json",
        "schema_version": "IA-015.1",
        "generated_at": run_ts,
        "screener_of_record": {
            "name": "William Gray Roncal",
            "orcid": "0000-0002-7362-9665",
        },
        "sync_note": (
            "This pool is reconstructed inside the repo from the IA-015 "
            "execution spec. Entries with route 'external-pool-member "
            "(reconstructed)' predate this artifact in the external protocol "
            "audit record; their original routes are not in this repo."
        ),
        "role_separation": (
            "A review may serve as a reference-list probe (discovery) and/or "
            "an attestation source (evidence). Discovery is never evidence."
        ),
        "declared_standing_gaps": [
            "alignment/registration has no review; stratum reported thin; "
            "Saalfeld/Cardona enter later as primary literature.",
        ],
        "known_absent_by_decision": [
            "'Collinson et al. 2023 community-standards piece' - could not be "
            "verified to exist (likely conflation with Peddie et al. 2022). "
            "Do not search further; this retraction of the claim is itself the log entry.",
        ],
        "entries": pool_entries,
    }
    pool_path = OUT_DIR / "review_pool.json"
    pool_path.write_text(json.dumps(pool, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {pool_path}")

    by_id = {e["pool_id"]: e for e in pool_entries}
    members = []
    for pool_id, panel_id, cluster, mode, notes in PANEL:
        e = by_id[pool_id]
        members.append(
            {
                "panel_id": panel_id,
                "pool_id": pool_id,
                "doi": e["doi"],
                "citation": e["citation"],
                "cluster": cluster,
                "probe": mode == "probe",
                "confirmation_only": mode == "confirmation-only",
                "attestation": True,
                "notes": notes,
                "s2_paper_id": e["semantic_scholar"].get("paper_id"),
                "openalex_id": e["openalex"].get("openalex_id"),
                "authors_s2": e["semantic_scholar"].get("authors", []),
                "authors_crossref": e["crossref"].get("authors", []),
                "authors_openalex": e["openalex"].get("authors", []),
                "reference_count_crossref": e["crossref"].get("reference_count"),
                "reference_count_s2": e["semantic_scholar"].get("reference_count"),
            }
        )

    panel = {
        "artifact": "probe_panel_frozen.json",
        "schema_version": "IA-015.1",
        "frozen_at": run_ts,
        "screener_of_record": {
            "name": "William Gray Roncal",
            "orcid": "0000-0002-7362-9665",
        },
        "rules": {
            "role_separation": pool["role_separation"],
            "confirmation_only_rule": (
                "P9 never counts toward discovery convergence thresholds; its "
                "citations are descriptive corroboration marks only."
            ),
            "attestation_coi": (
                "Each panel member's author set is COI-tagged relative to any "
                "work it attests; panel membership does not exempt from "
                "with/without-COI-1 Core sensitivity reporting. Tagging is "
                "deferred until the frozen COI artifact is synced into this repo."
            ),
            "post_freeze_changes": "Any change after freeze is a logged deviation.",
        },
        "exclusions": [PANEL_EXCLUSION],
        "declared_panel_gaps": PANEL_GAPS,
        "members": members,
    }
    body = json.dumps(panel, indent=2, sort_keys=True) + "\n"
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    panel_path.write_text(body, encoding="utf-8")
    (OUT_DIR / "probe_panel_frozen.sha256").write_text(sha + "\n", encoding="utf-8")
    print(f"wrote {panel_path}\nSHA-256: {sha}")

    (OUT_DIR / "resolution_log.json").write_text(
        json.dumps(log, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote resolution_log.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
