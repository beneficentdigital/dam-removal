# Feature Spec: Guadalquivir Basin River-Barrier Detection Pilot

**Phase 1 of 3** — Guadalquivir basin (pilot) → all of Spain → Europe,
country by country. This spec covers phase 1 only. See
[../../constitution.md](../../constitution.md) for the principles gating
each phase transition, and [../../research-brief.md](../../research-brief.md)
for the full research behind these decisions.

## Why

No reliable, geolocated count of river barriers (dams, weirs/azudes) exists
for Spain. Registries range from ~5,100 to ~29,882 recorded structures;
field-survey extrapolation suggests ~171,203 — but that number has no GPS
coordinates behind it. This project builds the pipeline to close that gap,
starting with the Guadalquivir basin because it has the strongest existing
ground truth (Agencia Andaluza del Agua + CEDEX + REDIAM combined inventory,
2022, includes azudes) to validate detections against.

## Scope: what counts as a barrier

Adopting RBOD's taxonomy minus groynes (which deflect flow from one bank
rather than obstructing/impounding it, so they aren't a "barrier" in the
sense this project cares about):

- **In scope**: dams, weirs/azudes, sluices, locks — any artificial
  in-channel structure that impounds or measurably obstructs streamflow
  across the channel.
- **Out of scope**: bridges, culverts that don't impound water, fords/
  causeways, natural rapids or rock outcrops, and bank-attached
  river-training structures that don't span the channel.

This matters most for `new-confirmed`/`new-uncertain` candidates, which
have no ground-truth record to inherit a type from — a detection layer's
output has to be checked against this definition, not accepted just
because something showed up at that location.

## Primary user story

A Dam Removal Europe researcher runs the pipeline against the Guadalquivir
basin and receives a downloadable CSV of candidate barrier locations. Each
row is traceable: which detection method(s) flagged it, how confident the
pipeline is, and whether it matches a barrier already in SNCZI, AMBER, the
Andalucía inventory, or OSM — or whether it's a genuinely new detection.
Alongside the CSV, the researcher gets a real precision/recall figure for
the basin, computed against the Andalucía ground truth.

## Acceptance scenarios

1. **Given** EU-Hydro river-line geometry clipped to the Guadalquivir basin
   boundary, **when** the pipeline runs, **then** all detection processing
   is scoped to those lines (plus a reasonable buffer), not scanned
   blindly across raster tiles.
2. **Given** PNOA (or Sentinel-2 fallback) imagery over the scoped area,
   **when** the direct structure-detection layer runs, **then** it outputs
   candidate barrier locations, each with a confidence score.
3. **Given** a set of candidates from one or more detection layers, **when**
   two candidates represent the same physical structure, **then** they are
   merged into a single record rather than reported as duplicates.
4. **Given** a candidate list, **when** matched against SNCZI, AMBER, the
   Andalucía inventory, and OSM, **then** each candidate is labeled
   `known` (matches an existing record within 30m), `new-confirmed` (no
   match, flagged with high confidence), or `new-uncertain` (no match, but
   the pipeline isn't confident enough to call it — routed for manual
   human review rather than auto-classified either way).
5. **Given** a completed pilot run, **when** the output CSV is opened in a
   standard spreadsheet or GIS tool, **then** it contains, at minimum: lat,
   lon (WGS84), detection method(s), confidence score, match status, and
   the matched ground-truth record ID where applicable.
6. **Given** the completed run, **when** results are compared to the
   Andalucía regional inventory, **then** the pipeline reports precision
   and recall for the basin — whatever those numbers turn out to be.
7. **Given** free-tier Earth Engine/Colab quotas, **when** the pilot runs,
   **then** it completes (possibly across multiple resumed sessions)
   without requiring paid compute.

## Edge cases

- Barriers on tributaries too small to appear in EU-Hydro's current line
  network — the scaffold may itself be incomplete.
- Cloud/shadow gaps in PNOA/Sentinel-2 coverage over parts of the basin.
- Coordinate reference system mismatches (SNCZI in ETRS89, EU-Hydro and
  detection outputs in whatever CRS the tooling defaults to) — must be
  standardized before matching or CSV export.
- False positives from structures that look like barriers but aren't
  (bridges, fords, culverts).
- Two detection layers disagreeing on the same location — needs a defined
  rule for combining confidence, not silent preference for one layer.
- River reaches that sit on the Guadalquivir basin boundary and are shared
  with a neighboring basin.
