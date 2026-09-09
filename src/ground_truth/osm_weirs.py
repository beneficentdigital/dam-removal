"""Pull OSM waterway=weir nodes/ways within a bounding box via Overpass API.

NOTE: bbox filtering is a placeholder until the real Guadalquivir basin
boundary polygon is available (T001) — re-run with a proper polygon clip
once that's resolved, since a bbox will include areas outside the basin.
"""

import json
import sys
import urllib.request

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_weirs(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> list[dict]:
    query = f"""
    [out:json][timeout:60];
    (
      node["waterway"="weir"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["waterway"="weir"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """
    req = urllib.request.Request(
        OVERPASS_URL,
        data=query.encode("utf-8"),
        headers={
            "Content-Type": "text/plain",
            "User-Agent": "howmanydamsinspain-pilot/0.1 (research project, Dam Removal Europe)",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.load(resp)

    records = []
    for el in data.get("elements", []):
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        records.append(
            {
                "source": "OSM",
                "source_id": f"{el['type']}/{el['id']}",
                "lat": lat,
                "lon": lon,
                "barrier_type": "weir",
                "raw_attributes": json.dumps(el.get("tags", {})),
            }
        )
    return records


if __name__ == "__main__":
    # Provisional Guadalquivir-region bbox (min_lat, min_lon, max_lat, max_lon)
    # — replace with a real polygon clip once T001 is resolved.
    records = fetch_weirs(36.7, -7.2, 38.7, -2.3)
    print(f"Fetched {len(records)} OSM weir records in the provisional bbox")
    out_path = sys.argv[1] if len(sys.argv) > 1 else "../../data/raw/osm_weirs_provisional.json"
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Wrote {out_path}")
