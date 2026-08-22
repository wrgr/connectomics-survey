# Codex task: harden and validate the deterministic nanoscale-connectomics pipeline

This repository contains a packaged implementation of the deterministic literature-field-map workflow discussed with Will Gray-Roncal. The source bundle is stored under `handoff/` as base64 chunks; run `bash bootstrap_bundle.sh` to reconstruct and unpack it.

## Objective

Turn the supplied v0.1.1 package into a robust, reproducible end-to-end implementation for building a broad nanoscale/synaptic-resolution connectomics training bibliography, citation/network map, contributor map, people-development/training-outreach corpus, and health-translation bridge.

## Non-negotiable scientific scope

The initial lexical search MUST cover these first-class axes, not rely on citation expansion to discover them later:

1. direct nanoscale/synaptic connectomics
2. tissue preparation and EM acquisition
3. registration, segmentation, agglomeration, reconstruction
4. synapse detection and partner assignment
5. proofreading, annotation, reconstruction error, QC
6. data infrastructure, versioning, storage, serving, collaborative annotation
7. network science / graph analysis: motifs, topology, modularity, communities, centrality, wiring rules, controllability, graph querying
8. organism/circuit biological applications
9. structure-function connectomics, connectome-constrained modeling, NeuroAI
10. alternative single-synapse modalities
11. people development = training, education, workforce/capacity development, mentoring, citizen/community science, and outreach
12. health/disease/human translation, while retaining the nanoscale/synaptic boundary

`people development` does NOT mean the bibliometric contributor map. The contributor map is a separate downstream product derived from retained-paper authorship and coauthorship.

## Required retrieval architecture

- Semantic Scholar Academic Graph API is the PRIMARY scholarly search and graph backend.
- Read the API key only from `SEMANTIC_SCHOLAR_API_KEY`.
- Never print, cache, serialize, commit, hash, or log the secret value.
- Respect <= 1 request/second globally; the supplied code targets >=1.2 seconds between keyed calls.
- Cache responses by a request fingerprint that excludes auth headers.
- Use one-hop citation expansion only: references + citations of retained seeds. Do NOT silently add a second hop.
- Compute co-citation and bibliographic coupling deterministically from the retrieved graph.
- Use Crossref only as metadata/DOI verification, not as the primary discovery graph.
- NIH RePORTER/BRAIN funding is a separate discovery/corroboration layer; grant status is not an importance score.

## Screening philosophy

Do not use broad destructive negative filters such as `NOT MRI` or rejecting every paper containing `functional connectivity`. Use positive nanoscale/synaptic scope gates. A translational or structure-function paper can survive if it truly contains synaptic-resolution connectomics; pure dMRI/fMRI connectomics should fail the positive scope gate.

Preprints and final publications should be deduplicated as one intellectual work when confidently resolvable, with the final publication preferred and merge provenance retained.

## Ranking / outputs

Keep transparent evidence columns. Avoid a single opaque importance score as the only result. Preserve raw components such as:

- lexical query axes / count
- direct seed links
- co-citation support
- bibliographic coupling support
- PageRank percentile
- k-core / component
- age-normalized citation signal
- recent-work safeguard
- method/resource axis evidence

Produce separate outputs for papers, graph edges, paper metrics, contributor/author network, training/outreach, health bridge, funding, retrieval provenance, screening decisions, and hashes/manifests.

## Temporary protocol deviation

For this implementation, defer both:

- frozen-349 screener tagging
- Absolute-Core / independent-groups adjudication

Do not claim true group independence has been established. Preserve an explicit disclosure in outputs. These checks must remain separable so they can be restored later without redesigning discovery.

## What I want Codex to do

1. Unpack and inspect v0.1.1.
2. Audit the Semantic Scholar API assumptions/endpoints, pagination, rate limiting, error handling, retry/backoff, caching, and field schemas against the current API behavior.
3. Fix implementation defects and simplify the architecture where possible without changing the scientific contract above.
4. Add mocked/offline unit tests for all API clients and pagination behavior.
5. Add an integration/smoke-test mode that can validate credentials and run a tiny bounded query before a full run.
6. Ensure the default fresh run is deterministic given the same API responses/cache/config.
7. Ensure the Stage-1 126-paper seed is OPTIONAL; fresh mode must not depend on it.
8. Verify that people-development/training-outreach results are distinct from the contributor map.
9. Verify that network-science and proofreading/QC queries are first-class and survive screening.
10. Verify the health bridge requires BOTH nanoscale/synaptic scope and a health/human-translational signal.
11. Add useful coverage diagnostics by search axis, year, venue, organism/method branch, and retrieval channel.
12. Run the test suite and report exact pass/fail status. Do not fabricate a live Semantic Scholar run if the token/network is unavailable.
13. Keep all scientific policy choices in config/query files where feasible, rather than burying them in model reasoning or hard-coded ad hoc logic.

Please make changes on this branch or a child branch and open a draft PR back to `main` with a concise audit of what was changed, what remains uncertain, and any API limitations encountered.
