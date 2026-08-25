# IA-007-v3 full agent adjudication

Prompt profile: `IA-007-v3-work-level` (strict core, fair placement ladder)

**Queue is complete.** Ingest finished 2026-08-24: **4,136 / 4,136** screened, **0** undecided (`run_manifest.json`, `llm_relevance_summary.json`). Agent batch JSON under `adjudication/decisions/` is frozen. Later membership changes are IA-014 overlays, not re-adjudication.

Criteria: `postanalysis/llm_agent_v3/adjudication/criteria.md` and `docs/IA-007-v3-screening-criteria-draft.md` (accepted; filename retained). Provenance index: `docs/IA-014-post-v3-overlays-and-decision-provenance.md`.

## Ingest (already run)

```bash
python analysis/llm_relevance_screen.py \
  --works-csv postanalysis/enriched/canonical_works_enriched.csv \
  --out postanalysis/llm_agent_v3 \
  --prompt-version v3 \
  --ingest-decisions postanalysis/llm_agent_v3/adjudication/decisions \
  --adjudicator agent:cursor/claude-opus-5-thinking \
  --require-complete
```

## Compare v2 vs v3

```bash
python analysis/compare_v2_v3_quick.py
```

## Rebuild derived views after overlay CSV edits

Human overlay and seeds are applied at corpus-build time. After editing those CSVs, rebuild citation roles / graph views rather than editing agent JSON.

## Historical queue commands (do not re-open a completed ingest)

```bash
python analysis/adjudication_queue.py --root postanalysis/llm_agent_v3/adjudication status
```
