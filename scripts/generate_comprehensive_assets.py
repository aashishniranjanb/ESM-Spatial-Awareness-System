import struct
import json
import os
import math

def build_glb(output_path, primitives_data):
    """
    primitives_data is a list of dicts:
    {
      'vertices': [x,y,z, ...],
      'indices': [i0, i1, i2, ...],
      'color': [r, g, b, 1.0],
      'metallic': 0.1,
      'roughness': 0.8
    }
    """
    total_vert_bytes = bytearray()
    total_idx_bytes = bytearray()
    
    meshes = []
    materials = []
    accessors = []
    buffer_views = []
    
    # We combine into 2 main bufferViews: indices and vertices
    current_idx_offset = 0
    current_vert_offset = 0
    
    idx_list = []
    vert_list = []
    
    for i, p in enumerate(primitives_data):
        v = p['vertices']
        idx = p['indices']
        
        # vertex buffer bytes
        v_bytes = struct.pack(f"<{len(v)}f", *v)
        # index buffer bytes
        i_bytes = struct.pack(f"<{len(idx)}H", *idx)
        
        vert_list.append(v_bytes)
        idx_list.append(i_bytes)
        
        materials.append({
            "pbrMetallicRoughness": {
                "baseColorFactor": p.get('color', [0.5, 0.5, 0.5, 1.0]),
                "metallicFactor": p.get('metallic', 0.1),
                "roughnessFactor": p.get('roughness', 0.8)
            }
        })
        
    full_idx_data = bytearray()
    full_vert_data = bytearray()
    
    mesh_primitives = []
    
    for i, p in enumerate(primitives_data):
        v = p['vertices']
        idx = p['indices']
        
        # Pad each index chunk to 2 or 4 byte boundary
        idx_offset = len(full_idx_data)
        idx_bytes = struct.pack(f"<{len(idx)}H", *idx)
        full_idx_data.extend(idx_bytes)
        while len(full_idx_data) % 4 != 0:
            full_idx_data.extend(b'\x00')
            
        vert_offset = len(full_vert_data)
        vert_bytes = struct.pack(f"<{len(v)}f", *v)
        full_vert_data.extend(vert_bytes)
        while len(full_vert_data) % 4 != 0:
            full_vert_data.extend(b'\x00')
            
        # Accessor for indices
        idx_acc_idx = len(accessors)
        accessors.append({
            "bufferView": 0,
            "byteOffset": idx_offset,
            "componentType": 5123, # UNSIGNED_SHORT
            "count": len(idx),
            "type": "SCALAR",
            "max": [max(idx) if idx else 0],
            "min": [min(idx) if idx else 0]
        })
        
        # Accessor for positions
        hx = [v[k] for k in range(0, len(v), 3)]
        hy = [v[k] for k in range(1, len(v), 3)]
        hz = [v[k] for k in range(2, len(v), 3)]
        
        vert_acc_idx = len(accessors)
        accessors.append({
            "bufferView": 1,
            "byteOffset": vert_offset,
            "componentType": 5126, # FLOAT
            "count": len(v) // 3,
            "type": "VEC3",
            "max": [max(hx), max(hy), max(hz)],
            "min": [min(hx), min(hy), min(hz)]
        })
        
        mesh_primitives.append({
            "attributes": {"POSITION": vert_acc_idx},
            "indices": idx_acc_idx,
            "material": i
        })
        
    buffer_views = [
        {"buffer": 0, "byteOffset": 0, "byteLength": len(full_idx_data), "target": 34963}, # ELEMENT_ARRAY_BUFFER
        {"buffer": 0, "byteOffset": len(full_idx_data), "byteLength": len(full_vert_data), "target": 34962} # ARRAY_BUFFER
    ]
    
    bin_data = full_idx_data + full_vert_data
    while len(bin_data) % 4 != 0:
        bin_data.extend(b'\x00')
        
    gltf_dict = {
        "asset": {"version": "2.0", "generator": "ESM Spatial 3D Asset Tool"},
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": mesh_primitives}],
        "materials": materials,
        "buffers": [{"byteLength": len(bin_data)}],
        "bufferViews": buffer_views,
        "accessors": accessors
    }
    
    json_bytes = json.dumps(gltf_dict).encode('utf-8')
    while len(json_bytes) % 4 != 0:
        json_bytes += b' '
        
    total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    header = struct.pack("<4sII", b"glTF", 2, total_length)
    json_chunk_header = struct.pack("<II", len(json_bytes), 0x4E4F534A)
    bin_chunk_header = struct.pack("<II", len(bin_data), 0x004E4942)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(header)
        f.write(json_chunk_header)
        f.write(json_bytes)
        f.write(bin_chunk_header)
        f.write(bin_data)

