"""Dump scene facts to JSON for the deterministic structural checks (runs inside Blender)."""
from __future__ import annotations

import bpy

from cameras import collection_bbox

TRACKED = ["House_Shell", "Kitchen", "LivingRoom", "Bedroom_1", "Bedroom_2", "Bedroom_3",
           "Road", "Garden", "Lighting"]
PROCEDURAL = {"ShaderNodeTexNoise", "ShaderNodeTexVoronoi", "ShaderNodeTexWave",
              "ShaderNodeTexBrick", "ShaderNodeTexChecker", "ShaderNodeTexMagic",
              "ShaderNodeTexGradient", "ShaderNodeTexMusgrave", "ShaderNodeTexWhiteNoise"}


def _material_info(mat: bpy.types.Material) -> dict:
    info = {"name": mat.name, "nodes": 0, "principled": False, "image_tex": False,
            "procedural": False, "normal_or_bump": False, "transmission": 0.0,
            "flat_grey": False}
    if not mat.use_nodes or not mat.node_tree:
        info["flat_grey"] = True
        return info
    nodes = mat.node_tree.nodes
    info["nodes"] = len(nodes)
    for n in nodes:
        if n.bl_idname == "ShaderNodeBsdfPrincipled":
            info["principled"] = True
            tw = n.inputs.get("Transmission Weight") or n.inputs.get("Transmission")
            if tw is not None and not tw.is_linked:
                info["transmission"] = max(info["transmission"], float(tw.default_value))
            bc = n.inputs.get("Base Color")
            if bc is not None and not bc.is_linked:
                r, g, b, _ = bc.default_value
                if abs(r - g) < 0.02 and abs(g - b) < 0.02 and 0.7 < r < 0.82:
                    info["flat_grey"] = True  # Blender's default 0.8 grey
        elif n.bl_idname == "ShaderNodeBsdfGlass":
            info["transmission"] = 1.0
        elif n.bl_idname == "ShaderNodeTexImage" and n.image is not None:
            info["image_tex"] = True
        elif n.bl_idname in PROCEDURAL:
            info["procedural"] = True
        elif n.bl_idname in {"ShaderNodeNormalMap", "ShaderNodeBump", "ShaderNodeDisplacement"}:
            info["normal_or_bump"] = True
    return info


def _world_info() -> dict:
    w = bpy.context.scene.world
    out = {"exists": w is not None, "env_texture": False, "sky_texture": False, "env_image": None}
    if w and w.use_nodes and w.node_tree:
        for n in w.node_tree.nodes:
            if n.bl_idname == "ShaderNodeTexEnvironment" and n.image:
                out["env_texture"] = True
                out["env_image"] = n.image.filepath
            if n.bl_idname == "ShaderNodeTexSky":
                out["sky_texture"] = True
    return out


def inspect() -> dict:
    scene = bpy.context.scene
    cols = {}
    for name in TRACKED:
        col = bpy.data.collections.get(name)
        if col is None:
            cols[name] = {"exists": False}
            continue
        objs = list(col.all_objects)
        polys = sum(len(o.data.polygons) for o in objs if o.type == "MESH")
        box = collection_bbox(name)
        cols[name] = {
            "exists": True,
            "n_objects": len(objs),
            "n_meshes": sum(o.type == "MESH" for o in objs),
            "polys": polys,
            "object_names": sorted({o.name.split(".")[0] for o in objs})[:200],
            "bbox": [list(box[0]), list(box[1])] if box else None,
        }
    meshes = [o for o in scene.objects if o.type == "MESH"]
    mats = [_material_info(m) for m in bpy.data.materials if m.users > 0]
    untextured_objs = sum(1 for o in meshes if not o.material_slots or all(s.material is None for s in o.material_slots))
    lights = [o for o in scene.objects if o.type == "LIGHT"]
    return {
        "collections": cols,
        "totals": {
            "objects": len(scene.objects),
            "meshes": len(meshes),
            "polys": sum(len(o.data.polygons) for o in meshes),
            "bevel_modifiers": sum(1 for o in meshes for m in o.modifiers if m.type == "BEVEL"),
            "meshes_without_material": untextured_objs,
        },
        "materials": mats,
        "world": _world_info(),
        "lights": [{"name": o.name, "type": o.data.type, "energy": float(o.data.energy)} for o in lights],
        "color_management": {
            "view_transform": scene.view_settings.view_transform,
            "look": scene.view_settings.look,
            "exposure": scene.view_settings.exposure,
        },
    }
