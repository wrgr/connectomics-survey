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

replace_once(client, "import json, os\n", "import json, os, time\n")

replace_once(
    client,
    '''    def request_json(self, method: str, url: str, params=None, body=None, headers=None) -> tuple[dict, dict]:\n        fp = self._fingerprint(method, url, params, body)\n        cache_path = self.cache_dir / f"{fp}.json"\n        meta = {"request_fingerprint": fp, "url": url, "method": method.upper(), "cached": False}\n        if cache_path.exists():\n            meta["cached"] = True\n            return json.loads(cache_path.read_text(encoding="utf-8")), meta\n\n        self.rate.wait()\n        r = self.session.request(\n            method.upper(), url, params=params, json=body, headers=headers or {},\n            timeout=self.timeout_seconds,\n        )\n        meta["status_code"] = r.status_code\n        if r.status_code >= 400:\n            raise RuntimeError(f"HTTP {r.status_code} for {url}: {r.text[:500]}")\n        data = r.json()\n        cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")\n        return data, meta\n''',
    '''    def request_json(self, method: str, url: str, params=None, body=None, headers=None) -> tuple[dict, dict]:\n        fp = self._fingerprint(method, url, params, body)\n        cache_path = self.cache_dir / f"{fp}.json"\n        meta = {\n            "request_fingerprint": fp, "url": url, "method": method.upper(),\n            "cached": False, "attempts": 0, "retry_delays": [],\n        }\n        if cache_path.exists():\n            meta["cached"] = True\n            return json.loads(cache_path.read_text(encoding="utf-8")), meta\n\n        retryable_statuses = {429, 500, 502, 503, 504}\n        max_attempts = 6\n        last_error = None\n\n        for attempt in range(max_attempts):\n            self.rate.wait()\n            meta["attempts"] = attempt + 1\n            try:\n                r = self.session.request(\n                    method.upper(), url, params=params, json=body, headers=headers or {},\n                    timeout=self.timeout_seconds,\n                )\n            except requests.RequestException as exc:\n                last_error = exc\n                if attempt + 1 >= max_attempts:\n                    raise RuntimeError(\n                        f"Request failed after {max_attempts} attempts for {url}: {exc}"\n                    ) from exc\n                delay = min(32.0, float(2 ** (attempt + 1)))\n                meta["retry_delays"].append(delay)\n                time.sleep(delay)\n                continue\n\n            meta["status_code"] = r.status_code\n            if r.status_code < 400:\n                data = r.json()\n                cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")\n                return data, meta\n\n            if r.status_code not in retryable_statuses or attempt + 1 >= max_attempts:\n                raise RuntimeError(f"HTTP {r.status_code} for {url}: {r.text[:500]}")\n\n            retry_after = (r.headers.get("Retry-After") or "").strip()\n            try:\n                delay = float(retry_after) if retry_after else float(2 ** (attempt + 1))\n            except ValueError:\n                delay = float(2 ** (attempt + 1))\n            delay = max(self.rate.min_interval, min(60.0, delay))\n            meta["retry_delays"].append(delay)\n            time.sleep(delay)\n\n        raise RuntimeError(f"Request failed for {url}: {last_error or 'unknown error'}")\n''',
)

(ROOT / "connectomics_pipeline" / "__init__.py").write_text(
    '__version__ = "0.1.3"\n', encoding="utf-8"
)

(ROOT / "tests" / "test_http_retry.py").write_text(
    '''import json\n\nimport pytest\n\nfrom connectomics_pipeline.client import CachedJSONClient\n\n\nclass FakeResponse:\n    def __init__(self, status_code, payload=None, text="", headers=None):\n        self.status_code = status_code\n        self._payload = payload if payload is not None else {}\n        self.text = text or json.dumps(self._payload)\n        self.headers = headers or {}\n\n    def json(self):\n        return self._payload\n\n\nclass FakeSession:\n    def __init__(self, responses):\n        self.responses = list(responses)\n        self.calls = 0\n\n    def request(self, *args, **kwargs):\n        self.calls += 1\n        return self.responses.pop(0)\n\n\ndef test_retries_429_then_succeeds(tmp_path, monkeypatch):\n    client = CachedJSONClient(str(tmp_path), min_interval_seconds=0, timeout_seconds=1)\n    client.session = FakeSession([\n        FakeResponse(429, text="too many", headers={"Retry-After": "0"}),\n        FakeResponse(200, payload={"ok": True}),\n    ])\n    monkeypatch.setattr("connectomics_pipeline.client.time.sleep", lambda _: None)\n    data, meta = client.request_json("GET", "https://example.test/x")\n    assert data == {"ok": True}\n    assert client.session.calls == 2\n    assert meta["attempts"] == 2\n    assert meta["status_code"] == 200\n\n\ndef test_nonretryable_400_fails_immediately(tmp_path, monkeypatch):\n    client = CachedJSONClient(str(tmp_path), min_interval_seconds=0, timeout_seconds=1)\n    client.session = FakeSession([FakeResponse(400, text="bad request")])\n    monkeypatch.setattr("connectomics_pipeline.client.time.sleep", lambda _: None)\n    with pytest.raises(RuntimeError, match="HTTP 400"):\n        client.request_json("GET", "https://example.test/x")\n    assert client.session.calls == 1\n\n\ndef test_429_without_retry_after_uses_exponential_delay(tmp_path, monkeypatch):\n    client = CachedJSONClient(str(tmp_path), min_interval_seconds=0, timeout_seconds=1)\n    client.session = FakeSession([\n        FakeResponse(429, text="too many"),\n        FakeResponse(200, payload={"ok": True}),\n    ])\n    sleeps = []\n    monkeypatch.setattr("connectomics_pipeline.client.time.sleep", sleeps.append)\n    data, meta = client.request_json("GET", "https://example.test/x")\n    assert data == {"ok": True}\n    assert sleeps == [2.0]\n    assert meta["retry_delays"] == [2.0]\n''',
    encoding="utf-8",
)

print("Applied deterministic HTTP retry/backoff patch v0.1.3")
