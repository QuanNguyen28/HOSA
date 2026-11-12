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
  MeshStandardMaterial,
  Quaternion,
  SRGBColorSpace,
  Uint32BufferAttribute,
  Vector3,
} from "three";

import {
  MOON_SCENE_RADIUS,
  approximateSunVector,
  coordinateToVector,
  isSurfaceSelectionGesture,
  surfaceHitToCoordinate,
} from "../lib/lunar";
import {
  buildTerrainMeshData,
  worldSunToTerrainAxes,
} from "../lib/terrainGeometry";
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

function SceneRig({
  preset,
  surfaceRadiusKm,
}: {
  preset: CameraPreset;
  surfaceRadiusKm?: number;
}) {
  const { camera } = useThree();
  const desired = useRef(new Vector3(0, 0.3, 6.4));
  const transitioning = useRef(false);

  useEffect(() => {
    const terrainRadius = surfaceRadiusKm ?? 8;
    desired.current =
      preset === "south-pole"
        ? new Vector3(0.25, -5.8, 0.7)
        : preset === "surface"
          ? new Vector3(
              terrainRadius * 1.28 + 0.25,
              terrainRadius * 0.74 + 0.3,
              terrainRadius * 1.28 + 0.25,
            )
          : new Vector3(0, 0.35, 6.4);
    transitioning.current = true;
  }, [preset, surfaceRadiusKm]);

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

function DynamicTerrain({
  terrain,
  coordinate,
  time,
  enhancedLight,
  onReady,
}: {
  terrain: TerrainWindow;
  coordinate: LunarCoordinate;
  time: Date;
  enhancedLight: boolean;
  onReady: () => void;
}) {
  const terrainMesh = useMemo(() => {
    const grid = terrain.grid;
    const metadata = terrain.geometry;
    if (!grid || !metadata) return null;
    const mesh = buildTerrainMeshData(grid, metadata);
    const output = new BufferGeometry();
    output.setAttribute("position", new Float32BufferAttribute(mesh.positions, 3));
    output.setIndex(new Uint32BufferAttribute(mesh.indices, 1));
    output.computeVertexNormals();
    output.computeBoundingBox();
    output.computeBoundingSphere();
    return { geometry: output, mesh };
  }, [terrain]);

  const localSun = useMemo(() => {
    if (!terrain.geometry) return [0.35, 0.7, 0.25] as const;
    return worldSunToTerrainAxes(
      approximateSunVector(time),
      coordinate,
      terrain.geometry,
    );
  }, [coordinate, terrain.geometry, time]);

  useEffect(() => {
    if (terrainMesh) onReady();
    return () => terrainMesh?.geometry.dispose();
  }, [terrainMesh, onReady]);

  if (!terrainMesh || !terrain.grid) return null;
  const lightDistance = 24;
  const lightPosition: [number, number, number] = [
    localSun[0] * lightDistance,
    localSun[1] * lightDistance,
    localSun[2] * lightDistance,
  ];
  const shadowHalfSize =
    Math.max(terrainMesh.mesh.widthSceneUnits, terrainMesh.mesh.depthSceneUnits) * 0.58;

  return (
    <group>
      <ambientLight intensity={enhancedLight ? 0.16 : 0.018} />
      <hemisphereLight
        color="#dbe4e8"
        groundColor="#030405"
        intensity={enhancedLight ? 0.12 : 0.015}
      />
      <directionalLight
        castShadow
        position={lightPosition}
        intensity={localSun[1] > 0 ? 3.1 : 0.08}
        color="#fff2d9"
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-shadowHalfSize}
        shadow-camera-right={shadowHalfSize}
        shadow-camera-top={shadowHalfSize}
        shadow-camera-bottom={-shadowHalfSize}
        shadow-camera-near={0.1}
        shadow-camera-far={60}
        shadow-bias={-0.00018}
        shadow-normalBias={0.012}
      />
      <mesh
        geometry={terrainMesh.geometry}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial
          color="#99978f"
          roughness={0.98}
          metalness={0}
        />
      </mesh>
      <group position={[0, terrainMesh.mesh.centerYSceneUnits + 0.032, 0]}>
        <mesh>
          <sphereGeometry args={[0.032, 20, 20]} />
          <meshBasicMaterial color="#dffaff" toneMapped={false} />
        </mesh>
        <pointLight color="#6edcf4" intensity={0.8} distance={0.6} />
        <Line points={[[0, 0, 0], [0, 0.22, 0]]} color="#7ce3ff" lineWidth={1} />
      </group>
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
  const orientation = useMemo(
    () => new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), normal),
    [normal],
  );

  return (
    <group
      position={[position.x, position.y, position.z]}
      quaternion={[orientation.x, orientation.y, orientation.z, orientation.w]}
    >
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
    <group position={[position.x, position.y, position.z]}>
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
        position={[sun.x * 8, sun.y * 8, sun.z * 8]}
      />
      <directionalLight
        color="#769ab1"
        intensity={layers.enhancedLight ? 0.58 : 0.035}
        position={[sun.x * -6, sun.y * -6, sun.z * -6]}
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
    props.selected !== null &&
    props.terrainWindow?.coverage_status === "COVERED";
  return (
    <Canvas
      shadows
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
        {localSurface && props.terrainWindow && props.selected ? (
          <DynamicTerrain
            terrain={props.terrainWindow}
            coordinate={props.selected}
            time={props.time}
            enhancedLight={props.layers.enhancedLight}
            onReady={props.onReady}
          />
        ) : (
          <Moon {...props} />
        )}
      </Suspense>
      <SceneRig
        preset={props.cameraPreset}
        surfaceRadiusKm={props.terrainWindow?.radius_km}
      />
      {localSurface ? (
        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.065}
          minDistance={0.18}
          maxDistance={36}
          rotateSpeed={0.38}
          zoomSpeed={0.65}
          panSpeed={0.35}
          enablePan
          minPolarAngle={MathUtils.degToRad(4)}
          maxPolarAngle={MathUtils.degToRad(88)}
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
