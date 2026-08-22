# IA-002 — Observability-only workflow amendment

**Logged:** 2026-08-22 (America/New_York), after cancellation of a test full run and before the next scientific run.

## Classification

Operational/reproducibility amendment only. IA-002 does **not** change the preregistered scientific protocol frozen at commit `38b01f40f8a5727fe51420f8c1febd2a1d5a757c`.

It does not alter:

- query families or lexical search strings;
- Semantic Scholar retrieval endpoints or requested scientific fields;
- inclusion/exclusion or scope-screening rules;
- citation expansion depth or seed logic;
- deduplication;
- graph construction, metrics, or ranking/core assignment;
- contributor/people derivation;
- NIH, health, or training/outreach scientific logic;
- stopping or saturation criteria.

## Changes

### Pipeline progress output

The runtime package is labeled v0.1.5 and emits timestamped, flushed progress messages at the existing 16 deterministic stage boundaries. It also reports bounded loop progress for:

- every lexical query, including query identifier and axis;
- citation expansion every 25 seeds plus first/last, including retrieved-paper and edge counts;
- author saturation every 25 candidate authors plus first/last;
- Crossref verification every 100 papers plus first/last;
- final retained-paper, people, and paper-edge counts.

These messages are observational only; they do not feed back into any scientific decision.

### GitHub Actions runtime visibility

The existing `Full deterministic connectomics run` workflow now:

- tees pipeline stdout/stderr to `run_observability/full_run_stdout.log`;
- emits a heartbeat every 60 seconds with elapsed time, cached-response count, output-file count/bytes, and the most recent pipeline line;
- writes the final heartbeat and pipeline tail to the GitHub Actions step summary;
- uploads observability logs together with outputs even after failure.

## Provenance

The v0.1.5 observability patch is added to the deterministic bootstrap patch chain and therefore appears in the regenerated package manifest. The underlying preregistered scientific implementation remains the PR #4 freeze; v0.1.5 is an operational wrapper/diagnostic revision.
