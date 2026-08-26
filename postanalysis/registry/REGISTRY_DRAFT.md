# Dataset & methods registry — preliminary draft (v5 checklist step 2)

**PLACEHOLDER v0.2 (2026-08-26).** Quick-pass snapshot for exploration: every
entry is provisional and will be revisited wholesale at formal charting.
**All v0.1 todos resolved:** the methods table is now backed by
`methods_registry_draft.csv` — 39 entries, every one Crossref-verified to a
resolving DOI with matching title or recorded as a software record
(`analysis/build_methods_registry.py` reproduces the verification); DS20's
placeholder became three corpus-pinned comparative datasets (Ciona 2016,
octopus vertical lobe, Platynereis); DS17 was resolved by scoping decision
(platform collection + pinned method anchors; volume enumeration is
charting-time work); the BRAIN CONNECTS milestone is pinned to "The Mind of a
Mouse" (in corpus) plus the program launch. Nothing here is frozen or
deposited; nothing locks anything in.

**Status: DRAFT for screener review — nothing here is frozen.** Seeds the v5 §5
dataset registry and sketches the stage × methods × bridges map. Entries marked
`corpus-anchored` have verified presence in the frozen pilot corpus (grep-level
anchoring recorded in the IA chain); `needs_verification` entries come from the
screener's and drafter's field knowledge and must be verified per §12.3-style
identifier resolution before the registry freeze. Representation is intended to
be fair across labs and consortia and is explicitly **non-exhaustive**; the
registry grows during charting, with growth logged.

**Companion files:** `methods_registry_draft.csv` (verified methods),
`MILESTONES_DRAFT.md` (progression axes), and `REVIEWS_FIELD_OPINION.md`
(the 15-review diverse set and cross-cluster citation counts — the
field-opinion layer; e.g., FAFB cited by all 8 panel clusters, White 1986
by 6).

## 1. Datasets (registry seed)

See `dataset_registry_draft.csv` (20 seed entries): the *C. elegans* lineage
(White 1986 → Cook 2019 → Witvliet 2021); the *Drosophila* family (larva L1,
FAFB, hemibrain, FlyWire, FANC/MANC, male CNS); mouse retina (e2198, k0725);
cortex (Kasthuri 2015, Motta L4, MICrONS); human (H01, Wilson hypothalamus);
zebrafish (Hildebrand 2017); auditory brainstem (Spirou calyx of Held);
songbird (Kornfeld); NCMIR cellular EM collections (Ellisman).

**Platform collections (distinct from datasets):** BossDB (APL/JHU — hosts
MICrONS, Kasthuri, Witvliet, and others), neuPrint (Janelia), FlyWire
Codex (Princeton), CAVE (Allen/Princeton/Seattle), CATMAID instances,
WormWiring, EyeWire museum, CCDB/Cell Image Library (NCMIR), OpenOrganelle
(Janelia COSEM; cell-biology vEM), DANDI, EBRAINS.

## 2. Methods anchored to each pipeline stage (representative, not exhaustive)

**Verified version of record: `methods_registry_draft.csv`** (39 entries;
per-entry Crossref-verified DOI + title, pilot-corpus cross-check, software
records for repository-only tools; rebuilt by
`analysis/build_methods_registry.py`). The table below is the readable
summary; where they disagree, the CSV wins.

