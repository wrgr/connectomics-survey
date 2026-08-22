from pathlib import Path

ROOT = Path("connectomics_deterministic_pipeline")
PIPELINE = ROOT / "connectomics_pipeline" / "pipeline.py"


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Expected patch target not found: {old!r}")
    return text.replace(old, new, 1)


text = PIPELINE.read_text(encoding="utf-8")

text = replace_once(
    text,
    "from .util import normalize_doi, normalize_title, sha256_file, stable_json\n\n",
    "from .util import normalize_doi, normalize_title, sha256_file, stable_json\n\n"
    "def _progress(message: str):\n"
    "    ts = datetime.now(timezone.utc).strftime(\"%Y-%m-%dT%H:%M:%SZ\")\n"
    "    print(f\"[{ts}] {message}\", flush=True)\n\n",
)

text = replace_once(
    text,
    '    out = Path(cfg["outdir"]).resolve()\n    out.mkdir(parents=True, exist_ok=True)\n',
    '    out = Path(cfg["outdir"]).resolve()\n    out.mkdir(parents=True, exist_ok=True)\n'
    '    _progress(f"run started; mode={cfg.get(\'mode\')} outdir={out}")\n',
)

stage_replacements = [
    ('    # 1. Optional locked seeds.\n', '    # 1. Optional locked seeds.\n    _progress("stage 1/16: optional locked seeds")\n'),
    ('    # 2. Multi-axis lexical search.\n', '    # 2. Multi-axis lexical search.\n    _progress(f"stage 2/16: lexical retrieval across {len(queries)} queries")\n'),
    ('    # 3. Deterministic lexical scope screen.\n', '    _progress(f"lexical retrieval complete; unique retrieved papers={len(store)}")\n    # 3. Deterministic lexical scope screen.\n    _progress("stage 3/16: lexical scope screening")\n'),
    ('    # 4. One-hop citations/references from accepted seeds.\n', '    _progress(f"lexical screening complete; retained lexical papers={len(lexical_retained)}")\n    # 4. One-hop citations/references from accepted seeds.\n    _progress(f"stage 4/16: one-hop citation expansion from {len(seed_ids)} seeds")\n'),
    ('    # 5. Scope-screen one-hop candidates.\n', '    _progress(f"citation expansion retrieval complete; total retrieved papers={len(store)} raw_edges={len(graph_edges)}")\n    # 5. Scope-screen one-hop candidates.\n    _progress("stage 5/16: scope screen one-hop candidates")\n'),
    ('    # 6. Deduplicate canonical scientific objects.\n', '    _progress(f"one-hop screening complete; retained papers pre-dedupe={len(retained)}")\n    # 6. Deduplicate canonical scientific objects.\n    _progress("stage 6/16: deduplicate retained papers")\n'),
    ('    # 7. Graph metrics + transparent ranking.\n', '    _progress(f"dedupe complete; retained deduped papers={len(retained)} merges={len(merges)}")\n    # 7. Graph metrics + transparent ranking.\n    _progress("stage 7/16: graph metrics and transparent ranking")\n'),
    ('    # 8. People map before author saturation.\n', '    _progress(f"ranking complete; ranked papers={len(ranked)}")\n    # 8. People map before author saturation.\n    _progress("stage 8/16: initial people map")\n'),
    ('    # 9. Deterministic author saturation.\n', '    _progress(f"initial people map complete; people={len(people_rows)}")\n    # 9. Deterministic author saturation.\n    _progress("stage 9/16: deterministic author saturation")\n'),
    ('    # 10. Crossref verification.\n', '    _progress(f"author saturation complete; retained papers={len(retained)} people={len(people_rows)}")\n    # 10. Crossref verification.\n    _progress("stage 10/16: Crossref verification")\n'),
    ('    # 11. NIH funding enrichment and deterministic people merge.\n', '    _progress(f"Crossref verification complete; rows={len(verification_rows)}")\n    # 11. NIH funding enrichment and deterministic people merge.\n    _progress("stage 11/16: NIH funding enrichment and people merge")\n'),
    ('    # 12. Health bridge: exact matched terms.\n', '    _progress(f"funding enrichment complete; projects={len(funding)} funding_people={len(funding_people_rows)}")\n    # 12. Health bridge: exact matched terms.\n    _progress("stage 12/16: health and training/outreach bridge outputs")\n'),
    ('    # 13. Write graphs.\n', '    _progress(f"bridge outputs prepared; health={len(health_rows)} training_outreach={len(training_rows)}")\n    # 13. Write graphs.\n    _progress("stage 13/16: write graph files")\n'),
    ('    # 14. Write tables.\n', '    _progress("graph files written")\n    # 14. Write tables.\n    _progress("stage 14/16: write tables and retrieval logs")\n'),
    ('    # 15. Coverage diagnostics.\n', '    _progress("tables and logs written")\n    # 15. Coverage diagnostics.\n    _progress("stage 15/16: coverage diagnostics")\n'),
    ('    # 16. Hash manifest.\n', '    _progress("coverage summary written")\n    # 16. Hash manifest.\n    _progress("stage 16/16: hash output manifest")\n'),
]
for old, new in stage_replacements:
    text = replace_once(text, old, new)

