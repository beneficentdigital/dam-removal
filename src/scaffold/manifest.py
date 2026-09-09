"""Resumability manifest: one row per AOI tile, one status column per
pipeline stage. Designed to live on Drive so a Colab disconnect doesn't
lose progress (constitution principle 3).
"""

import sqlite3
from pathlib import Path

STAGES = ["imagery", "layer1", "layer2", "layer3", "layer4", "fusion"]
STATUSES = ("pending", "done", "failed")


def init_manifest(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    cols = ", ".join(f"{stage} TEXT DEFAULT 'pending'" for stage in STAGES)
    con.execute(
        f"""
        CREATE TABLE IF NOT EXISTS tiles (
            tile_id TEXT PRIMARY KEY,
            geometry_wkt TEXT NOT NULL,
            {cols}
        )
        """
    )
    con.commit()
    con.close()


def add_tile(db_path: str, tile_id: str, geometry_wkt: str) -> None:
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT OR IGNORE INTO tiles (tile_id, geometry_wkt) VALUES (?, ?)",
        (tile_id, geometry_wkt),
    )
    con.commit()
    con.close()


def set_status(db_path: str, tile_id: str, stage: str, status: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    con = sqlite3.connect(db_path)
    con.execute(f"UPDATE tiles SET {stage} = ? WHERE tile_id = ?", (status, tile_id))
    con.commit()
    con.close()


def get_pending(db_path: str, stage: str) -> list[str]:
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    con = sqlite3.connect(db_path)
    rows = con.execute(
        f"SELECT tile_id FROM tiles WHERE {stage} != 'done'"
    ).fetchall()
    con.close()
    return [r[0] for r in rows]


def progress_summary(db_path: str) -> dict:
    con = sqlite3.connect(db_path)
    total = con.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
    summary = {"total_tiles": total}
    for stage in STAGES:
        done = con.execute(
            f"SELECT COUNT(*) FROM tiles WHERE {stage} = 'done'"
        ).fetchone()[0]
        summary[stage] = f"{done}/{total}"
    con.close()
    return summary