| Stage | Significant methods/tools | Groups (for representation) |
|---|---|---|
| Preparation & staining | rOTO/en-bloc protocols; ECS-preserving fixation; whole-brain staining | MPI (Hua, Mikula); NCMIR/Ellisman; Janelia |
| Sectioning & collection | SBF-SEM (Denk & Horstmann 2004); ATUM tape collection; FIB-SEM incl. enhanced/long-run; GridTape; hot-knife; gas-cluster ion beam | MPI; Harvard/Lichtman (Hayworth); Janelia/Hess (Xu); Harvard/Lee (Phelps); EPFL (Knott) |
| EM acquisition | TEMCA camera arrays; multibeam SEM; FAST-EM; ML-guided acquisition (SmartEM) | Janelia (Bock); Zeiss/Harvard; Delft (Hoogenboom, Kievits); MIT/Harvard |
| Alignment & registration | Elastic serial-section alignment; SOFIMA-class flow methods | Janelia/Saalfeld; Google | 
| Segmentation & agglomeration | Flood-filling networks; affinity nets + watershed/agglomeration (SegEM, GALA, waterz); CDeep3M cloud segmentation | Google (Januszewski/Jain); MPI (Berning); Janelia (Funke); Princeton/Seung; NCMIR (Ellisman) |
| Proofreading & annotation | CATMAID; Eyewire (crowdsourced); Neuroglancer; webKnossos/KNOSSOS; VAST; PyChunkedGraph/CAVE proofreading | Cambridge/Janelia (Cardona, Saalfeld); Princeton (Seung, Dorkenwald); Google; MPI; Harvard (Berger) |
| Synapse detection & partners | SynEM; synful-style partner prediction (Buhmann); ilastik-lineage interactive ML; SyConn | MPI (Staffler); Janelia (Funke); EMBL (Kreshuk); MPI (Kornfeld) |
| Graph construction & infrastructure | BossDB; neuPrint; CloudVolume/Igneous; DVID; CAVE; connectome file formats | APL/JHU (incl. screener, COI-0); Janelia; Princeton; Allen |
| Analysis & network science | natverse/navis; motif and null-model analysis; cell-type clustering; connectome statistics | Cambridge (Jefferis, Bates); community |
| Modeling & NeuroAI | Connectome-constrained network models; whole-circuit simulation | Janelia/Columbia (Turaga, Litwin-Kumar, Lappalainen) |

## 3. Bridge fields (charted as ties, per v5 §1)

- **Training / outreach / citizen science:** EyeWire (crowdsourced proofreading
  as public engagement); FlyWire community proofreading and annotation
  community; **CIRCUIT summer program** (undergraduate connectomics research/
  outreach, JHU/APL — Gray Roncal; **COI-0, screener's own program**; in the
  retained corpus, doi:10.1109/isecon.2018.8340467, and the pilot's positive
  control for outreach role-bridge detection); platform-based courses and
  hackathons (BossDB/APL outreach; Allen Institute education). Pilot corpus
  people-development axis: 213 works.
- **Network science:** motif/topology/null-model literature applied to
  connectome graphs (substantive-use test governs adjacency). Pilot
  network-science axis: 2,044 works (broad; needs the boundary test).
- **Health / translation:** pathology and clinical vEM; human surgical/postmortem
  volumes (H01 epilepsy-tissue provenance; Wilson-lab immersion-fixation brain
  banking for ultrastructure-preserving human postmortem tissue — the enabling
  step for banked-brain connectomics); disease-model connectomics. Pilot health
  axis: 891 works. *(Correction 2026-08-26: an earlier draft attributed "human
  feeding-circuit" work to the Wilson lab; that claim could not be verified
  against any publication or release and is retracted — the retraction is the
  log entry.)*

## 4. Fair-representation checklist (screener's concern, made explicit)

Big consortia (Janelia, Google, Princeton, Harvard, Allen, MPI) anchor the
registry, and the following are explicitly included so the map does not
collapse onto the largest labs: NCMIR/Ellisman (SBEM lineage, cellular EM,
infrastructure), Spirou (auditory brainstem SBEM), A. M. Wilson (human serial
EM), Delft/Hoogenboom (FAST-EM throughput), EPFL/Knott (FIB-SEM), Cambridge
natverse community, Cardona larva community, EMBL/Kreshuk (interactive ML),
Vermont/Bock (FAFB), Toronto/Zhen (developmental *C. elegans*). Gaps in this
list are expected and are filled during charting through logged additions, not
by memory.

## 5. What this draft is not

Not frozen, not a ranking, not exhaustive, and not a substitute for charting:
every entry and tie above must survive identifier verification and
corpus-grounded charting before it appears in any output. Its purpose is to
make v5's registry seeding concrete and reviewable in one sitting.
