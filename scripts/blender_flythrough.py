"""Render a camera fly-through of a generated scene.blend (runs inside Blender).

blender -b scene.blend --python scripts/blender_flythrough.py -- OUT_DIR [FRAMES] [SAMPLES] [W] [H] [SHOTS]
SHOTS: comma list of "orbit" (aerial orbit around the house) and/or "living" (slow 300° pan in the living room).
Writes OUT_DIR/<shot>/####.png
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rsi" / "blender_side"))
from cameras import collection_bbox, union  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
out = Path(argv[0])
frames = int(argv[1]) if len(argv) > 1 else 150
samples = int(argv[2]) if len(argv) > 2 else 32
W, H = (int(argv[3]), int(argv[4])) if len(argv) > 4 else (960, 540)
shots = argv[5].split(",") if len(argv) > 5 else ["orbit", "living"]

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "GPU"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.get_devices()
for d in prefs.devices:
    d.use = True
sc.cycles.samples = samples
sc.cycles.use_adaptive_sampling = True
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"

rooms = ["Kitchen", "LivingRoom", "Bedroom_1", "Bedroom_2", "Bedroom_3", "House_Shell"]
house = union(*[collection_bbox(n) for n in rooms])
lo, hi = house
center = (lo + hi) / 2
size = max(hi.x - lo.x, hi.y - lo.y)

cam_data = bpy.data.cameras.new("FLY")
cam_data.clip_start, cam_data.clip_end = 0.05, 2000
cam = bpy.data.objects.new("FLY", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look(loc, target):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def render(name, poses, lens):
    cam_data.lens = lens
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    for i, (loc, tgt) in enumerate(poses):
        f = d / f"{i:04d}.png"
        if f.exists():
            continue
        look(loc, tgt)
        sc.render.filepath = str(f)
        bpy.ops.render.render(write_still=True)
        print(f"[fly] {name} {i + 1}/{len(poses)}", flush=True)


if "orbit" in shots:
    R = size * 1.25 + 8
    poses = []
    for i in range(frames):
        t = i / frames
        a = -math.pi / 2 + 2 * math.pi * t          # start in front of the house (-Y, street side)
        z = hi.z + 6 + 4 * math.sin(math.pi * t)     # rise a little mid-orbit
        loc = (center.x + R * math.cos(a), center.y + R * math.sin(a), z)
        poses.append((loc, (center.x, center.y, lo.z + 1.5)))
    render("orbit", poses, 30)

if "living" in shots:
    b = collection_bbox("LivingRoom")
    if b:
        rlo, rhi = b
        c = (rlo + rhi) / 2
        z = rlo.z + 1.5
        n = max(2, frames * 2 // 3)
        poses = []
        for i in range(n):
            a = math.radians(300) * i / (n - 1)
            poses.append(((c.x, c.y, z), (c.x + math.cos(a), c.y + math.sin(a), z - 0.08)))
        render("living", poses, 18)
