import struct
import json
import os

def create_box_glb(output_path: str, sx=0.5, sy=0.5, sz=0.5, color_rgb=(0.2, 0.4, 0.8)):
    # 8 vertices of a cuboid centered at origin
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    vertices = [
        -hx, -hy,  hz,   hx, -hy,  hz,   hx,  hy,  hz,  -hx,  hy,  hz, # Front
        -hx, -hy, -hz,  -hx,  hy, -hz,   hx,  hy, -hz,   hx, -hy, -hz, # Back
        -hx,  hy, -hz,  -hx,  hy,  hz,   hx,  hy,  hz,   hx,  hy, -hz, # Top
        -hx, -hy, -hz,   hx, -hy, -hz,   hx, -hy,  hz,  -hx, -hy,  hz, # Bottom
         hx, -hy, -hz,   hx,  hy, -hz,   hx,  hy,  hz,   hx, -hy,  hz, # Right
        -hx, -hy, -hz,  -hx, -hy,  hz,  -hx,  hy,  hz,  -hx,  hy, -hz, # Left
    ]
    indices = [
         0,  1,  2,   0,  2,  3, # Front
         4,  5,  6,   4,  6,  7, # Back
         8,  9, 10,   8, 10, 11, # Top
        12, 13, 14,  12, 14, 15, # Bottom
        16, 17, 18,  16, 18, 19, # Right
        20, 21, 22,  20, 22, 23  # Left
    ]

    vert_bytes = struct.pack(f"<{len(vertices)}f", *vertices)
    idx_bytes = struct.pack(f"<{len(indices)}H", *indices)

    # Pad buffers to 4-byte boundary
    while len(idx_bytes) % 4 != 0:
        idx_bytes += b'\x00'
    while len(vert_bytes) % 4 != 0:
        vert_bytes += b'\x00'

    bin_data = idx_bytes + vert_bytes

    gltf_dict = {
        "asset": {"version": "2.0", "generator": "EchoMap Minimal GLB Generator"},
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "attributes": {"POSITION": 1},
                "indices": 0,
                "material": 0
            }]
        }],
        "materials": [{
            "pbrMetallicRoughness": {
                "baseColorFactor": [color_rgb[0], color_rgb[1], color_rgb[2], 1.0],
                "metallicFactor": 0.2,
                "roughnessFactor": 0.7
            }
        }],
        "buffers": [{"byteLength": len(bin_data)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(idx_bytes), "target": 34963},
            {"buffer": 0, "byteOffset": len(idx_bytes), "byteLength": len(vert_bytes), "target": 34962}
        ],
        "accessors": [
            {"bufferView": 0, "byteOffset": 0, "componentType": 5123, "count": len(indices), "type": "SCALAR", "max": [max(indices)], "min": [min(indices)]},
            {"bufferView": 1, "byteOffset": 0, "componentType": 5126, "count": len(vertices)//3, "type": "VEC3", "max": [hx, hy, hz], "min": [-hx, -hy, -hz]}
        ]
    }

    json_str = json.dumps(gltf_dict)
    json_bytes = json_str.encode('utf-8')
    while len(json_bytes) % 4 != 0:
        json_bytes += b' '

    # GLB Header: magic (4B), version (4B), total length (4B)
    total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    header = struct.pack("<4sII", b"glTF", 2, total_length)
    json_chunk_header = struct.pack("<II", len(json_bytes), 0x4E4F534A) # JSON
    bin_chunk_header = struct.pack("<II", len(bin_data), 0x004E4942)   # BIN

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(header)
        f.write(json_chunk_header)
        f.write(json_bytes)
        f.write(bin_chunk_header)
        f.write(bin_data)

# Generate low-poly assets
create_box_glb("public/assets/3d/avatar/wearer_marker.glb", 0.35, 1.7, 0.35, (0.05, 0.6, 0.85))
create_box_glb("public/assets/3d/furniture/chair.glb", 0.45, 0.75, 0.45, (0.4, 0.3, 0.2))
create_box_glb("public/assets/3d/furniture/desk.glb", 1.2, 0.75, 0.6, (0.3, 0.35, 0.4))
create_box_glb("public/assets/3d/environment/door_frame.glb", 0.9, 2.0, 0.1, (0.2, 0.25, 0.3))
create_box_glb("public/assets/3d/environment/wall_segment.glb", 2.0, 2.4, 0.15, (0.15, 0.2, 0.25))
create_box_glb("public/assets/3d/pedestrians/pedestrian.glb", 0.4, 1.75, 0.4, (0.7, 0.3, 0.3))
create_box_glb("public/assets/3d/road/bollard.glb", 0.2, 0.9, 0.2, (0.9, 0.7, 0.1))
create_box_glb("public/assets/3d/road/kerb_curb.glb", 2.5, 0.15, 0.3, (0.25, 0.28, 0.32))

print("Created all standalone bundled 3D GLB assets successfully.")
