# Constitution — How Many Dams in Spain

Reference: Dam Removal Europe river-barrier detection project. These are the
non-negotiable principles for this work; the plan and tasks must comply with
them, not the other way round.

1. **Ground truth before headline numbers.** Every detection layer is
   validated against SNCZI/AMBER/Andalucía-regional/OSM before it's trusted.
   Report real precision/recall, even when it's not flattering — no one has
   published a strong number for this yet, and establishing one honestly is
   part of the deliverable, not a footnote.

2. **Free-tier, reproducible stack by default.** Google Earth Engine + Colab
   + open data (PNOA, PNOA-MDT, Sentinel-2, EU-Hydro). Paid compute is an
   opt-in escalation for later scale-up phases, never a starting assumption
   — the pilot and Spain-wide run must fit inside free tier.

3. **Resumable, checkpointed pipelines.** Imagery pulls and inference runs
   must survive interruption and resume rather than restart from scratch.
   Probe the worst-case tile/unit cost before committing to a full run.
   Parallelize where the free tier allows it. This is going to involve large,
   possibly overnight/multi-day batch jobs at national and eventually
   continental scale.

4. **Scoped, not blind.** All detection runs against the EU-Hydro river-line
   scaffold. We never scan raw tiles hoping to find a river.

5. **Every output point carries its provenance.** The final CSV is not just
   lat/lon — each row records which method(s) flagged it, a confidence
   score, and whether it matches an existing registry entry or is a
   genuinely new detection. Closing the gap between recorded and estimated
   counts is the point of the project, so the dataset has to make that gap
   visible and checkable, not just add more dots on a map.

6. **Incremental geographic scale-up, gated by pilot results.** Guadalquivir
   basin pilot → all of Spain → Europe country-by-country, prioritizing the
   AMBER/EU-Hydro data-blank countries (Albania, Bosnia, North Macedonia,
   Montenegro, Serbia) last, per the brief's own reasoning about where
   scaffold data barely exists. Each geographic jump happens only once the
   previous phase's precision/recall is something we're willing to stand
   behind publicly. See [scaling-strategy.md](./scaling-strategy.md) for
   the concrete design decisions that keep each new country/basin a
   data-plumbing exercise rather than a rewrite.

## Locked decisions

- **Pilot area:** Guadalquivir basin / Andalucía — chosen over the
  Axarquía Mediterranean-draining rivers because it has the strongest
  existing ground truth (Agencia Andaluza del Agua + CEDEX + REDIAM
  combined inventory, updated 2022, includes azudes) to validate against.
- **Compute budget:** free-tier only (Earth Engine + Colab free tier)
  through the pilot and the Spain-wide run. Revisit only if free tier
  genuinely can't finish a phase in reasonable time.
- **Layer 1 training approach:** manually annotate (draw bounding boxes
  around) ~50-100 known Guadalquivir dams in PNOA imagery to fine-tune the
  detection model on local imagery and terrain, rather than relying on
  the RBOD checkpoint as-is. Chosen over a faster/lower-effort approach
  because maximum accuracy is the priority here, even at the cost of more
  upfront manual work.
- **Layer scope for the pilot:** all four detection layers (direct
  structure, DEM/hydrological, water-signature, ecological/algae) are
  built before the pilot's precision/recall is computed — the stacked
  result is the thing worth establishing, not a single-layer number.
- **Match tolerance:** 30 meters between a detection and an existing
  ground-truth record counts as a match — wide enough to absorb
  georeferencing error between SNCZI/AMBER/OSM sources, tight enough not
  to merge distinct nearby barriers.
- **Human review tier:** detections the pipeline can't confidently call
  either "known" or "new" are never silently auto-classified — they're
  routed to a distinct, human-reviewable output so a person makes the
  final call.
- **Spain-specific hydrography scaffold:** for Spain phases (pilot and
  Spain-wide), supplement EU-Hydro with a denser national network —
  IGN's Red Hidrográfica and/or our own DEM-derived stream network from
  PNOA-MDT (a byproduct of the Layer 2 flow-accumulation work) — so small
  tributaries EU-Hydro's pan-European scaffold may miss aren't
  structurally excluded from detection. EU-Hydro alone remains the
  baseline once the project reaches phase 3 (Europe), for consistency
  across countries that lack an equivalent national network.
- **Removed-barrier tracking (auxiliary, not counted):** registry entries
  (SNCZI/AMBER/Andalucía) that no longer show a barrier/impoundment
  signature in current imagery are flagged and recorded separately — they
  feed a likely future project mapping the impact of dam removal — but
  they are explicitly excluded from the pilot's headline barrier count
  and from precision/recall against current ground truth.
- **DEM/hydrological layer outreach-first:** before building this layer,
  email Dr. Wen Dai (wen.dai@nuist.edu.cn) to ask for private code
  access, the paper's omitted parameters, his validation data as a
  benchmark, and his read on whether the method transfers from Loess
  Plateau check dams to Guadalquivir river weirs — only fall back to
  blind reproduction if he doesn't respond. If neither path works out,
  report the pilot as a documented 3-layer result rather than blocking
  indefinitely on one unreproducible method.
