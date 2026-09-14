# Implementation Plan: Guadalquivir Basin River-Barrier Detection Pilot

Technical design for [spec.md](./spec.md). Governed by
[../../constitution.md](../../constitution.md).

## Stack

- **Google Earth Engine** (Python API, called from Colab) — imagery access
  (PNOA, Sentinel-2 fallback), DEM access (PNOA-MDT), raster ops at scale.
- **Google Colab free tier** — model inference/fine-tuning. Drive-mounted
  for persistent storage across sessions (free tier sessions disconnect
  after ~90min idle / 12hr max — see Risks).
- **Python geospatial stack** — geopandas/shapely/rasterio for vector and
  raster handling; `ultralytics` (YOLOv8-OBB) for the RBOD-derived model;
  OmniWaterMask and CyFi as their published packages.
- **Storage** — Google Drive for tile manifests, checkpoints, model
  weights, and intermediate outputs. No paid storage/compute (per locked
  compute-budget decision).

## Pipeline stages

**0. Scaffold prep**
Get the Guadalquivir basin boundary (source TBD — first task is to inspect
EU-Hydro's own structure and candidate boundary sources, e.g. Confederación
Hidrográfica del Guadalquivir vs. a WFD river-basin-district shapefile,
before picking one). Clip EU-Hydro river lines to that boundary. Buffer
each reach (proposed: 200m either side — wide enough to catch a dam's
reservoir/structure without pulling in unrelated terrain) to define the
area of interest (AOI). Split the AOI into tiles small enough for one
Earth Engine/Colab unit of work each — this tiling is also the resumability
unit (stage 5).

**Spain-specific supplement**: also pull IGN's Red Hidrográfica network
for the basin and/or derive a stream network from PNOA-MDT flow
accumulation (a byproduct of stage 4's method). Union this with the
clipped EU-Hydro lines before buffering/tiling, so small tributaries
EU-Hydro's pan-European scaffold omits aren't structurally excluded from
detection. This supplement is Spain-only — phase 3 (Europe) falls back to
EU-Hydro alone in countries without an equivalent national network.

**1. Ground truth ingestion**
Pull SNCZI (shapefile), Andalucía regional inventory, AMBER Barrier Atlas
(filtered to the basin), and an OSM Overpass extract (`waterway=weir`
within the basin boundary). Normalize every source to one schema:
`source, source_id, lat, lon (WGS84), barrier_type, raw_attributes`. This
is the join target for matching (stage 6) and the basis for precision/
recall (stage 7).

**2. Imagery acquisition**
Pull PNOA imagery per AOI tile via Earth Engine (`Spain/PNOA/PNOA10` —
confirmed available, but the EE mirror only covers flights through 2018;
check currency against IGN's own download center before relying on it for
current-state detection, e.g. the removed-barrier check in stage 12).
Fall back to Sentinel-2 where PNOA coverage/resolution/currency is
insufficient. Record per-tile status (pending / done / failed) in a
manifest — this is what makes stage 2 resumable rather than restarted
whole.

**3. Layer 1 — Direct structure detection**
Annotate (draw bounding boxes around) ~50-100 known Guadalquivir dams in
PNOA imagery, using stage-1 ground truth to know where to look — a GPS
point alone isn't a training label; the model needs a box drawn around
the actual structure in the image. Use `segment-geospatial` (samgeo,
Meta's Segment Anything Model for geospatial data) to propose each box
from a point click, with a human verifying/adjusting every one — this
keeps the human-verified accuracy the "maximum accuracy" decision calls
for, while cutting the manual effort of drawing every box from scratch.
Use these to fine-tune RBOD's best architecture (YOLOv8x-OBB) or adapt
Sun et al.'s published checkpoint. Run inference per tile. Output:
oriented bounding box → centroid lat/lon + confidence.

**Coordinate-quality filter** (found during build, 2026-09-12): spot-
checking real PNOA crops for the 66-dam training set showed a
meaningful fraction with no visible structure/water at all within the
150m crop — across all sources, not just AMBER/OSM (an SNCZI-registered
"embalse" record showed a farmstead, no water). Before annotating,
visually confirm each crop actually shows a structure; skip and replace
from the deduped pool (select_annotation_set.py) rather than forcing a
box onto an empty or wrong-looking crop. Widen the buffer (currently
150m) first if the structure looks like it's just outside frame.

Hold out a portion of the annotated set (proposed: 20%, or all of it if
the count stays near 50) from fine-tuning entirely, so it can serve as an
independent check — and, critically, none of the annotated set is used
when computing the basin-wide precision/recall in stage 11 (FR-007a).
Fine-tuning on examples and then "measuring" against those same examples
would just report how well the model memorized them.

**Canonical point rule** (resolves the spec's cross-layer point-alignment
edge case): every layer reduces its output to the same kind of point
before fusion — where the detected structure/impoundment crosses the
river centerline, not a bounding-box or blob centroid. For Layer 1
specifically, project the OBB centroid onto the nearest river-line point
rather than using it directly, so a barrier the width of its reservoir
doesn't shift the reported coordinate away from the channel.

**4. Layer 2 — DEM/hydrological — STOPPED 2026-09-14, see constitution.md**
Reproduce the Yellow River check-dam paper's method (flow accumulation +
valley-shape analysis) against PNOA-MDT for the same AOI tiles, per the
outreach-first approach with Dr. Wen Dai (see Risks). In parallel,
evaluate DL-HFCS (Deep Learning + Hydrological Feature Constraint
Strategies, Remote Sensing 2025, DOI 10.3390/rs17071194) as a second
candidate — a YOLOv5s + hydrological-constraint approach validated across
multiple regions rather than one basin, which lowers transferability risk
relative to the Yellow River method. Neither has confirmed public code;
treat this whole layer as the plan's highest implementation risk (see
Risks). Output: candidate point + confidence proxy.

