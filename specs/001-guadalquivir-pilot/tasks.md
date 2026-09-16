# Tasks: Guadalquivir Basin River-Barrier Detection Pilot

Actionable breakdown of [plan.md](./plan.md). Ordered by dependency;
`[P]` marks tasks that can run in parallel with the one(s) above them.
Long-running steps note the resumability/probing approach from
constitution principle 3.

## 0. Setup

- [x] **T001** — Resolved: EEA's WISE WFD2022 River Basin District
  dataset, feature `GUADALQUIVIR` (`ES050`), pulled via public ArcGIS
  REST (`water.discomap.eea.europa.eu/.../WFD2022_RiverBasinDistrict_WM`).
  No login needed; CHG's own portal doesn't appear to publish this
  boundary separately.
- [ ] **T002** `[P]` (partial) — Strong positive signal: REDIAM's own
  metadata record for the related presas/embalses WMS states CC BY 4.0.
  The specific IECA/DERA page we actually downloaded from didn't show
  explicit terms in a quick check — still needs final confirmation
  before publishing (plan.md Risks), but licensing risk looks low.
- [ ] **T003** `[P]` — Send the outreach email to Dr. Wen Dai
  ([outreach-wen-dai.md](./outreach-wen-dai.md)). Also a long lead time
  item — send now so a reply has time to arrive before Layer 2 work
  starts.
- [ ] **T004** `[P]` — Set up the Python environment: geopandas, shapely,
  rasterio, `ultralytics`, `segment-geospatial`, OmniWaterMask, CyFi,
  Earth Engine Python API.
- [ ] **T005** — Authenticate Google Earth Engine access in Colab (your
  account/project with Spain access already set up).
- [ ] **T006** — Design and create the resumability manifest (Drive-backed
  CSV or SQLite): one row per AOI tile, one status column per pipeline
  stage (`imagery`, `layer1`, `layer2`, `layer3`, `layer4`, `fusion`).

## 1. Scaffold prep (plan.md stage 0)

- [x] **T007** — Done: 17,033 EU-Hydro river-line features pulled via
  public ArcGIS REST (`image.discomap.eea.europa.eu/.../EUHydro_RiverNetworkDatabase`)
  for a provisional bbox superset; still needs the precise spatial clip
  to T001's polygon (see T009).
- [x] **T008** (partial, 2026-09-15) — Pulled via IGN's public WFS
  (`servicios.idee.es/wfs-inspire/hidrografia`, `hy-n:WatercourseLink`,
  CC BY 4.0): 61,000 line features for the basin bbox, saved to
  `data/raw/red_hidrografica_watercourses.gpkg`. Hit a 61,000-feature
  safety cap in the pagination loop — there may be more; raise the cap
  and re-pull to confirm completeness before relying on this as final.
  Bonus find in the same WFS: `hy-p:DamOrWeir` (28,774 features
  nationally) — a 5th ground-truth source not yet pulled or merged into
  `ground_truth_guadalquivir.csv`.
- [x] **T009** (resolved 2026-09-15, not the originally-planned way) —
  Decided against re-tiling: the 2,369-tile manifest and the in-progress
  NDWI basin pass stay on the EU-Hydro-only grid, so the completed
  Sentinel-2 pull and DEM chunks aren't discarded. Instead Red
  Hidrográfica is folded into `dedup_ndwi_candidates.py` as a second
  river-line source for the anomalous-widening check only (T030a): it
  gets a fixed default half-width, since it has no Strahler-order field
  to scale by, but still lets small tributaries EU-Hydro's sparser
  network misses count as "normal channel" instead of false-flagging as
  anomalous widening. Any reach missing from *both* networks (e.g. the
  Doñana delta) is still an open gap — no imagery tile exists there at
  all, since tiling itself wasn't touched.

## 2. Ground truth ingestion (plan.md stage 1)

