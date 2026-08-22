from __future__ import annotations

import csv
import json
import pickle
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import yaml

from . import __version__
from .client import SemanticScholarClient, CrossrefClient
from .schema import s2_to_record
from .scope import classify_scope
from .dedupe import dedupe
from .networks import paper_graph_metrics, indirect_support
from .ranking import rank_papers
from .people import build_people
from .nih import search_reporter, funding_people
from .util import normalize_doi, normalize_title, normalize_name, sha256_file
from .pipeline import _write_csv, _write_jsonl, load_queries, merge_record, resolve_seed_row

PHASES = ("discovery", "graph", "people", "enrichment", "finalize")
CHECKPOINTS = {
    "discovery": "01_discovery.pkl",
    "graph": "02_graph.pkl",
    "people": "03_people.pkl",
    "enrichment": "04_enrichment.pkl",
}
PREVIOUS = {
    "graph": "discovery",
    "people": "graph",
    "enrichment": "people",
    "finalize": "enrichment",
}


def _progress(message: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {message}", flush=True)


def _checkpoint_path(state_dir: Path, phase: str) -> Path:
    return state_dir / CHECKPOINTS[phase]


def _state_summary(state: dict) -> dict:
    return {
        "phase": state.get("phase", ""),
        "mode": state.get("cfg", {}).get("mode"),
        "retrieved_papers": len(state.get("store") or {}),
        "seed_papers": len(state.get("seed_ids") or set()),
        "lexical_retained": len(state.get("lexical_retained") or set()),
        "retained_papers": len(state.get("retained") or set()),
        "ranked_papers": len(state.get("ranked") or []),
        "people": len(state.get("people_rows") or []),
        "graph_edges": len(state.get("graph_edges_unique") or []),
        "crossref_rows": len(state.get("verification_rows") or []),
        "funding_projects": len(state.get("funding") or []),
        "health_bridge_papers": len(state.get("health_rows") or []),
        "training_outreach_papers": len(state.get("training_rows") or []),
    }


def _save_state(state_dir: Path, phase: str, state: dict) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    state["phase"] = phase
    path = _checkpoint_path(state_dir, phase)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)
    summary = _state_summary(state)
    (state_dir / f"{phase}_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _progress(f"checkpoint saved: {path}; summary={summary}")
    return path


def _load_state(state_dir: Path, phase: str) -> dict:
    prev = PREVIOUS[phase]
    path = _checkpoint_path(state_dir, prev)
    if not path.exists():
        raise RuntimeError(f"Missing prerequisite checkpoint for phase={phase}: {path}")
    with path.open("rb") as f:
        state = pickle.load(f)
    if state.get("phase") != prev:
        raise RuntimeError(f"Checkpoint phase mismatch: expected {prev}, got {state.get('phase')}")
    if state.get("checkpoint_schema_version") != 1:
        raise RuntimeError(f"Unsupported checkpoint schema: {state.get('checkpoint_schema_version')}")
    if state.get("package_version") != __version__:
        raise RuntimeError(f"Checkpoint package version mismatch: {state.get('package_version')} != {__version__}")
    cfg_path = Path(state["cfg_path"])
    query_path = Path(state["query_path"])
    if sha256_file(cfg_path) != state.get("config_sha256"):
        raise RuntimeError("Configuration changed after checkpoint creation")
    if sha256_file(query_path) != state.get("query_file_sha256"):
        raise RuntimeError("Query file changed after checkpoint creation")
    _progress(f"checkpoint loaded: {path}; summary={_state_summary(state)}")
    return state


def _init_state(config_path: str) -> dict:
    started = datetime.now(timezone.utc)
    cfg_path = Path(config_path).resolve()
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if int(cfg["retrieval"].get("citation_hops", 1)) != 1:
        raise RuntimeError("This protocol implementation is intentionally 1-hop only. Set citation_hops: 1.")
    out = Path(cfg["outdir"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    query_path = (cfg_path.parent / cfg["retrieval"]["query_file"]).resolve()
    queries = load_queries(query_path)
    return {
        "started": started,
        "checkpoint_schema_version": 1,
        "package_version": __version__,
        "cfg_path": str(cfg_path),
        "config_sha256": sha256_file(cfg_path),
        "cfg": cfg,
        "out": str(out),
        "query_path": str(query_path),
        "query_file_sha256": sha256_file(query_path),
        "queries": queries,
        "retrieval_log": [],
        "store": {},
        "seed_ids": set(),
    }


def _s2(state: dict) -> SemanticScholarClient:
    cfg = state["cfg"]
    out = Path(state["out"])
    s2cfg = cfg["semantic_scholar"]
    return SemanticScholarClient(
        cache_dir=str(out / s2cfg["cache_dir"]),
        min_interval_seconds=float(s2cfg.get("min_interval_seconds", 1.2)),
        timeout_seconds=int(s2cfg.get("timeout_seconds", 90)),
    )


def phase_discovery(config_path: str, state_dir: Path) -> dict:
    state = _init_state(config_path)
    cfg = state["cfg"]
    queries = state["queries"]
    retrieval_log = state["retrieval_log"]
    store = state["store"]
    seed_ids = state["seed_ids"]
    s2 = _s2(state)
    s2cfg = cfg["semantic_scholar"]

    _progress("MODULAR 1/5 discovery: optional seeds + lexical retrieval + lexical screening")

    if cfg.get("mode") == "seed_expand":
        seed_csv = cfg.get("seed_csv")
        if not seed_csv:
            raise RuntimeError("mode=seed_expand requires seed_csv")
        seed_path = (Path(state["cfg_path"]).parent / seed_csv).resolve()
        for row in csv.DictReader(seed_path.open(encoding="utf-8")):
            p, meta = resolve_seed_row(s2, row)
            if not p:
                retrieval_log.append({"channel": "seed_unresolved", "title": row.get("title", ""), "doi": row.get("doi", "")})
                continue
            merge_record(store, p, channel="seed")
            seed_ids.add(p["paper_id"])
            retrieval_log.append({
                "channel": "seed", "paper_id": p["paper_id"], "title": p["title"],
                "request_fingerprint": meta.get("request_fingerprint", "") if meta else "",
            })

    for q_idx, q in enumerate(queries, start=1):
        _progress(f"discovery lexical query {q_idx}/{len(queries)}: {q['id']} axis={q['axis']}")
        max_pages = s2cfg.get("max_bulk_pages_per_query")
        for page_rows, meta in s2.bulk_search(q["query"], max_pages=max_pages):
            for raw in page_rows:
                p = s2_to_record(raw)
                merge_record(store, p, q["id"], q["axis"], "lexical")
                retrieval_log.append({
                    "channel": "lexical", "query_id": q["id"], "axis": q["axis"],
                    "query": q["query"], "paper_id": p["paper_id"], "title": p["title"],
                    "request_fingerprint": meta.get("request_fingerprint", ""),
                })

    screening = []
    lexical_retained = set(seed_ids)
    for p in store.values():
        sc = classify_scope(p, set(p.get("query_axes") or set()), cfg["screening"])
        p.update(sc)
        if sc["keep"]:
            lexical_retained.add(p["paper_id"])
        screening.append({
            "paper_id": p["paper_id"], "title": p["title"], "stage": "lexical",
            "keep": sc["keep"], "scope_reasons": sc["scope_reasons"],
            "query_axes": ";".join(sorted(p.get("query_axes") or set())),
            "health_hits": sc["health_hits"], "people_development_hits": sc.get("people_development_hits", ""),
            "network_hits": sc["network_hits"], "qc_hits": sc["qc_hits"],
        })

    if cfg.get("mode") == "fresh":
        seed_ids = set(lexical_retained)

    state.update({
        "seed_ids": seed_ids,
        "screening": screening,
        "lexical_retained": lexical_retained,
    })
    _save_state(state_dir, "discovery", state)
    return state


def phase_graph(state_dir: Path) -> dict:
    state = _load_state(state_dir, "graph")
    cfg = state["cfg"]
    s2cfg = cfg["semantic_scholar"]
    s2 = _s2(state)
    store = state["store"]
    seed_ids = state["seed_ids"]
    lexical_retained = state["lexical_retained"]
    screening = state["screening"]
    retrieval_log = state["retrieval_log"]

    _progress("MODULAR 2/5 graph: 1-hop expansion + scope + dedupe + ranking")
    graph_edges = []
    citation_max_pages = s2cfg.get("max_citation_pages_per_paper")
    page_limit = int(s2cfg.get("page_limit", 1000))
    seed_id_list = sorted(seed_ids)
    for seed_idx, sid in enumerate(seed_id_list, start=1):
        if seed_idx == 1 or seed_idx % 25 == 0 or seed_idx == len(seed_id_list):
            _progress(f"graph citation seed {seed_idx}/{len(seed_id_list)}: {sid}; retrieved={len(store)} edges={len(graph_edges)}")
        for direction in ("references", "citations"):
            try:
                for rows, meta in s2.citation_neighbors(sid, direction, max_pages=citation_max_pages, limit=page_limit):
                    for raw in rows:
                        p = s2_to_record(raw)
                        merge_record(store, p, channel=f"1hop_{direction}")
                        pid = p["paper_id"]
                        if direction == "references":
                            graph_edges.append({"source": sid, "target": pid, "edge_type": "citation"})
                        else:
                            graph_edges.append({"source": pid, "target": sid, "edge_type": "citation"})
                        retrieval_log.append({
                            "channel": f"1hop_{direction}", "seed_paper_id": sid,
                            "paper_id": pid, "title": p["title"],
                            "request_fingerprint": meta.get("request_fingerprint", ""),
                        })
            except Exception as e:
                retrieval_log.append({"channel": f"1hop_{direction}_error", "seed_paper_id": sid, "error": str(e)[:500]})

    retained = set(lexical_retained)
    for pid, p in store.items():
        if pid in retained:
            continue
        text = ((p.get("title") or "") + " " + (p.get("abstract") or "")).lower()
        inferred = set()
        if any(x in text for x in ("proofread", "quality control", "merge error", "split error")):
            inferred.add("proofreading_qc")
        if any(x in text for x in ("graph", "motif", "network topology", "centrality", "modularity")):
            inferred.add("network_science")
        if any(x in text for x in ("alzheimer", "parkinson", "epilep", "disease", "patholog", "biopsy", "patient")):
            inferred.add("health_translation")
        p["query_axes"] |= inferred
        sc = classify_scope(p, p["query_axes"], cfg["screening"])
        p.update(sc)
        if sc["keep"]:
            retained.add(pid)
        screening.append({
            "paper_id": pid, "title": p["title"], "stage": "1hop",
            "keep": sc["keep"], "scope_reasons": sc["scope_reasons"],
            "query_axes": ";".join(sorted(p.get("query_axes") or set())),
            "health_hits": sc["health_hits"], "people_development_hits": sc.get("people_development_hits", ""),
            "network_hits": sc["network_hits"], "qc_hits": sc["qc_hits"],
        })

    deduped, merges = dedupe([store[pid] for pid in retained])
    retained = {p["paper_id"] for p in deduped}

    edge_seen = set()
    graph_edges_unique = []
    for e in graph_edges:
        k = (e["source"], e["target"], e["edge_type"])
        if k not in edge_seen:
            edge_seen.add(k)
            graph_edges_unique.append(e)

    metrics = paper_graph_metrics(deduped, graph_edges_unique)
    indirect = indirect_support(seed_ids, graph_edges_unique)
    ranked = rank_papers(deduped, metrics, indirect, cfg, int(cfg["retrieval"].get("recent_year_start", 2024)))

    state.update({
        "retained": retained,
        "deduped": deduped,
        "merges": merges,
        "graph_edges_unique": graph_edges_unique,
        "metrics": metrics,
        "ranked": ranked,
    })
    _save_state(state_dir, "graph", state)
    return state


def phase_people(state_dir: Path) -> dict:
    state = _load_state(state_dir, "people")
    cfg = state["cfg"]
    s2 = _s2(state)
    store = state["store"]
    screening = state["screening"]
    retrieval_log = state["retrieval_log"]
    retained = state["retained"]
    merges = state["merges"]
    graph_edges_unique = state["graph_edges_unique"]
    seed_ids = state["seed_ids"]
    ranked = state["ranked"]
    metrics = state["metrics"]

    _progress("MODULAR 3/5 people: contributor map + deterministic author saturation")
    by_ranked = {p["paper_id"]: p for p in ranked}
    people_rows, pa_edges, co_g = build_people(ranked, set(by_ranked), cfg)

    passes = int(cfg["retrieval"].get("author_saturation_passes", 1))
    for pass_i in range(passes):
        candidates = [r for r in people_rows if r["author_saturation_candidate"]]
        candidate_list = sorted(candidates, key=lambda r: r["author_id"])
        _progress(f"people author saturation pass {pass_i+1}/{passes}; candidates={len(candidate_list)}")
        new_any = False
        for cand_idx, person in enumerate(candidate_list, start=1):
            if cand_idx == 1 or cand_idx % 25 == 0 or cand_idx == len(candidate_list):
                _progress(f"people candidate {cand_idx}/{len(candidate_list)}: {person['name']} ({person['author_id']}); retained={len(retained)}")
            try:
                for rows, meta in s2.author_papers(person["author_id"], int(cfg["retrieval"].get("max_author_papers", 1000))):
                    for raw in rows:
                        p = s2_to_record(raw)
                        if p["paper_id"] in store:
                            continue
                        p["query_ids"] = set()
                        p["query_axes"] = set()
                        p["retrieval_channels"] = {"author_saturation"}
                        text = ((p.get("title") or "") + " " + (p.get("abstract") or "")).lower()
                        for axis, terms in {
                            "network_science": ["graph", "motif", "network topology", "centrality", "modularity"],
                            "proofreading_qc": ["proofread", "quality control", "merge error", "split error"],
                            "health_translation": ["alzheimer", "parkinson", "epilep", "disease", "patholog", "biopsy", "patient"],
                            "people_development": ["training", "education", "course", "curriculum", "workshop", "summer school", "workforce", "outreach", "citizen science", "community science", "mentoring", "trainee"],
                            "infrastructure": ["versioning", "database", "petascale", "annotation platform", "storage"],
                        }.items():
                            if any(t in text for t in terms):
                                p["query_axes"].add(axis)
                        sc = classify_scope(p, p["query_axes"], cfg["screening"])
                        p.update(sc)
                        store[p["paper_id"]] = p
                        screening.append({
                            "paper_id": p["paper_id"], "title": p["title"], "stage": "author_saturation",
                            "keep": sc["keep"], "scope_reasons": sc["scope_reasons"],
                            "query_axes": ";".join(sorted(p["query_axes"])),
                            "health_hits": sc["health_hits"], "people_development_hits": sc.get("people_development_hits", ""),
                            "network_hits": sc["network_hits"], "qc_hits": sc["qc_hits"],
                        })
                        retrieval_log.append({
                            "channel": "author_saturation", "author_id": person["author_id"],
                            "author_name": person["name"], "paper_id": p["paper_id"], "title": p["title"],
                            "request_fingerprint": meta.get("request_fingerprint", ""),
                        })
                        if sc["keep"]:
                            retained.add(p["paper_id"])
                            new_any = True
            except Exception as e:
                retrieval_log.append({"channel": "author_saturation_error", "author_id": person["author_id"], "error": str(e)[:500]})
        if not new_any:
            break
        deduped, merges2 = dedupe([store[pid] for pid in retained])
        merges.extend(merges2)
        metrics = paper_graph_metrics(deduped, graph_edges_unique)
        indirect = indirect_support(seed_ids, graph_edges_unique)
        ranked = rank_papers(deduped, metrics, indirect, cfg, int(cfg["retrieval"].get("recent_year_start", 2024)))
        by_ranked = {p["paper_id"]: p for p in ranked}
        people_rows, pa_edges, co_g = build_people(ranked, set(by_ranked), cfg)

    state.update({
        "retained": retained,
        "merges": merges,
        "ranked": ranked,
        "metrics": metrics,
        "people_rows": people_rows,
        "pa_edges": pa_edges,
        "co_g": co_g,
    })
    _save_state(state_dir, "people", state)
    return state


def phase_enrichment(state_dir: Path) -> dict:
    state = _load_state(state_dir, "enrichment")
    cfg = state["cfg"]
    out = Path(state["out"])
    ranked = state["ranked"]
    people_rows = state["people_rows"]

    _progress("MODULAR 4/5 enrichment: Crossref + NIH + health/training branches")
    verification_rows = []
    crcfg = cfg.get("crossref") or {}
    if crcfg.get("enabled", False):
        cr = CrossrefClient(str(out / crcfg.get("cache_dir", ".cache/crossref")), crcfg.get("mailto", ""), float(crcfg.get("min_interval_seconds", 0.2)))
        total_ranked = len(ranked)
        for verify_idx, p in enumerate(ranked, start=1):
            if verify_idx == 1 or verify_idx % 100 == 0 or verify_idx == total_ranked:
                _progress(f"enrichment Crossref verification {verify_idx}/{total_ranked}")
            doi = normalize_doi(p.get("doi"))
            if not doi:
                verification_rows.append({"paper_id": p["paper_id"], "doi": "", "crossref_status": "not_checked_no_doi", "title_match": ""})
                continue
            try:
                msg, meta = cr.work(doi)
                cr_title = ((msg.get("title") or [""])[0] if isinstance(msg.get("title"), list) else msg.get("title", ""))
                title_match = normalize_title(cr_title) == normalize_title(p.get("title"))
                verification_rows.append({
                    "paper_id": p["paper_id"], "doi": doi, "crossref_status": "found",
                    "crossref_title": cr_title, "title_match": title_match,
                    "request_fingerprint": meta.get("request_fingerprint", ""),
                })
            except Exception as e:
                verification_rows.append({"paper_id": p["paper_id"], "doi": doi, "crossref_status": "error", "error": str(e)[:500]})

    funding = search_reporter(cfg.get("nih_reporter") or {})
    funding_people_rows = funding_people(funding)
    funding_by_name = {}
    for fr in funding_people_rows:
        funding_by_name.setdefault(fr["normalized_name"], []).append(fr)
    for person in people_rows:
        matches = funding_by_name.get(normalize_name(person["name"]), [])
        person["nih_project_count"] = len({m["project_num"] for m in matches if m["project_num"]})
        person["nih_project_numbers"] = ";".join(sorted({m["project_num"] for m in matches if m["project_num"]}))
        person["nih_project_titles"] = " | ".join(sorted({m["project_title"] for m in matches if m["project_title"]}))
        person["nih_public_health_relevance"] = " | ".join(sorted({m["public_health_relevance"] for m in matches if m["public_health_relevance"]}))

    health_rows = []
    for p in ranked:
        if p.get("health_hits"):
            health_rows.append({
                "paper_id": p["paper_id"], "title": p["title"], "year": p.get("year"),
                "doi": p.get("doi", ""), "health_terms": p.get("health_hits", ""),
                "scope_reasons": p.get("scope_reasons", ""), "tier": p.get("tier", ""),
            })

    training_rows = []
    for p in ranked:
        axes = set(p.get("query_axes") or set())
        if "people_development" not in axes and not p.get("people_development_hits"):
            continue
        training_rows.append({
            "paper_id": p["paper_id"], "title": p["title"], "year": p.get("year"),
            "doi": p.get("doi", ""), "people_development_terms": p.get("people_development_hits", ""),
            "scope_reasons": p.get("scope_reasons", ""), "tier": p.get("tier", ""),
            "authors": p.get("authors") or [],
        })

    state.update({
        "verification_rows": verification_rows,
        "funding": funding,
        "funding_people_rows": funding_people_rows,
        "people_rows": people_rows,
        "health_rows": health_rows,
        "training_rows": training_rows,
    })
    _save_state(state_dir, "enrichment", state)
    return state


def phase_finalize(state_dir: Path) -> dict:
    state = _load_state(state_dir, "finalize")
    cfg = state["cfg"]
    out = Path(state["out"])
    ranked = state["ranked"]
    people_rows = state["people_rows"]
    graph_edges_unique = state["graph_edges_unique"]
    co_g = state["co_g"]
    pa_edges = state["pa_edges"]
    metrics = state["metrics"]
    health_rows = state["health_rows"]
    training_rows = state["training_rows"]
    funding = state["funding"]
    funding_people_rows = state["funding_people_rows"]
    verification_rows = state["verification_rows"]
    store = state["store"]
    screening = state["screening"]
    merges = state["merges"]
    retrieval_log = state["retrieval_log"]

    _progress("MODULAR 5/5 finalize: graphs + tables + coverage + manifest")
    by_ranked = {p["paper_id"]: p for p in ranked}

    pg = nx.DiGraph()
    for p in ranked:
        pg.add_node(p["paper_id"], title=p.get("title", ""), year=p.get("year") or 0, tier=p.get("tier", ""))
    for e in graph_edges_unique:
        if e["source"] in pg and e["target"] in pg:
            pg.add_edge(e["source"], e["target"])
    nx.write_graphml(pg, out / "paper_graph.graphml")
    nx.write_graphml(co_g, out / "coauthor_graph.graphml")

    _write_csv(out / "papers_all.csv", store.values())
    _write_csv(out / "papers_retained.csv", ranked)
    _write_csv(out / "paper_graph_edges.csv", graph_edges_unique)
    _write_csv(out / "paper_metrics.csv", metrics)
    _write_csv(out / "screening_log.csv", screening)
    _write_csv(out / "dedupe_log.csv", merges)
    _write_csv(out / "people.csv", people_rows)
    _write_csv(out / "paper_author_edges.csv", pa_edges)
    co_edges = [{"author_1": a, "author_2": b, "weight": d.get("weight", 1)} for a, b, d in co_g.edges(data=True)]
    _write_csv(out / "coauthor_edges.csv", co_edges)
    _write_csv(out / "health_bridge.csv", health_rows)
    _write_csv(out / "training_outreach.csv", training_rows)
    _write_csv(out / "crossref_verification.csv", verification_rows)
    _write_jsonl(out / "retrieval_log.jsonl", retrieval_log)
    _write_jsonl(out / "funding_projects.jsonl", funding)
    _write_csv(out / "funding_people.csv", funding_people_rows)

    axis_counts = Counter()
    for p in ranked:
        for axis in p.get("query_axes") or set():
            axis_counts[axis] += 1
    coverage = {
        "retained_papers": len(ranked),
        "people": len(people_rows),
        "paper_edges": sum(1 for e in graph_edges_unique if e["source"] in by_ranked and e["target"] in by_ranked),
        "health_bridge_papers": len(health_rows),
        "training_outreach_papers": len(training_rows),
        "funding_projects": len([r for r in funding if not r.get("_error")]),
        "axis_counts": dict(sorted(axis_counts.items())),
        "tier_counts": dict(Counter(p["tier"] for p in ranked)),
        "retrieval_channel_counts": dict(Counter(x.get("channel", "") for x in retrieval_log)),
    }
    (out / "coverage_summary.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")

    ended = datetime.now(timezone.utc)
    output_files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "manifest.json")
    manifest = {
        "package_version": __version__,
        "started_utc": state["started"].isoformat(),
        "ended_utc": ended.isoformat(),
        "config_sha256": sha256_file(Path(state["cfg_path"])),
        "query_file_sha256": sha256_file(Path(state["query_path"])),
        "mode": cfg.get("mode"),
        "citation_hops": cfg["retrieval"].get("citation_hops", 1),
        "counts": coverage,
        "deviations": cfg.get("deviations") or {},
        "output_sha256": {p.name: sha256_file(p) for p in output_files},
        "secret_handling": "SEMANTIC_SCHOLAR_API_KEY read from environment only; never serialized.",
        "orchestration": "modular_checkpointed",
        "modular_phases": list(PHASES),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (state_dir / "05_finalize_summary.json").write_text(json.dumps({"phase": "finalize", "counts": coverage}, indent=2) + "\n", encoding="utf-8")
    _progress(f"modular run complete; retained_papers={coverage['retained_papers']} people={coverage['people']} paper_edges={coverage['paper_edges']}")
    return manifest


def run_phase(config_path: str, state_dir: str, phase: str) -> dict:
    if phase not in PHASES:
        raise ValueError(f"Unknown phase {phase!r}; expected one of {PHASES}")
    sd = Path(state_dir).resolve()
    if phase == "discovery":
        return phase_discovery(config_path, sd)
    if phase == "graph":
        return phase_graph(sd)
    if phase == "people":
        return phase_people(sd)
    if phase == "enrichment":
        return phase_enrichment(sd)
    return phase_finalize(sd)