**5. Layer 3 — Water-signature**
Run OmniWaterMask (NDWI + DL + OSM water bodies) over the AOI to flag
river-line pooling/widening consistent with an impoundment. Output:
candidate point + confidence.

**6. Layer 4 — Ecological/algae**
Run CyFi over Sentinel-2 for the AOI as a confirming pass — flag algal
buildup near existing candidates from stages 3–5, rather than as an
independent discovery layer (per the brief, this is a confirming signal,
not primary).

**7. Candidate fusion**
Merge detections from stages 3–6 within a 50m fusion radius into one
candidate record, keeping a list of which layer(s) contributed and each
one's confidence.

**8. Ground-truth matching**
Spatial-join fused candidates against stage-1 ground truth within 30m
(locked tolerance). Label `known` on match.

**9. Confirmed vs. uncertain rule** *(resolves the spec's open threshold
question)*
For unmatched candidates:
- `new-confirmed` if **either** (a) ≥2 independent detection layers agree
  within the 50m fusion radius, **or** (b) a single layer flags with
  confidence ≥0.85.
- `new-uncertain` otherwise (single layer, confidence <0.85).

This rule is a starting point, not fixed — expect to tune the 0.85
threshold once real pilot detections exist to look at.

**10. Output generation**
- `pilot_output.csv` — every candidate: lat, lon (WGS84), detection
  method(s), confidence, match status, matched ground-truth ID where
  applicable, imagery date. This is the shareable dataset — the count
  answering "how many dams" comes only from `known` + `new-confirmed`
  rows here.
- `review_uncertain.csv` — the `new-uncertain` subset only, each row
  including an Earth Engine static thumbnail URL for that coordinate
  (chosen over a Google Maps link so the review image is tied to the
  actual source imagery/date used for detection) so you can review
  without needing GEE/Colab access, per FR-013.
- `ATTRIBUTION.md` — per FR-014, credits and license terms for every
  source used (PNOA/IGN, SNCZI/MITECO, AMBER Atlas — CC-BY-4.0 confirmed
  — and the Andalucía inventory, whose license needs confirming before
  this ships publicly; see Risks).

**11. Metrics**
Compute precision/recall of `known` + `new-confirmed` detections against
the Andalucía inventory (the strongest local ground truth), excluding the
Layer-1 annotation set per FR-007a. Before reporting the precision figure,
manually spot-check a random sample of apparent false positives against
source imagery (FR-007b) — the Andalucía inventory has its own errors and
gaps, so an "extra" detection may be a registry omission rather than a
model mistake; report both counts (raw disagreement vs. confirmed model
error) rather than collapsing them into one number. Write up in
`results.md` alongside basin coverage stats and free-tier compute time
actually used (this last figure informs whether Spain-wide needs paid
compute, ahead of that decision).

