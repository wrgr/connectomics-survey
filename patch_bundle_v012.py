from pathlib import Path

ROOT = Path("connectomics_deterministic_pipeline")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected patch target not found in {path}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Semantic Scholar's current bulk-paper response field is s2FieldsOfStudy.
# fieldsOfStudy remains a query FILTER parameter, so confusing the two yields a bad request.
replace_once(
    ROOT / "connectomics_pipeline" / "client.py",
    '"externalIds","publicationTypes","publicationDate","url","fieldsOfStudy"',
    '"externalIds","publicationTypes","publicationDate","url","s2FieldsOfStudy"',
)

# Normalize current S2 output to our stable internal schema while retaining a legacy fallback.
replace_once(
    ROOT / "connectomics_pipeline" / "schema.py",
    '"fields_of_study": ";".join(p.get("fieldsOfStudy") or []),',
    '"fields_of_study": ";".join(p.get("s2FieldsOfStudy") or p.get("fieldsOfStudy") or []),',
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
    '''from connectomics_pipeline.client import SemanticScholarClient\nfrom connectomics_pipeline.schema import s2_to_record\n\n\ndef test_bulk_fields_use_current_s2_field_name():\n    client = object.__new__(SemanticScholarClient)\n    fields = client.paper_fields.split(",")\n    assert "s2FieldsOfStudy" in fields\n    assert "fieldsOfStudy" not in fields\n\n\ndef test_schema_accepts_current_s2_fields_of_study():\n    row = s2_to_record({\n        "paperId": "P1",\n        "title": "x",\n        "s2FieldsOfStudy": ["Biology", "Computer Science"],\n    })\n    assert row["fields_of_study"] == "Biology;Computer Science"\n\n\ndef test_schema_keeps_legacy_fields_of_study_fallback():\n    row = s2_to_record({\n        "paperId": "P2",\n        "title": "x",\n        "fieldsOfStudy": ["Biology"],\n    })\n    assert row["fields_of_study"] == "Biology"\n''',
    encoding="utf-8",
)

print("Applied deterministic package compatibility patch v0.1.2")
