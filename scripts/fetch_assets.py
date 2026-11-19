"""One-time download of a fixed list of CC0 assets from Poly Haven into ./assets.

Writes assets/manifest.json, which the generator embeds in its prompt so scripts only
reference files that exist. The pipeline itself never downloads anything.

Usage: uv run python scripts/fetch_assets.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
API = "https://api.polyhaven.com/files/"
UA = {"User-Agent": "rsi-asset-fetch"}

HDRIS = {  # id: description
    "wide_street_01": "sunny suburban/urban street, daylight",
    "kloofendal_48d_partly_cloudy_puresky": "partly cloudy pure sky, daylight, no ground",
    "noon_grass": "noon sun over grass field",
}
TEXTURES = {
    "asphalt_02": "road asphalt",
    "concrete_floor_02": "concrete sidewalk / driveway / slab",
    "red_brick": "red brick exterior wall",
    "painted_plaster_wall": "painted interior plaster wall",
    "white_plaster_02": "white exterior render / ceiling",
    "laminate_floor_02": "wood laminate floor (living room, bedrooms)",
    "floor_tiles_06": "ceramic floor tiles (kitchen)",
    "clay_roof_tiles_02": "clay roof tiles",
    "leafy_grass": "lawn grass ground",
    "forest_ground_04": "garden soil / flower bed mulch",
    "bark_brown_02": "tree bark",
    "fabric_pattern_07": "upholstery / bedding fabric",
    "marble_01": "marble kitchen countertop",
    "wood_table_001": "wooden furniture / cabinet doors",
}
MODELS = {
    "sofa_02": "sofa",
    "modern_arm_chair_01": "armchair",
    "coffee_table_round_01": "coffee table",
    "wooden_table_02": "dining table",
    "painted_wooden_chair_01": "dining chair",
    "television_02": "television",
    "old_bed_frame": "bed frame (add mattress/bedding procedurally)",
    "painted_wooden_nightstand": "nightstand",
    "drawer_cabinet": "drawer cabinet / dresser",
    "modern_wooden_cabinet": "tall cabinet / wardrobe",
    "electric_stove": "kitchen stove",
    "modern_ceiling_lamp_01": "ceiling lamp",
    "desk_lamp_arm_01": "desk / bedside lamp",
    "potted_plant_02": "potted plant (indoor)",
    "potted_plant_04": "potted plant",
    "shrub_01": "garden shrub",
    "shrub_04": "garden shrub",
    "tree_small_02": "small garden tree",
    "jacaranda_tree": "large tree",
    "street_lamp_01": "street lamp",
    "modular_chainlink_fence": "chainlink fence module",
    "outdoor_table_chair_set_01": "garden table and chairs",
}
TEX_MAPS = {"Diffuse": "diff", "nor_gl": "nor_gl", "Rough": "rough", "AO": "ao", "Displacement": "disp"}


def get_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def download(url: str, dest: Path, md5: str | None = None) -> None:
    if dest.exists() and (md5 is None or hashlib.md5(dest.read_bytes()).hexdigest() == md5):
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        tmp.write_bytes(r.read())
    tmp.rename(dest)


def plan() -> tuple[list[tuple[str, Path, str | None]], dict]:
    jobs: list[tuple[str, Path, str | None]] = []
    manifest: dict = {"hdris": [], "textures": [], "models": [], "root": "assets"}
    for aid, desc in HDRIS.items():
        f = get_json(API + aid)["hdri"]["2k"]["hdr"]
        p = ASSETS / "hdris" / f"{aid}_2k.hdr"
        jobs.append((f["url"], p, f.get("md5")))
        manifest["hdris"].append({"id": aid, "desc": desc, "path": str(p.relative_to(ROOT))})
    for aid, desc in TEXTURES.items():
        files = get_json(API + aid)
        maps = {}
        for key, short in TEX_MAPS.items():
            if key not in files:
                continue
            f = files[key]["2k"]["jpg"] if key != "Displacement" else files[key]["2k"].get("jpg") or files[key]["2k"]["png"]
            ext = Path(f["url"]).suffix
            p = ASSETS / "textures" / aid / f"{aid}_{short}_2k{ext}"
            jobs.append((f["url"], p, f.get("md5")))
            maps[short] = str(p.relative_to(ROOT))
        manifest["textures"].append({"id": aid, "desc": desc, "maps": maps})
    for aid, desc in MODELS.items():
        g = get_json(API + aid)["gltf"]["1k"]["gltf"]
        base = ASSETS / "models" / aid
        p = base / f"{aid}.gltf"
        jobs.append((g["url"], p, g.get("md5")))
        for rel, inc in g.get("include", {}).items():
            jobs.append((inc["url"], base / rel, inc.get("md5")))
        manifest["models"].append({"id": aid, "desc": desc, "path": str(p.relative_to(ROOT))})
    return jobs, manifest


def main() -> int:
    jobs, manifest = plan()
    print(f"{len(jobs)} files to ensure")
    errors = []

    def run(job):
        try:
            download(*job)
        except Exception as e:  # noqa: BLE001 - report all failures at the end
            errors.append((job[0], repr(e)))

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(run, jobs))
    if errors:
        for u, e in errors:
            print("FAILED", u, e, file=sys.stderr)
        return 1
    (ASSETS / "manifest.json").write_text(json.dumps(manifest, indent=2))
    total = sum(p.stat().st_size for _, p, _ in jobs)
    print(f"ok: {total / 1e6:.0f} MB in {ASSETS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
