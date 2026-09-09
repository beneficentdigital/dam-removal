"""Merge SNCZI, AMBER, and OSM into one normalized ground-truth table for
the Guadalquivir basin (plan.md stage 1). Andalucía regional inventory
still pending.

Schema: source, source_id, lat, lon (WGS84), barrier_type, raw_attributes
"""

import json

import geopandas as gpd
import pandas as pd

BOUNDARY_PATH = "data/raw/basin_boundary/guadalquivir_rbd.geojson"


def load_snczi():
    boundary = gpd.read_file(BOUNDARY_PATH)
    presa = gpd.read_file("data/raw/snczi/presa/egis_presa_geoetrs89sinTitular.shp")
    embalse = gpd.read_file("data/raw/snczi/embalse/egis_embalse_geoetrs89sinTitular.shp")

    rows = []
    for df, kind, id_col in [(presa, "presa", "ID_INFRAES"), (embalse, "embalse", "ID_EMBALSE")]:
        # Cross-check DEMARC field against a real spatial clip rather than
        # trusting the text field alone (AMBER's BasinName taught us that
        # basin-name fields can be sparse/unreliable).
        by_field = df[df["DEMARC"] == "GUADALQUIVIR"]
        by_field_wgs84 = by_field.to_crs(epsg=4326)
        clipped = gpd.clip(df.to_crs(epsg=4326), boundary)
        only_in_field = set(by_field[id_col]) - set(clipped[id_col])
        only_in_clip = set(clipped[id_col]) - set(by_field[id_col])
        print(
            f"{kind}: DEMARC field={len(by_field)}, spatial clip={len(clipped)}, "
            f"field-only={len(only_in_field)}, clip-only={len(only_in_clip)}"
        )
        # Use the spatial clip as the authoritative set (consistent with
        # FR-001's scoping rule), DEMARC field kept as a cross-check note.
        for _, r in clipped.iterrows():
            geom = r.geometry
            pt = geom if geom.geom_type == "Point" else geom.centroid
            rows.append(
                {
                    "source": "SNCZI",
                    "source_id": f"{kind}_{r[id_col]}",
                    "lat": pt.y,
                    "lon": pt.x,
                    "barrier_type": kind,
                    "raw_attributes": json.dumps(
                        {k: r[k] for k in df.columns if k != "geometry"}, default=str
                    ),
                }
            )
    return pd.DataFrame(rows)


def load_amber():
    boundary = gpd.read_file(BOUNDARY_PATH)
    df = pd.read_csv(
        "data/raw/amber_atlas/AMBER_BARRIER_ATLAS_V1.csv", encoding="utf-8", low_memory=False
    )
    df = df[df["Country"] == "SPAIN"]
    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["Longitude_WGS84"], df["Latitude_WGS84"]), crs="EPSG:4326"
    )
    clipped = gpd.clip(gdf, boundary)
    print(f"AMBER: Spain total={len(df)}, spatial clip to Guadalquivir={len(clipped)}")
    rows = []
    for _, r in clipped.iterrows():
        rows.append(
            {
                "source": "AMBER",
                "source_id": r["GUID"],
                "lat": r["Latitude_WGS84"],
                "lon": r["Longitude_WGS84"],
                "barrier_type": r.get("LabelAtlas"),
                "raw_attributes": json.dumps(
                    {k: r[k] for k in df.columns if k != "geometry"}, default=str
                ),
            }
        )
    return pd.DataFrame(rows)


def load_osm():
    with open("data/raw/osm_weirs_provisional.json") as f:
        records = json.load(f)
    boundary = gpd.read_file(BOUNDARY_PATH)
    gdf = gpd.GeoDataFrame(
        records, geometry=gpd.points_from_xy([r["lon"] for r in records], [r["lat"] for r in records]),
        crs="EPSG:4326",
    )
    clipped = gpd.clip(gdf, boundary)
    print(f"OSM: provisional bbox pull={len(gdf)}, spatial clip to Guadalquivir={len(clipped)}")
    return clipped.drop(columns="geometry")


if __name__ == "__main__":
    snczi = load_snczi()
    amber = load_amber()
    osm = load_osm()
    combined = pd.concat([snczi, amber, osm], ignore_index=True)
    combined.to_csv("data/processed/ground_truth_guadalquivir.csv", index=False)
    print(f"\nTotal ground-truth records for Guadalquivir: {len(combined)}")
    print(combined["source"].value_counts())
