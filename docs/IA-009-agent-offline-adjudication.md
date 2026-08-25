# IA-009 — Offline agent adjudication of the IA-007 screen

## Status

Derived post-processing extension of IA-007. It adds a second *execution path* for the
same screen and changes no criteria, no prompt text, no decision vocabulary, and no
downstream output schema beyond three additive provenance columns. It does not alter the
preregistered retrieval corpus, original `keep` values, IA-004 core labels, IA-006 bridge
labels, or IA-008 work/version links.

IA-009 exists because this repository has no `LLM_API_KEY` configured, so the IA-007 API
path cannot execute. Rather than leave the 4,136-work screen unrun, the screen is
adjudicated offline by a reasoning agent working directly over the exported per-work
prompts, recorded under an agent model identifier, and structured so that a conventional
API run can be executed later and compared against it with
`analysis/compare_screening_runs.py`.

## Rationale, and what this design does not buy

IA-007 already commits to LLM screening as a *high-sensitivity first pass under later human
oversight*, not as a gold standard, citing Homiar A et al. (*Development and evaluation of
prompts for a large language model to screen titles and abstracts in a living systematic
review.* BMJ Mental Health. 2025;28:e301762), Matsui K et al. (*Human-Comparable Sensitivity
of Large Language Models in Identifying Eligible Studies Through Title and Abstract
Screening.* J Med Internet Res. 2024;26:e52758), and Janoudi G et al. (*Validating Loon Lens
1.0 for Autonomous Abstract Screening and Confidence-Guided Human-in-the-Loop Workflows in
Systematic Reviews.* Value in Health. 2025;28(11):1630-1636). IA-009 inherits that framing
unchanged: it produces provisional labels and a human-review queue, and it mutates no
scientific status.

Two independent lines of evidence make an unrun screen the worse option than an
imperfectly-controlled screen. First, human abstract screening itself has a measurable
error rate: Wang Z, Nayfeh T, Tetzlaff J, O'Blenis P, Murad MH. *Error rates of human
reviewers during abstract screening in systematic reviews.* PLOS ONE. 2020;15(1):e0227742.
doi:10.1371/journal.pone.0227742 — across 329,332 dual-independent screening decisions by
86 reviewers, the combined false-inclusion/false-exclusion rate at abstract screening was
10.76% (95% CI 7.43–14.09), varying 5.76–21.11% by clinical area, and the authors
explicitly conclude that the human gold standard is not perfect. That is also why dual
independent screening with third-reviewer arbitration is the standard recommendation
(Cochrane Handbook for Systematic Reviews of Interventions v6, study-selection guidance;
PRISMA 2020 reporting of the screening procedure). Second, the LLM
screening literature above reports usable sensitivity precisely when uncertainty is scored
and audited rather than suppressed. Both arguments are about *process*, and the process
below is preserved exactly.

What IA-009 does **not** buy, stated plainly:

- **It is not a controlled single-model API run.** There is no temperature setting, no
  pinned model snapshot, no `response_format` enforcement at the transport layer, no
  per-request seed, and no vendor-side determinism guarantee. Re-running the same batch
  with the same prompt may produce different labels, and the run is not
  bit-reproducible in the sense the API path aspires to.
- **Confidence is self-reported, not calibrated.** It is usable for triage ordering (which
  is all IA-007 uses it for) and must not be reported as a probability.
- **Context hygiene is mitigated, not guaranteed.** An adjudicating agent operates inside a
  session that may have seen repository context. The batching rules below reduce leakage;
  they cannot prove its absence the way a stateless HTTP call can.
- **Agreement with a later API run is not accuracy.** Two automated screeners agreeing tells
  you the criteria are unambiguous on those works. It says nothing about whether either
  matches human judgment. Only the IA-007 human audit can speak to that.
- **The overlap set measures internal consistency only.** It is a floor on this run's noise,
  not a correction applied to it.

