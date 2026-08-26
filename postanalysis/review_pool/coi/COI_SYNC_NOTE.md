# COI_sets_WGR_frozen.json — sync and hash-verification note (2026-08-25)

Synced into the repo 2026-08-25 from the screener's copy (identical bytes to the
copy inside `files_53.zip`).

## Hash status

| Quantity | Value |
|---|---|
| SHA-256 of the file as received (both copies) | `b162b0ca4aea466c272bb7fd62f8a188d6748a49660bf0dcfd4b616b6ef3d060` |
| Internal field `sha256_of_content_excluding_this_field` | `46f8688242f00b4e3c162d3958ca062b898f748f4e16461d27b268ae0aaf9d08` |
| SHA recorded in the execution spec and in `bootstrap_2026-08-25/MANIFEST.md` | `46f86882…` (matches the internal field) |

The recorded `46f86882…` is therefore the artifact's **internal content hash**,
not a file hash, and the spec/manifest references are consistent with the file.
However, the content hash could **not be independently reproduced** from the
current content under any standard JSON canonicalization
(sorted/unsorted × compact/indented × ascii/utf-8), and the file carries two
freeze timestamps (`frozen_utc_v1` 2026-08-21T18:12:32Z, `frozen_utc`
2026-08-21T18:15:08Z), indicating the content was extended after v1 without
recomputing the embedded hash.

## Consequence and recommendation

The artifact is accepted as the COI set of record (content is internally
consistent: 94 screener works, 349 distance-1 coauthors, D-001 d2 handling),
but its self-hash is not verifiable by a third party. Recommended, as a logged
deviation superseding-but-retaining this file: re-freeze with the hash computed
over the **byte stream of the file** and stored in a sidecar (the convention
used for `probe_panel_frozen.json`), so verification is
`sha256sum <file> == <sidecar>` with no serialization ambiguity. Until then,
cite the file hash `b162b0ca…` (now pinned by this repo's git history) alongside
the internal `46f86882…`.
