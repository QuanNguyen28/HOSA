import { Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import {
  Line,
  OrbitControls,
  Stars,
  TrackballControls,
  useTexture,
} from "@react-three/drei";
import {
  AdditiveBlending,
  BufferGeometry,
  Color,
  Float32BufferAttribute,
  MathUtils,
  Mesh,
  MeshStandardMaterial,
  SRGBColorSpace,
  Vector3,
} from "three";

import {
  MOON_SCENE_RADIUS,
  approximateSunVector,
  coordinateToVector,
  isSurfaceSelectionGesture,
  surfaceHitToCoordinate,
} from "../lib/lunar";
import type {
  CameraPreset,
  LayerState,
  LunarCoordinate,
  Site,
} from "../types";
import type { TerrainWindow } from "../hooks/useTerrainWindow";

type MoonSceneProps = {
  time: Date;
  cameraPreset: CameraPreset;
  layers: LayerState;
  sites: Site[];
  selected: LunarCoordinate | null;
  selectedSiteId: string | null;
  terrainWindow: TerrainWindow | null;
  onSelect: (coordinate: LunarCoordinate, siteId?: string) => void;
  onHover: (coordinate: LunarCoordinate | null) => void;
  onReady: () => void;
};

function SceneRig({ preset }: { preset: CameraPreset }) {
  const { camera } = useThree();
  const desired = useRef(new Vector3(0, 0.3, 6.4));
  const transitioning = useRef(false);

  useEffect(() => {
    desired.current =
      preset === "south-pole"
        ? new Vector3(0.25, -5.8, 0.7)
        : preset === "surface"
          ? new Vector3(3.7, 2.65, 3.7)
          : new Vector3(0, 0.35, 6.4);
    transitioning.current = true;
  }, [preset]);

  useFrame((_, delta) => {
    if (!transitioning.current) return;
    camera.position.lerp(desired.current, 1 - Math.exp(-delta * 3.2));
    camera.lookAt(0, 0, 0);
    if (camera.position.distanceTo(desired.current) < 0.008) {
      camera.position.copy(desired.current);
      transitioning.current = false;
    }
  });

  return null;
}

const LOCAL_TERRAIN = {
  Site01_P1: {
    height: "/assets/terrain/site01_height.png",
    hillshade: "/assets/terrain/site01_hillshade.jpg",
    marker: [-0.164, 0.54, 0.13] as [number, number, number],
  },
  Site04_P1: {
    height: "/assets/terrain/site04_height.png",
    hillshade: "/assets/terrain/site04_hillshade.jpg",
    marker: [-0.475, 0.54, -0.25] as [number, number, number],
  },
} as const;

function LocalTerrain({
  siteId,
  onReady,
}: {
  siteId: keyof typeof LOCAL_TERRAIN;
  onReady: () => void;
}) {
  const config = LOCAL_TERRAIN[siteId];
  const [heightMap, hillshade] = useTexture([
    config.height,
    config.hillshade,
  ]);

  useEffect(() => {
    hillshade.colorSpace = SRGBColorSpace;
    heightMap.anisotropy = 4;
    hillshade.anisotropy = 8;
    onReady();
  }, [heightMap, hillshade, onReady]);

  return (
    <group>
      <ambientLight intensity={0.12} />
      <directionalLight position={[-4, 7, 3]} intensity={3.2} color="#fff3df" />
      <directionalLight position={[4, 1, -4]} intensity={0.22} color="#5f89a3" />
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[4.5, 4.5, 256, 256]} />
        <meshStandardMaterial
          map={hillshade}
          displacementMap={heightMap}
          displacementScale={0.7}
          displacementBias={-0.15}
          roughness={1}
          metalness={0}
          color="#c6c2b7"
        />
      </mesh>
      <group position={config.marker}>
        <mesh>
          <sphereGeometry args={[0.035, 20, 20]} />
          <meshBasicMaterial color="#dffaff" toneMapped={false} />
        </mesh>
        <pointLight color="#6edcf4" intensity={1.2} distance={0.7} />
        <Line points={[[0, 0, 0], [0, 0.42, 0]]} color="#7ce3ff" lineWidth={1} />
      </group>
      <gridHelper args={[4.5, 8, "#6f9cab", "#31454c"]} position={[0, 0.012, 0]} />
    </group>
  );
}

