"""Layer 3 confirmation pass: for each deduped NDWI candidate (fast,
broad, noisy -- layer3_water_signature.py + dedup_ndwi_candidates.py),
pull a small 4-band Sentinel-2 crop and run OmniWaterMask in batches to
confirm/reject it.

Two-stage design (cheap high-recall proposal -> expensive high-precision
confirm) avoids running OmniWaterMask across all 2,369 tiles (~100hrs on
this hardware, confirmed 2026-09-14). Batching + dropping the
building/road OSM checks (we only care about water) cuts per-item cost
further on top of that.

Run under .venv-owm/bin/python3. Crop pulling shells out to the main
Python (3.9, has earthengine-api + auth); this venv doesn't need it.
"""

import concurrent.futures
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANDIDATES_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer3_water_candidates_deduped.jsonl")
CROP_DIR = os.path.join(PROJECT_ROOT, "data/raw/layer3_confirm_crops")
MASK_DIR = os.path.join(PROJECT_ROOT, "data/raw/layer3_confirm_masks")
OUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer3_confirmed.jsonl")
PROGRESS_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer3_confirm_progress.jsonl")
BUFFER_M = 200  # >=32px margin at 10m/px after reprojection rounding -- 150m
# produced a 31x32 crop for at least one real candidate (OmniWaterMask's
# hard 32px minimum), found 2026-09-15 probing real candidates
BATCH_SIZE = 8
PULL_CONCURRENCY = 6


def polygon_centroid(geometry: dict) -> tuple:
    """Returns (lon, lat). Uses shapely rather than manual coordinate
    parsing -- geometry nesting differs between raw Earth Engine
    GeoJSON (Polygon) and the deduped file's shapely-round-tripped
    GeoJSON (can come back as MultiPolygon), which broke a manual
    coords[0] parse here (2026-09-14)."""
    from shapely.geometry import shape

    c = shape(geometry).centroid
    return c.x, c.y


def candidate_key(cand: dict) -> str:
    """Stable identity across reruns even as dedup_ndwi_candidates.py's
    output order/count shifts (more NDWI tiles finish, dedup reruns) --
    keyed on tile + rounded centroid rather than list position, so
    resuming after an interruption (constitution.md principle 3) doesn't
    require the candidate file to be frozen."""
    lon, lat = polygon_centroid(cand["geometry"])
    return f"{cand['tile_id']}_{lon:.6f}_{lat:.6f}"


