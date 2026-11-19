Build a photorealistic single-storey suburban brick house in late-afternoon sun. It has:
- a kitchen, a living room and three bedrooms;
- a two-lane traffic road with sidewalks in front (−Y);
- a fenced, planted backyard garden behind (+Y);
- a believable neighbourhood around it (no endless empty plane).

The look should be a real-estate photo: AgX, natural daylight, warm interior lights. Keep the script within the system prompt's budget; build only what is listed here.

## House (meters; floor top FL=0.15, ceiling 2.85, exterior wall top 3.0)
- Footprint: x −8..8, y 0..10.5. Concrete foundation x −8.3..8.3, y −0.3..10.8, z 0..0.1.
- Exterior walls: thickness 0.25, centred on x=±8, y=0 and y=10.5. Brick outside, paint inside, including the reveals.
- Interior walls: thickness 0.12, centred on these lines (openings as u_centre:width):
  - y=4.5, x −8..8: Living→hall opening x=−1.0:1.4; Entry→hall opening x=1.5:2.4; Kitchen door x=4.0:0.9.
  - y=5.7, x −8..8: doors x=−4.2:0.9 (Bedroom_1), −2.0:0.8 (bath), 0.0:0.9 (Bedroom_2), 4.4:0.9 (Bedroom_3).
  - Solid walls: x=0 and x=3, both spanning y 0..4.5; x=−3.2, −0.8 and 3.4, all spanning y 5.7..10.5.
- Interior rectangles (floor and ceiling must match exactly):

| Space | x | y | Collection |
|---|---|---|---|
| LivingRoom | −7.875..−0.06 | 0.125..4.44 | LivingRoom |
| Kitchen | 3.06..7.875 | 0.125..4.44 | Kitchen |
| Entry | 0.06..2.94 | 0.125..4.44 | House_Shell |
| Hall | −7.875..7.875 | 4.56..5.64 | House_Shell |
| Bedroom_1 | −7.875..−3.26 | 5.76..10.375 | Bedroom_1 |
| Bath | −3.14..−0.86 | 5.76..10.375 | House_Shell |
| Bedroom_2 | −0.74..3.34 | 5.76..10.375 | Bedroom_2 |
| Bedroom_3 | 3.46..7.875 | 5.76..10.375 | Bedroom_3 |

- Windows: sill FL+0.9, head FL+2.2 (bath sill FL+1.5).
  - Front y=0: x=−6.0 (2.0 wide), x=−2.5 (1.6), x=5.5 (1.6).
  - Back y=10.5: x=−5.6 (1.6), x=−2.0 (0.6), x=1.3 (1.6), x=5.7 (1.6).
  - East x=8: y=2.2 (1.2, kitchen sink, sill FL+1.0), y=9.6 (1.0, Bedroom_3).
- Front door: y=0 at x=1.5, 1.0 wide, panelled wood with a brass knob. Porch step x 0.7..2.3, y −1.0..−0.3. Flat canopy over the door on two posts.
- Side door: east wall at y=5.1, 0.9 wide.
- Roof:
  - Gable with the ridge along X at y=5.25; eaves z=3.0 at y=−0.5 and y=11.0; slope 0.55 (ridge z≈6.16); 0.2 thick; overhang to x=±8.6.
  - Clay roof tiles, ridge cap, brick gable triangles, white fascia and soffit, gutters, 4 downpipes.
  - Brick chimney x 4..4.7, y 7..7.7, top 6.9.

## Interiors
Corner cameras stand in each room's SW corner looking NE, so feature pieces face them from the north/east walls. Every item stays inside its rectangle. Corners stay clear of anything taller than 0.9 m for 1 m. No door leaves.

**All rooms**
- Floors are laminate, except: Kitchen 'Kitchen_Stone_Tiles'; Bedroom_2 laminate tinted darker (0.6, 0.48, 0.4); Bath 'Subway_Tiles'.
- Every room has: pleated curtains on its windows, at least one framed art piece, skirting, and its own ceiling light.

**Ceiling fixtures**
- LivingRoom and Kitchen use the modern_ceiling_lamp_01 pendant (emissive shade + point light).
- Bedrooms use a procedural drum pendant, NOT the globe:
  - frustum shade r 0.28→0.25, 0.22 tall, emissive fabric;
  - thin cord box up to the ceiling;
  - point light inside;
  - name '<Room>_Lamp_Pendant'.

**LivingRoom** (keep this layout; it scored best)
- TV wall: west wall x=−7.875. Wooden console 1.8×0.45×0.5 at y=2.3 with television_02 on top.
- sofa_02 at x≈−4.2, y=2.3, facing west.
- coffee_table_round_01 at (−5.8, 2.3), with a 3.0×2.4 rug under it.
- modern_arm_chair_01 at (−5.8, 0.95) facing +Y, and another at (−5.8, 3.65) facing −Y.
- drawer_cabinet against the north wall at x=−4.5.
- Procedural floor lamp (pole + emissive drum + point light) at (−3.2, 3.7).
- potted_plant_02 at (−2.0, 0.6), h 1.1.
- Art 1.2×0.8 on the east wall at y=2.3, z=1.7.
- Pendant over the coffee table.