function DynamicTerrain({
  terrain,
  onReady,
}: {
  terrain: TerrainWindow;
  onReady: () => void;
}) {
  const geometry = useMemo(() => {
    const grid = terrain.grid;
    if (!grid) return null;
    const output = new BufferGeometry();
    const positions: number[] = [];
    const colors: number[] = [];
    const indices: number[] = [];
    const span = Math.max(grid.max_elevation_m - grid.min_elevation_m, 1);
    for (let row = 0; row < grid.rows; row += 1) {
      for (let column = 0; column < grid.columns; column += 1) {
        const value = grid.elevation_m_row_major[row * grid.columns + column];
        const normalized = value === null ? 0 : (value - grid.min_elevation_m) / span;
        positions.push(
          (column / (grid.columns - 1) - 0.5) * 4.5,
          normalized * 0.72 - 0.16,
          (row / (grid.rows - 1) - 0.5) * 4.5,
        );
        const shade = value === null ? 0.03 : 0.34 + normalized * 0.5;
        colors.push(shade * 0.93, shade * 0.91, shade * 0.84);
      }
    }
    for (let row = 0; row < grid.rows - 1; row += 1) {
      for (let column = 0; column < grid.columns - 1; column += 1) {
        const a = row * grid.columns + column;
        const b = a + 1;
        const c = a + grid.columns;
        const d = c + 1;
        const valid = [a, b, c, d].every(
          (index) => grid.elevation_m_row_major[index] !== null,
        );
        if (valid) indices.push(a, c, b, b, c, d);
      }
    }
    output.setAttribute("position", new Float32BufferAttribute(positions, 3));
    output.setAttribute("color", new Float32BufferAttribute(colors, 3));
    output.setIndex(indices);
    output.computeVertexNormals();
    return output;
  }, [terrain]);

  useEffect(() => {
    if (geometry) onReady();
    return () => geometry?.dispose();
  }, [geometry, onReady]);

  if (!geometry || !terrain.grid) return null;
  const centre = terrain.grid.elevation_m_row_major[
    Math.floor(terrain.grid.rows / 2) * terrain.grid.columns + Math.floor(terrain.grid.columns / 2)
  ];
  const centreY =
    centre === null
      ? 0
      : ((centre - terrain.grid.min_elevation_m) /
          Math.max(terrain.grid.max_elevation_m - terrain.grid.min_elevation_m, 1)) *
          0.72 -
        0.16;

  return (
    <group>
      <ambientLight intensity={0.11} />
      <directionalLight position={[-4, 7, 3]} intensity={3.4} color="#fff3df" />
      <directionalLight position={[4, 1, -4]} intensity={0.24} color="#5f89a3" />
      <mesh geometry={geometry}>
        <meshStandardMaterial vertexColors roughness={1} metalness={0} />
      </mesh>
      <group position={[0, centreY + 0.035, 0]}>
        <mesh>
          <sphereGeometry args={[0.035, 20, 20]} />
          <meshBasicMaterial color="#dffaff" toneMapped={false} />
        </mesh>
        <pointLight color="#6edcf4" intensity={1.2} distance={0.7} />
        <Line points={[[0, 0, 0], [0, 0.42, 0]]} color="#7ce3ff" lineWidth={1} />
      </group>
      <gridHelper args={[4.5, 8, "#6f9cab", "#31454c"]} position={[0, -0.155, 0]} />
    </group>
  );
}