**12. Removed-barrier check (auxiliary, not counted)**
For each stage-1 ground-truth record with no matching current-day
candidate (i.e. a registry entry the detection layers didn't reconfirm),
check the current imagery/water-signature layer at that point for a
barrier/impoundment signature. If it's genuinely absent, flag the record
as `possibly-removed` in a separate `removed_barriers.csv` (source,
location, last-confirmed date/imagery). This output is explicitly
excluded from the pilot's headline count and from the precision/recall
in stage 11 — it exists to feed a likely future project mapping the
impact of dam removal, not to answer "how many dams."

## Resumability design

A single manifest (CSV or SQLite in Drive) keyed by tile ID tracks status
per stage (`imagery: done`, `layer1: pending`, ...). Every stage checks the
manifest before processing a tile and skips completed work. This is what
lets a Colab disconnect or a multi-day run pick back up rather than
restart — required by constitution principle 3.

## Risks

| Risk | Mitigation |
|---|---|
| DEM/hydrological method (stage 4) has no *public* code, and Yellow River "check dams" (small earthen silt-trapping structures in ephemeral Loess Plateau gullies) may be physically different enough from Guadalquivir river weirs/azudes that the method doesn't transfer at all | **Before** starting build work on this layer, email the paper's corresponding author, **Dr. Wen Dai** (wen.dai@nuist.edu.cn, Nanjing University of Information Science and Technology — Dai et al. 2023, *Combining Deep Learning and Hydrological Analysis for Identifying Check Dam Systems... in the Yellow River Basin*, PMC10002097), asking for: (1) access to any private code (GitHub repo, Zenodo/OSF deposit, or shared Drive/Colab — "no public code" doesn't mean no code), (2) the DEM resolution / flow-accumulation threshold / OBIA segmentation parameters the paper omits, (3) his own validation data (Jiuyuangou watershed) as a benchmark to test a reimplementation against before trusting it on new terrain, and (4) his honest read on whether the method generalizes to perennial-river weirs rather than ephemeral-gully check dams. Only fall back to blind reproduction from the paper alone if he doesn't respond. If neither path works out in reasonable time, report the pilot as a documented 3-layer result rather than blocking indefinitely. |
| RBOD trained on Google Earth basemap imagery, not PNOA — generalization unverified, and the brief notes RBOD over-represents warm-temperate zones (Mediterranean untested) | Validate fine-tuned model against a small hand-labeled PNOA subset before trusting full-basin inference |
| Colab free-tier session limits (idle disconnect, 12hr cap) | Manifest-based resumability (above); checkpoint after every tile, not after every stage |
| Earth Engine compute quota on a whole-basin pull | Tiling scoped to buffered river lines only (stage 0), never the full basin bounding box |
| CRS mismatches (SNCZI in ETRS89, others variable) | Normalize every source to WGS84 at ingestion (stage 1), before any spatial join |
| Andalucía regional inventory's redistribution license is unconfirmed — the whole point of this project is a *shareable* dataset, so this could block publishing even after everything else works | Confirm the license when pulling the data in stage 1 (AMBER is confirmed CC-BY-4.0, SNCZI/PNOA are open under Spain's public-sector reuse law with attribution — Andalucía is the one gap). If it turns out to be restrictive, the CSV can still report match status against it without republishing the underlying records themselves |
| Reusing Layer-1 fine-tuning examples when computing pilot precision/recall would inflate the reported accuracy | Explicit held-out split (stage 3) and exclusion from stage 11's evaluation set (FR-007a) |

## Exit criteria (gate to phase 2 — Spain-wide)

Per constitution principle 6, moving to the Spain-wide run requires:
1. All three remaining layers (Layer 2 stopped, see constitution.md) run
   across the full Guadalquivir basin scope.
2. Precision/recall computed and written up against the Andalucía inventory.
3. `pilot_output.csv`, `review_uncertain.csv`, and `removed_barriers.csv`
   produced and shareable.
4. At least one pass of manual review completed on `new-uncertain`.
5. Actual free-tier compute time/quota usage documented, to inform whether
   Spain-wide can stay free-tier or needs the "willing to pay modestly"
   escalation already agreed in the constitution.
