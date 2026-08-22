from __future__ import annotations

import copy
from pathlib import Path

import yaml

from connectomics_pipeline import modular, pipeline


P1 = {
    "paperId": "P1",
    "title": "Electron microscopy connectome synaptic reconstruction",
    "abstract": "A dense connectome from electron microscopy with synaptic connectivity.",
    "year": 2024,
    "authors": [{"authorId": "A1", "name": "Ada Example"}],
    "venue": "X",
    "citationCount": 10,
    "externalIds": {"DOI": "10.1/p1"},
    "publicationTypes": ["JournalArticle"],
    "publicationDate": "2024-01-01",
    "url": "",
    "s2FieldsOfStudy": [{"category": "Biology", "source": "test"}],
}
P2 = {
    "paperId": "P2",
    "title": "Synaptic connectome from electron microscopy",
    "abstract": "Dense connectome and synapse reconstruction using electron microscopy.",
    "year": 2023,
    "authors": [{"authorId": "A2", "name": "Ben Example"}],
    "venue": "Y",
    "citationCount": 5,
    "externalIds": {"DOI": "10.1/p2"},
    "publicationTypes": ["JournalArticle"],
    "publicationDate": "2023-01-01",
    "url": "",
    "s2FieldsOfStudy": [{"category": "Biology", "source": "test"}],
}


class FakeS2:
    def __init__(self, *args, **kwargs):
        pass

    def bulk_search(self, query, max_pages=None):
        yield [copy.deepcopy(P1)], {"request_fingerprint": "bulk"}

    def citation_neighbors(self, paper_id, direction, max_pages=None, limit=1000):
        if paper_id == "P1" and direction == "references":
            yield [copy.deepcopy(P2)], {"request_fingerprint": "ref"}

    def author_papers(self, author_id, max_papers=1000):
        if False:
            yield [], {}

    def paper_by_doi(self, doi):
        raise RuntimeError("unused in fresh-mode fixture")

    def title_match(self, title):
        raise RuntimeError("unused in fresh-mode fixture")


def _fixture_config(tmp_path: Path, outdir: Path, name: str) -> Path:
    cfg = yaml.safe_load(Path("config.example.yaml").read_text(encoding="utf-8"))
    cfg["outdir"] = str(outdir)
    cfg["crossref"]["enabled"] = False
    cfg["nih_reporter"]["enabled"] = False
    cfg["semantic_scholar"]["max_bulk_pages_per_query"] = 1
    cfg["semantic_scholar"]["max_citation_pages_per_paper"] = 1
    cfg["retrieval"]["author_saturation_passes"] = 0
    cfg["people"]["author_saturation_min_retained_papers"] = 99
    cfg["retrieval"]["query_file"] = "q.yaml"

    (tmp_path / "q.yaml").write_text(
        yaml.safe_dump({"queries": [{"id": "q1", "axis": "direct_connectomics", "query": "connectome electron microscopy"}]}, sort_keys=False),
        encoding="utf-8",
    )
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


def test_modular_runner_matches_monolith_on_synthetic_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "SemanticScholarClient", FakeS2)
    monkeypatch.setattr(modular, "SemanticScholarClient", FakeS2)

    mono_out = tmp_path / "mono"
    modular_out = tmp_path / "modular"
    state_dir = tmp_path / "state"
    mono_cfg = _fixture_config(tmp_path, mono_out, "mono")
    modular_cfg = _fixture_config(tmp_path, modular_out, "modular")

    mono_manifest = pipeline.run(str(mono_cfg))
    result = None
    for phase in modular.PHASES:
        result = modular.run_phase(str(modular_cfg), str(state_dir), phase)

    assert result is not None
    assert mono_manifest["counts"] == result["counts"]

    excluded = {"manifest.json"}
    mono_files = {p.name: p.read_bytes() for p in mono_out.iterdir() if p.is_file() and p.name not in excluded}
    modular_files = {p.name: p.read_bytes() for p in modular_out.iterdir() if p.is_file() and p.name not in excluded}
    assert mono_files.keys() == modular_files.keys()
    assert mono_files == modular_files


def test_checkpoint_has_no_api_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "secret-value-that-must-not-be-pickled")
    monkeypatch.setattr(modular, "SemanticScholarClient", FakeS2)
    out = tmp_path / "out"
    cfg = _fixture_config(tmp_path, out, "secret")
    state_dir = tmp_path / "state"
    modular.run_phase(str(cfg), str(state_dir), "discovery")
    blob = (state_dir / "01_discovery.pkl").read_bytes()
    assert b"secret-value-that-must-not-be-pickled" not in blob