text = replace_once(
    text,
    '    for q in queries:\n',
    '    for q_idx, q in enumerate(queries, start=1):\n'
    '        _progress(f"lexical query {q_idx}/{len(queries)}: {q[\'id\']} axis={q[\'axis\']}")\n',
)

text = replace_once(
    text,
    '    for sid in sorted(seed_ids):\n',
    '    seed_id_list = sorted(seed_ids)\n'
    '    for seed_idx, sid in enumerate(seed_id_list, start=1):\n'
    '        if seed_idx == 1 or seed_idx % 25 == 0 or seed_idx == len(seed_id_list):\n'
    '            _progress(f"citation expansion seed {seed_idx}/{len(seed_id_list)}: {sid}; retrieved={len(store)} edges={len(graph_edges)}")\n',
)

text = replace_once(
    text,
    '        for person in sorted(candidates, key=lambda r:r["author_id"]):\n',
    '        candidate_list = sorted(candidates, key=lambda r:r["author_id"])\n'
    '        _progress(f"author saturation pass {pass_i+1}/{passes}; candidates={len(candidate_list)}")\n'
    '        for cand_idx, person in enumerate(candidate_list, start=1):\n'
    '            if cand_idx == 1 or cand_idx % 25 == 0 or cand_idx == len(candidate_list):\n'
    '                _progress(f"author saturation candidate {cand_idx}/{len(candidate_list)}: {person[\'name\']} ({person[\'author_id\']}); retained={len(retained)}")\n',
)

text = replace_once(
    text,
    '        for p in ranked:\n            doi = normalize_doi(p.get("doi"))\n',
    '        total_ranked = len(ranked)\n'
    '        for verify_idx, p in enumerate(ranked, start=1):\n'
    '            if verify_idx == 1 or verify_idx % 100 == 0 or verify_idx == total_ranked:\n'
    '                _progress(f"Crossref verification {verify_idx}/{total_ranked}")\n'
    '            doi = normalize_doi(p.get("doi"))\n',
)

text = replace_once(
    text,
    '    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")\n    return manifest\n',
    '    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")\n'
    '    _progress(f"run complete; retained_papers={coverage[\'retained_papers\']} people={coverage[\'people\']} paper_edges={coverage[\'paper_edges\']}")\n'
    '    return manifest\n',
)

PIPELINE.write_text(text, encoding="utf-8")
(ROOT / "connectomics_pipeline" / "__init__.py").write_text('__version__ = "0.1.5"\n', encoding="utf-8")

(ROOT / "tests" / "test_observability.py").write_text(
    '''from pathlib import Path\n\n\ndef test_observability_patch_is_logging_only():\n    text = Path("connectomics_pipeline/pipeline.py").read_text(encoding="utf-8")\n    assert "stage 2/16: lexical retrieval" in text\n    assert "citation expansion seed" in text\n    assert "author saturation candidate" in text\n    assert "Crossref verification" in text\n    assert "run complete; retained_papers=" in text\n\n\ndef test_progress_prints_are_flushed():\n    text = Path("connectomics_pipeline/pipeline.py").read_text(encoding="utf-8")\n    assert "print(f\\\"[{ts}] {message}\\\", flush=True)" in text\n''',
    encoding="utf-8",
)

print("Applied observability-only patch v0.1.5")