What it does buy: a complete, auditable, schema-identical first pass over all 4,136 works
now; an explicit disagreement queue for humans; and a directly comparable baseline for the
API run when a key becomes available.

## Mechanism

### Offline adjudication mode in `analysis/llm_relevance_screen.py`

The script gains a third mode alongside its existing `--prepare-only` and API modes. The
API path is unchanged in behavior. The offline path reuses, unmodified, the *same*
`build_prompt()`, the *same* `CRITERIA`/`SYSTEM` text, the *same* `validate()`, the *same*
`annotate()` (which already factors out review-priority assignment and the seeded
exclusion audit), and the *same* `screen_record()`/`emit()` progress stream — so
`analysis/watch_progress.py` observes an offline run with no changes.

Proposed CLI additions:

| flag | default | meaning |
|---|---|---|
| `--export-prompts` | off | write the exact per-work prompts that would have been sent, batched, then exit |
| `--batch-size N` | `100` | works per adjudication batch |
| `--overlap-fraction F` | `0.03` | share of exported works additionally placed in replicate batches |
| `--overlap-replicates R` | `2` | number of independent replicate adjudications of the overlap set |
| `--overlap-seed S` | `20260822` | seed for stratified overlap sampling |
| `--ingest-decisions PATH` | none | file or directory of adjudicator decision JSON; enables offline mode |
| `--adjudicator ID` | none | required with `--ingest-decisions`; value written to the `model` column |
| `--require-complete` | off | fail unless every exported work has exactly one home-batch decision |

`--export-prompts` and `--ingest-decisions` are mutually exclusive, and neither may be
combined with `--prepare-only`. Offline mode must not read `LLM_API_KEY` and must not open
a socket.

Directory layout under `--out` (e.g. `postanalysis/llm_agent`):

```text
postanalysis/llm_agent/
  llm_screening_input.jsonl                  # existing prepare output, unchanged
  llm_prepare_summary.json                   # existing prepare output, unchanged
  adjudication/
    manifest.json                            # denominators, batch map, prompt hashes, criteria hash
    criteria.md                              # verbatim SYSTEM + CRITERIA text for this export
    prompts/batch_000.jsonl ... batch_NNN.jsonl
    prompts/overlap_r1_000.jsonl ...         # replicate batches over the overlap set
    decisions/                               # adjudicator writes here; script only reads
      batch_000.json ...
      overlap_r1_000.json ...
  cache/agent_offline/<model_slug>/<hash>.json
  llm_screen_progress.jsonl                  # existing stream, emitted by the offline path too
  overlap_replicate_r1/llm_relevance_results.csv   # replicate view, comparison-tool shaped
  llm_relevance_results.csv
  human_review_queue.csv
  llm_relevance_summary.json
  run_manifest.json
  agent_adjudication_audit.json
```

**Works with no abstract are deliberately not exported.** The existing API path never calls
the model for them; it assigns `insufficient_abstract` directly. The offline export must
mirror that exactly, which has the useful side effect that the adjudicator is never given
the opportunity to exclude a work from its title alone. The manifest records
`auto_insufficient_abstract` so `exported + auto_insufficient_abstract == prepared_works`
reconciles.

Each `prompts/*.jsonl` file begins with one header record and then one record per work:

```json
{"record":"criteria","prompt_version":"IA-007-v2-work-level","criteria_sha256":"…","system":"You are a high-recall …","criteria":"Scope for this evidence map: …"}
{"record":"work","batch":"batch_000","work_id":"W00001","canonical_paper_id":"…","source_group":"unresolved","version_count":1,"member_paper_ids":"…","title":"…","prompt_sha256":"…","prompt":"<exact string build_prompt() returns>"}
```

The header is repeated verbatim in **every** batch file so an adjudicating subagent needs
no conversation context and no other file to do its job.

Each `decisions/<batch>.json` is a single JSON object:

