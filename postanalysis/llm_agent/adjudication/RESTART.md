# Adjudication hard reset (20260823T070628Z)

## Why

Stop all in-flight workers. Clear **every** prior adjudication artifact so the run uses
only the accurate full title/abstract process (no keyword-assisted shortcuts, no mixed
pilots, no stale leases).

## Cleared into `postanalysis/llm_agent/adjudication/_full_clear_20260823T070628Z`

- all `decisions/` (home batches + claim decisions + prior clear folders)
- all `queue/` (active claims, packs, released_archive)
- `wave_live.jsonl`, `pilot_live.jsonl`, pilot packs
- `cache/` if present

## Preserved (inputs of record)

- `manifest.json`, `criteria.md`, `prompts/*.jsonl`
- `../llm_screening_input.jsonl`

## Process of record

1. Claim via `analysis/adjudication_queue.py claim --agent <name> --size <N>`
2. Input = that claim's pack only (`queue/packs/<claim>.json`)
3. Full title + full abstract for every work; pack system/criteria verbatim
4. Labels: core_relevant | adjacent_relevant | role_bridge | out_of_scope | uncertain
5. Ambiguity → uncertain. No insufficient_abstract. No outside knowledge / heuristics
6. Write `decisions/claims/<claim>.json`, then `complete --claim-id ... --agent ... --decisions ...`
7. Append-only to `wave_live.jsonl`
8. After complete, claim next open pack until queue empty

Pack size is an orchestration knob; completeness via the queue is the requirement.
