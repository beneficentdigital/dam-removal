# Handoff — 2026-09-17

Read `constitution.md` and `specs/001-guadalquivir-pilot/{spec,plan,tasks}.md`
first — they're current and accurate as of this commit. This note is the
fast-path summary on top of them.

## What's actually done

**Layer 3 (water-signature) is complete, real, basin-wide.** 2,369/2,369
tiles, 845 stable candidates, 822 confirmed, 816 fused. After merging in
IGN's DamOrWeir registry (see below): **27 known, 62 new-confirmed, 727
new-uncertain**. This is the one layer with a trustworthy result — but
"new-confirmed" is not the same as "verified real dam." See the review
tool below before quoting a headline count anywhere.

**Layer 1 (direct structure)** — training pipeline works (16/17 held-out
recall), but a real-world pilot found it produces near-all false
positives when scanning raw, uncentered tiles (1/94 landed near real
ground truth). Root cause diagnosed (no negative examples in training);
the fix that was tried (17 verified negatives) didn't work — recall
collapsed, or noise stayed the same after recalibrating. **Not ready for
a full-basin PNOA pull** (would be 115-187GB anyway — that alone needs a
scope decision before it's attempted). Real next step: hard-negative
mining from the actual false-positive tiles already on disk
(`data/raw/pnoa_pilot_area/`), not more randomly-sampled negatives.

**Layer 2** — not attempted. DL-HFCS has no public code and shares
Sentinel-2's resolution limit; not recommended.

**Layer 4 (algae)** — running now, detached (`caffeinate`, PID check:
`ps aux | grep layer4_algae`). Was rewritten today to chunk + checkpoint
+ backoff after a full-batch run crashed immediately on a Microsoft
Planetary Computer rate limit. Resumable: rerun
`python3 src/layers/layer4_algae.py data/processed/fused_candidates.csv 2024-06-15`
any time and it picks up from `data/raw/layer4_cyfi/preds_*.csv`, skipping
finished chunks. ~55 chunks total, each with real per-chunk network cost —
expect hours, not minutes.

## The review tool — the actual next action

**[Dam Candidate Review](https://claude.ai/artifact/81kQ6J7vVRFyoZ57scX8aM)**
— 250 candidates (all 62 new-confirmed + 188 new-uncertain, real PNOA
imagery), yes/no/unsure, keyboard-driven (Y/N/U), progress persisted
server-side. Source checked in at `src/review_tool/dam_review_tool.html`.

Labels are already coming in (100+ as of this note) — read them back with
the Artifact tool: `action: "read_db"`, `collection: "labels"`. Each
label is `{status, ts}` keyed by `candidate_id`; cross-reference against
`data/processed/review_batch1.csv` for lat/lon.

**Two things to know before trusting this batch:**
1. 13/62 new-confirmed candidates sit in a known river-mapping gap near
   the Doñana coast (lon < -6.2) where the pipeline mistakes open
   coastline for a water candidate — flagged with a warning badge in the
   tool now, but real false positives, not a display bug.
2. Only 250 of 789 total candidates have images pulled/reviewable so far.
   To add more: `python3 src/imagery/pull_review_crops.py <csv> <outdir>`,
   then republish the artifact with the new crops added to `files` (keep
   `url` pointed at the same artifact to preserve labels and the link).

## Real findings worth carrying forward

- **The 30m ground-truth match tolerance may be too tight for
  detections specifically** (as opposed to cross-registry dedup, which
  is what it was calibrated for). Real candidates that visually look
  like reservoirs still land 137-898m from the nearest registry point
  even after snapping to the nearest river-line point. Not resolved —
  needs a spot-check pass (T042) once there's a bigger sample.
- **Confidence ≈ 1.0 is closer to an anti-signal than a good one** for
  "is this a dam" — it usually means the confirmation crop was
  wall-to-wall water (ocean, open lake), not that a dam wall was
  clearly visible at the water's edge.
- Two ground-truth licenses are still unconfirmed (SNCZI, Andalucía
  DERA) — don't ship `pilot_output.csv` publicly until closed. See
  `ATTRIBUTION.md`.

## Bugs fixed this session (for context, not action)

Anomalous-widening filter wiring, a batch-poisoning undersized-crop bug,
a resumability bug that would've permanently blocked retries on
transient failures, a silent result-misattribution bug in the confirm
script (zip-by-position instead of by-filename — the serious one), an
Overture Maps endpoint that hung the confirm job twice (switched to
OSM), a single-shot auto-relaunch that left two jobs idle 6+ hours
overnight, thumbnail rendering bugs (solid black / green wash), and now
the Layer 4 rate-limit crash. All documented in
`specs/001-guadalquivir-pilot/tasks.md` with real numbers, not just
"fixed a bug."

## Straightforward next steps, roughly in order

1. Keep reviewing in the tool; watch Layer 4 finish in the background.
2. Once Layer 4 has real results, re-run
   `python3 src/fusion/fuse_candidates.py` (needs a `layer4_water_signature`-
   style normalizer added — not built yet, Layer 4 isn't wired into
   fusion the way Layer 3 is) — this is real remaining work, not a
   rerun of existing code.
3. Pull crops + extend the review tool to the remaining ~540 candidates.
4. Feed the review tool's yes/no/unsure labels back into Layer 1 as a
   real, human-verified training set (hundreds of examples instead of
   28+17) — this was the plan discussed with the user, not yet built.
5. Spot-check the 30m tolerance gap (T042) once there's more review
   data to look at it with.