function LunarGrid() {
  const lines = useMemo(() => {
    const generated: Vector3[][] = [];
    const radius = MOON_SCENE_RADIUS * 1.0025;
    for (let latitude = -60; latitude <= 60; latitude += 30) {
      const points: Vector3[] = [];
      for (let longitude = -180; longitude <= 180; longitude += 3) {
        points.push(coordinateToVector({ latitude, longitude }, radius));
      }
      generated.push(points);
    }
    for (let longitude = -150; longitude < 180; longitude += 30) {
      const points: Vector3[] = [];
      for (let latitude = -90; latitude <= 90; latitude += 3) {
        points.push(coordinateToVector({ latitude, longitude }, radius));
      }
      generated.push(points);
    }
    return generated;
  }, []);

  return (
    <group>
      {lines.map((points, index) => (
        <Line
          key={index}
          points={points}
          color="#80b7c8"
          transparent
          opacity={0.16}
          lineWidth={0.45}
        />
      ))}
    </group>
  );
}

function SiteMarker({
  site,
  active,
  onSelect,
}: {
  site: Site;
  active: boolean;
  onSelect: (coordinate: LunarCoordinate, siteId?: string) => void;
}) {
  const position = useMemo(
    () => coordinateToVector(site, MOON_SCENE_RADIUS * 1.009),
    [site],
  );
  const normal = useMemo(() => position.clone().normalize(), [position]);

  return (
    <group position={position} quaternion={new Mesh().quaternion.setFromUnitVectors(new Vector3(0, 1, 0), normal)}>
      <mesh
        onClick={(event) => {
          event.stopPropagation();
          onSelect(site, site.id);
        }}
      >
        <sphereGeometry args={[active ? 0.029 : 0.022, 20, 20]} />
        <meshBasicMaterial color={active ? "#ffffff" : "#e5bd76"} />
      </mesh>
      <mesh position={[0, -0.035, 0]}>
        <ringGeometry args={[0.038, 0.052, 36]} />
        <meshBasicMaterial
          color="#e5bd76"
          transparent
          opacity={active ? 0.95 : 0.55}
          side={2}
        />
      </mesh>
    </group>
  );
}

function SelectedMarker({ coordinate }: { coordinate: LunarCoordinate }) {
  const position = useMemo(
    () => coordinateToVector(coordinate, MOON_SCENE_RADIUS * 1.012),
    [coordinate],
  );

  return (
    <group position={position}>
      <mesh>
        <sphereGeometry args={[0.025, 18, 18]} />
        <meshBasicMaterial color="#7ce3ff" toneMapped={false} />
      </mesh>
      <pointLight color="#62d8ff" intensity={0.5} distance={0.5} />
    </group>
  );
}

