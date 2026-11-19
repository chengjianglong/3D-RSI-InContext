"""Deterministic structural score (0-100) from inspect.json, scored against goal_spec."""
from __future__ import annotations

from itertools import combinations


def _bbox(col: dict):
    return col.get("bbox") if col and col.get("exists") else None


def _xy_area(b) -> float:
    return max(0.0, b[1][0] - b[0][0]) * max(0.0, b[1][1] - b[0][1])


def _overlap(a, b) -> float:
    dx = min(a[1][0], b[1][0]) - max(a[0][0], b[0][0])
    dy = min(a[1][1], b[1][1]) - max(a[0][1], b[0][1])
    return max(0.0, dx) * max(0.0, dy)


def _matches(names: list[str], keywords: list[str]) -> list[str]:
    low = [n.lower() for n in names]
    return [k for k in keywords if any(k in n for n in low)]


def score(inspect: dict, goal: dict) -> dict:
    cols = inspect["collections"]
    req = goal["required"]
    fails: list[str] = []
    parts: dict[str, float] = {}

    # --- presence (30)
    tracked = list(cols)
    present = [c for c in tracked if cols[c].get("exists") and cols[c].get("n_objects", 0) > 0]
    for c in set(tracked) - set(present):
        fails.append(f"collection {c} missing or empty")
    parts["presence"] = 30 * len(present) / len(tracked)

    # --- layout (25)
    layout = 0.0
    rooms = req["rooms"]
    room_boxes = {r: _bbox(cols.get(spec["collection"])) for r, spec in rooms.items()}
    house_boxes = [b for b in [*room_boxes.values(), _bbox(cols.get("House_Shell"))] if b]
    house = None
    if house_boxes:
        house = [[min(b[0][i] for b in house_boxes) for i in range(3)],
                 [max(b[1][i] for b in house_boxes) for i in range(3)]]
    road, garden = _bbox(cols.get("Road")), _bbox(cols.get("Garden"))
    if house and road:
        if (road[0][1] + road[1][1]) / 2 < house[0][1]:
            layout += 5
        else:
            fails.append("road is not in front of the house (should be at -Y of the house)")
    if house and garden:
        if (garden[0][1] + garden[1][1]) / 2 > house[1][1] - 1.0:
            layout += 5
        else:
            fails.append("garden is not behind the house (should be at +Y of the house)")
    for r, spec in rooms.items():
        b = room_boxes[r]
        if not b:
            continue
        a = _xy_area(b)
        lo, hi = spec["area_m2"]
        if lo <= a <= hi:
            layout += 7.5 / len(rooms)
        else:
            fails.append(f"{r} footprint {a:.1f} m2 outside plausible range {lo}-{hi} m2")
    pairs = [(a, b) for a, b in combinations(room_boxes, 2) if room_boxes[a] and room_boxes[b]]
    if pairs:
        bad = []
        for a, b in pairs:
            ov = _overlap(room_boxes[a], room_boxes[b])
            if ov > 0.15 * min(_xy_area(room_boxes[a]), _xy_area(room_boxes[b])):
                bad.append(f"{a}/{b}")
        layout += 5 * (1 - len(bad) / len(pairs))
        if bad:
            fails.append("rooms overlap in plan: " + ", ".join(bad))
    shell = _bbox(cols.get("House_Shell"))
    if shell:
        inside = [r for r, b in room_boxes.items() if b and all(
            b[0][i] >= shell[0][i] - 0.5 and b[1][i] <= shell[1][i] + 0.5 for i in (0, 1))]
        layout += 2.5 * len(inside) / len(rooms)
        if len(inside) < len(rooms):
            fails.append("some rooms extend outside the house shell: "
                         + ", ".join(r for r in rooms if r not in inside))
    parts["layout"] = layout

    # --- furniture / elements (20)
    groups = {r: (spec["collection"], spec["furniture"]) for r, spec in rooms.items()}
    for k in ("House", "Road", "Garden"):
        spec = req["exterior"][k]
        groups[k] = (spec["collection"], spec["elements"])
    elem = 0.0
    for g, (cname, keys) in groups.items():
        col = cols.get(cname) or {}
        hit = _matches(col.get("object_names", []), keys)
        need = min(3, len(keys))
        elem += min(1.0, len(hit) / need)
        missing = [k for k in keys if k not in hit]
        if len(hit) < need:
            fails.append(f"{g}: no recognizable objects named like {missing} (found {hit})")
    parts["elements"] = 20 * elem / len(groups)

    # --- realism proxies (25)
    real = 0.0
    w = inspect["world"]
    if w.get("env_texture") or w.get("sky_texture"):
        real += 5
    else:
        fails.append("no HDRI/sky world lighting")
    mats = inspect["materials"]
    if mats:
        textured = sum(m["image_tex"] or m["procedural"] for m in mats) / len(mats)
        bumped = sum(m["normal_or_bump"] for m in mats) / len(mats)
        grey = sum(m["flat_grey"] for m in mats) / len(mats)
        real += 7 * textured + 3 * bumped
        if textured < 0.6:
            fails.append(f"only {textured:.0%} of materials use image/procedural textures")
        if bumped < 0.4:
            fails.append(f"only {bumped:.0%} of materials have normal/bump detail")
        if not any(m["transmission"] > 0.5 for m in mats):
            fails.append("no glass material (windows)")
        else:
            real += 2
    else:
        grey = 1.0
        fails.append("no materials at all")
    tot = inspect["totals"]
    untex = tot["meshes_without_material"] / max(1, tot["meshes"])
    real += 3 * (1 - max(grey, untex))
    if untex > 0:
        fails.append(f"{tot['meshes_without_material']} meshes have no material")
    if tot["bevel_modifiers"] > 0 or tot["polys"] > 200_000:
        real += 2
    elif tot["polys"] > 50_000:
        real += 1
    lights = inspect["lights"]
    has_sun = any(l["type"] == "SUN" for l in lights) or w.get("env_texture") or w.get("sky_texture")
    interior = sum(l["type"] in {"AREA", "POINT", "SPOT"} for l in lights)
    real += (1 if has_sun else 0) + min(2, 2 * interior / 5)
    if interior < 5:
        fails.append(f"only {interior} interior lights for 5 rooms (interiors may render dark)")
    parts["realism_proxies"] = real

    total = sum(parts.values())
    return {"score": round(total, 2), "parts": {k: round(v, 2) for k, v in parts.items()},
            "failures": fails}
