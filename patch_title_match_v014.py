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

replace_once(
    client,
    '''    def title_match(self, title: str):\n        data, meta = self.request_json(\n            "GET", f"{self.BASE}/paper/search/match",\n            params={"query": title, "fields": self.paper_fields}, headers=self._headers\n        )\n        return data, meta\n''',
    '''    def title_match(self, title: str):\n        data, meta = self.request_json(\n            "GET", f"{self.BASE}/paper/search/match",\n            params={"query": title, "fields": self.paper_fields}, headers=self._headers\n        )\n        # Current Semantic Scholar title search wraps the single best match in\n        # a top-level ``data`` list. Keep compatibility with a direct paper\n        # object as well, so cached historical responses remain readable.\n        if isinstance(data, dict) and data.get("paperId"):\n            return data, meta\n        rows = data.get("data") if isinstance(data, dict) else None\n        if isinstance(rows, list) and rows and isinstance(rows[0], dict):\n            return rows[0], meta\n        return {}, meta\n''',
)

(ROOT / "connectomics_pipeline" / "__init__.py").write_text(
    '__version__ = "0.1.4"\n', encoding="utf-8"
)

(ROOT / "tests" / "test_title_match.py").write_text(
    '''from connectomics_pipeline.client import SemanticScholarClient\n\n\ndef bare_client():\n    client = object.__new__(SemanticScholarClient)\n    client._headers = {"x-api-key": "not-a-real-key"}\n    return client\n\n\ndef test_title_match_unwraps_current_data_array():\n    client = bare_client()\n    client.request_json = lambda *args, **kwargs: (\n        {"data": [{"paperId": "P1", "title": "Matched", "matchScore": 1.0}]},\n        {"status_code": 200},\n    )\n    paper, meta = client.title_match("Matched")\n    assert paper["paperId"] == "P1"\n    assert paper["title"] == "Matched"\n    assert meta["status_code"] == 200\n\n\ndef test_title_match_accepts_direct_paper_shape_for_compatibility():\n    client = bare_client()\n    client.request_json = lambda *args, **kwargs: (\n        {"paperId": "P2", "title": "Matched"},\n        {"status_code": 200},\n    )\n    paper, _ = client.title_match("Matched")\n    assert paper["paperId"] == "P2"\n''',
    encoding="utf-8",
)

print("Applied Semantic Scholar title-match response patch v0.1.4")