**Kitchen** (L-shaped)
- Base cabinets 0.6 deep with a plinth and doors with handles; marble counter top at FL+0.92.
- Runs along the east wall (y 1.2..4.44) and the north wall (x 5.4..7.875).
- Sink + faucet (2 boxes) under the east window at y=2.2; no upper cabinets over the window.
- electric_stove in the north run at x=6.4, with a steel hood and flue above.
- Upper cabinets FL+1.5..FL+2.2.
- Subway_Tiles backsplash from the counter to the uppers.
- Steel fridge at x 4.6..5.35 against the north wall.
- wooden_table_02 at (4.9, 1.9) with 4 painted_wooden_chair_01; pendant above it.
- ONE potted_plant_04 (h 0.35) ON the counter at (7.55, 3.5). No floor plants.
- Art 0.6×0.8 on the west wall at y=2.3.

**Bedroom_1** (x −7.875..−3.26)
- Bed_1: procedural double bed 1.6×2.05.
  - Wood base 0.35 high; upholstered headboard 1.1 high against the EAST wall (x=−3.26), centred y=8.0. The bed extends west to x≈−5.31.
  - Blue-grey draped duvet (0.42, 0.5, 0.58), white folded band, 2 superellipsoid pillows.
- painted_wooden_nightstand against the east wall at y≈6.92 and y≈9.08 (names include 'Nightstand'); desk_lamp_arm_01 (h 0.45) on each ('Lamp').
- Sage accent panel (0.55, 0.62, 0.52) on the east wall, y 6.8..9.3.
- Art 1.0×0.6 above the headboard at z FL+1.75.
- Procedural 'Bedroom_1_Wardrobe' 1.2×0.6×2.1 (wood, 2 doors, steel handles) against the west wall, centred y=8.0.
- Rug x −6.4..−4.0, y 6.7..9.3.
- potted_plant_02 h 1.0 at (−6.8, 9.2).
- Curtains on the north window; drum pendant at (−4.6, 8.0).

**Bedroom_2** (study bedroom, x −0.74..3.34)
- Bed_2: procedural single bed 0.95×2.0.
  - Wooden headboard 0.9 high against the EAST wall (x=3.34), centred y=7.4.
  - Mustard duvet (0.78, 0.58, 0.16), cream band, 1 pillow.
- painted_wooden_nightstand against the east wall at y≈8.15, with desk_lamp_arm_01 on it.
- Desk 1.2×0.6×0.75 (merged top + 4 legs) under the north window, centred x=1.3, y 9.77..10.37.
  - painted_wooden_chair_01 at (1.3, 9.45) facing the desk.
  - A second desk_lamp_arm_01 on the desk.
- Procedural 'Bedroom_2_Wardrobe' against the west wall, centred y=7.8.
- Pale blue accent (0.60, 0.68, 0.76) on the east wall, y 6.8..9.3; art 0.8×0.6 above the headboard.
- Rug x −0.2..1.2, y 6.6..8.6.
- Curtains (pale blue) on the north window; drum pendant at (1.6, 7.6).

**Bedroom_3** (guest bedroom, x 3.46..7.875)
- Bed_3: procedural double bed 1.5×2.05.
  - Slatted wooden headboard 1.0 high against the EAST wall (x=7.875), centred y=7.5.
  - Terracotta duvet (0.72, 0.4, 0.28), cream band, 2 pillows.
- Nightstands against the east wall at y≈6.5 and y≈8.5; lamp on the north one.
- Terracotta accent (0.72, 0.55, 0.45) on the east wall, y 6.8..8.95; art above the headboard.
- drawer_cabinet renamed 'Bedroom_3_Wardrobe' against the west wall, centred y=8.0, with potted_plant_04 on top.
- modern_arm_chair_01 at (4.4, 9.3) angled toward the bed.
- Large rug x 4.6..7.2, y 6.3..8.9.
- Curtains on the north (x=5.7) and east (y=9.6) windows; drum pendant at (6.0, 7.5).

**Bath**
- Floor and ceiling in House_Shell.
- Tub box 1.7×0.75×0.55 along the back wall (x −2.85..−1.15), Ceramic.
- Vanity box on the west wall with a mirror box above it.

**Hall/Entry**
- Laminate floor, ceiling area light. Art in the entry on the west wall.

## Road and front (collection Road; everything outside the house at y < 5.25)
**Road**
- Road_Asphalt: x −300..300, y −16..−9, top z 0.02.
- Curb_Near: y −9.15..−9. Curb_Far: y −16..−15.85. Curbs are 0.15 high.
- Sidewalk_Near: y −9..−7. Sidewalk_Far: y −18..−16. Sidewalks top z 0.15, joints every 1.5 m.

**Markings**
- Road_Marking_Center: yellow dashes 3 m on / 3 m off, 0.12 wide, at y=−12.5.
- Road_Marking_Edge: white solid lines at y=−9.45 and y=−15.55.
- Road_Marking_Crosswalk: 6 white stripes at x −22..−19.

