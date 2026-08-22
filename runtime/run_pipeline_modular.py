from __future__ import annotations

import argparse
import json

from connectomics_pipeline.modular import PHASES, _state_summary, run_phase


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Checkpointed modular runner for the deterministic connectomics pipeline")
    ap.add_argument("--config", required=True)
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--phase", required=True, choices=PHASES)
    args = ap.parse_args()

    result = run_phase(args.config, args.state_dir, args.phase)
    if args.phase == "finalize":
        print(json.dumps(result.get("counts", {}), indent=2), flush=True)
    else:
        print(json.dumps(_state_summary(result), indent=2), flush=True)