- [x] **T010** — Done: SNCZI presa/embalse shapefiles downloaded manually
  (gis.miteco.gob.es resets automated TLS connections — needed a browser),
  spatial-clipped to the real basin boundary: 495 presas + 492 embalses.
  `DEMARC='GUADALQUIVIR'` field matched the spatial clip exactly (reliable).
- [x] **T011** — Done: Andalucía's IECA/DERA reference dataset (layer
  `T03_12_Presa`, 592 records region-wide), downloaded from
  juntadeandalucia.es (a 95MB GeoPackage bundle — the server dropped
  connections repeatedly under a naive retry; a proper resume-loop that
  re-checks bytes-on-disk before each attempt fixed it and survived an
  overnight network drop cleanly). Spatial-clipped to the basin: 353
  records.
- [x] **T012** — Done: AMBER Barrier Atlas pulled from Figshare (full
  629,955-record CSV), spatial-clipped to the basin: 2,659 records.
  (Confirms `BasinName` text field is unreliable — only 151 had
  "GUADALQUIVIR" tagged explicitly; spatial join was the right call.)
- [x] **T013** — Done: OSM Overpass query for `waterway=weir`, clipped
  to the basin: 409 records (1,217 pulled in the provisional bbox before
  clipping).
- [x] **T014** — Done: SNCZI + AMBER + Andalucía DERA + OSM merged into
  `data/processed/ground_truth_guadalquivir.csv` (4,408 records, all
  WGS84). Stage 1 complete.

## 3. Imagery acquisition (plan.md stage 2)

- [x] **T015** (revised) — PNOA10 confirmed to have zero coverage of the
  Guadalquivir basin (its EE extent is northern/central Spain only, see
  research-brief.md). Switched to Sentinel-2 as primary per FR-002's
  documented fallback; `src/imagery/pull_imagery.py` written using
  direct per-tile download (no Drive API needed) rather than the
  originally-planned Drive export.
- [x] **T016** — Done: probed `tile_000_008` end-to-end (auth, query,
  real GeoTIFF download), verified with rasterio (correct CRS/bounds/
  pixel dimensions) before committing to the full run.
- [x] **T017** — Done: full basin Sentinel-2 pull complete, 2,369/2,369
  tiles, 0 failures, 5.6GB (`data/raw/sentinel2_tiles/`). Ran detached
  (nohup + disown + caffeinate) so it survived independently of any
  single chat session.

## 4. Layer 1 — direct structure detection (plan.md stage 3)

- [x] **T018** — Done: deduped ground truth across sources first (50m
  radius, source-priority SNCZI > Andalucía DERA > AMBER > OSM — found
  813 cross-source duplicates, 4,408 -> 3,595 unique structures), then a
  10x10 grid-stratified sample for geographic spread: 66 for annotation
  + 17 held out (FR-007a), saved to
  `data/processed/layer1_annotation_training_set.csv` and
  `layer1_holdout_set.csv`.
