# IA-007 — LLM-first semantic relevance screening

## Status

Derived post-processing workflow. It does not alter the preregistered retrieval corpus, original `keep` values, IA-004 core labels, IA-006 bridge labels, or IA-008 work/version links.

## Rationale

Large language models (LLMs) have increasingly been evaluated for title/abstract screening in evidence synthesis. The emerging literature supports LLMs as first-pass screeners when the workflow is designed for high sensitivity and preserves later human oversight, rather than treating model exclusions as an unquestioned gold standard.

Examples:

- Homiar A et al. *Development and evaluation of prompts for a large language model to screen titles and abstracts in a living systematic review.* BMJ Mental Health. 2025;28:e301762. Refined prompts achieved very high sensitivity in the evaluated review while the authors still recommended uncertainty scoring and manual audits.
- Matsui K et al. *Human-Comparable Sensitivity of Large Language Models in Identifying Eligible Studies Through Title and Abstract Screening.* J Med Internet Res. 2024;26:e52758.
- Janoudi G et al. *Validating Loon Lens 1.0 for Autonomous Abstract Screening and Confidence-Guided Human-in-the-Loop Workflows in Systematic Reviews.* Value in Health. 2025;28(11):1630-1636.

These studies do not imply that a particular model/prompt will reproduce their performance in connectomics. IA-007 therefore treats LLM output as a provisional first pass whose local behavior is later audited by humans.

## Revised sequencing after IA-008

IA-007 no longer screens raw paper records. First:

1. the 3,768 originally retained records and 391 IA-006 recovered bridge records form a **4,159-record semantic-analysis universe**;
2. IA-008 reconciles preprint/final and metadata-duplicate versions into canonical works;
3. IA-008 attempts best-effort abstract rescue;
4. IA-007 screens the resulting canonical enriched works.

The frozen-run work-reconciliation dry run produces **4,136 canonical works** from 4,159 records:

- 1,678 `core_audit` works;
- 2,062 `unresolved` works;
- 396 `role_bridge` works.

This count is the current expected LLM denominator before any later manual correction of work links. The 391 recovered bridge records are therefore fully included in semantic screening.

## Missing abstracts

Work reconciliation first carries the best available abstract across linked versions. `analysis/rescue_missing_abstracts.py` then attempts Semantic Scholar, Europe PMC, optional OpenAlex, and Crossref enrichment. The frozen-run dry run leaves 321 works without abstracts **before** network rescue.

Any work still missing an abstract after rescue is assigned `insufficient_abstract`; it cannot be excluded from title alone and is routed to later human/full-text review.

## LLM-first decisions

Each canonical title/abstract receives one provisional decision:

- `core_relevant`
- `adjacent_relevant`
- `role_bridge`
- `out_of_scope`
- `uncertain`
- `insufficient_abstract`

The model also returns role labels, confidence, supplied-text evidence, a concise reason, and noise flags.

The prompt is intentionally high recall: plausible but ambiguous relevance should become `uncertain`, not `out_of_scope`.

## Human review later

No LLM decision directly changes scientific status. Later human review prioritizes:

1. `uncertain` and `insufficient_abstract` works;
2. low-confidence decisions;
3. every core-audit work classified as `out_of_scope`, `uncertain`, or missing abstract;
4. a deterministic sample of high-confidence exclusions from unresolved and role-bridge groups to estimate false-negative risk.

## Reproducibility

`analysis/llm_relevance_screen.py` records work ID, canonical/version identifiers, source group, prompt version, model name, structured decision/confidence, evidence/reason and deterministic audit sampling. Results are cached by work + prompt + model hash.

The scientific source corpus remains immutable.
