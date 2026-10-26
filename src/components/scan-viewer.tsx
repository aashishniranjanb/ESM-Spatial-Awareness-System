"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

export type ScanPoint = {
  id: string;
  x: number;
  y: number;
  z: number;
  distance: number;
  intensity: number;
  uncertainty?: number;
  quality_flag?: string;
};

export type VisionOverlay = {
  id: string;
  label: string;
  confidence: number;
  spatial_coords?: { x: number; y: number; z: number };
  est_distance_m?: number;
  is_approximate: boolean;
  has_valid_depth?: boolean;
};

export type PersistentLandmark = {
  id: string;
  x: number;
  y: number;
  z: number;
  label?: string;
  confidence: number;
  observation_count: number;
  uncertainty: number;
  provenance: "measured" | "estimated" | "illustrative";
  source: string;
  track_id?: number;
  is_stale: boolean;
  has_valid_depth: boolean;
  depth_source?: string;
};

export type CameraTrajectoryPose = {
  frame_id: number;
  timestamp_ms: number;
  position?: [number, number, number];
  tracking_state: string;
  source: string;
};

/**
 * Procedural stylized 3D human avatar representing the wearer.
 * Robust, high-contrast, fully self-contained (no external glTF loading failure).
 * Renders head with smart glasses, sensor pod, torso, arms, legs, directional radar cone,
 * and idle breathing + sensor scanning indicator animation.
 */