- The Andalucía regional inventory's redistribution license hasn't been
  confirmed (AMBER Atlas is confirmed CC-BY-4.0; SNCZI and PNOA are open
  under Spain's public-sector reuse law with attribution) — needs
  checking before the output CSV is shared publicly.
- Different detection layers describe a barrier's location differently —
  a bounding-box centroid (Layer 1), a DEM-derived "dam-controlled area"
  (Layer 2), a water-signature pooling region (Layer 3) — without a
  shared convention for which point represents "the barrier," fusion
  (merging detections of the same structure) could misalign even when
  every layer correctly detected it.

## Functional requirements

- **FR-001**: Detection processing MUST be scoped to EU-Hydro river-line
  geometry intersecting the Guadalquivir basin (plus buffer), never to
  whole raster tiles scanned without a river-location prior.
- **FR-002**: The pipeline MUST acquire PNOA aerial imagery for the scoped
  area via Google Earth Engine, falling back to Sentinel-2 where PNOA
  coverage or resolution is insufficient.
- **FR-003**: The pipeline MUST run at least one direct, image-based
  structure-detection model over the scoped imagery, producing candidate
  barrier locations with a confidence score each.
- **FR-004**: The pipeline MUST ingest existing ground-truth barrier
  records for the pilot area from SNCZI/MITECO, the Andalucía regional
  inventory, the AMBER Barrier Atlas, and OSM `waterway=weir` tags.
- **FR-005**: Each candidate MUST be matched against ground-truth records
  by spatial proximity within 30 meters and labeled `known`,
  `new-confirmed`, or `new-uncertain`.
- **FR-005a**: A candidate MUST be labeled `new-uncertain` (rather than
  `new-confirmed`) whenever it has no ground-truth match AND either (a)
  only one detection layer flagged it, (b) its confidence is below the
  threshold set in the plan, or (c) detection layers disagree on it.
  `new-uncertain` records MUST NOT be silently promoted to `new-confirmed`
  or discarded — they are a distinct, intentional output.
- **FR-006**: Candidates representing the same physical barrier — whether
  from the same or different detection methods — MUST be merged into one
  output record rather than reported as separate rows.
- **FR-007**: The pipeline MUST compute and report precision and recall
  against the Andalucía regional ground-truth inventory. These are pilot
  outcomes to be measured, not preset targets to hit.
- **FR-007a**: The barriers manually annotated to fine-tune Layer 1 (see
  plan.md stage 3) MUST be excluded from, or clearly separated within,
  the FR-007 precision/recall computation. Reusing training examples as
  evaluation examples would inflate the reported accuracy and violate
  constitution principle 1 (report real numbers, even unflattering ones).
- **FR-007b**: Because the Andalucía inventory is itself an imperfect
  ground truth (it can have its own errors and omissions), a random
  sample of apparent false positives MUST be manually spot-checked
  against source imagery before being reported as pipeline errors —
  distinguishing "the model was wrong" from "the registry was wrong or
  incomplete" changes what the precision figure actually means.
- **FR-008**: The output MUST be a single CSV containing at minimum:
  latitude, longitude (WGS84), detection method(s) that flagged the
  record, confidence score, match status, and matched ground-truth record
  ID where applicable.
- **FR-009**: The CSV MUST be self-contained and shareable — openable and
  interpretable without external credentials or live API access.
- **FR-010**: Imagery pulls and inference runs MUST be resumable /
  checkpointed, so an interrupted run does not have to restart from zero.
- **FR-011**: The pilot MUST run within Google Earth Engine + Colab
  free-tier limits — no paid compute for this phase.
- **FR-012**: `new-confirmed` and `new-uncertain` candidates SHOULD carry
  enough information (coordinates, imagery date, confidence) to support
  later routing through AMBER's Barrier Tracker app for human
  verification, even if that routing itself is not built in this phase.
- **FR-013**: `new-uncertain` candidates MUST be exported as a distinct,
  human-reviewable output (e.g. a review CSV/sheet with a link or
  reference to the source imagery for that coordinate) so a person can
  confirm, reject, or re-flag each one — this review MUST be possible
  without needing GEE/Colab access, since it's a manual step done outside
  the pipeline.
- **FR-014**: The output CSV MUST ship with an attribution/license note
  covering every ground-truth and imagery source used (PNOA/IGN, SNCZI/
  MITECO, AMBER Atlas — CC-BY-4.0 — and the Andalucía regional inventory
  once its license is confirmed), so the dataset can be shared externally
  without violating source licensing terms.

## Key entities

- **Barrier candidate** — a detected (or matched) barrier location:
  id, geometry/point, detection method(s), confidence, imagery source,
  imagery date, match status.
- **Ground truth record** — an entry from SNCZI, AMBER, the Andalucía
  inventory, or OSM: source, source ID, location, barrier type.
- **River reach** — an EU-Hydro segment used to scope detection and to
  report results per-basin or per-sub-catchment.

## Out of scope (this phase)

- Running detection beyond the Guadalquivir basin (Spain-wide is phase 2;
  Europe is phase 3 — see [../../constitution.md](../../constitution.md)).
- Building full submission integration with AMBER's Barrier Tracker app
  (only the data needed to support it, per FR-012).
- Training a new detection architecture from scratch — this phase
  fine-tunes/adapts existing published models (RBOD, Sun et al.) rather
  than developing a novel one.
- The methane/impact-argument detection angle from the brief — explicitly
  not a discovery method, relevant only after barriers are confirmed.

## Resolved during clarification

- **Layer scope**: all four detection layers (direct structure, DEM/
  hydrological, water-signature, ecological/algae) are built before the
  pilot's precision/recall is computed. See constitution.md.
- **Match tolerance**: 30 meters. See constitution.md.
- **Uncertain detections**: never silently auto-classified as known or
  new — routed to a distinct `new-uncertain` human-review output
  (FR-005a, FR-013).

## Open questions for the plan phase

- Exact confidence threshold (and cross-layer agreement rule) that
  separates `new-confirmed` from `new-uncertain` — plan should propose a
  concrete rule (e.g. "≥2 layers agree" or "single-layer confidence ≥0.8")
  that can be tuned once real pilot data exists.
- Format of the human-review output (plain CSV with lat/lon you paste into
  Google Maps/Earth, vs. a CSV with pre-rendered thumbnail image links, vs.
  a small viewer) — trade-off between build effort now and review effort
  later, given the reviewer is you.
- Source of the Guadalquivir basin boundary polygon used to clip EU-Hydro
  (e.g. Confederación Hidrográfica del Guadalquivir district boundary vs.
  a WFD river-basin-district shapefile) — deliberately deferred until we
  see how EU-Hydro and candidate boundary sources are actually structured.
