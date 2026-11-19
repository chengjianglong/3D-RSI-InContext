"""Hand-written trivial scene used to test the harness/checks without any LLM."""
import bpy


def box(name, col, loc, size):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    return ob


def build_scene(ctx):
    shell = ctx.collection("House_Shell")
    box("wall_floor", shell, (0, 0, -0.05), (14, 10, 0.1))
    box("roof", shell, (0, 0, 3.2), (14, 10, 0.2))
    rooms = {"Kitchen": (-4.5, -2.5), "LivingRoom": (0, -2.5), "Bedroom_1": (-4.5, 2.5),
             "Bedroom_2": (0, 2.5), "Bedroom_3": (4.5, 2.5)}
    for r, (x, y) in rooms.items():
        col = ctx.collection(r)
        box(f"{r}_floor", col, (x, y, 0.01), (4.4, 4.8, 0.02))
        box("bed" if r.startswith("Bed") else "sofa", col, (x, y, 0.3), (1.6, 2.0, 0.6))
    road = ctx.collection("Road")
    box("road", road, (0, -14, 0), (60, 7, 0.05))
    box("sidewalk", road, (0, -9.5, 0.05), (60, 2, 0.1))
    garden = ctx.collection("Garden")
    box("grass", garden, (0, 13, 0), (20, 16, 0.02))
    box("tree", garden, (3, 15, 2), (1, 1, 4))
    light = ctx.collection("Lighting")
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.rotation_euler = (0.8, 0.2, 0.5)
    light.objects.link(sun)
