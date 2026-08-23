# IA-007 — LLM-first semantic relevance screening

## Status

Derived post-processing workflow. It does not alter the preregistered retrieval corpus, original `keep` values, IA-004 core labels, or IA-006 bridge labels.

## Rationale

Large language models (LLMs) have increasingly been evaluated for title/abstract screening in evidence synthesis. The emerging literature supports LLMs as first-pass screeners when the workflow is designed for high sensitivity and preserves human oversight, rather than treating model exclusions as an unquestioned gold standard.

Examples:

- Homiar A et al. *Development and evaluation of prompts for a large language model to screen titles and abstracts in a living systematic review.* BMJ Mental Health. 2025;28:e301762. doi:10.1136/bmjment-2025-301762. Refined GPT-4o prompts achieved 100% sensitivity for studies ultimately included after full-text screening in the evaluated living review, with simulated workload reductions of 65–85%; the authors still recommend manual audits, uncertainty scoring, and human-in-the-loop safeguards because performance varied across updates and ambiguous abstracts were difficult.
- Matsui K et al. *Human-Comparable Sensitivity of Large Language Models in Identifying Eligible Studies Through Title and Abstract Screening: 3-Layer Strategy Using GPT-3.5 and GPT-4 for Systematic Reviews.* J Med Internet Res. 2024;26:e52758. doi:10.2196/52758. A multilayer criterion-based approach achieved human-comparable sensitivity on two review datasets and treated human screening as the reference standard.
- Janoudi G et al. *Validating Loon Lens 1.0 for Autonomous Abstract Screening and Confidence-Guided Human-in-the-Loop Workflows in Systematic Reviews.* Value in Health. 2025;28(11):1630-1636. doi:10.1016/j.jval.2025.09.008. Across eight reviews, the system achieved 98.9% sensitivity and 95.2% specificity, while confidence-guided human review concentrated effort on a small subset of records.

These results do not imply that a particular model/prompt will achieve the same performance in connectomics. IA-007 therefore treats LLM output as a **provisional first pass** whose local performance must later be checked by human adjudication/auditing.

## Target population

The default semantic screen covers:

1. the **2,068 unresolved originally-retained papers**; and
2. all **1,685 derived nanoscale-core papers** as a false-positive/noise audit.

Thus the default target contains **3,753 papers**.

The 15 strict retained role bridges and 391 recovered `keep=False` role bridges are outside the default pass because they already have separate role-bridge provenance and can be audited later if needed.

On the frozen reference artifact, 242/3,753 target records lack abstracts. These are automatically routed to `insufficient_abstract` and are never excluded from title alone.

## LLM-first decisions

Each title/abstract receives one provisional decision:

- `core_relevant`
- `adjacent_relevant`
- `role_bridge`
- `out_of_scope`
- `uncertain`
- `insufficient_abstract`

The model also returns role labels, confidence, abstract-grounded evidence, a concise reason, and red/noise flags.

The prompt is intentionally **high recall**: when plausible relevance exists but the abstract is ambiguous, the model is instructed to choose `uncertain` rather than `out_of_scope`.

## Human review later

No LLM decision directly changes a paper's scientific status.

The later human pass prioritizes:

1. every `uncertain` or `insufficient_abstract` record;
2. low-confidence model decisions;
3. every core paper classified as `out_of_scope`, `uncertain`, or `insufficient_abstract` (core-noise audit);
4. a deterministic random sample of high-confidence unresolved-paper exclusions to estimate false-negative risk.

The default exclusion audit fraction is 10% but is a configurable local validation parameter, not a literature-standard constant. It should be changed after inspecting the first-pass distributions and available review resources.

## Reproducibility

`analysis/llm_relevance_screen.py` records:

- prompt version;
- model name;
- source group and current deterministic category;
- structured decision and confidence;
- model-grounded evidence/reason;
- deterministic human-audit sampling seed;
- cached per-paper results keyed by paper ID + prompt + model + prompt version.

The scientific source corpus and deterministic post-analysis outputs remain immutable.
