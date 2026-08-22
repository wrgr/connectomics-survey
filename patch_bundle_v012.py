from pathlib import Path

ROOT = Path("connectomics_deterministic_pipeline")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected patch target not found in {path}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


client = ROOT / "connectomics_pipeline" / "client.py"

# Current Semantic Scholar paper response fields used by this pipeline.
# fieldsOfStudy is intentionally NOT requested: S2 documents s2FieldsOfStudy as its replacement.
replace_once(
    client,
    '''    @property\n    def paper_fields(self) -> str:\n        return ",".join([\n            "title","abstract","year","authors","venue","citationCount",\n            "externalIds","publicationTypes","publicationDate","url","fieldsOfStudy"\n        ])\n''',
    '''    @property\n    def paper_fields(self) -> str:\n        return ",".join([\n            "title","abstract","year","authors","venue","citationCount",\n            "externalIds","publicationTypes","publicationDate","url","s2FieldsOfStudy"\n        ])\n\n    @property\n    def citation_edge_fields(self) -> str:\n        # These belong to citation/reference edges, not the nested paper object.\n        return "contexts,intents,isInfluential"\n\n    @property\n    def citation_fields(self) -> str:\n        return f"{self.citation_edge_fields},{self.paper_fields}"\n''',
)

# Citation/reference endpoints must request edge metadata separately from paper metadata.
replace_once(
    client,
    '                params={"fields": self.paper_fields, "offset": offset, "limit": limit},\n',
    '                params={"fields": self.citation_fields, "offset": offset, "limit": limit},\n',
)

# Replace the small normalization module wholesale so S2 field-of-study objects are handled correctly.
(ROOT / "connectomics_pipeline" / "schema.py").write_text(
    '''from __future__ import annotations\nfrom .util import normalize_doi\n\n\ndef _normalize_s2_fields_of_study(p: dict) -> tuple[list[str], list[str]]:\n    \"\"\"Return ordered categories plus provenance strings.\n\n    Current Semantic Scholar s2FieldsOfStudy entries are objects with\n    category/source. A legacy string-list fallback is retained only so cached or\n    historical records remain readable.\n    \"\"\"\n    current = p.get("s2FieldsOfStudy") or []\n    categories: list[str] = []\n    provenance: list[str] = []\n    for item in current:\n        if isinstance(item, dict):\n            category = str(item.get("category") or "").strip()\n            source = str(item.get("source") or "").strip()\n        else:\n            category = str(item or "").strip()\n            source = ""\n        if category and category not in categories:\n            categories.append(category)\n        if category:\n            token = f"{category}|{source}" if source else category\n            if token not in provenance:\n                provenance.append(token)\n\n    if not categories:\n        for item in p.get("fieldsOfStudy") or []:\n            category = str(item or "").strip()\n            if category and category not in categories:\n                categories.append(category)\n            if category and category not in provenance:\n                provenance.append(category)\n    return categories, provenance\n\n\ndef s2_to_record(p: dict) -> dict:\n    ext = p.get("externalIds") or {}\n    authors = p.get("authors") or []\n    fos, fos_provenance = _normalize_s2_fields_of_study(p)\n    return {\n        "paper_id": p.get("paperId") or "",\n        "title": p.get("title") or "",\n        "abstract": p.get("abstract") or "",\n        "year": p.get("year"),\n        "venue": p.get("venue") or "",\n        "citation_count": p.get("citationCount") or 0,\n        "doi": normalize_doi(ext.get("DOI")),\n        "pmid": str(ext.get("PubMed") or ""),\n        "arxiv_id": str(ext.get("ArXiv") or ""),\n        "publication_types": ";".join(p.get("publicationTypes") or []),\n        "publication_date": p.get("publicationDate") or "",\n        "url": p.get("url") or "",\n        "fields_of_study": ";".join(fos),\n        "fields_of_study_provenance": ";".join(fos_provenance),\n        "authors": [\n            {"author_id": a.get("authorId") or "", "name": a.get("name") or "", "position": i}\n            for i, a in enumerate(authors)\n        ],\n    }\n''',
    encoding="utf-8",
)

# NetworkX PageRank uses SciPy in the installed NetworkX release.
requirements = ROOT / "requirements.txt"
req = requirements.read_text(encoding="utf-8")
if "scipy" not in req.lower():
    if not req.endswith("\n"):
        req += "\n"
    req += "scipy>=1.11\n"
    requirements.write_text(req, encoding="utf-8")

(ROOT / "connectomics_pipeline" / "__init__.py").write_text(
    '__version__ = "0.1.2"\n', encoding="utf-8"
)

(ROOT / "tests" / "test_s2_schema.py").write_text(
    '''from connectomics_pipeline.client import SemanticScholarClient\nfrom connectomics_pipeline.schema import s2_to_record\n\n\ndef bare_client():\n    return object.__new__(SemanticScholarClient)\n\n\ndef test_paper_field_contract():\n    fields = bare_client().paper_fields.split(",")\n    assert fields == [\n        "title", "abstract", "year", "authors", "venue", "citationCount",\n        "externalIds", "publicationTypes", "publicationDate", "url", "s2FieldsOfStudy",\n    ]\n    assert "fieldsOfStudy" not in fields\n\n\ndef test_citation_edge_field_contract():\n    client = bare_client()\n    edge_fields = client.citation_edge_fields.split(",")\n    assert edge_fields == ["contexts", "intents", "isInfluential"]\n    combined = client.citation_fields.split(",")\n    assert combined[:3] == edge_fields\n    assert "s2FieldsOfStudy" in combined\n\n\ndef test_bulk_search_uses_token_pagination_without_undocumented_limit():\n    client = bare_client()\n    seen = {}\n    def fake(method, url, params=None, body=None, headers=None):\n        seen.update(params or {})\n        return {"data": [], "token": None}, {}\n    client.request_json = fake\n    client._headers = {}\n    next(client.bulk_search("connectomics", max_pages=1))\n    assert seen["query"] == "connectomics"\n    assert "limit" not in seen\n    assert "token" not in seen\n\n\ndef test_schema_accepts_current_s2_fields_of_study_objects():\n    row = s2_to_record({\n        "paperId": "P1",\n        "title": "x",\n        "s2FieldsOfStudy": [\n            {"category": "Biology", "source": "s2-fos-model"},\n            {"category": "Computer Science", "source": "external"},\n        ],\n    })\n    assert row["fields_of_study"] == "Biology;Computer Science"\n    assert row["fields_of_study_provenance"] == "Biology|s2-fos-model;Computer Science|external"\n\n\ndef test_schema_keeps_legacy_fields_of_study_fallback():\n    row = s2_to_record({\n        "paperId": "P2",\n        "title": "x",\n        "fieldsOfStudy": ["Biology"],\n    })\n    assert row["fields_of_study"] == "Biology"\n    assert row["fields_of_study_provenance"] == "Biology"\n\n\ndef test_external_id_mapping_and_author_defaults():\n    row = s2_to_record({\n        "paperId": "P3",\n        "externalIds": {"DOI": "10.1000/XYZ", "PubMed": "12345", "ArXiv": "2501.01234"},\n        "authors": [{"authorId": "A1", "name": "Ada Example"}],\n    })\n    assert row["doi"] == "10.1000/xyz"\n    assert row["pmid"] == "12345"\n    assert row["arxiv_id"] == "2501.01234"\n    assert row["authors"] == [{"author_id": "A1", "name": "Ada Example", "position": 0}]\n''',
    encoding="utf-8",
)

print("Applied deterministic package compatibility patch v0.1.2")
