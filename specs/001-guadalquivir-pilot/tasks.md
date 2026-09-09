# Tasks: Guadalquivir Basin River-Barrier Detection Pilot

Actionable breakdown of [plan.md](./plan.md). Ordered by dependency;
`[P]` marks tasks that can run in parallel with the one(s) above them.
Long-running steps note the resumability/probing approach from
constitution principle 3.

## 0. Setup

- [ ] **T001** — Decide the Guadalquivir basin boundary source: compare
  the Confederación Hidrográfica del Guadalquivir district boundary
  against a WFD river-basin-district shapefile once both are in hand;
  pick one and record the choice (resolves spec.md's deferred open
  question).
- [ ] **T002** `[P]` — Verify the Andalucía regional inventory's
  redistribution license (email Agencia Andaluza del Agua/REDIAM if not
  stated on the download page). Long lead time, doesn't block building —
  start it now, resolve before publishing (plan.md Risks).
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

- [ ] **T007** — Depends on T001. Pull EU-Hydro river lines and clip to
  the basin boundary.
- [ ] **T008** `[P]` — Pull IGN's Red Hidrográfica network for the basin
  (Spain-specific hydrography supplement, constitution locked decision).
- [ ] **T009** — Union T007 + T008, buffer 200m either side, split into
  AOI tiles, populate the manifest (T006) with one row per tile.

## 2. Ground truth ingestion (plan.md stage 1)

- [ ] **T010** `[P]` — Pull SNCZI shapefile for the basin; normalize to
  `source, source_id, lat, lon (WGS84), barrier_type, raw_attributes`.
- [ ] **T011** `[P]` — Pull the Andalucía regional inventory; normalize
  to the same schema (proceed even if T002's license check is still
  pending — needed for detection either way).
- [ ] **T012** `[P]` — Pull AMBER Barrier Atlas from Figshare, filter to
  the basin, normalize.
- [ ] **T013** `[P]` — Query OSM Overpass for `waterway=weir` within the
  basin boundary, normalize.
- [ ] **T014** — Merge T010–T013 into one `ground_truth.csv`/`.gpkg`, all
  in WGS84. This is the join target for every later matching step.

## 3. Imagery acquisition (plan.md stage 2)

- [ ] **T015** — Write the Earth Engine pull script for `Spain/PNOA/
  PNOA10` per AOI tile; check the collection's actual date coverage
  against IGN's own download center to confirm currency.
- [ ] **T016** — Probe the single worst-case tile (largest/most complex
  reach) end-to-end before committing to a full run, per past experience
  that this catches scaling problems early.
- [ ] **T017** — Run the full imagery pull across all AOI tiles, writing
  per-tile status to the manifest as each completes; must be safely
  restartable if a Colab session disconnects mid-run.

## 4. Layer 1 — direct structure detection (plan.md stage 3)

- [ ] **T018** — Select 50-100 known Guadalquivir dams from
  `ground_truth.csv` for annotation, spread across the basin rather than
  clustered; set aside ~20% of them as a held-out set used only for
  evaluation, never for fine-tuning (FR-007a).
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

## 5. Layer 2 — DEM/hydrological (plan.md stage 4)

- [ ] **T023** — Depends on T003's reply (or a time-box expiring without
  one — see plan.md Risks). Incorporate whatever Dr. Dai shares (code,
  parameters, validation data, transferability opinion) into the
  approach; if no reply, proceed to blind reproduction from the paper.
- [ ] **T024** `[P]` — In parallel, evaluate DL-HFCS (DOI 10.3390/
  rs17071194) as a second candidate for this layer.
- [ ] **T025** — Pull PNOA-MDT for the basin.
- [ ] **T026** — Implement the flow-accumulation/valley-shape method
  (from whichever of T023/T024 pans out); if validation data was
  obtained, benchmark the reimplementation against the source paper's
  reported numbers before trusting it on Guadalquivir data.
- [ ] **T027** — Run Layer 2 across all tiles, applying the canonical
  point rule to each output.
- [ ] **T028** — As a byproduct, derive a DEM-based stream network from
  the flow-accumulation step; reconcile with T008's Red Hidrográfica
  supplement (cross-check, don't just discard either).

## 6. Layer 3 — water-signature (plan.md stage 5)

- [ ] **T029** — Set up OmniWaterMask (NDWI + OSM water bodies) over the
  AOI tiles.
- [ ] **T030** — Run Layer 3, flagging river-line pooling/widening;
  canonical point rule applied.

## 7. Layer 4 — ecological/algae (plan.md stage 6)

- [ ] **T031** — Set up CyFi over Sentinel-2 for the AOI.
- [ ] **T032** — Depends on T030 (and T022/T027 for candidate locations
  to confirm against). Run CyFi as a confirming pass near existing
  candidates, not as an independent search.

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