def make_box(cx, cy, cz, sx, sy, sz):
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    v = [
        # Front
        cx-hx, cy-hy, cz+hz,  cx+hx, cy-hy, cz+hz,  cx+hx, cy+hy, cz+hz,  cx-hx, cy+hy, cz+hz,
        # Back
        cx-hx, cy-hy, cz-hz,  cx-hx, cy+hy, cz-hz,  cx+hx, cy+hy, cz-hz,  cx+hx, cy-hy, cz-hz,
        # Top
        cx-hx, cy+hy, cz-hz,  cx-hx, cy+hy, cz+hz,  cx+hx, cy+hy, cz+hz,  cx+hx, cy+hy, cz-hz,
        # Bottom
        cx-hx, cy-hy, cz-hz,  cx+hx, cy-hy, cz-hz,  cx+hx, cy-hy, cz+hz,  cx-hx, cy-hy, cz+hz,
        # Right
        cx+hx, cy-hy, cz-hz,  cx+hx, cy+hy, cz-hz,  cx+hx, cy+hy, cz+hz,  cx+hx, cy-hy, cz+hz,
        # Left
        cx-hx, cy-hy, cz-hz,  cx-hx, cy-hy, cz+hz,  cx-hx, cy+hy, cz+hz,  cx-hx, cy+hy, cz-hz,
    ]
    idx = [
         0,  1,  2,   0,  2,  3,
         4,  5,  6,   4,  6,  7,
         8,  9, 10,   8, 10, 11,
        12, 13, 14,  12, 14, 15,
        16, 17, 18,  16, 18, 19,
        20, 21, 22,  20, 22, 23
    ]
    return v, idx

def make_cylinder(cx, cy, cz, radius, height, segments=16):
    v = []
    idx = []
    half_h = height / 2.0
    
    # Top center vertex
    top_center_idx = 0
    v.extend([cx, cy + half_h, cz])
    # Bottom center vertex
    bot_center_idx = 1
    v.extend([cx, cy - half_h, cz])
    
    top_ring_start = 2
    bot_ring_start = 2 + segments
    
    for i in range(segments):
        theta = 2.0 * math.pi * i / segments
        px = cx + radius * math.cos(theta)
        pz = cz + radius * math.sin(theta)
        # top ring
        v.extend([px, cy + half_h, pz])
    for i in range(segments):
        theta = 2.0 * math.pi * i / segments
        px = cx + radius * math.cos(theta)
        pz = cz + radius * math.sin(theta)
        # bottom ring
        v.extend([px, cy - half_h, pz])
        
    for i in range(segments):
        nxt = (i + 1) % segments
        # Top cap
        idx.extend([top_center_idx, top_ring_start + i, top_ring_start + nxt])
        # Bottom cap
        idx.extend([bot_center_idx, bot_ring_start + nxt, bot_ring_start + i])
        # Side quad
        idx.extend([top_ring_start + i, bot_ring_start + i, top_ring_start + nxt])
        idx.extend([top_ring_start + nxt, bot_ring_start + i, bot_ring_start + nxt])
        
    return v, idx

print("Generator functions prepared.")

# 1. Rigged Human Avatar: Head, Smart Glasses, Torso, Arms, Legs
# Total height approx 1.75m. Origin at feet (y=0)
def generate_human_avatar():
    prims = []
    # Head (centered at y=1.55)
    v_head, i_head = make_box(0, 1.55, 0, 0.22, 0.24, 0.22)
    prims.append({'vertices': v_head, 'indices': i_head, 'color': [0.85, 0.72, 0.62, 1.0], 'roughness': 0.6})
    
    # Smart Glasses on head (y=1.57, z=-0.12)
    v_glasses, i_glasses = make_box(0, 1.57, -0.12, 0.24, 0.05, 0.06)
    prims.append({'vertices': v_glasses, 'indices': i_glasses, 'color': [0.0, 0.82, 0.91, 1.0], 'metallic': 0.8, 'roughness': 0.2})
    
    # Sensor Module on bridge (y=1.57, z=-0.16)
    v_sensor, i_sensor = make_box(0, 1.57, -0.16, 0.08, 0.04, 0.04)
    prims.append({'vertices': v_sensor, 'indices': i_sensor, 'color': [0.03, 0.47, 0.82, 1.0], 'metallic': 0.9, 'roughness': 0.1})
    
    # Torso (centered at y=1.05)
    v_torso, i_torso = make_box(0, 1.05, 0, 0.38, 0.62, 0.24)
    prims.append({'vertices': v_torso, 'indices': i_torso, 'color': [0.07, 0.23, 0.38, 1.0], 'roughness': 0.7})
    
    # Left Arm
    v_larm, i_larm = make_box(-0.25, 1.02, 0, 0.1, 0.55, 0.12)
    prims.append({'vertices': v_larm, 'indices': i_larm, 'color': [0.08, 0.28, 0.45, 1.0], 'roughness': 0.7})
    
    # Right Arm
    v_rarm, i_rarm = make_box(0.25, 1.02, 0, 0.1, 0.55, 0.12)
    prims.append({'vertices': v_rarm, 'indices': i_rarm, 'color': [0.08, 0.28, 0.45, 1.0], 'roughness': 0.7})
    
    # Left Leg (centered at y=0.4)
    v_lleg, i_lleg = make_box(-0.11, 0.4, 0, 0.14, 0.78, 0.16)
    prims.append({'vertices': v_lleg, 'indices': i_lleg, 'color': [0.05, 0.11, 0.18, 1.0], 'roughness': 0.8})
    
    # Right Leg
    v_rleg, i_rleg = make_box(0.11, 0.4, 0, 0.14, 0.78, 0.16)
    prims.append({'vertices': v_rleg, 'indices': i_rleg, 'color': [0.05, 0.11, 0.18, 1.0], 'roughness': 0.8})
    
    # Foot origin disc
    v_base, i_base = make_cylinder(0, 0.015, 0, 0.28, 0.03, segments=16)
    prims.append({'vertices': v_base, 'indices': i_base, 'color': [0.0, 0.76, 0.66, 1.0], 'metallic': 0.4, 'roughness': 0.3})
    
    build_glb("public/assets/3d/human/wearer_avatar.glb", prims)