**Street lamps** (Street_Lamp_*)
- street_lamp_01 at h=4.5, arm over the road.
- Near side x=−16, 18, −44, 46 (y=−8.5); far side x=−30, 30 (y=−16.6).
- No lamp within |x|<10.

**Ground** (lawn material)
- FrontYard_Lawn: x −1000..1000, y −7..5.25.
- Verge_Far: x −1000..1000, y −1000..−18.
- 'Verge_Grass' blades (grass helper): x −16..16, y −27.5..−18.1. This is the front camera's foreground.

**Front details**
- Driveway: concrete, x 9..12, y −7..4. If ids('car') is non-empty, place one car on it at (10.5, −1.5) facing −Y, h≈1.45.
- Front path: x 1.0..2.0, y −7..−1.
- Soil beds along the facade: y −1.6..−0.5, x −7.9..0.55 and 2.45..7.9.
  - shrub_01/shrub_04 at y=−1.15 every ~1.8 m, h 0.6–0.9, footprint ≤0.9 m (clearance rule).
- tree_small_02 h 6 at (−12, −4).
- Street trees on the far verge: tree_small_02 and jacaranda_tree alternating at y=−20, x=−40, −20, 20, 40.

**Neighbours** (Road collection; reuse ONE neighbour(cx, y_front, facing, wall_mat, roof_mat) function)
- Same side, facing −Y, front wall at y=0, footprint 12×9: cx = −56, −28, 28, 56.
- Across the street, facing +Y, front wall at y=−24, back wall at y=−33: cx = −30, 30. They are outside the front camera's view.
- Walls alternate between red_brick tinted lighter and painted render (0.85, 0.82, 0.75). Roofs are clay_roof_tiles_02, with alternate ones tinted grey-brown.
- Each neighbour has:
  - concrete base and 2.9 m walls;
  - gable roof with gable triangles, ridge and fascia;
  - 2 front windows (dark inset panel + Window_Glass pane);
  - a door, a path to the sidewalk and a 3 m concrete driveway;
  - 2 shrubs.
- Same-side neighbours' backyard lot fences: 1.2 m boards on lines x = cx±12, y 10.6..40, plus a rear line at y=40. Merge them all into ONE mesh 'Garden_Neighbour_Fences' (Garden collection).

## Backyard garden (collection Garden; every object at y > 10.5)
The backyard camera stands at about (0, 38, 1.5) looking at the house; it must be inside the fence and see a full, planted garden.

**Ground and fence**
- Garden_Lawn: x −1000..1000, y 5.25..1000 (lawn material).
- Garden_Fence: ONE merged mesh, wood_table_001 tinted grey-brown.
  - Side fences at x=±13, y 10.6..46: 1.5 m tall horizontal boards on posts.
  - Returns from the house corners (x ±8.1 → ±13 at y=10.6), 1.5 m tall.
  - ONE rear run at y=46, x −13..13: LOW 0.9 m picket (0.09 pickets, 0.08 gaps, two rails).
  - No other fence lines.

**Patio and path**
- Garden_Patio: concrete pavers x −3.5..3.5, y 10.6..14.
  - outdoor_table_chair_set_01 at (0, 12.3).
  - 2 potted_plant_04 at (±3.1, 13.6).
- Garden_Path: about 16 merged stepping stones (0.6×0.45, slight random rotation), curving gently (x = 1.0·sin) from (0, 14.5) to (0, 40).

**Beds** (Garden_Bed_*, forest_ground_04 soil, 0.05 high)
- Garden_Bed_East and Garden_Bed_West: x 11.6..12.9 and −12.9..−11.6, y 12..44. shrub_01/shrub_04 alternating every 3 m, h 0.8–1.3.
- Garden_Bed_Island: 4×2.2 at centre (−5.5, 26), with 5 flowers (ids('flower') if available, else shrub_04), h 0.4–0.7.
- Garden_Bed_Rear: y 44.4..45.6, x −12..12. Low shrubs every 3 m, h ≤0.7.
- Garden_Bed_Veg_0/1: raised wooden frames 3×1.2×0.35 at x 5..8, centred y=22 and y=25, filled with soil and holding small plants (h 0.4).

**Trees** (Garden_Tree_*)
- jacaranda_tree h 9 at (−10, 24).
- tree_small_02 h 6 at (10, 18) and at (10.5, 33).
- Keep |x|<6.5, y 11..42 free of anything taller than 1.2 m.

**Grass and context**
- 'Garden_Grass' blades: x −11.5..11.5, y 20..43. Skip the bed rectangles, veg beds, island, and 0.35 m around each path stone.
- Context trees:
  - about 20 duplicates at y 55..100, |x| 16..90, h 6–10 (Garden);
  - about 8 duplicates at y −40..−90, |x| 10..80 (Road).
  - These give a tree-line horizon in both directions.

## Lighting and look
- HDRI sky plus a low warm sun lighting the facade and casting window patches into the front rooms.
- Ceiling area lights at 4 W/m², glowing pendants and drums, and bedside lamps.
- AgX Medium High Contrast, exposure 0.
- Interiors bright but not blown out; the exterior facade lit by the sun with crisp shadows.