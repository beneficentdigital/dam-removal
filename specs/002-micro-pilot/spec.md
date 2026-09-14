# Feature Spec: Micro-Pilot — Proof of Method

**Not a new phase** — a deliberately tiny slice of phase 1
([../001-guadalquivir-pilot/](../001-guadalquivir-pilot/)), reusing all of
its ground truth, boundary, and infrastructure. Purpose: get the full
detection-to-validation loop working end-to-end on a small, real area in
a day or so, to prove the method works before investing days of build
time on the full basin.

## Why

Building all four layers across the full 2,369-tile basin before knowing
whether the approach works at all is a multi-day-plus commitment with a
real chance of failure at any layer. A tight area with rich cross-source
ground truth lets us find out fast, cheaply, and reuse everything learned
(code, bug fixes, annotation workflow) when scaling back up to the full
basin afterward.

## Scope

- **Area**: a 15km x 15km box near Sevilla province, EPSG:25830 bounds
  `287195, 4163965` to `302195, 4178965` (lat ~37.60-37.72, lon ~-5.41
  to -5.26) — the densest cross-source ground-truth cluster found in the
  full basin's merged data (86 records: 40 SNCZI, 25 AMBER, 20 Andalucía
  DERA, 1 OSM).
- **Layers attempted**: Layer 1 (direct detection, real PNOA) and Layer 3
  (water-signature/NDWI) — the two layers with no external dependency
  and no unproven research-reproduction risk. Layer 2 (DEM) and Layer 4
  (algae) are out of scope here, consistent with the full pilot's own
  documented fallback for Layer 2.
- **Deliverable**: a small candidate CSV for this box, matched against
  the 86 known records, with a rough precision/recall figure — not
  polished, but real and end-to-end.

## Out of scope

- Anything requiring Dr. Dai's reply or DEM reproduction (Layer 2).
- Full-basin tiling/inference — that's phase 1 proper, after this proves
  viable.
- Publishable rigor on the precision/recall figure (small-sample caveats
  apply) — this is a feasibility check, not the pilot's real result.