def pull_crop_via_main_python(lon: float, lat: float, out_path: str) -> str:
    """Returns 'OK', 'NO_COVERAGE' (genuinely no S2 scene there -- safe to
    permanently skip), or 'ERROR:<reason>' (transient: timeout, exception,
    quota -- must NOT be treated as permanently done, or a rerun can never
    retry it). Conflating these was the real bug behind the 567-candidate
    run coming back 0/567 "no coverage": every transient failure got
    written to the progress log exactly like a real no-coverage result,
    permanently blocking a retry (found + fixed 2026-09-15)."""
    script = f"""
import ee
ee.Initialize(project='sincere-kit-507519-u3')
region = ee.Geometry.Point([{lon},{lat}]).buffer({BUFFER_M}).bounds()
s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(region).filterDate('2023-01-01','2025-12-31').filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
if s2.size().getInfo() == 0:
    print('NO_COVERAGE')
else:
    image = s2.median().clip(region).select(['B4','B3','B2','B8'])
    url = image.getDownloadURL({{'region': region, 'scale': 10, 'crs': 'EPSG:25830', 'format': 'GEO_TIFF'}})
    import urllib.request
    urllib.request.urlretrieve(url, '{out_path}')
    print('OK')
"""
    try:
        result = subprocess.run(["python3", "-c", script], capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        print(f"  crop pull TIMEOUT for ({lon:.5f},{lat:.5f})")
        return "ERROR:timeout"
    if "OK" in result.stdout:
        return "OK"
    if "NO_COVERAGE" in result.stdout:
        return "NO_COVERAGE"
    reason = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "(no output)"
    print(f"  crop pull failed for ({lon:.5f},{lat:.5f}): {reason}")
    return f"ERROR:{reason[:200]}"


if __name__ == "__main__":
    os.makedirs(CROP_DIR, exist_ok=True)
    os.makedirs(MASK_DIR, exist_ok=True)

    candidates = []
    with open(CANDIDATES_PATH) as f:
        for line in f:
            candidates.append(json.loads(line))
    print(f"{len(candidates)} deduped NDWI candidates total")

    # Resumability (constitution.md principle 3): skip candidates already
    # scored by a prior run, keyed by tile+centroid rather than list
    # position, since dedup_ndwi_candidates.py's output reorders/regrows
    # as the basin-wide NDWI pass keeps producing new candidates.
    done_keys = set()
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH) as f:
            for line in f:
                done_keys.add(json.loads(line)["key"])
    candidates = [c for c in candidates if candidate_key(c) not in done_keys]
    print(f"{len(candidates)} not yet scored ({len(done_keys)} already done)")

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if limit:
        candidates = candidates[:limit]

    # Pull all crops first (concurrently -- I/O-bound, same pattern as
    # pull_imagery.py), so the batched OmniWaterMask call below sees a
    # ready set of local files rather than pulling one-by-one in between
    # inference batches. Crop filenames are keyed the same way so a crop
    # already pulled by an earlier, interrupted run is reused.
    print("Pulling crops...")
    crop_paths = [None] * len(candidates)
    keys = [candidate_key(c) for c in candidates]

    def pull_one(i, cand, key):
        lon, lat = polygon_centroid(cand["geometry"])
        crop_path = os.path.join(CROP_DIR, f"{key}.tif")
        if os.path.exists(crop_path):
            return i, crop_path, lon, lat, "OK"
        status = pull_crop_via_main_python(lon, lat, crop_path)
        return (i, crop_path if status == "OK" else None, lon, lat, status)

    lonlat = {}
    pull_status = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=PULL_CONCURRENCY) as pool:
        futures = [pool.submit(pull_one, i, c, keys[i]) for i, c in enumerate(candidates)]
        for fut in concurrent.futures.as_completed(futures):
            i, path, lon, lat, status = fut.result()
            crop_paths[i] = path
            lonlat[i] = (lon, lat)
            pull_status[i] = status

    valid = [(i, p) for i, p in enumerate(crop_paths) if p is not None]
    no_coverage = [i for i, s in pull_status.items() if s == "NO_COVERAGE"]
    errored = [i for i, s in pull_status.items() if s.startswith("ERROR")]
    print(f"Pulled {len(valid)}/{len(candidates)} crops ({len(no_coverage)} no coverage, {len(errored)} transient errors -- left unscored to retry)")

    from omniwatermask import make_water_mask

    progress_f = open(PROGRESS_PATH, "a")
    out_f = open(OUT_PATH, "a")

    # Only genuine no-coverage results are permanently "done" -- a
    # transient error (timeout, exception, quota) must NOT be recorded
    # here, or a rerun can never retry it (2026-09-15 bug, see
    # pull_crop_via_main_python's docstring).
    for i in no_coverage:
        progress_f.write(json.dumps({"key": keys[i], "confirmed": False, "reason": "no_coverage"}) + "\n")
    progress_f.flush()

    n_confirmed = 0
    for batch_start in range(0, len(valid), BATCH_SIZE):
        batch = valid[batch_start : batch_start + BATCH_SIZE]

        def run_mask(items):
            paths = [Path(p) for _, p in items]
            result_paths = make_water_mask(
                scene_paths=paths,
                band_order=[1, 2, 3, 4],
                batch_size=len(paths),
                output_dir=Path(MASK_DIR),
                overwrite=False,
                use_osm_building=False,
                use_osm_roads=False,
                # Overture's S3 endpoint (the default vector_source) has
                # hung this job twice now -- 8s+ for a bare HEAD request
                # when Google's endpoints answer in <1s, and OmniWaterMask's
                # own error message suggests this exact fix. Switching to
                # OSM/Overpass for the water vector target instead.
                vector_source="osm",
            )
            # Match each output back to its source crop by filename, not
            # position. OmniWaterMask silently drops a scene from its
            # return list (no exception) when that one scene's vector
            # targets fail to build -- e.g. the Overture Maps network
            # outage hit here 2026-09-15 -- so result_paths can be
            # shorter than items, and zipping positionally then
            # attributes every result AFTER the drop to the wrong
            # candidate. Output filenames are "{input_stem}_{version}.tif",
            # so the input stem is always a safe, unambiguous prefix.
            by_stem = {Path(p).stem: (i, p) for i, p in items}
            scored = []
            for result_path in result_paths:
                result_path = Path(result_path)
                matched = next((v for stem, v in by_stem.items() if result_path.stem.startswith(stem + "_")), None)
                if matched is None:
                    print(f"  WARNING: output {result_path.name} didn't match any input in this batch, dropping it")
                    continue
                scored.append((matched, result_path))
            return scored

        try:
            scored = run_mask(batch)
        except Exception as e:
            # One malformed crop (e.g. an off-by-a-pixel undersized crop,
            # found 2026-09-15) fails the whole batch under make_water_mask's
            # batching -- fall back to one-at-a-time so the other 7 good
            # crops in the batch aren't wasted along with the bad one.
            print(f"  batch {batch_start}: failed as a batch ({e}), retrying items individually")
            scored = []
            for item in batch:
                try:
                    scored.extend(run_mask([item]))
                except Exception as e2:
                    i = item[0]
                    print(f"  {keys[i]}: failed individually too ({e2}), skipping")
                    progress_f.write(json.dumps({"key": keys[i], "confirmed": False, "reason": "mask_error"}) + "\n")

        import rasterio

        for (i, _), mask_path in scored:
            with rasterio.open(mask_path) as src:
                mask = src.read(1)
            water_frac = float((mask > 0).mean())
            is_confirmed = water_frac > 0.01
            lon, lat = lonlat[i]
            print(f"  {keys[i]}: water_frac={water_frac:.3f} confirmed={is_confirmed}")
            progress_f.write(json.dumps({"key": keys[i], "confirmed": is_confirmed, "water_frac": water_frac}) + "\n")
            if is_confirmed:
                out_f.write(json.dumps({**candidates[i], "lon": lon, "lat": lat, "water_frac": water_frac}) + "\n")
                n_confirmed += 1
        # Flush after every batch, not just at the end, so a kill mid-run
        # loses at most one batch of progress rather than everything.
        progress_f.flush()
        out_f.flush()

    progress_f.close()
    out_f.close()
    print(f"\nConfirmed {n_confirmed}/{len(valid)} newly-scored candidates -> {OUT_PATH}")