function ProceduralWearerAvatar({
  yaw = 0,
  pitch = 0,
  isLive = false,
}: {
  yaw: number;
  pitch: number;
  isLive: boolean;
}) {
  const avatarGroup = useRef<THREE.Group>(null);
  const pulseRing = useRef<THREE.Mesh>(null);
  const headGroup = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (avatarGroup.current) {
      // Subtle idle breathing motion
      avatarGroup.current.position.y = -0.85 + Math.sin(t * 1.8) * 0.008;
    }
    if (pulseRing.current) {
      // Rotating scan ring on the floor around the wearer
      pulseRing.current.rotation.z = t * 0.8;
      const s = 1.0 + Math.sin(t * 3.0) * 0.04;
      pulseRing.current.scale.set(s, s, s);
    }
    if (headGroup.current) {
      // Head tilt with sensor pitch
      headGroup.current.rotation.x = pitch;
    }
  });

  return (
    <group ref={avatarGroup} position={[0, -0.85, 0]} rotation={[0, yaw, 0]}>
      {/* 1. Floor Orientation Ring / Pedestal */}
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.32, 0.38, 32]} />
        <meshBasicMaterial color="#00D1E8" transparent opacity={0.65} side={THREE.DoubleSide} />
      </mesh>
      <mesh ref={pulseRing} position={[0, 0.025, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.42, 0.44, 32]} />
        <meshBasicMaterial color="#0878D1" transparent opacity={0.4} side={THREE.DoubleSide} />
      </mesh>

      {/* Directional forward indicator arrow on floor */}
      <mesh position={[0, 0.03, -0.42]} rotation={[-Math.PI / 2, 0, 0]}>
        <coneGeometry args={[0.08, 0.16, 3]} />
        <meshBasicMaterial color="#00D1E8" side={THREE.DoubleSide} />
      </mesh>

      {/* 2. Feet / Boots */}
      <mesh position={[-0.1, 0.06, 0.02]}>
        <boxGeometry args={[0.1, 0.12, 0.22]} />
        <meshStandardMaterial color="#0D1B2A" roughness={0.6} />
      </mesh>
      <mesh position={[0.1, 0.06, 0.02]}>
        <boxGeometry args={[0.1, 0.12, 0.22]} />
        <meshStandardMaterial color="#0D1B2A" roughness={0.6} />
      </mesh>

      {/* 3. Legs */}
      <mesh position={[-0.1, 0.42, 0]}>
        <cylinderGeometry args={[0.065, 0.055, 0.65, 16]} />
        <meshStandardMaterial color="#13263A" roughness={0.7} />
      </mesh>
      <mesh position={[0.1, 0.42, 0]}>
        <cylinderGeometry args={[0.065, 0.055, 0.65, 16]} />
        <meshStandardMaterial color="#13263A" roughness={0.7} />
      </mesh>

      {/* 4. Hips / Pelvis */}
      <mesh position={[0, 0.77, 0]}>
        <boxGeometry args={[0.3, 0.14, 0.18]} />
        <meshStandardMaterial color="#0D1B2A" roughness={0.7} />
      </mesh>

      {/* 5. Torso */}
      <mesh position={[0, 1.08, 0]}>
        <boxGeometry args={[0.34, 0.5, 0.2]} />
        <meshStandardMaterial color="#0878D1" roughness={0.4} metalness={0.2} />
      </mesh>
      {/* High-visibility vest accent / chest emblem */}
      <mesh position={[0, 1.15, 0.105]}>
        <planeGeometry args={[0.16, 0.22]} />
        <meshBasicMaterial color="#00D1E8" transparent opacity={0.85} side={THREE.DoubleSide} />
      </mesh>

      {/* 6. Arms */}
      {/* Left Arm */}
      <mesh position={[-0.23, 1.02, 0]} rotation={[0, 0, 0.08]}>
        <cylinderGeometry args={[0.05, 0.045, 0.55, 12]} />
        <meshStandardMaterial color="#0B233A" roughness={0.5} />
      </mesh>
      {/* Left Hand */}
      <mesh position={[-0.25, 0.72, 0]}>
        <sphereGeometry args={[0.045, 12, 12]} />
        <meshStandardMaterial color="#D7B19D" roughness={0.8} />
      </mesh>

      {/* Right Arm */}
      <mesh position={[0.23, 1.02, 0]} rotation={[0, 0, -0.08]}>
        <cylinderGeometry args={[0.05, 0.045, 0.55, 12]} />
        <meshStandardMaterial color="#0B233A" roughness={0.5} />
      </mesh>
      {/* Right Hand */}
      <mesh position={[0.25, 0.72, 0]}>
        <sphereGeometry args={[0.045, 12, 12]} />
        <meshStandardMaterial color="#D7B19D" roughness={0.8} />
      </mesh>

      {/* 7. Neck */}
      <mesh position={[0, 1.37, 0]}>
        <cylinderGeometry args={[0.05, 0.055, 0.1, 12]} />
        <meshStandardMaterial color="#D7B19D" roughness={0.8} />
      </mesh>

      {/* 8. Head Group (Rotates with Pitch) */}
      <group ref={headGroup} position={[0, 1.52, 0]}>
        {/* Head */}
        <mesh position={[0, 0, 0]}>
          <sphereGeometry args={[0.12, 24, 24]} />
          <meshStandardMaterial color="#D7B19D" roughness={0.7} />
        </mesh>

        {/* Smart Glasses Frame */}
        <mesh position={[0, 0.02, -0.11]}>
          <boxGeometry args={[0.19, 0.04, 0.03]} />
          <meshStandardMaterial color="#0D1B2A" metalness={0.8} roughness={0.2} />
        </mesh>
        {/* Smart Glasses Cyan Display Lenses */}
        <mesh position={[-0.048, 0.02, -0.126]}>
          <planeGeometry args={[0.065, 0.032]} />
          <meshBasicMaterial color="#00D1E8" side={THREE.DoubleSide} />
        </mesh>
        <mesh position={[0.048, 0.02, -0.126]}>
          <planeGeometry args={[0.065, 0.032]} />
          <meshBasicMaterial color="#00D1E8" side={THREE.DoubleSide} />
        </mesh>

        {/* Sensor Pod (HC-SR04 + MPU6050 Module on Forehead/Glasses) */}
        <group position={[0, 0.05, -0.13]}>
          {/* Module housing */}
          <mesh>
            <boxGeometry args={[0.09, 0.03, 0.025]} />
            <meshStandardMaterial color="#0878D1" roughness={0.4} />
          </mesh>
          {/* Dual ultrasonic transducers (T and R barrels) */}
          <mesh position={[-0.025, 0, -0.015]} rotation={[-Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.012, 0.012, 0.015, 16]} />
            <meshStandardMaterial color="#C0C0C0" metalness={0.9} roughness={0.2} />
          </mesh>
          <mesh position={[0.025, 0, -0.015]} rotation={[-Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.012, 0.012, 0.015, 16]} />
            <meshStandardMaterial color="#C0C0C0" metalness={0.9} roughness={0.2} />
          </mesh>
        </group>

        {/* 9. Forward Sensor Acoustic Cone / Field of View Beam */}
        <mesh position={[0, 0.04, -0.9]} rotation={[-Math.PI / 2, 0, 0]}>
          <coneGeometry args={[0.35, 1.8, 20, 1, true]} />
          <meshBasicMaterial
            color={isLive ? "#00D1E8" : "#0878D1"}
            transparent
            opacity={isLive ? 0.22 : 0.12}
            wireframe
          />
        </mesh>

        {/* Central Forward Ray */}
        <mesh position={[0, 0.04, -1.0]} rotation={[-Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.003, 0.003, 2.0, 8]} />
          <meshBasicMaterial color="#00D1E8" transparent opacity={0.6} />
        </mesh>
      </group>

      {/* Floating Wearer Status Label */}
      <Html position={[0, 1.82, 0]} center>
        <div className="avatar-tag" style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: isLive ? "#00D1E8" : "#9FB1C5",
              boxShadow: isLive ? "0 0 6px #00D1E8" : "none",
              display: "inline-block",
            }}
          />
          <span>WEARER · (0, 0, 0)</span>
        </div>
      </Html>
    </group>
  );
}

