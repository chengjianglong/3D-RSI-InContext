"""Fixed evaluation cameras, derived from collection bounding boxes.

The harness (not the LLM) places these so views stay comparable across iterations.
Convention from goal_spec: +Z up, house front faces -Y (road), backyard at +Y (garden).
"""
from __future__ import annotations

import bpy
from mathutils import Vector

ROOMS = ["Kitchen", "LivingRoom", "Bedroom_1", "Bedroom_2", "Bedroom_3"]


def collection_bbox(name: str) -> tuple[Vector, Vector] | None:
    col = bpy.data.collections.get(name)
    if col is None:
        return None
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    found = False
    for ob in col.all_objects:
        if ob.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "EMPTY"}:
            continue
        if ob.type == "EMPTY" and not ob.instance_collection:
            continue
        for corner in ob.bound_box:
            w = ob.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
            found = True
    return (lo, hi) if found else None


def union(*boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    lo = Vector(map(min, *[b[0] for b in boxes])) if len(boxes) > 1 else boxes[0][0].copy()
    hi = Vector(map(max, *[b[1] for b in boxes])) if len(boxes) > 1 else boxes[0][1].copy()
    return lo, hi


def _cam(name: str, loc, target, lens=35.0, ortho_scale=None):
    data = bpy.data.cameras.new(f"EVAL_{name}")
    data.lens = lens
    data.clip_start = 0.05
    data.clip_end = 2000
    if ortho_scale:
        data.type = "ORTHO"
        data.ortho_scale = ortho_scale
    ob = bpy.data.objects.new(f"EVAL_{name}", data)
    ob.location = Vector(loc)
    direction = Vector(target) - Vector(loc)
    ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    col = bpy.data.collections.get("EVAL_Cameras")
    if col is None:
        col = bpy.data.collections.new("EVAL_Cameras")
        bpy.context.scene.collection.children.link(col)
    col.objects.link(ob)
    return ob


def build_eval_cameras() -> tuple[dict[str, bpy.types.Object], list[str]]:
    """Returns (view_name -> camera object, list of skipped views with reasons)."""
    cams: dict[str, bpy.types.Object] = {}
    skipped: list[str] = []
    rooms = {r: collection_bbox(r) for r in ROOMS}
    shell = collection_bbox("House_Shell")
    house = union(shell, *rooms.values())
    road = collection_bbox("Road")
    garden = collection_bbox("Garden")
    if house is None:
        return cams, ["all views: no House_Shell or room geometry found"]

    lo, hi = house
    c = (lo + hi) / 2
    size = hi - lo
    width = max(size.x, 6.0)
    eye = 1.7
    roof_mid = lo.z + min(size.z, 12) * 0.45

    # 1. Front street view: standing across the road, looking at the facade.
    front_y = (road[0].y - 2.0) if road else lo.y - 1.6 * width
    front_y = min(front_y, lo.y - 10.0)
    cams["front_street"] = _cam("front_street", (c.x - 0.25 * width, front_y, eye),
                                (c.x, lo.y, roof_mid), lens=26)

    # 2. Backyard view: from the far end of the garden back toward the house.
    back_y = (garden[1].y - 1.0) if garden else hi.y + 1.5 * width
    back_y = max(back_y, hi.y + 6.0)
    cams["backyard"] = _cam("backyard", (c.x + 0.25 * width, back_y, eye),
                            (c.x, hi.y, lo.z + 1.5), lens=24)

    # 3. Aerial three-quarter view of the whole property.
    world = union(house, road, garden)
    wc = (world[0] + world[1]) / 2
    diag = (world[1] - world[0]).length
    cams["aerial"] = _cam("aerial", (wc.x - 0.75 * diag, wc.y - 0.75 * diag, 0.6 * diag + 5),
                          wc, lens=35)

    # 4. Top-down orthographic plan view.
    ext = max(world[1].x - world[0].x, world[1].y - world[0].y) * 1.1
    cams["top_down"] = _cam("top_down", (wc.x, wc.y, world[1].z + 100), (wc.x, wc.y, 0),
                            lens=50, ortho_scale=ext)
    cams["top_down"].rotation_euler = (0, 0, 0)

    # 5-9. One interior camera per room: corner, eye height, looking at the opposite corner.
    for r, box in rooms.items():
        if box is None:
            skipped.append(f"{r}: collection missing or empty")
            continue
        rlo, rhi = box
        d = rhi - rlo
        z = rlo.z + 1.5 if d.z < 1.8 else min(rlo.z + 1.5, rhi.z - 0.3)
        loc = (rlo.x + 0.12 * d.x, rlo.y + 0.12 * d.y, z)
        tgt = (rhi.x - 0.1 * d.x, rhi.y - 0.1 * d.y, rlo.z + 0.9)
        cams[f"room_{r}"] = _cam(f"room_{r}", loc, tgt, lens=16)
    return cams, skipped
