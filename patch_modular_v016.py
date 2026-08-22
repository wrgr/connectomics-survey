from pathlib import Path
import shutil

ROOT = Path("connectomics_deterministic_pipeline")
RUNTIME = Path("runtime")

copies = {
    RUNTIME / "modular.py": ROOT / "connectomics_pipeline" / "modular.py",
    RUNTIME / "run_pipeline_modular.py": ROOT / "run_pipeline_modular.py",
    RUNTIME / "test_modular_equivalence.py": ROOT / "tests" / "test_modular_equivalence.py",
}
for src, dst in copies.items():
    if not src.exists():
        raise RuntimeError(f"Missing modular runtime source: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

(ROOT / "connectomics_pipeline" / "__init__.py").write_text('__version__ = "0.1.6"\n', encoding="utf-8")
print("Applied checkpointed modular-run patch v0.1.6")