```json
{
  "batch": "batch_000",
  "adjudicator": "agent:cursor/claude-opus-5-thinking@2026-08-22",
  "prompt_version": "IA-007-v2-work-level",
  "criteria_sha256": "…",
  "decisions": {
    "W00001": {
      "decision": "core_relevant",
      "roles": ["reconstruction_segmentation"],
      "confidence": 0.9,
      "evidence": "dense reconstruction of a cortical volume by serial-section EM",
      "reason": "Nanoscale EM reconstruction with synapse-level connectivity.",
      "noise_flags": [],
      "prompt_sha256": "…"
    }
  }
}
```

The per-work object is exactly the schema `validate()` already accepts, plus a
`prompt_sha256` echo. Ingest, per work:

1. resolve the work in the export manifest; an unknown `work_id` is a hard error;
2. compare `prompt_sha256` and `criteria_sha256` against the export — any mismatch is a
   hard error, because it means the criteria or prompt drifted between export and
   adjudication and the batch is not comparable;
3. pass the object through the existing `validate()` **unmodified**;
4. write the validated result into the namespaced cache;
5. append to `rows` with the same `base` dict the API path builds, and emit the same
   `screen_record(idx+1, len(screen), base, result, cache_hit)` progress line, where
   `cache_hit` is false on first ingest and true when re-ingesting an already-cached
   decision.

After the loop, the existing tail of `main()` runs untouched: `annotate(...)`,
`llm_relevance_results.csv`, `human_review_queue.csv`, `llm_relevance_summary.json`,
including the periodic `DUMP_EVERY` partial dump.

Implementation note for whoever does this: the only structural change required is to make
the per-work decision source pluggable — `call_model(...)` in API mode versus
`ingested[work_id]` in offline mode — inside the existing loop over `screen`. `annotate()`
is already factored out, so no further refactor of the tail is needed. Do not fork the file
and do not duplicate the loop.

### Provenance: distinguishing an agent run from an API run

**`model`.** Offline mode requires `--adjudicator` and must reject any value that does not
match `agent:<vendor>/<model>[@<date>]`. API mode takes `model` from `LLM_MODEL` as today
and must reject any value beginning with `agent:`. Concretely, this run writes
`agent:cursor/claude-opus-5-thinking@2026-08-22` and a later API run writes `gpt-5.6`. The
`model` column is therefore sufficient on its own to tell the two runs apart in
`llm_relevance_results.csv`, and `compare_screening_runs.py` surfaces it as
`provenance.same_model`.

**`prompt_version`.** It stays `IA-007-v2-work-level` and is *not* forked for the agent run.
That is the point: comparability requires that both runs answered byte-identical prompts, so
a differing execution path must not imply a differing prompt version. The rule is the
inverse — if the prompt or criteria text changes by a single byte, bump to
`IA-007-v3-<name>` regardless of which path runs it. To make "byte-identical" checkable
rather than asserted, results gain a `prompt_sha256` column.

**Three additive result columns**, filled by both paths:

- `run_mode`: `api` or `agent_offline`;
- `prompt_sha256`: hash of the exact prompt string for that work (empty for
  `insufficient_abstract` works, which receive no prompt);
- `adjudication_batch`: home batch id in offline mode, empty in API mode.

These are additive, so they do not disturb the existing consumers, and
`compare_screening_runs.py` requires only `work_id` and `decision`.

### Cache key

Today the key is `stable_hash({"work_id", "prompt", "model", "version"})` written flat to
`<out>/cache/<hash>.json`. `model` is already in the payload, so an agent entry and an API
entry for the same work do not collide *by hash*. Two things are still wrong for IA-009 and
must change.

First, the on-disk layout is unauditable: a flat directory of opaque hashes gives no way to
tell which entries came from which run, so a `--out` that ever hosted both paths becomes
permanently ambiguous. Second, the key is fragile in exactly the direction that matters: it
embeds the full prompt string, and it carries no schema tag, so any future normalization of
the prompt or of `model` would silently reuse stale entries across execution paths.

The required change:

```python
CACHE_SCHEMA="ia007-cache-v2"

def cache_key(work_id,prompt_sha,model,mode):
    return stable_hash({"schema":CACHE_SCHEMA,"work_id":work_id,"prompt_sha256":prompt_sha,
                        "prompt_version":PROMPT_VERSION,"run_mode":mode,"model":model})
```

with three accompanying rules:

1. **Namespaced path.** `<out>/cache/<run_mode>/<model_slug>/<hash>.json`, where
   `model_slug` is the `model` string reduced to `[0-9a-z_-]`. Agent and API entries then
   cannot share a directory even by accident, and a cache directory is self-describing.
2. **`run_mode` inside the key.** Belt and braces: even if someone sets `--adjudicator` to
   a string that collides with an API model name, the two runs still hash apart.
3. **`schema` inside the key, and `prompt_sha256` instead of the full prompt.** The schema
   tag forces a clean miss on every future key change instead of a silent stale hit. The
   hash-of-hash keeps keys short and printable, and it is what the export already commits
   to on disk.

Cached files become self-describing too:

```json
{"key":{"schema":"ia007-cache-v2","work_id":"W00001","prompt_sha256":"…","prompt_version":"IA-007-v2-work-level","run_mode":"agent_offline","model":"agent:cursor/claude-opus-5-thinking@2026-08-22"},"result":{"decision":"core_relevant","…":"…"}}
```

Legacy v1 flat entries are simply never looked up under the v2 layout. Do not migrate them
and do not delete them.

Cache namespacing is defense in depth, not the primary discipline. The primary discipline is
**one `--out` directory per run**: `postanalysis/llm_agent` and `postanalysis/llm_api`. The
script should additionally write a `run_manifest.json` recording `run_mode`, `model`,
`prompt_version`, `criteria_sha256` and the input CSV's SHA-256, and refuse to proceed if an
existing `run_manifest.json` in that directory disagrees.

### The high-recall contract is not weakened

IA-007's exclusion asymmetry is a hard constraint on IA-009, enforced mechanically rather
than by instruction:

- **Ambiguity becomes `uncertain`, never `out_of_scope`.** The exported prompt already
  carries "If plausible relevance exists but the abstract is ambiguous, choose uncertain
  rather than out_of_scope"; every batch header repeats it verbatim.
- **`insufficient_abstract` is not an adjudicator-available label.** `validate()` already
  excludes it from the allowed set, and that must stay. An ingested decision of
  `insufficient_abstract` is a hard error. The label is assigned only by the script, only
  from the empty-abstract branch, only after IA-008 rescue.
- **No work is excluded from a title alone.** Structurally guaranteed: abstract-less works
  are never exported, so no adjudicator ever sees one.
- **Exclusions must be justified from the supplied text.** Ingest rejects any
  `out_of_scope` decision with an empty `evidence` string. An exclusion has to name the
  phrase in the title/abstract that places the work outside scope; "no evidence of
  relevance" is not admissible as evidence.
- **Outside knowledge stays out.** `CRITERIA` already says "Do not use outside knowledge.
  Judge only supplied title and abstract." Adjudicating subagents must therefore not open
  `canonical_works_enriched.csv`, other `postanalysis/` outputs, or the web while
  adjudicating; the batch file is the whole input.
- **Every exclusion remains reviewable.** The unchanged `annotate()` routes all
  `uncertain`/`insufficient_abstract` works, all low-confidence decisions, all `core_audit`
  works not called relevant, and a seeded 10% sample of high-confidence
  `unresolved`/`role_bridge` exclusions into `human_review_queue.csv`.

### Batching across multiple adjudicating subagents

**Partition.** `screen` is already sorted by `work_id`. Chunk the exported works in that
order into `--batch-size` blocks; batch id is `batch_%03d` of the chunk index. This is
deterministic, reproducible from the input CSV alone, and independent of how many
subagents are used. At 100 works per batch, 4,136 works minus the abstract-less works yields
roughly 39 batches.

**Isolation rules for each adjudicating subagent:**