- [x] **T019/T020** (superseded, done 2026-09-16) — Constitution.md's
  2026-09-14 revision already dropped the SAM click-through workflow in
  favor of the micro-pilot's automated color-threshold heuristic
  ("speed now explicitly outweighs the marginal accuracy gain from
  manual annotation") — tasks.md just never got updated to say so.
  `src/layers/generate_layer1_boxes.py` runs that heuristic against the
  66 real PNOA training crops (`data/raw/pnoa_crops/`, already pulled).
  **Real finding**: the raw heuristic produced exactly-full-frame boxes
  for 28/58 (48%) of crops — a qualitatively different failure from
  "the water body is just large" (the micro-pilot's proven run only hit
  this 5/28 times) — visually these are crops with no dam visible at
  all (georeferencing gaps, or barrier types too small to show from
  above), where the color threshold falls back to catching roads/shadow
  across the whole frame. Added an area-fraction rejection (>85% of
  frame -> discard) rather than train on a label saying "the object is
  the entire image." Final clean set: 28/66 crops with a usable box.
- [x] **T021** (done 2026-09-16) — `src/layers/train_layer1.py`:
  YOLOv8n fine-tuned on the 28 clean boxes, 50 epochs (~6 min on this
  hardware). **Held-out recall: 16/17 (94%)** on the untouched holdout
  set (`layer1_holdout_set.csv`, PNOA crops pulled separately to
  `data/raw/pnoa_crops_holdout/`) — better than the micro-pilot's
  proven 11/12, on a more geographically diverse real sample. The one
  miss is a RAMP/BED SILL, a small in-channel structure type expected
  to be hardest to see from above. Some holdout crops get 2-4
  overlapping boxes at varying confidence (loose training-box
  supervision) — fine for a per-crop go/no-go recall check, but
  basin-wide inference (T022) will need real NMS/dedup across tile
  boundaries, not just "did it fire at all."
- [ ] **T022** — Not started at basin scale; a sub-area pilot run
  2026-09-16 found a real, blocking quality problem first. Full-basin
  *coverage* (not just the 83 training/holdout point-crops) at PNOA's
  0.25-0.5m needs real tiling — the existing 5km Sentinel-2 grid would
  be 10,000-20,000px/side per WMS request, and even scoped to the
  EU-Hydro-only river corridor (11,997 km², vs 19,544 km² with Red
  Hidrográfica) that's **115-187GB at native resolution** — too large
  to pull blind. Per an explicit decision to de-risk before committing
  that disk/time, piloted a small real sub-area first instead of
  guessing at a resolution/scope tradeoff:

  - `src/imagery/pull_pnoa_pilot_area.py`: tiled the real river corridor
    (200m buffer) inside a 0.1°×0.1° cell around the basin's densest
    known-dam cluster (36.85-36.95N, -3.95 to -3.85W — 111 real ground
    truth points inside the actual tile coverage, 108 of them OSM
    weirs), at native 0.5m/px, 500m/1000px tiles (a WMS-safe request
    size, confirmed by probing one tile first). 255/259 tiles pulled
    cleanly (0.28GB) — cheap enough to just run rather than estimate.
  - `src/layers/run_layer1_pilot_inference.py`: ran the T021 model
    across all 255 tiles, canonical-point-snapped, deduped within 50m,
    matched against ground truth.

  **Real, unflattering result: 94 detections, only 1 matched ground
  truth within 30m, and distances to the nearest real structure were
  large across the board (mean 948m, median 852m) — not a
  near-miss/tolerance problem like Layer 3's, a genuine false-positive
  problem.** Visually inspected the four highest-confidence detections
  (0.67-0.70 conf): every one is a full-tile box over ordinary
  forest/scrubland with no water or structure anywhere in frame.

  **Root cause, not just a bad run**: T021's 28 training examples were
  all *positive, object-centered* 300m point-crops — the model never
  saw a single true-negative "no barrier here" example during training,
  so on tightly-cropped holdout points (where a barrier is reliably
  somewhere near center) it looks great (16/17 recall), but scanning
  raw, mostly-empty terrain tiles gives it nothing to discriminate
  against and it falls back to the same "box the whole frame" failure
  mode found and partly filtered out of the *training* boxes (T019/T020)
  — except now baked into the model itself, on tiles that were never
  filtered because there's no ground truth to check them against ahead
  of time.

  **Not recommending the full 115-187GB pull on this model.** Real
  fix needed first: add true-negative training examples (empty river-
  corridor crops, no known structure nearby) so the model learns actual
  discrimination, then re-pilot the same sub-area before reconsidering
  full-basin scope. This is exactly what piloting first was for —
  caught before burning the disk/time budget on a model not ready for
  raw-tile scanning.

  **Tried the negative-example fix same session — it didn't work,
  honest result.** Sampled 40 random points along the river network far
  (>500m) from any registry point, pulled crops, and found the sampling
  itself was naively wrong at first: "far from a known dam" doesn't
  mean "no water" (rivers have water everywhere), and worse, the box
  heuristic's own >85%-of-frame degenerate-rejection (from T019/T020)
  meant "no box found" was silently conflating true empty scenes with
  scenes so dominated by a real reservoir that the heuristic rejected
  them outright — the opposite of a negative example. Fixed by
  measuring raw water-pixel fraction directly instead of trusting the
  box heuristic's null result; kept only the 17/40 crops under 5% water
  pixels as verified true negatives. Retrained (28 positive + 17
  negative, same 50-epoch recipe): held-out recall collapsed to 7/17 at
  the original conf=0.25 threshold — recovers to 16/17 at conf=0.05,
  but re-piloting the same sub-area at that lower threshold produced
  *more* raw detections (395 vs 94) with essentially the same
  signal-to-noise ratio (12/395 = 3% within 30m of real ground truth,
  vs 1/94 = 1% before; the overall distance distribution actually got
  slightly worse, mean 1107m vs 948m). 17 negatives against 28
  positives, 50 epochs, was enough to recalibrate the model's confidence
  scale but not enough to teach real discrimination — this needs
  meaningfully more negative examples (matching or exceeding the
  positive count) and likely hard-negative mining from the actual
  false-positive tiles already found, not a quick patch. Leaving this
  here rather than continuing to iterate blindly on model tuning within
  this session; T022 stays not-recommended for a full-basin pull until
  a real fix lands and re-validates against this same pilot area.

## 5. Layer 2 — DEM/hydrological — STOPPED 2026-09-14 (plan.md stage 4)

Fallback invoked per constitution.md after three failed scaling
attempts (5km tiles, 50km chunks, whole-basin mosaic — each ~10x short
of the last, all far below a real river network's expected flow
accumulation) and a negative diagnostic (masking suspected bad
zero-elevation data changed nothing). No reply from Dr. Dai. Data kept
for a future attempt if he or DL-HFCS's authors provide the real
method.

- [x] **T023** — No reply from Dr. Dai; proceeded to blind reproduction.
- [ ] **T024** — Not attempted (time went to the blind-reproduction
  scaling debugging instead); still a live option if Layer 2 is
  revisited.
- [x] **T025** (revised) — PNOA-MDT pulled as 55 contiguous 40km+5km-
  buffer chunks at 25m resolution (not per-tile — see research-brief.md
  finding), via IGN's public WCS. `data/raw/dem_chunks/`.
- [x] **T026** — Implemented flow-accumulation + along-stream step-
  detection (richdem D8). Mechanically works; scaling/data-quality
  issues prevented it from ever seeing a real stream network. Stopped,
  not benchmarked against Dai et al.'s reported numbers.
- [ ] **T027** — Not reached.
- [ ] **T028** — Not reached; the DEM-based stream network idea is
  moot without working flow accumulation.

## 6. Layer 3 — water-signature (plan.md stage 5)

Built as a two-stage pipeline rather than running OmniWaterMask
directly over all tiles (would take ~100hrs on this hardware): fast
NDWI proposes candidates basin-wide, OmniWaterMask confirms each one.
OmniWaterMask needed Python 3.10+ (every version, unlike
earthengine-api) — runs in its own venv (`.venv-owm/`, Python 3.11 via
Homebrew) rather than upgrading the whole project's Python.

- [x] **T029** (revised) — NDWI candidate generation running basin-wide
  (`layer3_water_signature.py`, server-side via Earth Engine
  `reduceToVectors`); OmniWaterMask confirmation built and batched
  (`layer3_confirm_owm.py`, ~20s/candidate after batching + dropping
  unneeded OSM building/road checks).
- [x] **T030a** (new, found 2026-09-14; anomalous-widening fix wired +
  validated 2026-09-15) — River-intersection alone was too loose (a
  plain river-touching test passes every ordinary, un-blocked stretch
  of river, since a river trivially touches its own line everywhere).
  Replaced with `filter_to_anomalous_widening()` in
  `dedup_ndwi_candidates.py`: candidate must extend beyond the river's
  Strahler-order-scaled normal channel width by >400m2 and >30% of its
  area to count as impoundment-like. The function was already written
  2026-09-14 but `__main__` still called the old, since-removed
  `filter_to_river_touching` — a silent no-op-on-crash bug, now fixed.
  Run against the 3,517 candidates generated so far (basin pass still
  in progress): 3,517 -> 601 -> 598 after dedup. Visually validated by
  rendering 6 kept + 6 rejected candidates over their Sentinel-2 RGB
  tile: correctly keeps a clear dendritic reservoir shoreline, correctly
  rejects ordinary river bends and isolated farm ponds near towns. One
  kept candidate (600m2, next to greenhouse/warehouse structures) looks
  like a possible NDWI false positive from reflective rooftops rather
  than real water — an upstream Layer 3 NDWI-generation noise question,
  not a bug in this filter. Red Hidrográfica folded in as a second
  river source 2026-09-15 (see T009): 3,583 -> 589 -> 587 after dedup,
  slightly fewer kept than the EU-Hydro-only run since some previously
  "anomalous" candidates turned out to sit on a real tributary EU-Hydro
  didn't have. The naive version (one global `union_all()` over the
  combined ~78k-segment network) hit the same expensive-full-union trap
  constitution.md already flagged once (19+ min of CPU for no result);
  switched to a local per-candidate union via spatial index instead, and
  the whole filter now runs in ~11s. **Still needed**: the same filter
  on Layer 1's full-basin inference once built (T022 was trained on
  real registry points so isn't affected, but full-basin scanning would
  hit the same problem).