# 2. Indoor Furniture: Ergonomic Chair
def generate_chair():
    prims = []
    # Seat (0.48 x 0.06 x 0.46 at y=0.45)
    v_seat, i_seat = make_box(0, 0.45, 0, 0.48, 0.06, 0.46)
    prims.append({'vertices': v_seat, 'indices': i_seat, 'color': [0.22, 0.28, 0.35, 1.0], 'roughness': 0.7})
    # Backrest (y=0.78, z=0.2)
    v_back, i_back = make_box(0, 0.78, 0.2, 0.46, 0.54, 0.05)
    prims.append({'vertices': v_back, 'indices': i_back, 'color': [0.18, 0.24, 0.31, 1.0], 'roughness': 0.7})
    # Legs (4 metal legs)
    for lx in [-0.2, 0.2]:
        for lz in [-0.19, 0.19]:
            v_leg, i_leg = make_box(lx, 0.21, lz, 0.04, 0.42, 0.04)
            prims.append({'vertices': v_leg, 'indices': i_leg, 'color': [0.65, 0.7, 0.75, 1.0], 'metallic': 0.8, 'roughness': 0.2})
    build_glb("public/assets/3d/indoor/office_chair.glb", prims)

# 3. Indoor Furniture: Desk / Table (1.2m x 0.75m x 0.7m)
def generate_table():
    prims = []
    # Top
    v_top, i_top = make_box(0, 0.72, 0, 1.25, 0.05, 0.75)
    prims.append({'vertices': v_top, 'indices': i_top, 'color': [0.38, 0.27, 0.19, 1.0], 'roughness': 0.5})
    # 4 Legs
    for lx in [-0.56, 0.56]:
        for lz in [-0.32, 0.32]:
            v_leg, i_leg = make_box(lx, 0.35, lz, 0.06, 0.69, 0.06)
            prims.append({'vertices': v_leg, 'indices': i_leg, 'color': [0.15, 0.18, 0.22, 1.0], 'metallic': 0.6, 'roughness': 0.4})
    build_glb("public/assets/3d/indoor/office_table.glb", prims)

# 4. Indoor Furniture: Filing Cabinet
def generate_cabinet():
    prims = []
    v_body, i_body = make_box(0, 0.65, 0, 0.5, 1.3, 0.55)
    prims.append({'vertices': v_body, 'indices': i_body, 'color': [0.28, 0.33, 0.39, 1.0], 'metallic': 0.5, 'roughness': 0.4})
    # Handles (3 drawers)
    for hy in [0.95, 0.65, 0.35]:
        v_h, i_h = make_box(0, hy, -0.29, 0.14, 0.03, 0.03)
        prims.append({'vertices': v_h, 'indices': i_h, 'color': [0.85, 0.9, 0.95, 1.0], 'metallic': 0.9, 'roughness': 0.1})
    build_glb("public/assets/3d/indoor/cabinet.glb", prims)

