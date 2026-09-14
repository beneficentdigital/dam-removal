"""Pull DEM chunks (build_dem_chunks.py) at 25m resolution via IGN's
WCS. Larger contiguous areas than the imagery tile grid, so flow
accumulation in layer2_dem_hydro.py sees real upstream watershed area.
"""

import concurrent.futures
import json
import os
import sys
import time

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WCS_URL = "https://servicios.idee.es/wcs-inspire/mdt"
COVERAGE_ID = "Elevacion25830_25"
CHUNKS_PATH = os.path.join(PROJECT_ROOT, "data/processed/dem_chunks.json")
OUT_DIR = os.path.join(PROJECT_ROOT, "data/raw/dem_chunks")
MAX_RETRIES = 3
CONCURRENCY = int(os.environ.get("PULL_CONCURRENCY", 6))


def fetch_chunk(chunk: dict) -> bool:
    minx, miny, maxx, maxy = chunk["fetch_bounds"]
    params = {
        "SERVICE": "WCS",
        "VERSION": "2.0.1",
        "REQUEST": "GetCoverage",
        "COVERAGEID": COVERAGE_ID,
        "SUBSET": [f"x({minx},{maxx})", f"y({miny},{maxy})"],
        "FORMAT": "image/tiff",
    }
    resp = requests.get(WCS_URL, params=params, timeout=120)
    resp.raise_for_status()
    if b"Exception" in resp.content[:500]:
        return False
    out_path = os.path.join(OUT_DIR, f"{chunk['chunk_id']}.tif")
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return True


def fetch_chunk_safe(chunk: dict) -> tuple:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return chunk["chunk_id"], fetch_chunk(chunk)
        except Exception as e:
            print(f"  {chunk['chunk_id']}: attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
    return chunk["chunk_id"], False


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(CHUNKS_PATH) as f:
        chunks = json.load(f)

    already_done = {f.replace(".tif", "") for f in os.listdir(OUT_DIR) if f.endswith(".tif")}
    pending = [c for c in chunks if c["chunk_id"] not in already_done]
    print(f"{len(pending)}/{len(chunks)} chunks pending")

    n_done = n_failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(fetch_chunk_safe, c): c["chunk_id"] for c in pending}
        for future in concurrent.futures.as_completed(futures):
            chunk_id, ok = future.result()
            n_done += ok
            n_failed += not ok
            print(f"  {chunk_id}: {'ok' if ok else 'FAILED'} ({n_done + n_failed}/{len(pending)})")

    print(f"Finished: {n_done} done, {n_failed} failed out of {len(pending)}")