function Moon({
  time,
  layers,
  sites,
  selected,
  selectedSiteId,
  onSelect,
  onHover,
  onReady,
}: Omit<MoonSceneProps, "cameraPreset">) {
  const [colorMap, elevationMap] = useTexture([
    "/assets/nasa/lroc_color_2k.jpg",
    "/assets/nasa/ldem_3_8bit.jpg",
  ]);
  const material = useRef<MeshStandardMaterial>(null);
  const sun = useMemo(() => approximateSunVector(time), [time]);

  useEffect(() => {
    colorMap.colorSpace = SRGBColorSpace;
    colorMap.anisotropy = 8;
    elevationMap.anisotropy = 4;
    onReady();
  }, [colorMap, elevationMap, onReady]);

  const handlePointer = (event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation();
    onHover(surfaceHitToCoordinate(event.point));
  };

  return (
    <>
      <ambientLight intensity={layers.enhancedLight ? 0.68 : 0.16} />
      <hemisphereLight
        color="#fff8ec"
        groundColor="#263845"
        intensity={layers.enhancedLight ? 0.72 : 0.18}
      />
      <directionalLight
        color="#fff6e7"
        intensity={layers.enhancedLight ? 2.65 : 2.4}
        position={sun.clone().multiplyScalar(8)}
      />
      <directionalLight
        color="#769ab1"
        intensity={layers.enhancedLight ? 0.58 : 0.035}
        position={sun.clone().multiplyScalar(-6)}
      />
      <mesh
        rotation={[0, Math.PI, 0]}
        onPointerMove={handlePointer}
        onPointerOut={() => onHover(null)}
        onClick={(event) => {
          event.stopPropagation();
          if (!isSurfaceSelectionGesture(event.delta)) return;
          onSelect(surfaceHitToCoordinate(event.point));
        }}
      >
        <sphereGeometry args={[MOON_SCENE_RADIUS, 256, 128]} />
        <meshStandardMaterial
          ref={material}
          map={colorMap}
          bumpMap={elevationMap}
          bumpScale={0.052}
          roughness={1}
          metalness={0}
          color={new Color("#d7d5cf")}
        />
      </mesh>
      <mesh scale={1.014}>
        <sphereGeometry args={[MOON_SCENE_RADIUS, 96, 64]} />
        <meshBasicMaterial
          color="#518ba0"
          transparent
          opacity={0.023}
          blending={AdditiveBlending}
          side={1}
        />
      </mesh>
      {layers.grid && <LunarGrid />}
      {layers.sites &&
        sites.map((site) => (
          <SiteMarker
            key={site.id}
            site={site}
            active={site.id === selectedSiteId}
            onSelect={onSelect}
          />
        ))}
      {selected && !selectedSiteId && <SelectedMarker coordinate={selected} />}
    </>
  );
}

export function MoonScene(props: MoonSceneProps) {
  const localSurface =
    props.cameraPreset === "surface" &&
    ((props.selectedSiteId !== null && props.selectedSiteId in LOCAL_TERRAIN) ||
      props.terrainWindow?.coverage_status === "COVERED");
  return (
    <Canvas
      dpr={[1, 1.8]}
      camera={{ position: [0, 0.35, 6.4], fov: 36, near: 0.02, far: 120 }}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.setClearColor("#030507");
        gl.toneMappingExposure = 1.05;
        // The renderer is already usable at this point.  Reveal the shell now
        // and let Suspense stream the lunar textures into the scene instead of
        // keeping the whole application behind a texture-loading overlay.
        props.onReady();
      }}
    >
      <color attach="background" args={["#030507"]} />
      <fog attach="fog" args={["#030507", 15, 55]} />
      <Stars
        radius={54}
        depth={24}
        count={2600}
        factor={1.6}
        saturation={0.12}
        fade
        speed={0.08}
      />
      <Suspense fallback={null}>
        {localSurface && props.selectedSiteId && props.selectedSiteId in LOCAL_TERRAIN ? (
          <LocalTerrain
            siteId={props.selectedSiteId as keyof typeof LOCAL_TERRAIN}
            onReady={props.onReady}
          />
        ) : localSurface && props.terrainWindow ? (
          <DynamicTerrain terrain={props.terrainWindow} onReady={props.onReady} />
        ) : (
          <Moon {...props} />
        )}
      </Suspense>
      <SceneRig preset={props.cameraPreset} />
      {localSurface ? (
        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.065}
          minDistance={1.2}
          maxDistance={8}
          rotateSpeed={0.38}
          zoomSpeed={0.65}
          panSpeed={0.35}
          enablePan
          minPolarAngle={MathUtils.degToRad(8)}
          maxPolarAngle={MathUtils.degToRad(82)}
        />
      ) : (
        <TrackballControls
          makeDefault
          minDistance={2.22}
          maxDistance={13}
          rotateSpeed={1.15}
          zoomSpeed={0.8}
          panSpeed={0.2}
          noPan
          staticMoving={false}
          dynamicDampingFactor={0.12}
        />
      )}
    </Canvas>
  );
}
