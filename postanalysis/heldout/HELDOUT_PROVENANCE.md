# Held-out comparison sets — provenance resolution (2026-08-25)

The protocol (§4, §21) names three held-out comparison sets: "the pre-existing
bespoke bibliography, the earlier 136-paper core, and the seven-paper held-out
set." The screener could not locate them. Findings of the 2026-08-25 search of
the repository, the handoff bundle, and the synced bootstrap state:

## 1. The "136-paper independent core" is `stage1_backbone_126.csv` — 126 papers

Found inside the Codex handoff bundle
(`handoff/connectomics_pipeline_v0.1.1.zip`, committed 2026-08-21, at
`optional_inputs/stage1_backbone_126.csv`), extracted here verbatim.

- 126 records (NC001…), hand-curated: author group, year, title, venue, branch,
  DOI/source, `verification` (A: 63 / B: 63), `core_status`
  (`field_defining_core`: 65 / `not_core`: 61), role tags, attestation and
  screener-tag placeholders.
- SHA-256 (byte stream): `f2945e7f8e8d998b9c5f0b36d850af959e3119364882182850c027cdcf0f4418`.
- The protocol's "136" is **number drift** in prose, of the same family as the
  retracted "Collinson 2023" citation and the P7 title drift (IA-015). No
  136-item version was found anywhere.

**Independence from the pilot, verified:** the frozen pilot run's config
(`config.ci.yaml`, SHA-256 `a11c830a…` — byte-identical to the hash recorded
in the run manifest) has `mode: fresh, seed_csv: null`. The backbone is wired
into the pipeline only via `config.seed-expand.yaml`, which the frozen run did
not use. The backbone therefore **did not seed the pilot's discovery** and
remains a valid held-out comparison set for both the pilot corpus and the
future protocol corpus. (§4's caveat stands regardless: the screener has seen
this list; independence is procedural, not epistemic.)

## 2. The "seven-paper held-out set" — no artifact exists

Not found in the repository, the handoff bundle, the bootstrap working state,
or the protocol's own history. §21's "one miss is a 14% failure rate" prose
implies it was once concrete, but nothing identifies its members. Until the
screener either produces the list from records or reconstructs it from memory
**with a dated note saying so**, it cannot serve as a validation set.
Recommended: strike it from §4/§21 as a logged deviation, or replace it with a
newly frozen list explicitly labeled as reconstructed-after-the-fact (usable
as a sanity check, not as independent validation).

## 3. The "bespoke bibliography"

Most plausibly the same object as the backbone (its `source_note`/curation
columns read as a personal reading list formalized), or a predecessor of it.
No separate artifact found. Recommended: treat "bespoke bibliography" and
"126-paper backbone" as one set unless the screener locates a distinct file.

## Screener statement on the backbone's quality (added 2026-08-25, same day)

The screener states the backbone list was **not thoughtfully created** — it is
an early working list from the learning phase, not a considered expert
curation. Consequence: it is unsuitable not only as a validation set but also
as a wholesale §9.1b seed designation (which requires per-paper designation
rationale the screener cannot honestly supply). Its status is **historical
artifact only**. The legitimate channel for any genuine knowledge embedded in
it is per-paper nomination: route `WGR-nominated` (family a) with a one-line
rationale, subject to normal screening — never wholesale designation.

## Proposed protocol amendments (screener decision; not yet applied)

- **D-010:** §4/§21 "136-paper independent core" → "126-paper curated backbone
  (`postanalysis/heldout/stage1_backbone_126.csv`, SHA `f2945e7f…`)"; drop or
  merge the separate "bespoke bibliography" reference accordingly.
- **D-011:** strike or reconstitute the seven-paper set per §2 above.

Both are wording/reference corrections to point §21 at artifacts that exist;
neither changes any corpus content. Apply in
`docs/protocol/connectomics_bibliography_methodology_v3.md` as dated
amendments (rev. 29+) once the screener decides.