# 5. Environment: Door Frame and Wall Segment
def generate_environment():
    # Wall segment
    prims_wall = []
    v_w, i_w = make_box(0, 1.25, 0, 2.2, 2.5, 0.18)
    prims_wall.append({'vertices': v_w, 'indices': i_w, 'color': [0.15, 0.22, 0.31, 1.0], 'roughness': 0.8})
    build_glb("public/assets/3d/environment/wall_partition.glb", prims_wall)
    
    # Door frame (opening 1.0m wide, 2.1m high)
    prims_door = []
    # Left post
    v_lp, i_lp = make_box(-0.55, 1.08, 0, 0.1, 2.16, 0.15)
    prims_door.append({'vertices': v_lp, 'indices': i_lp, 'color': [0.25, 0.32, 0.42, 1.0], 'roughness': 0.6})
    # Right post
    v_rp, i_rp = make_box(0.55, 1.08, 0, 0.1, 2.16, 0.15)
    prims_door.append({'vertices': v_rp, 'indices': i_rp, 'color': [0.25, 0.32, 0.42, 1.0], 'roughness': 0.6})
    # Top lintel
    v_tp, i_tp = make_box(0, 2.19, 0, 1.2, 0.1, 0.15)
    prims_door.append({'vertices': v_tp, 'indices': i_tp, 'color': [0.25, 0.32, 0.42, 1.0], 'roughness': 0.6})
    build_glb("public/assets/3d/environment/door_frame.glb", prims_door)

# 6. Outdoor: Pedestrian / Street Obstacle
def generate_pedestrian():
    prims = []
    v_head, i_head = make_box(0, 1.58, 0, 0.2, 0.22, 0.2)
    prims.append({'vertices': v_head, 'indices': i_head, 'color': [0.82, 0.68, 0.58, 1.0], 'roughness': 0.6})
    v_torso, i_torso = make_box(0, 1.08, 0, 0.36, 0.64, 0.22)
    prims.append({'vertices': v_torso, 'indices': i_torso, 'color': [0.65, 0.25, 0.22, 1.0], 'roughness': 0.7})
    v_legs, i_legs = make_box(0, 0.4, 0, 0.32, 0.78, 0.18)
    prims.append({'vertices': v_legs, 'indices': i_legs, 'color': [0.12, 0.15, 0.22, 1.0], 'roughness': 0.8})
    build_glb("public/assets/3d/outdoor/pedestrian.glb", prims)

# 7. Street: Traffic Cone / Safety Bollard
def generate_street_objects():
    # Traffic bollard with reflective band
    prims_b = []
    v_body, i_body = make_cylinder(0, 0.45, 0, 0.08, 0.9, segments=16)
    prims_b.append({'vertices': v_body, 'indices': i_body, 'color': [0.96, 0.65, 0.14, 1.0], 'roughness': 0.4})
    # Reflective band
    v_band, i_band = make_cylinder(0, 0.62, 0, 0.083, 0.16, segments=16)
    prims_b.append({'vertices': v_band, 'indices': i_band, 'color': [0.95, 0.95, 0.98, 1.0], 'metallic': 0.3, 'roughness': 0.1})
    # Base plate
    v_base, i_base = make_box(0, 0.02, 0, 0.28, 0.04, 0.28)
    prims_b.append({'vertices': v_base, 'indices': i_base, 'color': [0.12, 0.14, 0.18, 1.0], 'metallic': 0.6, 'roughness': 0.5})
    build_glb("public/assets/3d/street/traffic_bollard.glb", prims_b)
    
    # Park / Street Bench
    prims_bench = []
    # Seat planks
    v_seat, i_seat = make_box(0, 0.46, 0, 1.4, 0.05, 0.45)
    prims_bench.append({'vertices': v_seat, 'indices': i_seat, 'color': [0.44, 0.29, 0.18, 1.0], 'roughness': 0.6})
    # Backrest
    v_back, i_back = make_box(0, 0.74, 0.21, 1.4, 0.32, 0.04)
    prims_bench.append({'vertices': v_back, 'indices': i_back, 'color': [0.44, 0.29, 0.18, 1.0], 'roughness': 0.6})
    # Cast-iron side legs
    for sx in [-0.62, 0.62]:
        v_leg, i_leg = make_box(sx, 0.23, 0, 0.06, 0.46, 0.42)
        prims_bench.append({'vertices': v_leg, 'indices': i_leg, 'color': [0.12, 0.15, 0.18, 1.0], 'metallic': 0.8, 'roughness': 0.3})
    build_glb("public/assets/3d/street/park_bench.glb", prims_bench)
    
    # Walkway Kerb / Curb
    prims_kerb = []
    v_k, i_k = make_box(0, 0.08, 0, 2.5, 0.16, 0.35)
    prims_kerb.append({'vertices': v_k, 'indices': i_k, 'color': [0.32, 0.36, 0.42, 1.0], 'roughness': 0.85})
    build_glb("public/assets/3d/street/walkway_curb.glb", prims_kerb)

generate_human_avatar()
generate_chair()
generate_table()
generate_cabinet()
generate_environment()
generate_pedestrian()
generate_street_objects()

print("All categorized 3D GLB assets generated successfully.")