- [x] **T030** (complete 2026-09-16) — Basin-wide NDWI pass finished:
  2,369/2,369 tiles, 0 failed (the mop-up below cleared all of them).
  Confirmation pass finished against the stable final candidate set:
  845 deduped candidates, all scored, 822 confirmed as real water/dam
  signatures. See the network-outage findings below for what it took to
  get here — two real bugs surfaced and fixed along the way, plus one
  operational lesson (a single-shot auto-relaunch isn't enough; the
  monitor needed to retry every check, not just once, after a launch
  attempt silently died to a second network blip and sat idle 6+ hours
  before being caught).

  Two detached jobs ran concurrently (2026-09-15): the basin-wide NDWI
  candidate pass and `layer3_confirm_owm.py`, resumable so confirm
  picks up new candidates as NDWI produces + dedup regenerates them
  rather than waiting for NDWI to finish first.

  A local network outage during this run (DNS resolution failing for
  both `oauth2.googleapis.com`, breaking EE auth, and Overture Maps'
  S3/STAC endpoints) hit both jobs simultaneously and surfaced two
  distinct, real findings:
  - **NDWI job**: 147 tiles marked `failed` during the outage window.
    Not a bug — `get_pending_with_geometry`'s `WHERE {stage} != 'done'`
    already treats `failed` as retriable — but this one continuous
    process loaded its pending list once at launch hours earlier, so it
    won't revisit tiles that failed mid-run. **Needs a rerun of
    `layer3_water_signature.py` once the current pass exhausts its
    original queue** to pick the 147 back up (a fresh invocation
    requeries the manifest, which will include them).
  - **Confirm job**: a real, serious bug, not just a network hiccup.
    OmniWaterMask handles one scene's target-build failure (e.g. from
    that same Overture outage) by logging an error and skipping it —
    no exception raised, no padding of its return list. The confirm
    script was matching outputs back to inputs by `zip()` position, so
    every result *after* a mid-batch skip got silently attributed to
    the wrong candidate. A run that printed a clean "Confirmed 400/557"
    could have been silently wrong for an unknown fraction of those 400.
    Fixed by matching outputs to inputs by filename instead of
    position. Rolled `layer3_confirmed.jsonl` and
    `layer3_confirm_progress.jsonl` back to the last verified-safe
    checkpoint (38 entries, from before this run) rather than trying to
    guess which of the 400 survived unaffected — the discarded run's
    output is backed up locally (not committed, data/ is gitignored).
    Relaunched with the fix; 44/587 confirmed as of the relaunch.
  - **Third issue, found later the same run**: Overture's S3 endpoint
    (OmniWaterMask's default vector-source for the water target) hung
    the confirm job twice — 8s+ for a bare request when Google's own
    endpoints answered in <1s, and neither OmniWaterMask's internal
    retry/timeout nor a later relaunch (once even after the network had
    otherwise recovered) reliably bounded the wait; needed a manual
    kill each time. Fixed at the root by switching `vector_source` from
    the default `"overture"` to `"osm"` (OmniWaterMask's own error
    message names this as the intended workaround) — Overpass hit one
    transient 504 afterward but retried with a bounded 55s wait and
    succeeded, instead of hanging indefinitely.

## 7. Layer 4 — ecological/algae (plan.md stage 6)

- [x] **T031** — Done: CyFi installed in `.venv-owm` (needs Python
  3.10+, same as OmniWaterMask). One-time ~2GB land cover map download
  cached; batch mode (`layer4_algae.py`) tested on all 63 micro-pilot
  ground-truth points: 62/63 got predictions (61 high, 1 moderate
  severity — uniformly high, consistent with real Andalucían
  reservoirs in June/peak algae season; confirms this layer won't
  discriminate much *among* confirmed water bodies, only water vs. not,
  matching its planned role as a confirming signal, not primary).
- [ ] **T032** — Pending full-basin Layer 1/3 candidates to confirm
  against (not an independent search, per plan.md).

## 8. Fusion, matching, classification (plan.md stages 7-9)

- [x] **T033** (code done 2026-09-15, not yet run on final data) —
  `src/fusion/fuse_candidates.py`: union-find clustering within 50m,
  keyed to whichever layers are registered in `LAYER_NORMALIZERS` (only
  `layer3_water_signature` has real data right now — Layer 1 untrained,
  Layer 2 stopped, Layer 4 confirms rather than proposes). Also
  implements plan.md's canonical-point rule (every layer reduces to
  where the detection crosses the river centerline, not a raw blob
  centroid) via new `src/layers/river_network.py`, shared with
  `dedup_ndwi_candidates.py`'s river loading.
