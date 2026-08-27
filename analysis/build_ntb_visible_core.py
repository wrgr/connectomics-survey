#!/usr/bin/env python3
"""Build the NeuroTrailblazers visible-core source: one collection, many views.

First export is the visible core only (not the 1,806 catalog).
Reads the tagged core table and writes source_artifact/neurotrailblazers_visible_core/.
Does not rewrite paper_links.csv. Does not copy PDFs.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from label_from_title_abstract import load_abstracts  # noqa: E402

CATALOG = ROOT / "postanalysis/pdfs/paper_links.csv"
CORE = ROOT / "postanalysis/registry/sota_history_core_labeled.csv"
EDGES = ROOT / "source_artifact/connectomics_deterministic_pipeline/outputs/paper_graph_edges.csv"
ROLES = ROOT / "postanalysis/llm_agent_v3/citation_roles_by_work.csv"
OUT = ROOT / "source_artifact/neurotrailblazers_visible_core"
RELATED_CAP = 8

STAGE_TO_DIM = {
    "preparation": "image-acquisition",
    "sectioning": "image-acquisition",
    "acquisition": "image-acquisition",
    "alignment": "methods-general",
    "segmentation": "segmentation",
    "proofreading": "proofreading",
    "synapses": "neuroanatomy",
    "infrastructure": "infrastructure",
    "graph_analysis": "graph-analysis",
    "modeling": "neuroai",
}
AXIS_TO_DIM = {
    "field_synthesis": "review",
    "biological_application": "connectomics",
    "training_outreach": "methods-general",
    "health_translation": "connectomics",
    "bridge": "graph-analysis",
    "registry_dataset": "connectomics",
}
READING_PHASE = {
    "history": "1_foundations",
    "contemporary": "2_contemporary",
    "sota": "3_sota",
}
CELL_TYPE_RE = re.compile(r"\bcell types?\b|\bneuron types?\b|\bhemilineage", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Editorial paths from the live journal-club page, resolved by DOI / title.
READING_PATHS = [
    {
        "id": "historical_arc",
        "title": "Historical arc",
        "description": "White 1986 → Denk & Horstmann 2004 → Briggman & Bock 2012 → Kasthuri 2015 → Zheng 2018 → Dorkenwald 2024",
        "needles": [
            ("10.1098/rstb.1986.0056", "the structure of the nervous system of the nematode"),
            ("10.1371/journal.pbio.0020329", "serial block-face scanning electron"),
            ("10.1016/j.conb.2011.10.022", "volume electron microscopy for neuronal circuit"),
            ("10.1016/j.cell.2015.06.054", "saturated reconstruction of a volume of neocortex"),
            ("10.1016/j.cell.2018.06.019", "complete electron microscopy volume of the brain of adult drosophila"),
            ("10.1038/s41586-024-07558-y", "neuronal wiring of a complete adult"),
        ],
    },
    {
        "id": "methods_deep_dive",
        "title": "Methods deep dive",
        "description": "Imaging: Xu 2017 → Yin 2020. Segmentation: Januszewski 2018. Proofreading: Plaza 2014 → Dorkenwald 2022 FlyWire. Turaga 2010 and Sheridan 2023 are not in this catalog.",
        "needles": [
            ("10.7554/elife.25916", "enhanced fib-sem systems for large-volume"),
            ("10.1038/s41467-020-18659-3", "a petascale automated imaging pipeline"),
            ("10.1038/s41592-018-0049-4", "high-precision automated reconstruction of neurons"),
            ("", "focused proofreading: efficiently extracting"),
            ("10.1038/s41592-021-01330-0", "flywire: online community for whole-brain"),
        ],
    },
    {
        "id": "analysis_interpretation",
        "title": "Analysis and interpretation",
        "description": "Winding 2023 → Lappalainen 2024. Bullmore & Sporns 2009 and Rubinov & Sporns 2010 are not in this catalog (macroscale network-science classics).",
        "needles": [
            ("10.1126/science.add9330", "the connectome of an insect brain"),
            ("10.1038/s41586-024-07939-3", "connectome-constrained networks predict neural activity"),
        ],
    },
]


def _s(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    t = str(v).strip()
    return "" if t.lower() in ("", "nan", "none") else t


def _i(v) -> int:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _split(v: str) -> list[str]:
    return [p for p in (_s(v).split(";")) if p]


def uuid_of(doi: str, work_id: str) -> str:
    d = _s(doi).lower()
    return d if d else work_id


def slug_id(authors: str, year, doi: str, work_id: str) -> str:
    first = _s(authors).split(";")[0].split(",")[0].strip()
    last = re.sub(r"[^a-z0-9]+", "", (first.split()[-1] if first else "anon").lower())
    y = str(year) if year not in (None, "") else "nd"
    if _s(doi):
        tail = re.sub(r"[^a-z0-9]+", "-", _s(doi).split("/")[-1][:20].lower()).strip("-")
        return f"{last}-{y}-{tail}"
    return f"{last}-{y}-{work_id[-8:]}"


def sentences(text: str) -> list[str]:
    parts = SENT_SPLIT.split(_s(text).replace("\n", " "))
    return [p.strip() for p in parts if p.strip()]


def ntb_dimension(axis: str, stages: list[str], title: str) -> str:
    if CELL_TYPE_RE.search(title or ""):
        return "cell-types"
    if axis in AXIS_TO_DIM:
        return AXIS_TO_DIM[axis]
    for st in stages:
        if st in STAGE_TO_DIM:
            return STAGE_TO_DIM[st]
    return "connectomics"


def ntb_role(axis: str, stages: list[str]) -> str:
    if axis == "field_synthesis":
        return "review"
    if axis == "biological_application":
        return "biology"
    if axis in ("training_outreach", "health_translation"):
        return "bridge"
    if stages:
        return "methods"
    return "survey"


def yaml_quote(s: str) -> str:
    s = _s(s).replace("\r\n", "\n").replace("\r", "\n")
    if not s:
        return '""'
    if any(c in s for c in ":#{}[]&*!|>%@`'\"\n") or s[:1] in "-?":
        return json.dumps(s, ensure_ascii=False)
    return s


def pedagogy(title: str, abstract: str, stages: list[str], datasets: list[str], method: str) -> dict:
    sents = sentences(abstract)
    first = sents[0] if sents else title
    rest = " ".join(sents[1:]) if len(sents) > 1 else first
    last = sents[-1] if sents else ""
    stage_txt = ", ".join(stages) if stages else "the connectomics pipeline"
    method_txt = method.replace(";", ", ") if method else "the methods named in the paper"
    opportunity = first
    challenge = (
        sents[1]
        if len(sents) > 1
        else f"Doing this well required progress in {stage_txt}."
    )
    action = (
        f"The authors address this with {method_txt}."
        if method
        else (sents[2] if len(sents) > 2 else rest or first)
    )
    resolution = rest or first
    future = last if re.search(r"\b(future|remain|next|further|will|should)\b", last, re.I) else (
        "A natural next step is to test whether the result holds on other volumes and organisms."
    )
    beginner = first
    intermediate = abstract if abstract else title
    advanced = abstract if abstract else title
    prompts = [
        f"What problem in {stage_txt} does this paper actually solve, and what would falsify that?",
        (
            f"How far does this transfer beyond {', '.join(datasets)}?"
            if datasets
            else "Which dataset or organism would you trust this result on next, and why?"
        ),
        "What should a current reader still take from this paper, and what has been superseded?",
    ]
    tags = stages + datasets
    if method:
        tags.extend(_split(method.replace(",", ";")))
    tags = list(dict.fromkeys(t.lower() for t in tags if t))
    return {
        "annotation_status": "generated_from_abstract",
        "ocar": {
            "opportunity": opportunity,
            "challenge": challenge,
            "action": action,
            "resolution": resolution,
            "future_work": future,
        },
        "plain_language_summary": beginner,
        "summaries": {
            "beginner": beginner,
            "intermediate": intermediate,
            "advanced": advanced,
        },
        "discussion_prompts": prompts,
        "tags": tags[:12],
    }


def dump_yaml_papers(papers: list[dict], path: Path) -> None:
    """Minimal YAML emitter matching the live NTB journal_papers.yml shape."""
    lines = [
        "# Generated by analysis/build_ntb_visible_core.py",
        "# One collection. Views live in ../views/. Do not split into a second corpus.",
        "",
    ]
    for p in papers:
        ocar = p["ocar"]
        sums = p["summaries"]
        lines.append(f"- id: {p['id']}")
        lines.append(f"  uuid: {yaml_quote(p['uuid'])}")
        lines.append(f"  work_id: {p['work_id']}")
        lines.append(f"  title: {yaml_quote(p['title'])}")
        lines.append(f"  authors: {yaml_quote(p['authors'])}")
        lines.append(f"  year: {p['year'] if p['year'] is not None else 'null'}")
        lines.append(f"  journal: {yaml_quote(p['journal'])}")
        lines.append(f"  doi: {yaml_quote(p['doi'])}")
        lines.append(f"  dimension: {p['dimension']}")
        lines.append(f"  reading_phase: {p['reading_phase']}")
        lines.append(f"  role: {p['ntb_role']}")
        lines.append(f"  inclusion_role: {p['role']}")
        lines.append(f"  k_core: {p['graph']['k_core']}")
        lines.append(f"  in_degree: {p['graph']['in']}")
        lines.append(f"  out_degree: {p['graph']['out']}")
        lines.append(f"  annotation_status: {p['annotation_status']}")
        if p["tags"]:
            lines.append("  tags:")
            for t in p["tags"]:
                lines.append(f"    - {yaml_quote(t)}")
        else:
            lines.append("  tags: []")
        lines.append("  ocar:")
        for k in ("opportunity", "challenge", "action", "resolution", "future_work"):
            lines.append(f"    {k}: {yaml_quote(ocar[k])}")
        lines.append(f"  plain_language_summary: {yaml_quote(p['plain_language_summary'])}")
        lines.append("  summaries:")
        for k in ("beginner", "intermediate", "advanced"):
            lines.append(f"    {k}: {yaml_quote(sums[k])}")
        lines.append("  discussion_prompts:")
        for pr in p["discussion_prompts"]:
            lines.append(f"    - {yaml_quote(pr)}")
        lines.append(f"  pdf_url: {yaml_quote(p['pdf']['url'])}")
        lines.append(f"  pdf_status: {p['pdf']['status']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def resolve_path(needles: list[tuple[str, str]], by_doi: dict[str, str], papers: list[dict]) -> list[str]:
    uuids: list[str] = []
    for doi, needle in needles:
        if doi and doi in by_doi:
            uuids.append(by_doi[doi])
            continue
        hit = ""
        needle_l = needle.lower()
        for p in papers:
            if needle_l and needle_l in (p["title"] or "").lower():
                hit = p["uuid"]
                break
        if hit:
            uuids.append(hit)
    return list(dict.fromkeys(uuids))


def main() -> None:
    cat = pd.read_csv(CATALOG, low_memory=False).drop_duplicates("work_id", keep="first")
    core = pd.read_csv(CORE, low_memory=False)
    core = core[core["in_core"].fillna(0).astype(int) == 1].copy()
    abstracts = load_abstracts()
    pid_to_wid = {
        str(p): str(w)
        for p, w in zip(cat["canonical_paper_id"], cat["work_id"])
        if pd.notna(p) and str(p)
    }
    wid_to_pdf = dict(zip(cat["work_id"].astype(str), cat["pdf_url"].fillna("").astype(str)))
    core_ids = set(core["work_id"].astype(str))
    cites: dict[str, list[str]] = defaultdict(list)
    cited_by: dict[str, list[str]] = defaultdict(list)
    if EDGES.exists():
        edges = pd.read_csv(EDGES)
        for src, tgt in zip(edges["source"].astype(str), edges["target"].astype(str)):
            u = pid_to_wid.get(src)
            v = pid_to_wid.get(tgt)
            if u in core_ids and v in core_ids and u != v:
                cites[u].append(v)
                cited_by[v].append(u)
    k_of = {str(w): _i(k) for w, k in zip(core["work_id"], core["k_core"])}

    def rank_neighbors(ids: list[str]) -> list[str]:
        uniq = list(dict.fromkeys(ids))
        uniq.sort(key=lambda w: (-k_of.get(w, 0), w))
        return uniq[:RELATED_CAP]

    role_map: dict[str, dict] = {}
    if ROLES.exists():
        rdf = pd.read_csv(ROLES, low_memory=False)
        for r in rdf.itertuples(index=False):
            role_map[str(r.work_id)] = {
                "citation_role": _s(getattr(r, "citation_role", "")),
                "link_strength": _s(getattr(r, "citation_link_strength", "")),
            }

    papers: list[dict] = []
    for r in core.itertuples(index=False):
        wid = str(r.work_id)
        doi = _s(getattr(r, "doi", ""))
        uuid = uuid_of(doi, wid)
        title = _s(r.title)
        authors = _s(getattr(r, "authors", ""))
        year = _i(r.year) or None
        stages = _split(getattr(r, "stages", ""))
        datasets = _split(getattr(r, "datasets", ""))
        method = _s(getattr(r, "method", ""))
        axis = _s(getattr(r, "axis", ""))
        abstract = abstracts.get(wid, "")
        ped = pedagogy(title, abstract, stages, datasets, method)
        pdf_url = _s(getattr(r, "pdf_url", "")) or _s(getattr(r, "catalog_url", "")) or _s(getattr(r, "landing_url", ""))
        if not pdf_url:
            pdf_url = _s(wid_to_pdf.get(wid, "")) or (_s(getattr(r, "landing_url", "")) or (f"https://doi.org/{doi}" if doi else ""))
        rec = {
            "uuid": uuid,
            "id": slug_id(authors, year, doi, wid),
            "work_id": wid,
            "title": title,
            "authors": authors,
            "year": year,
            "journal": _s(getattr(r, "venue", "")),
            "doi": doi,
            "landing_url": _s(getattr(r, "landing_url", "")),
            "pdf": {
                "status": _s(getattr(r, "pdf_status", "")),
                "url": pdf_url,
                "local_path": _s(getattr(r, "pdf_path", "")),
            },
            "graph": {
                "in": _i(getattr(r, "in_degree", 0)),
                "out": _i(getattr(r, "out_degree", 0)),
                "k_core": _i(getattr(r, "k_core", 0)),
                "cites": _i(getattr(r, "cites", 0)),
                "year_cites_percentile": _i(getattr(r, "year_cites_percentile", 0)),
                **role_map.get(wid, {}),
            },
            "role": _s(getattr(r, "inclusion_role", "") or getattr(r, "time_role", "")),
            "era": _s(getattr(r, "era", "")),
            "why": _s(getattr(r, "why", "")),
            "streams": {
                "axis": axis,
                "stages": stages,
                "datasets": datasets,
                "organism": _split(getattr(r, "organism", "")),
                "method": _split(method.replace(",", ";")) if method else [],
                "training_outreach": _s(getattr(r, "training_outreach", "")),
                "health_translation": _s(getattr(r, "health_translation", "")),
                "biological_application": _s(getattr(r, "biological_application", "")),
                "bridge": _s(getattr(r, "bridge", "")),
                "field_synthesis": _s(getattr(r, "field_synthesis", "")),
            },
            "related": {"cites": [], "cited_by": []},
            "dimension": ntb_dimension(axis, stages, title),
            "reading_phase": READING_PHASE.get(_s(getattr(r, "inclusion_role", "") or getattr(r, "time_role", "")), "2_contemporary"),
            "ntb_role": ntb_role(axis, stages),
            **ped,
        }
        papers.append(rec)

    # Related uuids: map work_id neighbors through a precomputed uuid map (avoid per-row loc).
    uuid_of_wid = {p["work_id"]: p["uuid"] for p in papers}
    for p in papers:
        p["related"] = {
            "cites": [uuid_of_wid[w] for w in rank_neighbors(cites.get(p["work_id"], [])) if w in uuid_of_wid],
            "cited_by": [uuid_of_wid[w] for w in rank_neighbors(cited_by.get(p["work_id"], [])) if w in uuid_of_wid],
        }

    papers.sort(key=lambda p: (-p["graph"]["k_core"], -(p["year"] or 0), p["title"].lower()))
    by_uuid = {p["uuid"]: p for p in papers}
    by_doi = {p["doi"].lower(): p["uuid"] for p in papers if p["doi"]}

    out_views = OUT / "views"
    out_export = OUT / "ntb_export"
    out_views.mkdir(parents=True, exist_ok=True)
    out_export.mkdir(parents=True, exist_ok=True)

    def write_view(name: str, payload: dict) -> None:
        (out_views / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    write_view(
        "kcore",
        {
            "id": "kcore",
            "title": "Highest k-core",
            "description": "Same collection, ordered by corpus k-core. Not a second corpus.",
            "kind": "rank",
            "uuids": [p["uuid"] for p in papers],
        },
    )

    def group_view(vid: str, title: str, description: str, key_fn, order: list[str] | None = None) -> None:
        buckets: dict[str, list[str]] = defaultdict(list)
        for p in papers:
            keys = key_fn(p)
            if isinstance(keys, str):
                keys = [keys] if keys else []
            for k in keys:
                if k:
                    buckets[str(k)].append(p["uuid"])
        keys_sorted = order if order else sorted(buckets, key=lambda k: (-len(buckets[k]), k))
        groups = [{"key": k, "label": k, "n": len(buckets[k]), "uuids": buckets[k]} for k in keys_sorted if k in buckets]
        write_view(vid, {"id": vid, "title": title, "description": description, "kind": "group", "groups": groups})

    group_view(
        "era",
        "Era",
        "Historical ≤2018, contemporary 2019–2024, SOTA 2025–2026.",
        lambda p: p["role"],
        ["history", "contemporary", "sota"],
    )
    group_view(
        "pipeline_stage",
        "Pipeline stage",
        "Stereotyped connectomics pipeline. A paper may appear in more than one stage.",
        lambda p: p["streams"]["stages"],
        ["preparation", "sectioning", "acquisition", "alignment", "segmentation", "proofreading", "synapses", "infrastructure", "graph_analysis", "modeling"],
    )
    group_view("organism", "Organism", "Organism stream.", lambda p: p["streams"]["organism"])
    group_view("dataset", "Dataset", "Registry volumes named in title or abstract.", lambda p: p["streams"]["datasets"])
    group_view("method", "Method", "Named techniques from title and abstract.", lambda p: p["streams"]["method"])
    group_view(
        "axis",
        "Charting axis",
        "Including training/outreach and health translation. Highest k-core is a different view, not a different set.",
        lambda p: p["streams"]["axis"],
    )
    group_view("year", "Year", "Publication year.", lambda p: str(p["year"] or "unknown"))
    group_view(
        "dimension",
        "Journal-club dimension",
        "Derived mapping onto the old 11 NTB dimensions. Still one collection.",
        lambda p: p["dimension"],
    )

    path_groups = []
    for path in READING_PATHS:
        uuids = resolve_path(path["needles"], by_doi, papers)
        path_groups.append({"key": path["id"], "label": path["title"], "description": path["description"], "n": len(uuids), "uuids": uuids})
    write_view(
        "reading_paths",
        {
            "id": "reading_paths",
            "title": "Suggested reading paths",
            "description": "Editorial sequences from the journal-club page, resolved onto core uuids. Not inclusion criteria.",
            "kind": "group",
            "groups": path_groups,
        },
    )

    manifest = {
        "collection": "visible_core",
        "n": len(papers),
        "views": [
            {"id": "kcore", "title": "Highest k-core", "kind": "rank"},
            {"id": "era", "title": "Era", "kind": "group"},
            {"id": "pipeline_stage", "title": "Pipeline stage", "kind": "group"},
            {"id": "organism", "title": "Organism", "kind": "group"},
            {"id": "dataset", "title": "Dataset", "kind": "group"},
            {"id": "method", "title": "Method", "kind": "group"},
            {"id": "axis", "title": "Charting axis", "kind": "group"},
            {"id": "year", "title": "Year", "kind": "group"},
            {"id": "dimension", "title": "Journal-club dimension", "kind": "group"},
            {"id": "reading_paths", "title": "Suggested reading paths", "kind": "group"},
        ],
    }
    (out_views / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    meta = {
        "n_collection": len(papers),
        "n_history": sum(1 for p in papers if p["role"] == "history"),
        "n_contemporary": sum(1 for p in papers if p["role"] == "contemporary"),
        "n_sota": sum(1 for p in papers if p["role"] == "sota"),
        "n_with_doi": sum(1 for p in papers if p["doi"]),
        "n_without_doi": sum(1 for p in papers if not p["doi"]),
        "pdf_status": {str(k): int(v) for k, v in pd.Series([p["pdf"]["status"] for p in papers]).value_counts().items()},
        "n_with_related": sum(1 for p in papers if p["related"]["cites"] or p["related"]["cited_by"]),
        "annotation_status": {str(k): int(v) for k, v in pd.Series([p["annotation_status"] for p in papers]).value_counts().items()},
        "rule": "≤2018 history (P≥50 or k≥3); 2019–2024 contemporary (that or Out≥3); 2026 Out≥3 OR In≥1; 2025 Out≥3 AND In≥2",
        "uuid": "doi lowercase, else work_id",
        "export_scope": "visible_core_only",
        "n_catalog_not_exported": 1806,
        "n_working_set_not_exported": 1488,
        "n_earlier_two_period_union": 1142,
        "earlier_union_note": "1,142 was history-through-2023 plus 2024–2026 SOTA before the 2019–2024 contemporary split and dropping 4 unavailable PDFs. First NTB export is the current core, not that union and not the 1,806 catalog.",
        "source_catalog": "postanalysis/pdfs/paper_links.csv",
        "source_core": "postanalysis/registry/sota_history_core_labeled.csv",
        "replaces": [
            "https://www.neurotrailblazers.org/content-library/journal-papers/",
            "https://www.neurotrailblazers.org/technical-training/journal-club/",
        ],
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (OUT / "collection.json").write_text(json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "collection.jsonl").open("w", encoding="utf-8") as f:
        for p in papers:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    dump_yaml_papers(papers, out_export / "journal_papers.yml")

    compact = [
        {
            "uuid": p["uuid"],
            "id": p["id"],
            "t": p["title"],
            "y": p["year"],
            "a": p["authors"].split(";")[0].strip() if p["authors"] else "",
            "k": p["graph"]["k_core"],
            "i": p["graph"]["in"],
            "o": p["graph"]["out"],
            "role": p["role"],
            "ax": p["streams"]["axis"],
            "st": ";".join(p["streams"]["stages"]),
            "ds": ";".join(p["streams"]["datasets"]),
            "og": ";".join(p["streams"]["organism"]),
            "m": ";".join(p["streams"]["method"][:4]),
            "d": p["doi"],
            "pdf": p["pdf"]["url"],
            "dim": p["dimension"],
            "rc": len(p["related"]["cites"]),
            "rb": len(p["related"]["cited_by"]),
            "sum": p["plain_language_summary"][:320],
        }
        for p in papers
    ]
    (OUT / "compact_papers.json").write_text(json.dumps(compact, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("collection", len(papers), "history/contemporary/sota", meta["n_history"], meta["n_contemporary"], meta["n_sota"])
    print("doi coverage", meta["n_with_doi"], "missing", meta["n_without_doi"])
    print("pdf", meta["pdf_status"])
    print("related nonempty", meta["n_with_related"])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
