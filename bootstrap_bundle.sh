#!/usr/bin/env bash
set -euo pipefail

EXPECTED_SHA256="c12601d1f4b1ae3272d8201501ecefe4a8fd770eec1afbdcdf945688d0a839d3"
WORKDIR=".codex_handoff"
ZIP="$WORKDIR/connectomics_deterministic_pipeline_v0.1.1.zip"

mkdir -p "$WORKDIR"

cat \
  handoff/connectomics_pipeline_v0.1.1.zip.b64.part01 \
  handoff/connectomics_pipeline_v0.1.1.zip.b64.part02 \
  handoff/connectomics_pipeline_v0.1.1.zip.b64.part03 \
  handoff/connectomics_pipeline_v0.1.1.zip.b64.part04 \
  handoff/connectomics_pipeline_v0.1.1.zip.b64.part05a \
  handoff/connectomics_pipeline_v0.1.1.zip.b64.part05b1 \
  handoff/connectomics_pipeline_v0.1.1.zip.b64.part05b2 \
  | base64 --decode > "$ZIP"

ACTUAL_SHA256="$(sha256sum "$ZIP" | awk '{print $1}')"
if [[ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]]; then
  echo "ERROR: bundle SHA-256 mismatch" >&2
  echo "expected: $EXPECTED_SHA256" >&2
  echo "actual:   $ACTUAL_SHA256" >&2
  exit 1
fi

rm -rf connectomics_deterministic_pipeline
unzip -q "$ZIP"

# Apply deterministic compatibility fixes that are versioned in this repository.
python patch_bundle_v012.py
python patch_retry_v013.py
python patch_title_match_v014.py

# IA-002: observability only. Adds progress prints/tests without changing
# scientific search, screening, ranking, or stopping logic.
python patch_observability_v015.py

# IA-003: alternate checkpointed orchestration. The reference monolithic runner
# remains present and unchanged; the modular runner uses the same scientific rules.
python patch_modular_v016.py

# Rebuild package-verification metadata after the package reaches its final
# patched state. Do not inherit stale v0.1.1 compile/test claims.
python regenerate_package_manifest.py

echo "Verified and unpacked: connectomics_deterministic_pipeline/"
echo "Base ZIP SHA-256: $ACTUAL_SHA256"
echo "Applied repository patches through: v0.1.6"
echo "Regenerated package manifest for patched state"
echo "Available runners: run_pipeline.py (reference) and run_pipeline_modular.py (checkpointed)"
echo "Next: read CODEX_TASK.md and connectomics_deterministic_pipeline/README.md"
