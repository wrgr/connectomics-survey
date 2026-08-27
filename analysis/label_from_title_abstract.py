#!/usr/bin/env python3
"""Assign codebook tags from title + abstract for the analysis base.

Read-only on paper_links.csv and dryrun_work_tags.csv.
Does not join methods_registry_draft.csv as the sole method source — named
techniques in title/abstract are assigned, using registry strings when they match.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "postanalysis/pdfs/paper_links.csv"
JSON_IN = ROOT / "postanalysis/llm_agent_v3/corpus_filter_comparison.json"
TAGS = ROOT / "postanalysis/registry/dryrun_work_tags.csv"
STRAYS = ROOT / "postanalysis/registry/exploration_strays_adjudicated.csv"
METHODS = ROOT / "postanalysis/registry/methods_registry_draft.csv"
ENRICHED = ROOT / "postanalysis/enriched2/canonical_works_enriched_pass2.csv"
ENRICHED1 = ROOT / "postanalysis/enriched/canonical_works_enriched.csv"
SEEDS = ROOT / "postanalysis/works/manual_seed_works.csv"
CORE_IN = ROOT / "postanalysis/registry/sota_history_core_labeled.csv"
OUT_CORE = ROOT / "postanalysis/registry/sota_history_core_labeled.csv"
OUT_BASE = ROOT / "postanalysis/registry/working_set_labeled.csv"
OUT_FULL = ROOT / "postanalysis/registry/corpus_1806_tagged.csv"
OUT_JSON = ROOT / "postanalysis/llm_agent_v3/sota_history_core_labeled.json"
PDF_FILES = ROOT / "postanalysis/pdfs/files"
CANVAS_CORE = Path.home() / ".cursor/projects/Users-wgray13-projects-connectomics-survey/canvases/sota-history-core.canvas.tsx"
CANVAS_KCORE = Path.home() / ".cursor/projects/Users-wgray13-projects-connectomics-survey/canvases/corpus-kcore-vs-cites.canvas.tsx"
STAGE_NAMES = [
    "preparation",
    "sectioning",
    "acquisition",
    "alignment",
    "segmentation",
    "proofreading",
    "synapses",
    "infrastructure",
    "graph_analysis",
    "modeling",
]
ORG_NAMES = ["elegans", "fly", "mouse", "human", "zebrafish", "other"]

TIME_BINS = [
    ("pre-2005", "history", 0, 2004),
    ("2005–2009", "history", 2005, 2009),
    ("2010–2015", "history", 2010, 2015),
    ("2016–2018", "history", 2016, 2018),
    ("2019", "contemporary", 2019, 2019),
    ("2020", "contemporary", 2020, 2020),
    ("2021", "contemporary", 2021, 2021),
    ("2022", "contemporary", 2022, 2022),
    ("2023", "contemporary", 2023, 2023),
    ("2024", "contemporary", 2024, 2024),
    ("2025", "sota", 2025, 2025),
    ("2026", "sota", 2026, 2026),
]

DATASETS = {
    "DS01 C. elegans (White+)": r"c\.? ?elegans|caenorhabditis",
    "DS03 Drosophila larva": r"drosophila larva|larval drosophila",
    "DS04 FAFB": r"\bfafb\b|full adult fly brain",
    "DS05 hemibrain": r"\bhemibrain\b",
    "DS06 FlyWire": r"\bflywire\b",
    "DS07 VNC (FANC/MANC)": r"ventral nerve cord|\bfanc\b|\bmanc\b",
    "DS09/DS10 mouse retina": r"mouse retina|retinal connectom",
    "DS11 Kasthuri neocortex": r"\bkasthuri\b|saturated reconstruction of a volume of neocortex",
    "DS12 L4 barrel cortex": r"barrel cortex",
    "DS13 MICrONS": r"\bmicrons\b",
    "DS14 H01 human cortex": r"\bh01\b|petavoxel fragment of human",
    "DS15 zebrafish": r"\bzebrafish\b|\bdanio\b",
    "DS16 calyx of Held": r"calyx of held",
    "DS19 songbird": r"songbird|zebra finch",
    "DS20 Ciona": r"\bciona\b",
    "DS21 octopus": r"\boctopus\b",
    "DS22 Platynereis": r"\bplatynereis\b",
}
STAGES = {
    "preparation": r"stain|fixat|embed|osmium|\broto\b|sample preparation|extracellular space",
    "sectioning": r"serial.section|ultramicrotom|\batum\b|tape.collect|fib.?sem|focused ion beam|block.?face|milling|hot.?knife|gridtape|gcib",
    "acquisition": r"multibeam|multi.?beam|camera array|\btemca\b|scanning electron|transmission electron|volume electron",
    "alignment": r"\balignment\b|\bregistration\b|\bstitching\b",
    "segmentation": r"\bsegment|\baffinit|\bagglomerat|flood.?filling|supervoxel",
    "proofreading": r"proofread|annotation toolkit|manual tracing|skeletoniz|eyewire|catmaid",
    "synapses": r"synapse detection|synaptic partner|synapse prediction|synaptic cleft",
    "infrastructure": r"\bbossdb\b|\bneuprint\b|neuroglancer|cloudvolume|\bdvid\b|pychunkedgraph|virtual fly brain",
    "graph_analysis": r"wiring diagram|connectome graph|connectivity matrix|\bmotifs?\b",
    "modeling": r"connectome.?constrained|connectome.?based model",
}
DS_ORG = {
    "DS01": "elegans",
    "DS02": "elegans",
    "DS03": "fly",
    "DS04": "fly",
    "DS05": "fly",
    "DS06": "fly",
    "DS07": "fly",
    "DS08": "fly",
    "DS09": "mouse",
    "DS10": "mouse",
    "DS11": "mouse",
    "DS12": "mouse",
    "DS13": "mouse",
    "DS16": "mouse",
    "DS14": "human",
    "DS15": "zebrafish",
    "DS19": "other",
    "DS20": "other",
    "DS21": "other",
    "DS22": "other",
}
ORG_PATS = [
    (r"c\.? ?elegans|caenorhabditis", "elegans"),
    (r"\bdrosophila\b|\bflywire\b|\bhemibrain\b|\bfafb\b|\bfruit fly\b", "fly"),
    (r"\bzebrafish\b|\bdanio\b", "zebrafish"),
    (r"\bh01\b|human (cerebral )?cortex", "human"),
    (r"\bmouse\b|\bmus musculus\b|\bmicrons\b", "mouse"),
    (r"\brat\b|\bprimate\b|\bmacaque\b|\bmonkey\b|\bhydra\b|\bciona\b|\boctopus\b|\bplatynereis\b|\bsongbird\b|\bzebra finch\b|\bbee\b|\bmosquito\b", "other"),
]

# Named techniques. Registry strings used when the draft name matches.
# kind: named_em | software | other — generic EM modality is applied only if
# no named_em hit.
NAMED_METHODS: list[tuple[str, str, str]] = [
    ("SBF-SEM", r"\bsbf[- ]?sem\b|\bsbem\b|serial block[- ]face|block[- ]face scanning electron", "named_em"),
    ("FIB-SEM", r"\bfib[- ]?sem\b|focused ion beam", "named_em"),
    ("ATUM + WaferMapper", r"\batum\b|wafermapper|automatic tape[- ]collecting|tape[- ]collecting ultramicrotom", "named_em"),
    ("GridTape TEM", r"\bgridtape\b|grid[- ]tape", "named_em"),
    ("Hot-knife partitioning", r"hot[- ]knife", "named_em"),
    ("GCIB-SEM", r"\bgcib\b|gas cluster ion beam", "named_em"),
    ("TEMCA camera-array ssTEM", r"\btemca\b", "named_em"),
    ("Multibeam SEM", r"multibeam(?: scanning)? electron|multi[- ]beam sem|\bmbsem\b", "named_em"),
    ("FAST-EM array tomography", r"\bfast[- ]?em\b", "named_em"),
    ("SmartEM ML-guided acquisition", r"\bsmartem\b", "named_em"),
    ("array tomography", r"array tomograph", "named_em"),
    ("MagC", r"\bmagc\b", "named_em"),
    ("ssTEM", r"\bss[- ]?tem\b|serial[- ]section tem|serial section transmission", "named_em"),
    ("serial-section EM", r"serial[- ]section(?:ed|ing)? electron|electron micrographs? of serial|serial sections?.{0,40}electron", "named_em"),
    ("electron tomography", r"electron tomogram|electron tomograph", "named_em"),
    ("XNH", r"\bxnh\b|x[- ]ray holographic nanotomograph|x[- ]ray nanotomograph", "other"),
    ("expansion microscopy", r"expansion microscop", "other"),
    ("LICONN light-microscopy connectomics", r"\bliconn\b", "other"),
    ("mGRASP", r"\bmgrasp\b", "other"),
    ("Large-volume en-bloc staining (rOTO)", r"\broto\b|reduced osmium|en[- ]bloc stain", "named_em"),
    ("ECS-preserving fixation", r"extracellular space preserv", "named_em"),
    ("Elastic serial-section alignment", r"elastic (?:volume )?reconstr|elastic alignment", "software"),
    ("SOFIMA flow-based alignment", r"\bsofima\b", "software"),
    ("Flood-filling networks", r"flood[- ]filling network|\bffns?\b", "software"),
    ("SegEM", r"\bsegem\b", "software"),
    ("GALA agglomeration", r"graph[- ]based active learning of agglomeration|\bgala\b.{0,30}agglomerat", "software"),
    ("Structured-loss affinity segmentation", r"structured loss.{0,40}segment|affinity.{0,30}segment", "software"),
    ("CDeep3M cloud segmentation", r"\bcdeep3m\b", "software"),
    ("U-Net", r"\bu[- ]nets?\b", "software"),
    ("CATMAID", r"\bcatmaid\b", "software"),
    ("KNOSSOS + RESCOP consensus", r"\bknossos\b|\brescop\b", "software"),
    ("EyeWire crowd proofreading", r"\beyewire\b", "software"),
    ("webKnossos", r"\bwebknossos\b", "software"),
    ("VAST", r"volume annotation and segmentation", "software"),
    ("Neuroglancer", r"\bneuroglancer\b", "software"),
    ("CAVE / PyChunkedGraph", r"pychunkedgraph|connectome annotation versioning|\bcave\b.{0,50}(annotation|connectome|proofread|version)", "software"),
    ("SynEM", r"\bsynem\b", "software"),
    ("Synful partner prediction", r"\bsynful\b", "software"),
    ("ilastik interactive ML", r"\bilastik\b", "software"),
    ("SyConn", r"\bsyconn\b", "software"),
    ("TrakEM2", r"\btrakem2?\b", "software"),
    ("BossDB ecosystem", r"\bbossdb\b", "software"),
    ("neuPrint", r"\bneuprint\b", "software"),
    ("DVID", r"\bdvid\b", "software"),
    ("CloudVolume/Igneous", r"\bcloudvolume\b|\bigneous\b", "software"),
    ("natverse", r"\bnatverse\b", "software"),
    ("FlyWire", r"\bflywire\b", "software"),
    ("Network motifs", r"network motifs?|motif.{0,20}(connectome|network|circuit)", "software"),
    ("Connectome-constrained visual-system model", r"connectome[- ]constrained", "software"),
    ("CLEM", r"correlative light.{0,30}electron|\bclem\b", "other"),
    ("light-sheet", r"light[- ]?sheet", "other"),
    ("confocal", r"\bconfocal\b", "other"),
    ("two-photon", r"two[- ]photon|2[- ]photon", "other"),
    ("super-resolution LM", r"super[- ]resolution.{0,25}(microscop|imaging)|\bsted\b microscop", "other"),
    ("X-ray microscopy", r"synchrotron x[- ]ray|x[- ]ray microscop|x[- ]ray tomograph", "other"),
    ("serial two-photon", r"serial two[- ]photon|\bstpt\b|\bfmost\b", "other"),
]

GENERIC_EM = [
    ("volume EM", r"\bvem\b|volume electron microscop|3[- ]?d electron microscop"),
    ("TEM", r"transmission electron microscop"),
    ("SEM", r"scanning electron microscop"),
    ("electron microscopy", r"electron[- ]microscop|electron micrograph|electron imaging|electron tomogram|\bem (?:data|dataset|connectome|volume|image|reconstr)"),
]


def _rx(p: str) -> re.Pattern:
    return re.compile(p, re.I | re.S)


NAMED_RX = [(name, _rx(pat), kind) for name, pat, kind in NAMED_METHODS]
GEN_RX = []
for item in GENERIC_EM:
    if len(item) == 2:
        GEN_RX.append((item[0], _rx(item[1])))
    else:
        GEN_RX.append((item[0], _rx(item[1])))


def join_unique(parts: list[str]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        for tok in str(p or "").split(";"):
            t = tok.strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return ";".join(out)


def datasets_to_orgs(datasets: str) -> str:
    orgs: list[str] = []
    seen: set[str] = set()
    for part in str(datasets or "").split(";"):
        tok = part.strip()
        if not tok:
            continue
        key = tok.split()[0].split("/")[0]
        org = DS_ORG.get(key)
        if org and org not in seen:
            seen.add(org)
            orgs.append(org)
    return ";".join(orgs)


# People-development / dissemination (not ML "training").
TRAINING_OUTREACH_RE = re.compile(
    r"undergraduate|outreach|citizen science|curriculum|pedagog|"
    r"\bteaching\b|laboratory course|educational (application|method|neuroscience)|"
    r"user training|summer (program|school)|disseminat|\bcrowdsourcing\b",
    re.I,
)
ML_TRAINING_RE = re.compile(
    r"training labels|recursive training|self-?training|pretrain|"
    r"training of .{0,40}(network|cnn|nets?\b|model)",
    re.I,
)


HEALTH_TRANSLATION_RE = re.compile(
    r"\btranslational\b|\bclinical stud|\bpatients?\b|mouse models of|"
    r"health and disease|neurological disease|\balzheimer|\bparkinson|"
    r"\bpathology\b|myelin injury|recruitment and retention|"
    r"treatment-resistant|glioma treatment",
    re.I,
)


def is_training_outreach(title: str) -> bool:
    t = title or ""
    if ML_TRAINING_RE.search(t):
        return False
    return bool(TRAINING_OUTREACH_RE.search(t))


def is_health_translation(title: str, decision: str = "") -> bool:
    """Clinical/translational bridge — not every paper that mentions disease."""
    if str(decision) != "role_bridge":
        return False
    return bool(HEALTH_TRANSLATION_RE.search(title or ""))


def axis_from_stray(raw: str) -> str:
    s = (raw or "").lower()
    if "training" in s or "outreach" in s or "citizen" in s:
        return "training_outreach"
    if "health" in s:
        return "health_translation"
    if s.startswith("bridge"):
        return "bridge"
    if s.startswith("conceptual") or "field synthesis" in s:
        return "field_synthesis"
    if s.startswith("biology") or s.startswith("analysis"):
        return "biological_application"
    return ""


def load_abstracts() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (ENRICHED1, ENRICHED, SEEDS):
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                wid = str(r.get("work_id") or "")
                abs_ = (r.get("abstract") or "").strip()
                if wid and abs_:
                    out[wid] = abs_
    return out


def load_authors() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (ENRICHED1, ENRICHED, SEEDS):
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                wid = str(r.get("work_id") or "")
                authors = (r.get("authors") or "").strip()
                if wid and authors and wid not in out:
                    out[wid] = authors
    return out


def _clean_meta(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return "" if s.lower() in ("", "nan", "none") else s


def pdf_fields(r) -> dict[str, str]:
    """Local files/<stem>.pdf only when the catalog marks downloaded and the file exists."""
    status = _clean_meta(getattr(r, "pdf_status", ""))
    stem = _clean_meta(getattr(r, "stem", ""))
    pdf_url = _clean_meta(getattr(r, "pdf_url", ""))
    landing = _clean_meta(getattr(r, "landing_url", ""))
    doi_url = _clean_meta(getattr(r, "doi_url", ""))
    local_raw = _clean_meta(getattr(r, "local_path", ""))
    rel = f"files/{stem}.pdf" if stem else ""
    exists = False
    if status == "downloaded" and stem:
        abs_path = PDF_FILES / f"{stem}.pdf"
        exists = abs_path.is_file()
        if not exists and local_raw:
            exists = Path(local_raw).is_file()
    pdf_path = rel if exists else ""
    catalog_url = pdf_url or landing or doi_url
    if exists:
        pdf_link = pdf_path
    elif catalog_url:
        pdf_link = catalog_url
    else:
        pdf_link = status or "unavailable"
    return {
        "stem": stem,
        "pdf_status": status,
        "pdf_path": pdf_path,
        "pdf_url": pdf_url,
        "pdf_link": pdf_link,
        "landing_url": landing,
        "catalog_url": catalog_url,
    }


def axis_flags(
    axis: str,
    stray_raw: str,
    title: str,
    decision: str,
    stages: str,
    datasets: str,
) -> dict[str, str]:
    stray_ax = axis_from_stray(stray_raw)
    tr = (
        axis == "training_outreach"
        or stray_ax == "training_outreach"
        or is_training_outreach(title)
    )
    ht = (
        axis == "health_translation"
        or stray_ax == "health_translation"
        or is_health_translation(title, decision)
    )
    return {
        "pipeline_stage": stages,
        "registry_dataset": datasets,
        "biological_application": "yes"
        if axis == "biological_application" or stray_ax == "biological_application"
        else "",
        "bridge": "yes" if axis == "bridge" or stray_ax == "bridge" else "",
        "field_synthesis": "yes" if axis == "field_synthesis" else "",
        "training_outreach": "yes" if tr else "",
        "health_translation": "yes" if ht else "",
    }


def extract_methods(title: str, abstract: str, registry_method: str) -> tuple[str, str]:
    text = f"{title}\n{abstract}"
    named: list[str] = []
    kinds: set[str] = set()
    for name, rx, kind in NAMED_RX:
        if name == "VAST":
            if re.search(r"\bVAST\b", text) or re.search(
                r"volume annotation and segmentation tool", text, re.I
            ):
                named.append(name)
                kinds.add(kind)
            continue
        if rx.search(text):
            named.append(name)
            kinds.add(kind)
    if registry_method:
        named = join_unique([registry_method, *named]).split(";") if named else [registry_method]
        named = [n for n in named if n]
    if "named_em" not in kinds:
        for name, rx in GEN_RX:
            if rx.search(text):
                named.append(name)
                break
    methods = join_unique(named)
    src = "title_abstract" if methods else ""
    if registry_method:
        src = "registry+title_abstract" if methods != registry_method else "methods_registry"
    return methods, src


def extract_stages_datasets(title: str, abstract: str, st0: str, ds0: str) -> tuple[str, str, str]:
    text = f"{title}\n{abstract}"
    stages = [s for s in str(st0 or "").split(";") if s.strip()]
    datasets = [d for d in str(ds0 or "").split(";") if d.strip()]
    sources: list[str] = []
    if stages or datasets:
        sources.append("dryrun")
    added_st = added_ds = False
    for name, pat in STAGES.items():
        if name in stages:
            continue
        if re.search(pat, text, re.I):
            stages.append(name)
            added_st = True
    for name, pat in DATASETS.items():
        if name in datasets:
            continue
        if re.search(pat, text, re.I):
            datasets.append(name)
            added_ds = True
    if added_st or added_ds:
        sources.append("title_abstract")
    return join_unique(stages), join_unique(datasets), "+".join(sources) if sources else ""


def extract_organism(title: str, abstract: str, datasets: str) -> tuple[str, str]:
    from_ds = datasets_to_orgs(datasets)
    text_org = ""
    blob = f"{title}\n{abstract}"
    for pat, org in ORG_PATS:
        if re.search(pat, blob, re.I):
            text_org = org
            break
    if text_org:
        if from_ds and text_org not in from_ds.split(";"):
            return text_org, "title_abstract_organism_overrides_dryrun"
        if from_ds:
            return from_ds, "dataset_organism"
        return text_org, "title_abstract_organism"
    return from_ds, "dataset_organism" if from_ds else ""


FIELD_SYNTHESIS_FALLBACK = re.compile(
    r"\b(review|perspective|commentary|primer|editorial)\b|"
    r"big data.{0,60}connectom|challenges of connectomics|from cajal|"
    r"connectome and beyond|synaptome|a connectome is not enough",
    re.I,
)
BIO_TITLE_RE = re.compile(
    r"\b(circuits?|wiring|connectome of|connectomic|connectomes?|microcircuit|"
    r"synaptic (architecture|connectivity|connections?|organization|plasticity)|"
    r"driver lines?|connectomics|neuropil|mesoconnectome|neocortical)\b",
    re.I,
)
BIO_ABS_RE = re.compile(
    r"\bconnectom|\bneural circuits?\b|\bneuronal circuits?\b|\bmicrocircuits?\b",
    re.I,
)


def infer_axis(
    title: str,
    stages: str,
    datasets: str,
    stray_axis: str,
    decision: str = "",
    abstract: str = "",
) -> tuple[str, str]:
    # Charting axes, not screening tiers. Training/outreach and health translation
    # are already ROLE_BRIDGE in IA-007; they were missing as first-class axes.
    if is_training_outreach(title):
        return "training_outreach", "title_axis"
    axis = axis_from_stray(stray_axis)
    if axis == "health_translation":
        return axis, "strays_axis"
    if is_health_translation(title, decision):
        return "health_translation", "title_axis"
    if axis:
        return axis, "strays_axis"
    if stages:
        return "pipeline_stage", "stages"
    if datasets:
        return "registry_dataset", "datasets"
    if FIELD_SYNTHESIS_FALLBACK.search(title or ""):
        return "field_synthesis", "title_axis"
    if BIO_TITLE_RE.search(title or ""):
        return "biological_application", "title_axis"
    if BIO_ABS_RE.search(abstract or ""):
        return "biological_application", "abstract_axis"
    return "", ""


def time_bin_of(y) -> tuple[str, str]:
    if y is None or y == "":
        return "", ""
    y = int(y)
    for label, role, lo, hi in TIME_BINS:
        if lo <= y <= hi:
            return label, role
    if y < 2005:
        return "pre-2005", "history"
    return "2026", "sota"


def sota_history_flags(y, inn, out, pct, k) -> tuple[str, str]:
    """Return (role, why). role is history | contemporary | sota | "".

    Historical (≤2018): year-cites percentile ≥ 50 or k-core ≥ 3.
    Contemporary (2019–2024): that bar OR Out ≥ 3 (promotes busy-period papers
    that engage the corpus before cites/core catch up; 2024 is not the old AND window).
    SOTA (2025–2026): 2026 Out≥3 OR In≥1; 2025 Out≥3 AND In≥2.
    """
    if y is None:
        return "", "no year"
    y = int(y)
    if y == 2026:
        ok = out >= 3 or inn >= 1
        if ok:
            why = "sota_2026_out" if out >= 3 else "sota_2026_in"
        else:
            why = "unproven_2026_low_out"
        return ("sota" if ok else ""), why
    if y == 2025:
        ok = out >= 3 and inn >= 2
        return ("sota" if ok else ""), ("sota_2025_out_and_in" if ok else "unproven_2025_low_inout")
    if 2019 <= y <= 2024:
        ok = pct >= 50 or k >= 3 or out >= 3
        return ("contemporary" if ok else ""), ("contemporary_keep" if ok else "contemporary_below_bar")
    hist = pct >= 50 or k >= 3
    return ("history" if hist else ""), ("history_milestone" if hist else "history_below_bar")


def filled_stats(rows: list[dict], cols: tuple[str, ...]) -> dict:
    n = len(rows)
    out = {}
    for c in cols:
        k = sum(1 for r in rows if str(r.get(c) or "").strip())
        out[c] = [k, round(100.0 * k / n, 1) if n else 0.0]
    return out


def _stage_bits(stages: str) -> int:
    bits = 0
    for part in str(stages or "").split(";"):
        name = part.strip()
        if name in STAGE_NAMES:
            bits |= 1 << STAGE_NAMES.index(name)
    return bits


def _org_bits(organism: str) -> int:
    bits = 0
    for part in str(organism or "").split(";"):
        name = part.strip()
        if name in ORG_NAMES:
            bits |= 1 << ORG_NAMES.index(name)
    return bits


def _patch_filter_json(payload: dict, papers: list[dict], rows_all: list[dict]) -> None:
    """Refresh stage/organism bits and SOTA defaults without rebuilding the graph."""
    by_id = {r["work_id"]: r for r in rows_all}
    cat = pd.read_csv(CATALOG, low_memory=False).drop_duplicates("work_id", keep="first")
    for r, p in zip(cat.itertuples(index=False), papers):
        rec = by_id.get(str(r.work_id))
        if not rec:
            continue
        p["st"] = _stage_bits(rec["stages"])
        p["og"] = _org_bits(rec["organism"])
    meta = payload.setdefault("meta", {})
    meta["sotaHistoryDefaults"] = {
        "outMin": 3,
        "in2026": 1,
        "in2025": 2,
        "in2024": 3,
        "histP": 50,
        "histK": 3,
        "rule": "≤2018 history (P≥50 or k≥3); 2019–2024 contemporary (that or Out≥3); 2026 Out≥3 OR In≥1; 2025 Out≥3 AND In≥2",
    }
    meta["nUntaggedStage"] = int(sum(1 for p in papers if p.get("ws") and int(p.get("st") or 0) == 0))
    payload["papers"] = papers
    JSON_IN.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def _write_importance_tables(papers: list[dict]) -> None:
    """Topic × time and per-work measures from tagged papers (no networkx)."""
    import sys
    import types

    if "networkx" not in sys.modules:
        fake = types.ModuleType("networkx")
        fake.DiGraph = object  # type: ignore[attr-defined]
        sys.modules["networkx"] = fake
    from build_corpus_filter_comparison import write_importance_tables  # noqa: E402

    cat = pd.read_csv(CATALOG, low_memory=False).drop_duplicates("work_id", keep="first")
    write_importance_tables(cat, papers)


def _replace_ts_const(path: Path, name: str, type_hint: str, value) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    dumped = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    pat = re.compile(rf"const {re.escape(name)}: {re.escape(type_hint)} = .*?;\n")
    repl = f"const {name}: {type_hint} = {dumped};\n"
    new, n = pat.subn(repl, text, count=1)
    if n != 1:
        print("canvas const not patched", path.name, name, "n=", n)
        return
    path.write_text(new, encoding="utf-8")
    print("patched canvas", path.name, name)


def _kcore_meta_for_canvas(existing_meta: dict, payload_meta: dict) -> dict:
    """Keep the canvas Meta shape; refresh counts and the SOTA rule string."""
    out = dict(existing_meta)
    for k in (
        "n",
        "nExplore",
        "nWorkingSet",
        "nNamedWorkingSet",
        "nUnavailDropped",
        "nFillOutsideCatalog",
        "nExcluded",
        "nEdges",
        "nGraphTouched",
        "maxK",
        "maxKd",
        "maxKin",
        "yMin",
        "yMax",
        "tprAlpha",
        "tprFormula",
        "kCoreDef",
        "citesDef",
        "inOutDef",
        "cohortDef",
        "decadeNs",
        "heatYears",
        "heatOuts",
        "heat",
        "nOnlyOutRecent",
        "nOnlyOutRecentK3Drop",
        "nOnlyOutRecentC50Drop",
        "stageNames",
        "orgNames",
        "timeBins",
        "timeRoles",
        "nUntaggedStage",
    ):
        if k in payload_meta:
            out[k] = payload_meta[k]
    out["sotaHistoryDefaults"] = payload_meta.get("sotaHistoryDefaults", out.get("sotaHistoryDefaults"))
    return out


def main() -> None:
    cat = pd.read_csv(CATALOG, low_memory=False).drop_duplicates("work_id", keep="first")
    payload = json.loads(JSON_IN.read_text())
    papers = payload["papers"]
    if len(cat) != len(papers):
        raise SystemExit(f"catalog {len(cat)} vs papers {len(papers)}")

    tags = pd.read_csv(TAGS)
    tag_map = {
        str(w): (str(s or ""), str(d or ""))
        for w, s, d in zip(
            tags["work_id"].astype(str),
            tags.get("stages", pd.Series("", index=tags.index)).fillna(""),
            tags.get("datasets", pd.Series("", index=tags.index)).fillna(""),
        )
    }
    stray = pd.read_csv(STRAYS)
    stray_map = {
        str(w): str(a or "")
        for w, a, adj in zip(
            stray["work_id"].astype(str),
            stray["axis_or_reason"].fillna(""),
            stray["adjudication"].fillna(""),
        )
        if str(adj) == "keep"
    }
    methods = pd.read_csv(METHODS)
    method_by_doi = {
        str(d).strip().lower(): str(m)
        for d, m in zip(methods["doi"].fillna(""), methods["method"].fillna(""))
        if str(d).strip()
    }
    abstracts = load_abstracts()
    authors_map = load_authors()
    prev_core = pd.read_csv(CORE_IN) if CORE_IN.exists() else pd.DataFrame()

    rows_all: list[dict] = []
    for r, p in zip(cat.itertuples(index=False), papers):
        wid = str(r.work_id)
        doi = _clean_meta(r.doi)
        title = _clean_meta(r.title)
        venue = _clean_meta(getattr(r, "venue", ""))
        y = p.get("y")
        inn = int(p.get("i") or 0)
        out = int(p.get("o") or 0)
        k = int(p.get("k") or 0)
        pct = int(p.get("p") or 0)
        cites = int(p.get("c") or 0)
        abs_ = abstracts.get(wid, "")
        abs_missing = not bool(abs_)
        st0, ds0 = tag_map.get(wid, ("", ""))
        stages, datasets, td_src = extract_stages_datasets(title, abs_, st0, ds0)
        organism, org_src = extract_organism(title, abs_, datasets)
        decision = str(getattr(r, "decision", "") or "")
        stray_raw = stray_map.get(wid, "")
        axis, ax_src = infer_axis(
            title,
            stages,
            datasets,
            stray_raw,
            decision,
            abs_,
        )
        flags = axis_flags(axis, stray_raw, title, decision, stages, datasets)
        reg_m = method_by_doi.get(doi.lower(), "")
        method, m_src = extract_methods(title, abs_, reg_m)
        ws = bool(p.get("ws"))
        if not ws:
            time_role = ""
            why = "unavailable_pdf" if p.get("u") else "overlay_drop"
            in_core = 0
        else:
            time_role, why = sota_history_flags(y, inn, out, pct, k)
            in_core = 1 if time_role else 0
        era, _ = time_bin_of(y)
        sources = [s for s in (td_src, org_src, ax_src, m_src) if s]
        pdf = pdf_fields(r)
        rows_all.append(
            {
                "work_id": wid,
                "stem": pdf["stem"],
                "title": title,
                "year": y if y is not None else "",
                "authors": authors_map.get(wid, ""),
                "venue": venue,
                "doi": doi,
                "landing_url": pdf["landing_url"],
                "catalog_url": pdf["catalog_url"],
                "pdf_status": pdf["pdf_status"],
                "pdf_path": pdf["pdf_path"],
                "pdf_url": pdf["pdf_url"],
                "pdf_link": pdf["pdf_link"],
                "era": era,
                "inclusion_role": time_role,
                "time_role": time_role,
                "in_analysis_base": 1 if ws else 0,
                "in_degree": inn,
                "out_degree": out,
                "k_core": k,
                "year_cites_percentile": pct,
                "cites": cites,
                "in_core": in_core,
                "source_group": str(getattr(r, "source_group", "") or ""),
                "decision": decision,
                "datasets": datasets,
                "stages": stages,
                "organism": organism,
                "axis": axis,
                "method": method,
                "pipeline_stage": flags["pipeline_stage"],
                "registry_dataset": flags["registry_dataset"],
                "biological_application": flags["biological_application"],
                "bridge": flags["bridge"],
                "field_synthesis": flags["field_synthesis"],
                "training_outreach": flags["training_outreach"],
                "health_translation": flags["health_translation"],
                "abstract_missing": "true" if abs_missing else "false",
                "tag_source": "+".join(dict.fromkeys(sources)) if sources else "blank",
                "why": why,
            }
        )

    rows_base = [r for r in rows_all if r["in_analysis_base"] == 1]
    rows_core = [r for r in rows_all if r["in_core"] == 1]
    fieldnames = list(rows_all[0].keys())
    OUT_BASE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FULL.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_all)
    with OUT_BASE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_base)
    with OUT_CORE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_core)

    dims = (
        "stages",
        "datasets",
        "organism",
        "axis",
        "method",
        "training_outreach",
        "health_translation",
        "biological_application",
        "bridge",
        "field_synthesis",
        "pdf_path",
    )
    stats_core = filled_stats(rows_core, dims)
    stats_base = filled_stats(rows_base, dims)
    stats_all = filled_stats(rows_all, dims)
    n_core_abs_miss = sum(1 for r in rows_core if r["abstract_missing"] == "true")
    n_base_abs_miss = sum(1 for r in rows_base if r["abstract_missing"] == "true")
    n_all_abs_miss = sum(1 for r in rows_all if r["abstract_missing"] == "true")
    n_hist = sum(1 for r in rows_core if r["time_role"] == "history")
    n_contemp = sum(1 for r in rows_core if r["time_role"] == "contemporary")
    n_sota = sum(1 for r in rows_core if r["time_role"] == "sota")
    pdf_counts = dict(Counter(r["pdf_status"] for r in rows_all))

    stats = {
        "n_catalog": len(rows_all),
        "n_named_working_set": 1544,
        "n_analysis_base": len(rows_base),
        "n_core": len(rows_core),
        "n_history": n_hist,
        "n_contemporary": n_contemp,
        "n_sota": n_sota,
        "n_sota_2024": sum(1 for r in rows_core if r["year"] == 2024),
        "n_sota_2025": sum(1 for r in rows_core if r["year"] == 2025),
        "n_sota_2026": sum(1 for r in rows_core if r["year"] == 2026),
        "sota_rule": "≤2018 history (P≥50 or k≥3); 2019–2024 contemporary (that bar or Out≥3); 2026 Out≥3 OR In≥1; 2025 Out≥3 AND In≥2",
        "n_fill_outside_catalog": 47,
        "n_unavail_dropped": 4,
        "unavail_disposition": "drop all four (none a unique milestone; GCIB landmark is 10.1038/s41592-019-0641-2 in the working set)",
        "bins": [b[0] for b in TIME_BINS],
        "bin_scheme": "historical ≤2018 (pre-2005, 2005–2009, 2010–2015, 2016–2018); contemporary 2019–2024 yearly; SOTA 2025–2026 yearly",
        "fill_pct": stats_core,
        "fill_pct_base": stats_base,
        "fill_pct_catalog": stats_all,
        "pdf_status_catalog": pdf_counts,
        "n_abstract_missing_core": n_core_abs_miss,
        "n_abstract_missing_base": n_base_abs_miss,
        "n_abstract_missing_catalog": n_all_abs_miss,
        "tag_source_counts": dict(Counter(r["tag_source"] for r in rows_core)),
        "untagged_axis_and_stage": sum(
            1 for r in rows_core if not r["stages"] and not r["datasets"] and not r["axis"]
        ),
        "untagged_axis_and_stage_catalog": sum(
            1 for r in rows_all if not r["stages"] and not r["datasets"] and not r["axis"]
        ),
        "method_label_source": "title+abstract named techniques; registry names when they match",
        "full_tagged_table": str(OUT_FULL.relative_to(ROOT)),
    }

    compact = []
    for r in rows_core:
        compact.append(
            {
                "y": r["year"] if r["year"] != "" else None,
                "i": r["in_degree"],
                "o": r["out_degree"],
                "k": r["k_core"],
                "p": r["year_cites_percentile"],
                "c": r["cites"],
                "id": r["work_id"],
                "role": r["time_role"],
                "era": r["era"],
                "st": r["stages"],
                "ds": r["datasets"],
                "og": r["organism"],
                "ax": r["axis"],
                "m": r["method"],
                "dec": r["decision"],
                "t": (r["title"][:96] + "…") if len(r["title"]) > 96 else r["title"],
                "d": r["doi"],
            }
        )
    OUT_JSON.write_text(json.dumps({"meta": stats, "papers": compact}, separators=(",", ":")), encoding="utf-8")

    _patch_filter_json(payload, papers, rows_all)
    try:
        _write_importance_tables(papers)
    except Exception as exc:  # noqa: BLE001
        print("importance tables skipped:", exc)

    _replace_ts_const(CANVAS_CORE, "DATA", "Paper[]", compact)
    canvas_meta = {
        k: stats[k]
        for k in (
            "n_catalog",
            "n_named_working_set",
            "n_analysis_base",
            "n_core",
            "n_history",
            "n_contemporary",
            "n_sota",
            "n_sota_2024",
            "n_sota_2025",
            "n_sota_2026",
            "sota_rule",
            "n_fill_outside_catalog",
            "n_unavail_dropped",
            "unavail_disposition",
            "bins",
            "bin_scheme",
            "fill_pct",
            "fill_pct_base",
            "n_abstract_missing_core",
            "n_abstract_missing_base",
            "tag_source_counts",
            "untagged_axis_and_stage",
            "method_label_source",
        )
    }
    _replace_ts_const(CANVAS_CORE, "META", "Meta", canvas_meta)
    if CANVAS_KCORE.exists():
        ktext = CANVAS_KCORE.read_text(encoding="utf-8")
        km = re.search(r"const META: Meta = (\{.*?\});\n", ktext)
        existing_kmeta = json.loads(km.group(1)) if km else {}
        kmeta = _kcore_meta_for_canvas(existing_kmeta, payload["meta"])
        _replace_ts_const(CANVAS_KCORE, "DATA", "Paper[]", papers)
        _replace_ts_const(CANVAS_KCORE, "META", "Meta", kmeta)
        ktext = CANVAS_KCORE.read_text(encoding="utf-8")
        ktext = ktext.replace(
            "Era bins: pre-2005, 2005–2009, 2010–2015,\n            then 2-year cells through 2023, yearly 2024–2026.",
            "Era bins: pre-2005, 2005–2009, 2010–2015, 2016–2018;\n            contemporary 2019–2024 yearly; SOTA 2025–2026 yearly.",
        )
        ktext = ktext.replace(
            "2026 Out≥3 OR In≥1; 2025 Out≥3 AND In≥2; 2024 Out≥3 AND In≥3",
            "≤2018 history (P≥50 or k≥3); 2019–2024 contemporary (that or Out≥3); 2026 Out≥3 OR In≥1; 2025 Out≥3 AND In≥2",
        )
        CANVAS_KCORE.write_text(ktext, encoding="utf-8")

    print("catalog", len(rows_all), "base", len(rows_base), "core", len(rows_core))
    print("core split history/contemporary/sota", n_hist, n_contemp, n_sota)
    print("pdf_status", pdf_counts)
    print("abstract missing catalog/base/core", n_all_abs_miss, n_base_abs_miss, n_core_abs_miss)
    print("fill % core", stats_core)
    print("fill % catalog", stats_all)
    print("wrote", OUT_FULL)
    print("wrote", OUT_CORE)
    print("wrote", OUT_BASE)
    print("wrote", OUT_JSON)

    prev_empty = {
        str(w)
        for w, m in zip(
            prev_core.get("work_id", pd.Series(dtype=str)).astype(str),
            prev_core.get("method", pd.Series(dtype=str)).fillna(""),
        )
        if not str(m).strip()
    }
    newly = [r for r in rows_core if r["work_id"] in prev_empty and r["method"]]
    print("newly filled method on core", len(newly))
    for r in newly[:8]:
        print(f"NEW {r['year']} {r['method'][:60]:60} {r['title'][:70]}")


if __name__ == "__main__":
    main()