1. one batch per subagent invocation, in a fresh context;
2. the batch file is the only input — no other batch's prompts or decisions, no repository
   files, no network;
3. the criteria header is read from the batch file itself, never paraphrased and never
   supplied by the orchestrating agent, so criteria text cannot drift between batches;
4. output is exactly one decision object per `work_id` in the batch, in input order, written
   to `decisions/<batch>.json`;
5. no subagent sees aggregate statistics (running exclusion rates, decision counts) — that
   is the mechanism by which a target-rate expectation would leak in and bias later batches.

**Variance, and what to do about it.** Batch-to-batch variance is real and unavoidable here:
different subagent invocations are different draws. Prompt-sensitivity findings in Homiar et
al. and the confidence-guided-review design in Janoudi et al. both point the same direction —
measure the instability and route it to humans rather than hide it.

Measurement uses a **held-out overlap set**: sample `--overlap-fraction` of exported works
(default 0.03, about 120 works), stratified by `source_group` with `--overlap-seed`, and emit
each sampled work into `--overlap-replicates` additional replicate batches
(`overlap_r1_*`, `overlap_r2_*`) adjudicated by *different* subagent invocations that do not
see the home-batch decision. Overlap works are not marked as such in the batch files.

The home-batch decision is always the run of record; replicates never override it. Ingest
writes each replicate as its own `overlap_replicate_r<i>/llm_relevance_results.csv` so
internal consistency is measured with the same tool used for the agent-vs-API comparison:

```bash
python analysis/compare_screening_runs.py \
  --run-a postanalysis/llm_agent/llm_relevance_results.csv \
  --run-b postanalysis/llm_agent/overlap_replicate_r1/llm_relevance_results.csv \
  --label-a agent-home --label-b agent-replicate-1 \
  --out postanalysis/screen_comparison/agent_internal_r1
```

`agent_adjudication_audit.json` records, per replicate: overlap size, per-group agreement,
Cohen's kappa, and the count of tier-5 (relevant-versus-`out_of_scope`) internal conflicts.
Report these numbers alongside the run; do not average replicates into a consensus label,
because that would quietly convert a measured-noise estimate into an unmeasured one. Any work
whose replicates disagree on relevant-versus-excluded is forced into
`human_review_queue.csv` with reason `internal_replicate_conflict`.

## Run validation

**Denominator.** The frozen-run dry run fixes the expected input at **4,136 canonical
works**: 1,678 `core_audit`, 2,062 `unresolved`, 396 `role_bridge` (see IA-008 and
`docs/POSTANALYSIS_PAPER_FLOW.md`). The realized number is whatever
`canonical_works_enriched.csv` contains after the actual networked abstract rescue; the
script writes it at runtime and the expected figures are the reconciliation target, not a
hard-coded constant.

**Invariants to assert, failing loudly:**

1. `prepared_works == len(canonical_works_enriched rows in the three source groups)`, and
   per-group counts reconcile to the manifest;
2. `exported_prompts + auto_insufficient_abstract == prepared_works`;
3. home batches partition the exported works exactly — no work in two home batches, no
   exported work in none, union equals the export;
4. every ingested `work_id` is known to the manifest, and with `--require-complete` every
   exported work has exactly one home-batch decision;
5. every ingested `prompt_sha256` and `criteria_sha256` matches the export;
6. every decision passes the unmodified `validate()`; no ingested `insufficient_abstract`;
   no `out_of_scope` with empty `evidence`;
7. `len(results) == prepared_works`, `work_id` unique, and results' per-group counts equal
   the input's;
8. exactly one distinct `model`, one `prompt_version`, and one `run_mode` across the run;
   offline `model` matches `agent:<vendor>/<model>`;
9. `human_review_queue.csv` is a subset of `llm_relevance_results.csv` and contains every
   `uncertain`, every `insufficient_abstract`, every `core_audit` work not called relevant,
   and every `internal_replicate_conflict`;
