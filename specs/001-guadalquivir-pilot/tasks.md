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
- [ ] **T009** — Union T007 + T008 (once confirmed complete), buffer
  200m either side, split into AOI tiles. **Not done** — the existing
  2,369-tile manifest and all Sentinel-2/DEM pulls so far were built
  from EU-Hydro alone; redoing this with the denser network would
  change the tile grid. Decide whether to redo the AOI with the fuller
  network or treat Red Hidrográfica as a river-line source for the
  Layer 3 anomalous-widening fix (spec.md FR-015) without re-tiling.

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
- [ ] **T019** — Set up a `segment-geospatial` (SAM) assisted annotation
  workflow: click each selected dam's location, review/adjust the
  proposed box.
- [ ] **T020** — Depends on T019. Annotate the training portion of T018's
  set.
- [ ] **T021** — Fine-tune RBOD's YOLOv8x-OBB (or adapt Sun et al.'s
  checkpoint) on the annotated training set.
- [ ] **T022** — Run Layer 1 inference across all imagery tiles; project
  each detection's centroid onto the nearest river-line point (canonical
  point rule, plan.md stage 3/7) rather than reporting the raw centroid.

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
- [x] **T030a** (new, found 2026-09-14) — River-intersection filter
  (FR-015): only 23-35% of raw NDWI candidates actually touched a real
  river line even at 100m tolerance — the rest were disconnected ponds/
  irrigation reservoirs within the 200m AOI buffer but not on the river
  itself. Added to `dedup_ndwi_candidates.py` (30m tolerance, spatial
  join — not a full river-network union, which took 19+ min of CPU for
  no result). Cuts the candidate set ~3.5x as a side effect (3093 ->
  870 on the partial basin run so far). **Still needed**: the same
  filter on Layer 1's full-basin inference once built (T022 was
  trained on real registry points so isn't affected, but full-basin
  scanning would hit the same problem).
- [ ] **T030** — In progress: NDWI pass running basin-wide (detached,
  monitored); confirmation pass to follow once it completes and
  candidates are deduped + river-filtered (T030a).

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

- [ ] **T033** — Depends on T022, T027, T030, T032. Implement candidate
  fusion: merge detections within a 50m radius into one record per
  physical structure, keeping each contributing layer + its confidence.
- [ ] **T034** — Depends on T014, T033. Spatial-join fused candidates
  against ground truth within 30m; label `known` on match.
- [ ] **T035** — Implement the `new-confirmed`/`new-uncertain` rule (≥2
  layers agree within 50m, or single-layer confidence ≥0.85; else
  uncertain) per plan.md stage 9 and FR-005a.

## 9. Removed-barrier check (plan.md stage 12)

- [ ] **T036** — Depends on T034. For unmatched ground-truth records
  (no current-day candidate reconfirmed them), check the current
  imagery/water-signature layer at that point for an impoundment
  signature; flag `possibly-removed` if genuinely absent.

## 10. Outputs (plan.md stage 10)

- [ ] **T037** — Depends on T035. Generate `pilot_output.csv` (known +
  new-confirmed + new-uncertain, full schema per FR-008).
- [ ] **T038** — Generate `review_uncertain.csv` with an Earth Engine
  thumbnail URL per row (FR-013).
- [ ] **T039** — Depends on T036. Generate `removed_barriers.csv`
  (auxiliary, excluded from the headline count).
- [ ] **T040** — Depends on T002 (or its time-box). Write
  `ATTRIBUTION.md` covering every source's license (FR-014).

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
