# Scaling Strategy: Guadalquivir → Spain → Europe

Cross-phase design decisions made during pilot planning so that reaching
phase 3 (any European country) is a data-plumbing exercise, not a
rewrite. Referenced from [constitution.md](./constitution.md); each
future phase's plan should point back here rather than re-deriving it.

## 1. Country/basin config, not hardcoded values

Every geography-specific parameter — boundary source, imagery source,
which ground-truth sources exist, CRS — lives in a per-country/basin
config, not inline in pipeline code. The Guadalquivir pilot's config is
the first instance of this, not a special case baked into the code.

## 2. Two-tier scaffold: pan-European baseline + optional national upgrade

- **Baseline (works in all 36 AMBER countries today):** EU-Hydro (river
  lines) + Sentinel-2 (imagery, already in Earth Engine) + AMBER Barrier
  Atlas (ground truth). Free, open, pan-European — the pipeline must be
  able to run on this alone.
- **National enrichment (layered on top when available):** PNOA-grade
  national imagery, a denser national hydrography network (Red
  Hidrográfica for Spain), regional inventories (Andalucía-style). These
  improve results where they exist but are never a hard requirement —
  the AMBER/EU-Hydro data-blank countries (Albania, Bosnia, North
  Macedonia, Montenegro, Serbia) have little to none of this and must
  still be reachable on the baseline tier alone.

## 3. Repeatable fine-tuning workflow, not a one-off Spain model

Each new country still needs some local fine-tuning (imagery and terrain
differ). The samgeo/SAM-assisted annotation approach from the Guadalquivir
plan (point-and-verify instead of drawing every box by hand) is what
makes that affordable to repeat per-country rather than a one-time
investment that doesn't generalize.

## 4. Adopt RF-YOLOv11's candidate-area pre-filter before Spain-wide

Its whole purpose — narrowing the search area with a Random Forest filter
before running full detection — is what keeps compute proportional as
area grows. Needed before the Spain-wide run, essential before any
country-wide European run, to stay inside free-tier budgets.

## 5. Per-country gate, not one global precision/recall bar

Ground-truth quality varies enormously by country — Andalucía's inventory
won't exist in the Balkans. Constitution principle 6 ("each geographic
jump happens only once the previous phase's precision/recall is something
we're willing to stand behind") means *evaluated against whatever ground
truth exists in that country*, not a Spain-calibrated number applied
blindly elsewhere. A country with only AMBER Atlas as ground truth will
have a different, probably lower, achievable bar than Spain — document
that per-country rather than treating it as failure.

## 6. Namespaced resumability manifest

The tile-status manifest (see the Guadalquivir plan's Resumability
design) should key tiles by `country/basin/tile_id`, not just `tile_id`,
so multiple countries' runs can proceed independently without collision,
and one slow or blocked country doesn't stall the others once phase 3
starts running several in parallel.