- [x] **T034** (code done 2026-09-15) — Wired the existing
  `match_ground_truth.py` into the fusion script (spatial join, 30m,
  locked tolerance). **Real finding, not yet resolved**: smoke-tested
  against the 28 Layer 3 candidates confirmed so far, 0 matched within
  30m even after canonical-point snapping. Splits into two distinct
  causes: (a) candidates west of lon -6.2 (the Doñana delta/estuary
  region) are 5-14km from the nearest ground truth — likely the
  already-documented EU-Hydro delta mapping gap producing false
  positives there, not real missed matches; (b) candidates elsewhere in
  the basin (well short of the delta) still land 137-898m from a real
  nearby registry point even after snapping to the nearest river-network
  point — canonical-point projection alone isn't closing the gap to
  FR-005's locked 30m tolerance. Left the tolerance as spec'd rather
  than quietly loosening a locked requirement; per constitution
  principle 1 this needs an honest look (likely at T042's false-positive
  spot-check stage) once there's enough real data to see whether 137-898m
  is a consistent pattern or noise from this being a 28-candidate sample.
- [x] **T035** (code done 2026-09-15) — `classify()` in the same file:
  `new-confirmed` if ≥2 layers agree within the fusion radius or a
  single layer's confidence ≥0.85, else `new-uncertain`. On the current
  28-candidate smoke test: 16 new-confirmed, 11 new-uncertain, 0 known
  (see T034's caveat — some of these "new" candidates are probably
  actually known dams the point-alignment gap is hiding).

