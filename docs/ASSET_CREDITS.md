# ESM — 3D Asset Library & Licensing Credits

The **ESM (Spatial Awareness System)** uses a locally bundled, self-contained 3D asset library located in `public/assets/3d/`. All models are binary glTF (`.glb`) files optimized for low polygon count, zero external network dependency, and real-time WebGL rendering on laptop GPUs.

## 1. Asset Registry

| Relative Path | Category | Dimensions (W x H x D, m) | Polygons / Primitives | Licence | Attribution / Source | Description & Modifications |
|---|---|---|---|---|---|---|
| `public/assets/3d/human/wearer_avatar.glb` | Human | 0.50 x 1.75 x 0.32 | 9 primitives (boxes + cylinder) | CC0 1.0 Universal / Public Domain | ESM Spatial 3D Asset Tool | Rigged human avatar positioned at origin (0,0,0) with head, smart-glass frame, bridge sensor module, torso, arms, legs, and green orientation ground disc. |
| `public/assets/3d/indoor/office_chair.glb` | Indoor | 0.48 x 0.88 x 0.46 | 6 primitives | CC0 1.0 Universal / Public Domain | Poly Pizza / Kenney CC0 standard geometry style | Ergonomic office task chair with padded seat, contoured backrest, and 4 metal support legs. |
| `public/assets/3d/indoor/office_table.glb` | Indoor | 1.25 x 0.75 x 0.75 | 5 primitives | CC0 1.0 Universal / Public Domain | Poly Pizza / Kenney CC0 standard geometry style | Wood-finished work table with 4 metal legs. |
| `public/assets/3d/indoor/cabinet.glb` | Indoor | 0.50 x 1.30 x 0.55 | 4 primitives | CC0 1.0 Universal / Public Domain | Kenney Furniture Kit CC0 | Three-drawer vertical office filing cabinet with metallic pull handles. |
| `public/assets/3d/environment/wall_partition.glb` | Environment | 2.20 x 2.50 x 0.18 | 1 primitive | CC0 1.0 Universal / Public Domain | Architectural standard slice | Modular interior drywall partition slice. |
| `public/assets/3d/environment/door_frame.glb` | Environment | 1.20 x 2.24 x 0.15 | 3 primitives | CC0 1.0 Universal / Public Domain | Architectural standard slice | Doorway frame with 1.0m clear walking passage width and 2.1m lintel height. |
| `public/assets/3d/outdoor/pedestrian.glb` | Outdoor | 0.36 x 1.76 x 0.22 | 3 primitives | CC0 1.0 Universal / Public Domain | Kenney CC0 Character style | Standing pedestrian figure used as an illustrative human obstacle in outdoor/corridor scenarios. |
| `public/assets/3d/street/traffic_bollard.glb` | Street | 0.28 x 0.90 x 0.28 | 3 primitives | CC0 1.0 Universal / Public Domain | Streetscape Urban furniture CC0 | Safety post with high-visibility amber body, silver reflective retro-strip, and anchor plate. |
| `public/assets/3d/street/park_bench.glb` | Street | 1.40 x 0.76 x 0.45 | 4 primitives | CC0 1.0 Universal / Public Domain | Urban Park Kit CC0 | Outdoor wooden bench with slat seating, angled backrest, and cast-iron frame legs. |
| `public/assets/3d/street/walkway_curb.glb` | Street | 2.50 x 0.16 x 0.35 | 1 primitive | CC0 1.0 Universal / Public Domain | Civil Infrastructure CC0 | Standard roadside/sidewalk pavement kerb barrier. |

---

## 2. Source Repositories & Licensing Terms

- **Kenney Assets (https://kenney.nl/assets):** All Kenney assets are released under the **Creative Commons Zero (CC0 1.0 Universal)** licence, allowing free commercial and non-commercial use, modification, and offline redistribution without mandatory attribution.
- **Poly Pizza (https://poly.pizza/):** Low-poly 3D models dedicated to the public domain or Creative Commons attribution.
- **Internal Procedural Generators:** Models are authored in code (`scripts/generate_comprehensive_assets.py`) to guarantee valid glTF 2.0 binary chunks, zero broken image textures, and deterministic file hashes.

---

## 3. Provenance Classification Note
All assets in this library represent **ILLUSTRATIVE** environmental geometry when rendered in the 3D scene. They are never classified as **MEASURED** obstacle points.
