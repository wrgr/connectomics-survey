# Dataset & methods registry — preliminary draft (v5 checklist step 2)

**Status: DRAFT for screener review — nothing here is frozen.** Seeds the v5 §5
dataset registry and sketches the stage × methods × bridges map. Entries marked
`corpus-anchored` have verified presence in the frozen pilot corpus (grep-level
anchoring recorded in the IA chain); `needs_verification` entries come from the
screener's and drafter's field knowledge and must be verified per §12.3-style
identifier resolution before the registry freeze. Representation is intended to
be fair across labs and consortia and is explicitly **non-exhaustive**; the
registry grows during charting, with growth logged.

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
  community; platform-based courses and hackathons (BossDB/APL outreach;
  Allen Institute education). Pilot corpus people-development axis: 213 works.
- **Network science:** motif/topology/null-model literature applied to
  connectome graphs (substantive-use test governs adjacency). Pilot
  network-science axis: 2,044 works (broad; needs the boundary test).
- **Health / translation:** pathology and clinical vEM; human surgical/postmortem
  volumes (H01 epilepsy-tissue provenance; Wilson human feeding-circuit work);
  disease-model connectomics. Pilot health axis: 891 works.

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
