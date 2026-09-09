"""Pull EU-Hydro river network lines from EEA's public ArcGIS REST service
(no auth needed — CLMS's own web viewer uses this same backend).

Pulls by bounding-box envelope for now; re-clip to the real Guadalquivir
basin polygon (spatial intersection, not a re-download) once that's
available — this bbox is a safe superset of the basin.
"""

import json
import time
import urllib.parse
import urllib.request

BASE = "https://image.discomap.eea.europa.eu/arcgis/rest/services/EUHydro/EUHydro_RiverNetworkDatabase/MapServer"
PAGE_SIZE = 1000

# Strahler order layers 1-9 under the "River_Net_lines" group (layer ids 5-13)
STRAHLER_LAYER_IDS = list(range(5, 14))


def _query(layer_id: int, bbox: tuple[float, float, float, float], offset: int) -> dict:
    params = {
        "geometry": ",".join(str(x) for x in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "resultOffset": str(offset),
        "resultRecordCount": str(PAGE_SIZE),
        "f": "geojson",
    }
    url = f"{BASE}/{layer_id}/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": "howmanydamsinspain-pilot/0.1 (research project)"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def fetch_layer(layer_id: int, bbox: tuple[float, float, float, float]) -> list[dict]:
    features = []
    offset = 0
    while True:
        page = _query(layer_id, bbox, offset)
        page_features = page.get("features", [])
        features.extend(page_features)
        if len(page_features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.2)  # be polite to a public government endpoint
    return features


if __name__ == "__main__":
    import sys

    bbox = (-7.2, 36.7, -2.3, 38.7)  # provisional Guadalquivir-region bbox
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "../../data/raw/eu_hydro"
    import os

    os.makedirs(out_dir, exist_ok=True)

    total = 0
    for layer_id in STRAHLER_LAYER_IDS:
        print(f"Fetching layer {layer_id}...", end=" ", flush=True)
        feats = fetch_layer(layer_id, bbox)
        total += len(feats)
        print(f"{len(feats)} features")
        with open(f"{out_dir}/strahler_layer_{layer_id}.geojson", "w") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f)
    print(f"Total river-line features pulled: {total}")
