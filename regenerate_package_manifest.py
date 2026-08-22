from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path("connectomics_deterministic_pipeline")
MANIFEST = ROOT / "PACKAGE_MANIFEST.json"
BASE_ZIP_SHA256 = "c12601d1f4b1ae3272d8201501ecefe4a8fd770eec1afbdcdf945688d0a839d3"
PATCH_CHAIN = [
    "patch_bundle_v012.py",
    "patch_retry_v013.py",
    "patch_title_match_v014.py",
    "patch_observability_v015.py",
    "patch_modular_v016.py",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def include_file(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if rel.as_posix() == "PACKAGE_MANIFEST.json":
        return False
    if any(part in {".pytest_cache", "__pycache__"} for part in rel.parts):
        return False
    if path.suffix in {".pyc", ".pyo"}:
        return False
    return path.is_file()


def package_version() -> str:
    text = (ROOT / "connectomics_pipeline" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    if not match:
        raise RuntimeError("Could not determine package version")
    return match.group(1)


files = []
for path in sorted((p for p in ROOT.rglob("*") if include_file(p)), key=lambda p: p.relative_to(ROOT).as_posix()):
    rel = path.relative_to(ROOT).as_posix()
    files.append({
        "path": rel,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    })

manifest = {
    "manifest_schema_version": 2,
    "package_version": package_version(),
    "source_bundle": {
        "version": "0.1.1",
        "sha256": BASE_ZIP_SHA256,
    },
    "applied_patch_chain": PATCH_CHAIN,
    "files": files,
    "compile_ok": None,
    "tests_returncode": None,
    "tests_stdout": "",
    "verification_status": "not_run_at_manifest_generation",
    "verification_note": (
        "This manifest is regenerated deterministically after compatibility patches. "
        "It does not inherit compile/test claims from the v0.1.1 source bundle; "
        "CI workflow results are the authoritative execution record."
    ),
    "semantic_note": "people_development = training/outreach/workforce/capacity; contributor map is separate",
}

MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
print(f"Regenerated {MANIFEST} for package v{manifest['package_version']} with {len(files)} files")