10. `llm_screen_progress.jsonl` contains exactly one record per work in the run, with
    contiguous `index` values and a constant `total`;
11. `--limit` is 0 for any run reported as complete;
12. the SHA-256 of `canonical_works_enriched.csv` is identical before and after the run, and
    no file outside `--out` is written.

**Reporting.** `llm_relevance_summary.json` gains `run_mode`, `adjudicator`,
`criteria_sha256`, batch count, overlap size, and per-group exclusion rates. A `core_audit`
`out_of_scope` share far above the IA-004 noise expectation is a signal to re-examine the
adjudication, not a finding — that is exactly what the `core_noise_audit` queue exists for.

**Agent-versus-API comparison.** When `LLM_API_KEY` becomes available, run the API path into
a separate `--out` and compare with the tool built for it:

```bash
python analysis/compare_screening_runs.py \
  --run-a postanalysis/llm_agent/llm_relevance_results.csv \
  --run-b postanalysis/llm_api/llm_relevance_results.csv \
  --label-a agent --label-b api \
  --out postanalysis/screen_comparison \
  --expected-works 4136
```

It reports coverage, decision agreement and Cohen's kappa overall and per source group, a
full confusion matrix, the sensitivity-focused view of exclusions one run makes that the
other treats as relevant, role and noise-flag set agreement, confidence calibration, and
human-review-queue overlap. Its tier-5 disagreements are the human adjudication queue for
the comparison. Neither run is the reference standard, and the comparison output says so.

## Reproducibility

The scientific source corpus remains immutable. `llm_screening_input.jsonl`,
`adjudication/prompts/*.jsonl`, `adjudication/criteria.md`,
`adjudication/decisions/*.json`, `adjudication/manifest.json`, the namespaced cache and
`run_manifest.json` are committed together, so the exact text every adjudicator saw and the
exact JSON it returned are both recoverable. The API path's reproducibility story is
unchanged. The agent path's honest reproducibility claim is *auditability, not
determinism*: the inputs and outputs are fully recoverable and verifiable by hash, while
re-adjudication is not guaranteed to reproduce the same labels — which is precisely why the
overlap set is measured and why the API comparison remains on the plan.

## Addendum A — Frozen-run operational record (2026-08-23)

This addendum records **execution-path** events for the completed IA-007-v2 / IA-009 agent
offline run. It does not change criteria, prompt text, or decision vocabulary.

### Queue process of record

Full-process adjudication used `analysis/adjudication_queue.py` (claim leases, wave packs,
`wave_live.jsonl`) rather than keyword shortcuts. Decisions land under
`postanalysis/llm_agent/adjudication/decisions/` and are ingested with
`analysis/llm_relevance_screen.py --ingest-decisions`.

### Hard reset (cleared prior partial work)

A full clear archived earlier incomplete adjudication state to:

`postanalysis/llm_agent/adjudication/_full_clear_20260823T070628Z/`

After the reset, the process of record re-ran to completion: **3,983 / 3,983** exported
works decided (plus auto-`insufficient_abstract` outside that exported set), **0** active
claims. Aborted post-reset workers that wrote no decisions (`wave2_w1`, `wave2_w2`) are
non-events for the scientific record.

### Role-vocabulary normalization at ingest

Some batch decision files used role strings outside IA-007 `ALLOWED_ROLES` (e.g.
`graph_construction`, `network_analysis`, `proofreading_annotation`,
`infrastructure_software`). Ingest rejected those files until roles were normalized onto
the allowed vocabulary (**82 role substitutions across 10 batch files**). Decisions
(decision/confidence/evidence/reason) were otherwise unchanged. This is an ingest hygiene
fix to satisfy the frozen schema, not a re-adjudication.

### What this run does not include

Post-decision derived layers (inclusive checkpoint corpus, curriculum labels, checkpoint
person-name reconciliation) are **IA-012**, not IA-009. The later v3 re-screen used this
same offline agent path; v3 ingest and post-v3 overlays are **IA-007-v3** and **IA-014**.