// Measured ultrasonic point cloud
function PointCloud({ points, visible = true }: { points: ScanPoint[]; visible?: boolean }) {
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const positions: number[] = [];
    const colors: number[] = [];
    for (const p of points) {
      positions.push(p.x, p.y, p.z);
      // Red (<1.5m), Amber (1.5-3m), Teal (>3m)
      const color =
        p.distance < 1.5
          ? new THREE.Color("#EF4444")
          : p.distance < 3.0
          ? new THREE.Color("#F5A623")
          : new THREE.Color("#00C2A8");
      colors.push(color.r, color.g, color.b);
    }
    g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    return g;
  }, [points]);

  if (!visible || points.length === 0) return null;

  return (
    <points geometry={geometry}>
      <pointsMaterial size={0.095} vertexColors transparent opacity={0.92} sizeAttenuation />
    </points>
  );
}

// 3D Obstacle Bounding Box with wireframe, solid accent base, and telemetry label
function ObstacleBoundingBox3D({
  position,
  size = [0.6, 0.8, 0.6],
  color = "#EF4444",
  label = "Obstacle",
  sublabel,
  isStale = false,
  showLabel = true,
}: {
  position: [number, number, number];
  size?: [number, number, number];
  color?: string;
  label?: string;
  sublabel?: string;
  isStale?: boolean;
  showLabel?: boolean;
}) {
  const [sx, sy, sz] = size;
  return (
    <group position={position}>
      {/* Semi-transparent bounding volume box */}
      <mesh position={[0, sy / 2, 0]}>
        <boxGeometry args={[sx, sy, sz]} />
        <meshStandardMaterial
          color={color}
          transparent
          opacity={isStale ? 0.12 : 0.22}
          roughness={0.3}
          metalness={0.1}
        />
      </mesh>

      {/* Crisp wireframe box cage */}
      <mesh position={[0, sy / 2, 0]}>
        <boxGeometry args={[sx, sy, sz]} />
        <meshBasicMaterial
          color={color}
          wireframe
          transparent
          opacity={isStale ? 0.35 : 0.85}
        />
      </mesh>

      {/* Floor projection boundary ring */}
      <mesh position={[0, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[Math.max(sx, sz) * 0.45, Math.max(sx, sz) * 0.55, 24]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={isStale ? 0.25 : 0.6}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Floating 3D engineering label */}
      {showLabel && (
        <Html position={[0, sy + 0.18, 0]} center>
          <div
            className="detection-tag"
            style={{
              borderColor: color,
              color: "#F4F7FB",
              background: "rgba(13, 27, 42, 0.88)",
              boxShadow: `0 0 8px ${color}44`,
              opacity: isStale ? 0.5 : 1.0,
              fontSize: "10px",
              padding: "2px 7px",
              borderRadius: "3px",
              border: `1px solid ${color}`,
              textAlign: "center",
              whiteSpace: "nowrap",
            }}
          >
            <strong style={{ display: "block", letterSpacing: "0.5px" }}>{label}</strong>
            {sublabel && (
              <span style={{ fontSize: "8.5px", color: "#9FB1C5", display: "block" }}>
                {sublabel}
              </span>
            )}
          </div>
        </Html>
      )}
    </group>
  );
}

// Persistent 3D Map Landmarks (Rendered with 3D Bounding Boxes)
function PersistentLandmarks3D({
  landmarks = [],
  visible = true,
}: {
  landmarks?: PersistentLandmark[];
  visible?: boolean;
}) {
  if (!visible || landmarks.length === 0) return null;

  return (
    <>
      {landmarks.map((lm) => {
        if (!lm.has_valid_depth) return null;

        const isStale = lm.is_stale;
        const isEcho = lm.source === "ultrasonic";
        const isVO = lm.source === "opencv_slam";

        // Color coding: Critical Red for measured close obstacle, Teal for safe echo, Violet for estimated vision track, Cyan for SLAM feature
        const color =
          isVO
            ? "#00D1E8"
            : lm.provenance === "measured"
            ? (Math.abs(lm.z) < 1.5 ? "#EF4444" : "#00C2A8")
            : "#B066FE";

        // Size based on obstacle category
        const boxSize: [number, number, number] =
          isVO
            ? [0.12, 0.12, 0.12]
            : isEcho
            ? [0.35, 0.45, 0.35]
            : lm.label?.toLowerCase().includes("person")
            ? [0.55, 1.6, 0.4]
            : [0.65, 0.7, 0.65];

        return (
          <ObstacleBoundingBox3D
            key={lm.id}
            position={[lm.x, lm.y, lm.z]}
            size={boxSize}
            color={color}
            label={lm.label || (isVO ? "SLAM Point" : "Obstacle")}
            sublabel={`${lm.provenance.toUpperCase()} · ${Math.abs(lm.z).toFixed(2)}m`}
            isStale={isStale}
            showLabel={!isVO}
          />
        );
      })}
    </>
  );
}

// Camera Trajectory Path in 3D
function CameraTrajectory({
  trajectory = [],
  visible = true,
}: {
  trajectory?: CameraTrajectoryPose[];
  visible?: boolean;
}) {
  const linePoints = useMemo(() => {
    if (!visible || trajectory.length < 2) return null;
    const pts: THREE.Vector3[] = [];
    for (const t of trajectory) {
      if (t.position) {
        pts.push(new THREE.Vector3(t.position[0], t.position[1], t.position[2]));
      }
    }
    if (pts.length < 2) return null;
    return new THREE.BufferGeometry().setFromPoints(pts);
  }, [trajectory, visible]);

  const lineObj = useMemo(() => {
    if (!linePoints) return null;
    const mat = new THREE.LineBasicMaterial({
      color: 0x00d1e8,
      linewidth: 2,
      transparent: true,
      opacity: 0.7,
    });
    return new THREE.Line(linePoints, mat);
  }, [linePoints]);

  if (!visible || !lineObj) return null;

  return <primitive object={lineObj} />;
}

// Procedural Illustrative Environmental Context Objects (No glTF loading dependencies)
function ContextEnvironment({
  isDemoMode,
  visible = true,
}: {
  isDemoMode: boolean;
  visible?: boolean;
}) {
  if (!visible) return null;

  return (
    <group position={[0, -0.85, 0]}>
      {/* Floor Ground Plane */}
      <mesh position={[0, -0.01, -2.5]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[12, 12]} />
        <meshStandardMaterial color="#071321" roughness={0.9} />
      </mesh>

      {/* Wall Partitions & Doorway Frame in distance (-4.8m) */}
      <group position={[0, 0, -4.8]}>
        {/* Left Wall Partition */}
        <mesh position={[-1.8, 1.2, 0]}>
          <boxGeometry args={[1.8, 2.4, 0.08]} />
          <meshStandardMaterial color="#13263A" roughness={0.8} />
        </mesh>
        {/* Door Frame Posts & Lintel */}
        <mesh position={[-0.45, 1.05, 0]}>
          <boxGeometry args={[0.08, 2.1, 0.12]} />
          <meshStandardMaterial color="#1E3850" roughness={0.6} />
        </mesh>
        <mesh position={[0.45, 1.05, 0]}>
          <boxGeometry args={[0.08, 2.1, 0.12]} />
          <meshStandardMaterial color="#1E3850" roughness={0.6} />
        </mesh>
        <mesh position={[0, 2.14, 0]}>
          <boxGeometry args={[0.98, 0.08, 0.12]} />
          <meshStandardMaterial color="#1E3850" roughness={0.6} />
        </mesh>
        {/* Right Wall Partition */}
        <mesh position={[1.8, 1.2, 0]}>
          <boxGeometry args={[1.8, 2.4, 0.08]} />
          <meshStandardMaterial color="#13263A" roughness={0.8} />
        </mesh>
      </group>

      {/* Office Table fixture on Left (-1.2, 0, -2.2) */}
      <group position={[-1.2, 0, -2.2]} rotation={[0, 0.2, 0]}>
        {/* Table Top */}
        <mesh position={[0, 0.72, 0]}>
          <boxGeometry args={[1.1, 0.04, 0.6]} />
          <meshStandardMaterial color="#1C354D" roughness={0.5} />
        </mesh>
        {/* 4 Table Legs */}
        <mesh position={[-0.5, 0.35, -0.25]}>
          <cylinderGeometry args={[0.02, 0.02, 0.7, 8]} />
          <meshStandardMaterial color="#0A1826" metalness={0.7} />
        </mesh>
        <mesh position={[0.5, 0.35, -0.25]}>
          <cylinderGeometry args={[0.02, 0.02, 0.7, 8]} />
          <meshStandardMaterial color="#0A1826" metalness={0.7} />
        </mesh>
        <mesh position={[-0.5, 0.35, 0.25]}>
          <cylinderGeometry args={[0.02, 0.02, 0.7, 8]} />
          <meshStandardMaterial color="#0A1826" metalness={0.7} />
        </mesh>
        <mesh position={[0.5, 0.35, 0.25]}>
          <cylinderGeometry args={[0.02, 0.02, 0.7, 8]} />
          <meshStandardMaterial color="#0A1826" metalness={0.7} />
        </mesh>
      </group>

      {/* Office Chair (-1.2, 0, -1.6) */}
      <group position={[-1.2, 0, -1.6]} rotation={[0, 0.4, 0]}>
        {/* Seat */}
        <mesh position={[0, 0.45, 0]}>
          <boxGeometry args={[0.42, 0.06, 0.42]} />
          <meshStandardMaterial color="#0D2033" roughness={0.6} />
        </mesh>
        {/* Backrest */}
        <mesh position={[0, 0.75, 0.18]}>
          <boxGeometry args={[0.38, 0.5, 0.05]} />
          <meshStandardMaterial color="#0D2033" roughness={0.6} />
        </mesh>
        {/* Stem */}
        <mesh position={[0, 0.22, 0]}>
          <cylinderGeometry args={[0.03, 0.03, 0.44, 8]} />
          <meshStandardMaterial color="#0878D1" metalness={0.8} />
        </mesh>
      </group>

      {/* Traffic Bollard on Right (1.4, 0, -1.8) */}
      <group position={[1.4, 0, -1.8]}>
        <mesh position={[0, 0.42, 0]}>
          <cylinderGeometry args={[0.07, 0.08, 0.84, 16]} />
          <meshStandardMaterial color="#F5A623" roughness={0.4} />
        </mesh>
        {/* Reflective Band */}
        <mesh position={[0, 0.65, 0]}>
          <cylinderGeometry args={[0.072, 0.072, 0.12, 16]} />
          <meshBasicMaterial color="#FFFFFF" />
        </mesh>
      </group>

      {/* Park Bench on Right (1.9, 0, -3.0) */}
      <group position={[1.9, 0, -3.0]} rotation={[0, -0.3, 0]}>
        {/* Seat Slats */}
        <mesh position={[0, 0.42, 0]}>
          <boxGeometry args={[1.2, 0.04, 0.45]} />
          <meshStandardMaterial color="#1C354D" roughness={0.7} />
        </mesh>
        {/* Backrest */}
        <mesh position={[0, 0.72, 0.2]}>
          <boxGeometry args={[1.2, 0.4, 0.04]} />
          <meshStandardMaterial color="#1C354D" roughness={0.7} />
        </mesh>
        {/* Legs */}
        <mesh position={[-0.52, 0.21, 0]}>
          <boxGeometry args={[0.06, 0.42, 0.4]} />
          <meshStandardMaterial color="#0A1826" metalness={0.7} />
        </mesh>
        <mesh position={[0.52, 0.21, 0]}>
          <boxGeometry args={[0.06, 0.42, 0.4]} />
          <meshStandardMaterial color="#0A1826" metalness={0.7} />
        </mesh>
      </group>

      {/* Demo Mode Pedestrian Obstacle with 3D Bounding Box (0.4, 0, -2.8) */}
      {isDemoMode && (
        <group position={[0.4, 0, -2.8]}>
          <ObstacleBoundingBox3D
            position={[0, 0, 0]}
            size={[0.7, 1.85, 0.6]}
            color="#EF4444"
            label="OBSTACLE: PEDESTRIAN"
            sublabel="PATH INTERSECTION · 2.8m"
          />
          <group rotation={[0, -Math.PI / 4, 0]}>
            {/* Head */}
            <mesh position={[0, 1.5, 0]}>
              <sphereGeometry args={[0.11, 16, 16]} />
              <meshStandardMaterial color="#D7B19D" />
            </mesh>
            {/* Body */}
            <mesh position={[0, 1.05, 0]}>
              <boxGeometry args={[0.3, 0.55, 0.18]} />
              <meshStandardMaterial color="#F5A623" roughness={0.5} />
            </mesh>
            {/* Legs */}
            <mesh position={[-0.08, 0.38, 0]}>
              <cylinderGeometry args={[0.05, 0.045, 0.75, 12]} />
              <meshStandardMaterial color="#13263A" />
            </mesh>
            <mesh position={[0.08, 0.38, 0]}>
              <cylinderGeometry args={[0.05, 0.045, 0.75, 12]} />
              <meshStandardMaterial color="#13263A" />
            </mesh>
          </group>
        </group>
      )}
    </group>
  );
}

function Scene({
  points,
  landmarks = [],
  trajectory = [],
  viewMode,
  wearerYaw = 0,
  wearerPitch = 0,
  isDemoMode = false,
  showPointCloud = true,
  showLandmarks = true,
  showTrajectory = true,
  showIllustrative = true,
  isLive = false,
}: {
  points: ScanPoint[];
  landmarks?: PersistentLandmark[];
  trajectory?: CameraTrajectoryPose[];
  viewMode: "3d" | "top" | "front";
  wearerYaw?: number;
  wearerPitch?: number;
  isDemoMode?: boolean;
  showPointCloud?: boolean;
  showLandmarks?: boolean;
  showTrajectory?: boolean;
  showIllustrative?: boolean;
  isLive?: boolean;
}) {
  return (
    <>
      <color attach="background" args={["#050E18"]} />
      <fog attach="fog" args={["#050E18", 8, 22]} />
      <ambientLight intensity={1.1} />
      <pointLight position={[3, 5, 4]} intensity={2.0} color="#00D1E8" />
      <directionalLight position={[-4, 7, -3]} intensity={1.2} color="#0878D1" />
      <directionalLight position={[0, -2, 4]} intensity={0.5} color="#00C2A8" />

      {/* Grid Floor */}
      <gridHelper args={[14, 28, "#0878D1", "#192C40"]} position={[0, -0.85, 0]} />
      <axesHelper args={[1.2]} />

      {/* 3D Rigged Wearer Avatar at origin with live animation */}
      <ProceduralWearerAvatar yaw={wearerYaw} pitch={wearerPitch} isLive={isLive} />

      {/* Illustrative Context Environment */}
      <ContextEnvironment isDemoMode={isDemoMode} visible={showIllustrative} />

      {/* Measured Ultrasonic Point Cloud */}
      <PointCloud points={points} visible={showPointCloud} />

      {/* Persistent Map Landmarks (Grounded Depth Only) */}
      <PersistentLandmarks3D landmarks={landmarks} visible={showLandmarks} />

      {/* Estimated Camera Trajectory */}
      <CameraTrajectory trajectory={trajectory} visible={showTrajectory} />

      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        target={[0, 0, -1.5]}
        maxDistance={16}
        minDistance={1.0}
      />

      {viewMode === "top" && (
        <Html position={[0, 3.5, 0]} center>
          <div className="scene-label">TOP ORTHO VIEW · DRAG TO ROTATE</div>
        </Html>
      )}
      {viewMode === "front" && (
        <Html position={[0, 2.5, -1.5]} center>
          <div className="scene-label">FRONT ELEVATION VIEW</div>
        </Html>
      )}
    </>
  );
}

export default function ScanViewer({
  points,
  landmarks = [],
  trajectory = [],
  viewMode = "3d",
  reducedMotion = false,
  wearerYaw = 0,
  wearerPitch = 0,
  isDemoMode = false,
  showPointCloud = true,
  showLandmarks = true,
  showTrajectory = true,
  showIllustrative = true,
  isLive = false,
}: {
  points: ScanPoint[];
  landmarks?: PersistentLandmark[];
  trajectory?: CameraTrajectoryPose[];
  viewMode: "3d" | "top" | "front";
  reducedMotion: boolean;
  wearerYaw?: number;
  wearerPitch?: number;
  isDemoMode?: boolean;
  showPointCloud?: boolean;
  showLandmarks?: boolean;
  showTrajectory?: boolean;
  showIllustrative?: boolean;
  isLive?: boolean;
}) {
  const cameraPosition: [number, number, number] = useMemo(() => {
    switch (viewMode) {
      case "top":
        return [0, 9.5, -0.01];
      case "front":
        return [0, 0.5, 5.0];
      case "3d":
      default:
        return [4.5, 3.2, 5.2];
    }
  }, [viewMode]);

  return (
    <Canvas
      camera={{ position: cameraPosition, fov: 48 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: false }}
      frameloop={reducedMotion ? "demand" : "always"}
    >
      <Scene
        points={points}
        landmarks={landmarks}
        trajectory={trajectory}
        viewMode={viewMode}
        wearerYaw={wearerYaw}
        wearerPitch={wearerPitch}
        isDemoMode={isDemoMode}
        showPointCloud={showPointCloud}
        showLandmarks={showLandmarks}
        showTrajectory={showTrajectory}
        showIllustrative={showIllustrative}
        isLive={isLive}
      />
    </Canvas>
  );
}