## 9. Removed-barrier check (plan.md stage 12)

- [ ] **T036** — Depends on T034. For unmatched ground-truth records
  (no current-day candidate reconfirmed them), check the current
  imagery/water-signature layer at that point for an impoundment
  signature; flag `possibly-removed` if genuinely absent.

## 10. Outputs (plan.md stage 10)

- [x] **T037** (real full-basin run 2026-09-16) —
  `src/output/generate_outputs.py` writes `pilot_output.csv` from
  `fused_candidates.csv`: lat, lon, layers, n_layers, confidence +
  per-layer breakdown, match_status, matched source/id/distance,
  source_refs (FR-008 + constitution.md principle 5 provenance). Real
  result against the complete, final Layer 3 dataset (822 confirmed
  candidates -> 816 fused): **24 known, 62 new-confirmed, 730
  new-uncertain**. This is a Layer-3-only result (Layer 1 untrained,
  Layer 2 stopped) — see T034's still-open point-alignment finding
  before reading the `known` count as final, and see the note below on
  why `new-uncertain` is so large with only one active layer.
- [x] **T038** (real full-basin run 2026-09-16) — same script writes
  `review_uncertain.csv` with an `ee_thumbnail_url` per row (FR-013),
  now for all 730 real new-uncertain rows (730 individual Earth Engine
  calls, ~1h40m wall time, 0 failures). Two real bugs found and fixed
  while probing a single thumbnail before generating the first batch
  (constitution.md principle 3): a fixed min/max (0-3000, the usual S2
  true-color preset) rendered this AOI's actual reflectance (~150-400)
  as solid black; a shared min/max across all three bands then produced
  a green-wash false-color mess once the range was fixed. Settled on a
  400m buffer (wide enough to show riverbank/land context, not just a
  mostly-water crop) with a per-band 2nd-98th-percentile stretch
  computed from that same AOI. Confirmed publicly fetchable with no
  auth (curl, HTTP 200). Spot-checking one of the early real thumbnails
  turned out to be a genuine, useful catch: an "uncertain" candidate
  near the Doñana coast that's visibly an ocean beach town, not a river
  structure at all — concrete evidence for T034's Doñana-delta-gap
  hypothesis, and a real demonstration that the review step does its
  job.

  **Why new-uncertain is 730/816 (89%) on this run**: FR-005a's
  new-confirmed rule needs either 2+ independent layers agreeing, or a
  single layer at confidence >=0.85 — with only Layer 3 active so far,
  "2+ layers" is structurally impossible, so every candidate below
  0.85 water_frac defaults to uncertain regardless of how real it looks.
  This isn't a sign the pipeline is unreliable; it's the expected shape
  of a single-layer result, and exactly why the human-review tier
  (constitution.md locked decision) exists. Expect this fraction to
  drop once Layer 1 and/or Layer 4 contribute real candidates to fuse
  against.
- [ ] **T039** — Depends on T036 (not reached — T036 itself not
  started).
- [x] **T040** (done 2026-09-15) — `ATTRIBUTION.md` written. SNCZI and
  Andalucía DERA licenses both still flagged unconfirmed (matches T002,
  open) — documented honestly rather than assumed, with an explicit
  "don't ship publicly until these two are closed" note.

## 11. Metrics (plan.md stage 11)

- [ ] **T041** — Depends on T037. Compute precision/recall of `known` +
  `new-confirmed` against the Andalucía inventory, excluding T018's
  annotation set entirely (FR-007a).
- [ ] **T042** — Manually spot-check a random sample of apparent false
  positives against source imagery; report registry-gap vs. confirmed
  model-error counts separately (FR-007b).
- [ ] **T043** — Write `results.md`: precision/recall, basin coverage,
  actual free-tier compute time/quota used.

## 12. Review and gate

- [ ] **T044** — Manually review `review_uncertain.csv` (Google Maps/
  Earth Engine thumbnails); record confirm/reject per row.
- [ ] **T045** — Check the phase against plan.md's exit criteria before
  starting the Spain-wide phase; document the go/no-go decision.
