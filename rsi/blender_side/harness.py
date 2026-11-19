"""Runs inside Blender:  blender -b --factory-startup --python harness.py -- job.json

job.json: {"script": path, "out_dir": path, "assets_root": path, "manifest": path,
           "render": {"samples": int, "resolution": [w, h], "time_limit_s": float},
           "skip_render": bool}

Writes into out_dir: result.json, inspect.json, scene.blend, renders/<view>.png
Exit code 0 on success, 2 when the generated script raised.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402

import cameras  # noqa: E402
import inspect_scene  # noqa: E402

HOUSE_CHILDREN = {"House_Shell", "Kitchen", "LivingRoom", "Bedroom_1", "Bedroom_2", "Bedroom_3"}


class Ctx:
    """The fixed API handed to build_scene(ctx). Pure plumbing; no quality helpers."""

    def __init__(self, assets_root: Path, manifest: dict):
        self.assets_root = str(assets_root)
        self.manifest = manifest
        self._project_root = assets_root.parent

    def asset(self, rel_path: str) -> str:
        """Absolute path for a manifest path such as 'assets/textures/x/x_diff_2k.jpg'."""
        p = (self._project_root / rel_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"asset not found: {rel_path}")
        return str(p)

    def collection(self, name: str) -> bpy.types.Collection:
        """Get or create a collection. Room and shell collections live under 'House'."""
        col = bpy.data.collections.get(name)
        if col is not None:
            return col
        col = bpy.data.collections.new(name)
        if name in HOUSE_CHILDREN:
            self.collection("House").children.link(col)
        else:
            bpy.context.scene.collection.children.link(col)
        return col

    def import_model(self, model_id: str, collection: bpy.types.Collection) -> list:
        """Import a manifest glTF model; returns its top-level (parentless) objects,
        all linked only into `collection`."""
        entry = next((m for m in self.manifest["models"] if m["id"] == model_id), None)
        if entry is None:
            raise KeyError(f"unknown model id {model_id!r}")
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=self.asset(entry["path"]))
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            collection.objects.link(o)
        return [o for o in new if o.parent is None]


def setup_render(scene, cfg: dict) -> None:
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = "GPU"
    except Exception:  # noqa: BLE001 - CPU fallback is fine
        scene.cycles.device = "CPU"
    scene.cycles.samples = int(cfg.get("samples", 128))
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.time_limit = float(cfg.get("time_limit_s", 0))
    w, h = cfg.get("resolution", [960, 540])
    scene.render.resolution_x, scene.render.resolution_y = int(w), int(h)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"


def main() -> int:
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
    out = Path(job["out_dir"])
    out.mkdir(parents=True, exist_ok=True)
    result: dict = {"status": "ok", "timings": {}}
    manifest = json.loads(Path(job["manifest"]).read_text())

    bpy.ops.wm.read_factory_settings(use_empty=True)
    t0 = time.time()
    try:
        src = Path(job["script"]).read_text()
        ns: dict = {"__name__": "generated_scene"}
        exec(compile(src, "scene_script.py", "exec"), ns)  # noqa: S102 - generated code is the point
        if "build_scene" not in ns:
            raise RuntimeError("script does not define build_scene(ctx)")
        ns["build_scene"](Ctx(Path(job["assets_root"]), manifest))
    except Exception:  # noqa: BLE001
        result.update(status="error", traceback=traceback.format_exc()[-6000:])
        (out / "result.json").write_text(json.dumps(result, indent=2))
        return 2
    result["timings"]["build_s"] = round(time.time() - t0, 1)

    scene = bpy.context.scene
    (out / "inspect.json").write_text(json.dumps(inspect_scene.inspect(), indent=2))
    cams, skipped = cameras.build_eval_cameras()
    result["skipped_views"] = skipped
    setup_render(scene, job.get("render", {}))

    try:
        bpy.ops.file.pack_all()
    except Exception as e:  # noqa: BLE001
        result["pack_warning"] = repr(e)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"), compress=True)

    renders = out / "renders"
    renders.mkdir(exist_ok=True)
    result["views"] = []
    if not job.get("skip_render"):
        for view, cam in cams.items():
            t1 = time.time()
            scene.camera = cam
            scene.render.filepath = str(renders / f"{view}.png")
            bpy.ops.render.render(write_still=True)
            result["views"].append(view)
            result["timings"][f"render_{view}_s"] = round(time.time() - t1, 1)
    (out / "result.json").write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    # Blender ignores the --python script's return value; force the process exit code.
    import os
    os._exit(code)
