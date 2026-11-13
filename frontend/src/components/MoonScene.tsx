import { useTranslation } from "../i18n/language";
import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import {
  Billboard,
  Html,
  Line,
  MapControls,
  OrbitControls,
  Stars,
  TrackballControls,
  useTexture,
} from "@react-three/drei";
import {
  AdditiveBlending,
  BufferGeometry,
  Color,
  DataTexture,
  DirectionalLight,
  Float32BufferAttribute,
  LinearFilter,
  MathUtils,
  MeshStandardMaterial,
  PCFSoftShadowMap,
  Quaternion,
  RepeatWrapping,
  RGBAFormat,
  SRGBColorSpace,
  Uint32BufferAttribute,
  UnsignedByteType,
  Vector3,
} from "three";

import {
  MOON_SCENE_RADIUS,
  approximateSunVector,
  coordinateToVector,
  isSurfaceSelectionGesture,
  surfaceRayToCoordinate,
  terrainHitToCoordinate,
} from "../lib/lunar";
import {
  buildTerrainHorizonProfile,
  buildTerrainMeshData,
  buildSouthPolarCapMeshData,
  horizonAtAzimuth,
  skyDirectionToTerrainAxes,
  worldSunToTerrainAxes,
} from "../lib/terrainGeometry";
import type {
  SouthPolarFootprint,
  SouthPolarTerrain,
} from "../hooks/useSouthPolarTerrain";
import type {
  CameraPreset,
  LayerState,
  LunarCoordinate,
  Site,
} from "../types";
import type { TerrainWindow } from "../hooks/useTerrainWindow";
import { getLunarSurfaceTextures } from "../lib/lunarSurfaceTextures";
import { TERRAIN_SHADOW_SIZE, terrainShadowHalfSize, updateTerrainShadow } from "../lib/terrainLighting";
import { MoonTrekGlobe, MoonTrekTerrainMaterial, type ImageryStatus } from './MoonTrekImagery';

type MoonSceneProps = {
  imagery?: boolean;
  onImageryStatus?: (status: ImageryStatus) => void;
  time: Date;
  sunVector?: Vector3;
  cameraPreset: CameraPreset;
  layers: LayerState;
  sites: Site[];
  selected: LunarCoordinate | null;
  selectedSiteId: string | null;
  terrainWindow: TerrainWindow | null;
  terrainLods?: Array<TerrainWindow | null>;
  southPolarTerrain?: SouthPolarTerrain | null;
  groundSky?: GroundSky | null;
  onSelect: (coordinate: LunarCoordinate, siteId?: string) => void;
  onHover: (coordinate: LunarCoordinate | null) => void;
  onReady: () => void;
};

export type GroundSkyBody = {
  azimuthDeg: number;
  elevationDeg: number;
  angularRadiusDeg: number;
  horizonDeg?: number | null;
  clearanceDeg?: number | null;
  state?: "V" | "B" | "?";
};

export type GroundSky = {
  source: "JPL_HORIZONS" | "SHARED_SPICE" | "SHARED_SPICE_PREVIEW" | "MODEL_PREVIEW";
  observerHeightM: number;
  sun: GroundSkyBody;
  earth: GroundSkyBody;
};

const GLOBAL_LOLA_DISPLACEMENT_SCALE = 0.022906066536203522;
const GLOBAL_LOLA_DISPLACEMENT_BIAS = -0.0105047772533671;
const POLE_TARGET: [number, number, number] = [0, -10, 0];
const INITIAL_CAMERA = {
  position: [0, 0.35, 6.4] as [number, number, number],
  fov: 36,
  near: 0.02,
  far: 2_000,
};

function SceneRig({
  preset,
  surfaceTargetY = 0,
  surfaceViewDirection,
}: {
  preset: CameraPreset;
  surfaceTargetY?: number;
  surfaceViewDirection?: [number, number, number];
}) {
  const { camera } = useThree();
  const desired = useRef(new Vector3(0, 0.3, 6.4));
  const target = useRef(new Vector3(0, 0, 0));
  const transitioning = useRef(false);
  // Choose an initial sky-facing view on entry. Moving sunlight must not keep
  // rotating the camera or undo the user's inspection of terrain shadows.
  const entry = useRef({ preset, direction: surfaceViewDirection });
  if (entry.current.preset !== preset) entry.current = { preset, direction: surfaceViewDirection };
  const viewX = preset === "surface" ? entry.current.direction?.[0] ?? -0.55 : -0.55;
  const viewZ = preset === "surface" ? entry.current.direction?.[2] ?? -0.84 : -0.84;

  useEffect(() => {
    const viewLength = Math.hypot(viewX, viewZ) || 1;
    desired.current =
      preset === "south-pole"
        ? new Vector3(-105, 128, 178)
        : preset === "surface"
          ? new Vector3(
              -(viewX / viewLength) * 0.38,
              surfaceTargetY + 0.052,
              -(viewZ / viewLength) * 0.38,
            )
          : new Vector3(0, 0.35, 6.4);
    target.current = preset === "surface"
      ? new Vector3(0, surfaceTargetY + 0.018, 0)
      : preset === "south-pole"
        ? new Vector3(...POLE_TARGET)
        : new Vector3(0, 0, 0);
    if ("fov" in camera && typeof camera.fov === "number") {
      camera.fov = preset === "surface" ? 68 : preset === "south-pole" ? 44 : 36;
      camera.updateProjectionMatrix();
    }
    // The map controls own the camera after entering Pole. Keep their pose
    // through terrain swaps and time changes.
    transitioning.current = preset !== "south-pole";
    if (preset === "south-pole") {
      camera.position.copy(desired.current);
      camera.lookAt(target.current);
    }
  }, [
    camera,
    preset,
    surfaceTargetY,
    viewX,
    viewZ,
  ]);

  useFrame((_, delta) => {
    if (!transitioning.current) return;
    camera.position.lerp(desired.current, 1 - Math.exp(-delta * 3.2));
    camera.lookAt(target.current);
    if (camera.position.distanceTo(desired.current) < 0.008) {
      camera.position.copy(desired.current);
      transitioning.current = false;
    }
  });

  return null;
}

function useTerrainMesh(
  terrain?: TerrainWindow | null,
  innerRadiusSceneUnits = 0,
) {
  const terrainMesh = useMemo(() => {
    const grid = terrain?.grid;
    const metadata = terrain?.geometry;
    if (!grid || !metadata) return null;
    const mesh = buildTerrainMeshData(grid, metadata);
    const output = new BufferGeometry();
    output.setAttribute("position", new Float32BufferAttribute(mesh.positions, 3));
    const uvs = new Float32Array((mesh.positions.length / 3) * 2);
    for (let offset = 0; offset < mesh.positions.length; offset += 3) {
      const uvOffset = (offset / 3) * 2;
      // Stable physical texture scale across every LOD. The texture changes
      // shading only; the NASA DEM remains the sole source of mesh geometry.
      uvs[uvOffset] = mesh.positions[offset] / 0.65;
      uvs[uvOffset + 1] = mesh.positions[offset + 2] / 0.65;
    }
    output.setAttribute("uv", new Float32BufferAttribute(uvs, 2));
    const outerRadius = Math.min(mesh.widthSceneUnits, mesh.depthSceneUnits) * 0.5;
    const ringIndices: number[] = [];
    for (let offset = 0; offset < mesh.indices.length; offset += 3) {
      const triangle = [mesh.indices[offset], mesh.indices[offset + 1], mesh.indices[offset + 2]];
      const radii = triangle.map((index) => {
        const positionOffset = index * 3;
        return Math.hypot(mesh.positions[positionOffset], mesh.positions[positionOffset + 2]);
      });
      if (
        radii.every((radius) => radius <= outerRadius) &&
        (innerRadiusSceneUnits <= 0 || radii.every((radius) => radius >= innerRadiusSceneUnits))
      ) {
        ringIndices.push(...triangle);
      }
    }
    output.setIndex(new Uint32BufferAttribute(ringIndices, 1));
    output.computeVertexNormals();
    output.computeBoundingBox();
    output.computeBoundingSphere();
    return { geometry: output, mesh };
  }, [innerRadiusSceneUnits, terrain]);

  useEffect(() => () => terrainMesh?.geometry.dispose(), [terrainMesh]);
  return terrainMesh;
}

function LunarTerrainMaterial({
  color = "#c4c0b7",
  bumpScale = 0.006,
}: {
  color?: string;
  bumpScale?: number;
}) {
  const textures = useMemo(() => getLunarSurfaceTextures(), []);
  return (
    <meshStandardMaterial
      map={textures.albedo}
      bumpMap={textures.microRelief}
      bumpScale={bumpScale}
      color={color}
      roughness={0.98}
      metalness={0}
    />
  );
}

function coordinateInTerrainFrame(
  coordinate: LunarCoordinate,
  origin: LunarCoordinate,
  metadata: NonNullable<TerrainWindow["geometry"]>,
): [number, number] {
  const originVector = coordinateToVector(origin, 1).normalize();
  const targetVector = coordinateToVector(coordinate, 1).normalize();
  const latitude = MathUtils.degToRad(origin.latitude);
  const longitude = MathUtils.degToRad(origin.longitude);
  const east = new Vector3(-Math.sin(longitude), 0, -Math.cos(longitude));
  const north = new Vector3(
    -Math.sin(latitude) * Math.cos(longitude),
    Math.cos(latitude),
    Math.sin(latitude) * Math.sin(longitude),
  );
  const axisAt = (azimuthDeg: number) => east.clone()
    .multiplyScalar(Math.sin(MathUtils.degToRad(azimuthDeg)))
    .add(north.clone().multiplyScalar(Math.cos(MathUtils.degToRad(azimuthDeg))))
    .normalize();
  const delta = targetVector.sub(originVector);
  const lunarRadiusKm = metadata.lunar_reference_radius_m / 1_000;
  return [
    delta.dot(axisAt(metadata.column_azimuth_deg)) * lunarRadiusKm,
    delta.dot(axisAt(metadata.row_azimuth_deg)) * lunarRadiusKm,
  ];
}

function terrainHeightAt(
  terrainMesh: ReturnType<typeof useTerrainMesh>,
  x: number,
  z: number,
) {
  if (!terrainMesh) return null;
  const { mesh } = terrainMesh;
  const columns = Math.round(mesh.widthSceneUnits / Math.abs(
    mesh.positions[3] - mesh.positions[0],
  )) + 1;
  const rows = mesh.positions.length / 3 / columns;
  const column = Math.round((x / mesh.widthSceneUnits + 0.5) * (columns - 1));
  const row = Math.round((z / mesh.depthSceneUnits + 0.5) * (rows - 1));
  if (column < 0 || column >= columns || row < 0 || row >= rows) return null;
  return mesh.positions[(row * columns + column) * 3 + 1];
}

function CelestialMarker({
  name,
  body,
  color,
  observer,
  terrain,
  horizonProfile,
}: {
  name: "Sun" | "Earth";
  body: GroundSkyBody;
  color: string;
  observer: [number, number, number];
  terrain: TerrainWindow;
  horizonProfile: Float32Array;
}) {
  const { t: tr } = useTranslation();
  const metadata = terrain.geometry!;
  const direction = skyDirectionToTerrainAxes(
    body.azimuthDeg,
    body.elevationDeg,
    metadata,
  );
  const localHorizon = horizonAtAzimuth(horizonProfile, body.azimuthDeg);
  const horizon = body.horizonDeg ?? localHorizon;
  const clearance = body.clearanceDeg ?? body.elevationDeg - horizon;
  const state = body.state ?? (clearance + body.angularRadiusDeg > 0 ? "V" : "B");
  const visible = state === "V";
  const distance = name === "Sun" ? 1.72 : 1.56;
  const position: [number, number, number] = [
    observer[0] + direction.x * distance,
    observer[1] + direction.y * distance,
    observer[2] + direction.z * distance,
  ];

  return (
    <group>
      <Line
        points={[observer, position]}
        color={color}
        transparent
        opacity={visible ? 0.32 : 0.15}
        dashed={!visible}
        dashScale={18}
        dashSize={0.7}
        gapSize={0.55}
        lineWidth={1}
      />
      <group position={position}>
        {visible ? (
          <mesh renderOrder={4}>
            <sphereGeometry args={[name === "Sun" ? 0.052 : 0.039, 32, 24]} />
            <meshBasicMaterial color={color} toneMapped={false} />
          </mesh>
        ) : (
          <Billboard renderOrder={5}>
            <mesh>
              <ringGeometry args={[
                name === "Sun" ? 0.047 : 0.034,
                name === "Sun" ? 0.057 : 0.044,
                48,
              ]} />
              <meshBasicMaterial
                color={color}
                transparent
                opacity={0.48}
                depthTest={false}
                toneMapped={false}
              />
            </mesh>
          </Billboard>
        )}
        <Html center position={[0, 0.082, 0]} zIndexRange={[20, 10]}>
          <div className={`ground-sky-label ground-sky-label-${name.toLowerCase()}`}>
            <strong>{tr(name)}</strong>
            <span>{tr(state === "?" ? "unknown" : visible ? "visible" : "terrain hidden")}</span>
            <small>
              {tr("az ")}{body.azimuthDeg.toFixed(1)}{tr("° · el ")}{body.elevationDeg.toFixed(2)}° · {tr(clearance >= 0 ? "+" : "")}{clearance.toFixed(2)}°
            </small>
          </div>
        </Html>
      </group>
    </group>
  );
}

function DynamicTerrain({
  terrain,
  terrainLods,
  coordinate,
  time,
  enhancedLight,
  groundSky,
  overview = false,
  sites = [],
  selectedSiteId = null,
  onSelect,
  onHover,
  onReady,
  imagery = false,
  onImageryStatus,
}: {
  terrain: TerrainWindow;
  terrainLods?: Array<TerrainWindow | null>;
  coordinate: LunarCoordinate;
  time: Date;
  enhancedLight: boolean;
  groundSky?: GroundSky | null;
  overview?: boolean;
  sites?: Site[];
  selectedSiteId?: string | null;
  onSelect?: (coordinate: LunarCoordinate, siteId?: string) => void;
  onHover?: (coordinate: LunarCoordinate | null) => void;
  onReady: () => void;
  imagery?: boolean;
  onImageryStatus?: (status: ImageryStatus) => void;
}) {
  const sunLight = useRef<DirectionalLight>(null);
  const terrainMesh = useTerrainMesh(terrain);
  const midTerrain = terrainLods?.[1] ?? null;
  const farTerrain = terrainLods?.[2] ?? null;
  const contextTerrain = terrainLods?.[3] ?? null;
  const regionalTerrain = terrainLods?.[4] ?? null;
  const horizonTerrain = terrainLods?.[5] ?? null;
  const midTerrainMesh = useTerrainMesh(midTerrain, (terrain.radius_km ?? 1.5) * 0.94);
  const farTerrainMesh = useTerrainMesh(farTerrain, (midTerrain?.radius_km ?? 6) * 0.94);
  const contextTerrainMesh = useTerrainMesh(
    contextTerrain,
    (farTerrain?.radius_km ?? 24) * 0.9,
  );
  const regionalTerrainMesh = useTerrainMesh(
    regionalTerrain,
    (contextTerrain?.radius_km ?? 48) * 0.94,
  );
  const horizonTerrainMesh = useTerrainMesh(
    horizonTerrain,
    (regionalTerrain?.radius_km ?? 120) * 0.94,
  );

  const localSun = useMemo(() => {
    if (!terrain.geometry) return [0.35, 0.7, 0.25] as const;
    if (groundSky) {
      const direction = skyDirectionToTerrainAxes(
        groundSky.sun.azimuthDeg,
        groundSky.sun.elevationDeg,
        terrain.geometry,
      );
      return [direction.x, direction.y, direction.z] as const;
    }
    return worldSunToTerrainAxes(
      approximateSunVector(time),
      coordinate,
      terrain.geometry,
    );
  }, [coordinate, groundSky, terrain.geometry, time]);

  useEffect(() => {
    if (terrainMesh) onReady();
  }, [terrainMesh, onReady]);

  const observerHeightM = groundSky?.observerHeightM ?? 2;
  const horizonProfile = useMemo(
    () => !overview && terrainMesh && terrain.geometry
      ? buildTerrainHorizonProfile(terrainMesh.mesh, terrain.geometry, observerHeightM)
      : new Float32Array(),
    [overview, terrainMesh, terrain.geometry, observerHeightM],
  );
  const shadowHalfSize = terrainShadowHalfSize([
    terrainMesh?.mesh, midTerrainMesh?.mesh, farTerrainMesh?.mesh, contextTerrainMesh?.mesh,
    regionalTerrainMesh?.mesh, horizonTerrainMesh?.mesh,
  ]);
  useLayoutEffect(() => {
    if (sunLight.current) updateTerrainShadow(sunLight.current, shadowHalfSize);
  }, [shadowHalfSize]);
  if (!terrainMesh || !terrain.grid) return null;
  const observer: [number, number, number] = [
    0,
    terrainMesh.mesh.centerYSceneUnits + observerHeightM / 1_000,
    0,
  ];
  // Distant ridges must remain shadow casters in Ground as well as Pole.
  const lightDistance = 720;
  const lightPosition: [number, number, number] = [
    localSun[0] * lightDistance,
    localSun[1] * lightDistance,
    localSun[2] * lightDistance,
  ];
  const handleTerrainPointer = (event: ThreeEvent<PointerEvent>) => {
    if (!terrain.geometry) return;
    event.stopPropagation();
    onHover?.(terrainHitToCoordinate(event.point, coordinate, terrain.geometry));
  };
  const handleTerrainClick = (event: ThreeEvent<MouseEvent>) => {
    if (!terrain.geometry || !isSurfaceSelectionGesture(event.delta)) return;
    event.stopPropagation();
    onSelect?.(terrainHitToCoordinate(event.point, coordinate, terrain.geometry));
  };
  const terrainInteraction = {
    onPointerMove: handleTerrainPointer,
    onPointerOut: () => onHover?.(null),
    onClick: handleTerrainClick,
  };

  return (
    <group>
      <ambientLight intensity={enhancedLight ? (overview ? 0.11 : 0.055) : 0.008} />
      <hemisphereLight
        color="#d8d8d3"
        groundColor="#030405"
        intensity={enhancedLight ? (overview ? 0.075 : 0.04) : 0.006}
      />
      <directionalLight
        ref={sunLight}
        castShadow
        position={lightPosition}
        intensity={enhancedLight ? 8 : 4.4}
        color="#fff2d9"
        shadow-mapSize-width={TERRAIN_SHADOW_SIZE}
        shadow-mapSize-height={TERRAIN_SHADOW_SIZE}
        shadow-camera-left={-shadowHalfSize}
        shadow-camera-right={shadowHalfSize}
        shadow-camera-top={shadowHalfSize}
        shadow-camera-bottom={-shadowHalfSize}
        shadow-camera-near={1}
        shadow-camera-far={1_600}
        shadow-bias={-0.00008}
        shadow-normalBias={0.004}
      />
      <directionalLight
        position={[-lightPosition[0], Math.max(2, -lightPosition[1]), -lightPosition[2]]}
        intensity={enhancedLight ? 0.035 : 0.012}
        color="#769ab1"
      />
      {horizonTerrainMesh && (
        <mesh {...terrainInteraction} geometry={horizonTerrainMesh.geometry} position={[0, -0.012, 0]} receiveShadow castShadow>
          {imagery && horizonTerrain ? <MoonTrekTerrainMaterial terrain={horizonTerrain} fallback={<LunarTerrainMaterial color="#aaa79f" bumpScale={0.002}/>}/> : <LunarTerrainMaterial color="#aaa79f" bumpScale={0.002}/>}
        </mesh>
      )}
      {regionalTerrainMesh && (
        <mesh {...terrainInteraction} geometry={regionalTerrainMesh.geometry} position={[0, -0.009, 0]} receiveShadow castShadow>
          {imagery && regionalTerrain ? <MoonTrekTerrainMaterial terrain={regionalTerrain} fallback={<LunarTerrainMaterial color="#b2afa7" bumpScale={0.0025}/>}/> : <LunarTerrainMaterial color="#b2afa7" bumpScale={0.0025}/>}
        </mesh>
      )}
      {contextTerrainMesh && (
        <mesh
          geometry={contextTerrainMesh.geometry}
          position={[0, -0.0045, 0]}
          receiveShadow
          castShadow
          {...terrainInteraction}
        >
          {imagery && contextTerrain ? <MoonTrekTerrainMaterial terrain={contextTerrain} fallback={<LunarTerrainMaterial color="#b8b5ad" bumpScale={0.003}/>}/> : <LunarTerrainMaterial color="#b8b5ad" bumpScale={0.003}/>}
        </mesh>
      )}
      {farTerrainMesh && (
        <mesh {...terrainInteraction} geometry={farTerrainMesh.geometry} position={[0, -0.003, 0]} receiveShadow castShadow>
          {imagery && farTerrain ? <MoonTrekTerrainMaterial terrain={farTerrain} fallback={<LunarTerrainMaterial color="#bdb9b1" bumpScale={0.0035}/>}/> : <LunarTerrainMaterial color="#bdb9b1" bumpScale={0.0035}/>}
        </mesh>
      )}
      {midTerrainMesh && (
        <mesh {...terrainInteraction} geometry={midTerrainMesh.geometry} position={[0, -0.0015, 0]} receiveShadow castShadow>
          {imagery && midTerrain ? <MoonTrekTerrainMaterial terrain={midTerrain} fallback={<LunarTerrainMaterial color="#c1bdb5" bumpScale={0.0045}/>}/> : <LunarTerrainMaterial color="#c1bdb5" bumpScale={0.0045}/>}
        </mesh>
      )}
      <mesh
        {...terrainInteraction}
        geometry={terrainMesh.geometry}
        castShadow
        receiveShadow
      >
        {imagery ? <MoonTrekTerrainMaterial terrain={terrain} onStatus={onImageryStatus} fallback={<LunarTerrainMaterial color="#c5c1b8" bumpScale={0.006}/>}/> : <LunarTerrainMaterial color="#c5c1b8" bumpScale={0.006}/>}
      </mesh>
      {!overview && <group position={observer}>
        <mesh>
          <sphereGeometry args={[0.0025, 16, 16]} />
          <meshBasicMaterial color="#dffaff" toneMapped={false} />
        </mesh>
        <pointLight color="#6edcf4" intensity={0.08} distance={0.08} />
        <Line points={[[0, 0, 0], [0, 0.022, 0]]} color="#7ce3ff" lineWidth={1} />
      </group>}
      {!overview && <Line
        points={Array.from({ length: 129 }, (_, index) => {
          const angle = (index / 128) * Math.PI * 2;
          return [
            observer[0] + Math.sin(angle) * 1.38,
            observer[1],
            observer[2] + Math.cos(angle) * 1.38,
          ] as [number, number, number];
        })}
        color="#8fa2aa"
        transparent
        opacity={0.23}
        dashed
        dashScale={22}
        dashSize={0.55}
        gapSize={0.75}
        lineWidth={0.7}
      />}
      {!overview && groundSky && terrain.geometry && (
        <>
          <CelestialMarker
            name="Sun"
            body={groundSky.sun}
            color="#fbbf24"
            observer={observer}
            terrain={terrain}
            horizonProfile={horizonProfile}
          />
          <CelestialMarker
            name="Earth"
            body={groundSky.earth}
            color="#38bdf8"
            observer={observer}
            terrain={terrain}
            horizonProfile={horizonProfile}
          />
        </>
      )}
      {overview && terrain.geometry && sites.map((site) => {
        const [x, z] = coordinateInTerrainFrame(site, coordinate, terrain.geometry!);
        const distance = Math.hypot(x, z);
        if (distance > (horizonTerrain?.radius_km ?? 300) * 0.96) return null;
        const terrainAtSite = [
          terrainMesh,
          midTerrainMesh,
          farTerrainMesh,
          contextTerrainMesh,
          regionalTerrainMesh,
          horizonTerrainMesh,
        ].find((candidate) => candidate && distance <= Math.min(
          candidate.mesh.widthSceneUnits,
          candidate.mesh.depthSceneUnits,
        ) * 0.48);
        const y = terrainHeightAt(terrainAtSite ?? horizonTerrainMesh, x, z) ?? 0;
        const active = site.id === selectedSiteId;
        return (
          <group key={site.id} position={[x, y + 0.22, z]}>
            <mesh
              rotation={[-Math.PI / 2, 0, 0]}
              onClick={(event) => {
                event.stopPropagation();
                onSelect?.(site, site.id);
              }}
            >
              <ringGeometry args={[active ? 3.2 : 1.8, active ? 4.4 : 2.7, 48]} />
              <meshBasicMaterial
                color={active ? "#67e8f9" : "#f2c66d"}
                transparent
                opacity={active ? 1 : 0.88}
                depthTest={false}
                toneMapped={false}
              />
            </mesh>
            {active && (
              <Html center position={[0, 5.8, 0]} zIndexRange={[30, 10]}>
                <div className="site-marker-label">{site.name}</div>
              </Html>
            )}
          </group>
        );
      })}
    </group>
  );
}

function useSouthPolarCapMesh(terrain?: SouthPolarTerrain | null) {
  const mesh = useMemo(() => {
    if (!terrain?.grid || !terrain.projection) return null;
    const data = buildSouthPolarCapMeshData(
      terrain.grid,
      terrain.projection.bounds_xy_m,
      MOON_SCENE_RADIUS,
      terrain.projection.lunar_reference_radius_m,
    );
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new Float32BufferAttribute(data.positions, 3));
    geometry.setAttribute("uv", new Float32BufferAttribute(data.uvs, 2));
    geometry.setIndex(new Uint32BufferAttribute(data.indices, 1));
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();
    return geometry;
  }, [terrain]);

  useEffect(() => () => mesh?.dispose(), [mesh]);
  return mesh;
}

function useGlobeSiteTerrain(
  terrain: TerrainWindow | null,
  coordinate: LunarCoordinate | null,
  innerRadiusSceneUnits = 0,
  projectionBounds?: [number, number, number, number],
) {
  const geometry = useMemo(() => {
    if (!terrain?.grid || !terrain.geometry || !coordinate) return null;
    const local = buildTerrainMeshData(terrain.grid, terrain.geometry);
    const latitude = MathUtils.degToRad(coordinate.latitude);
    const longitude = MathUtils.degToRad(coordinate.longitude);
    const up = new Vector3(
      Math.cos(latitude) * Math.cos(longitude),
      Math.sin(latitude),
      -Math.cos(latitude) * Math.sin(longitude),
    );
    const east = new Vector3(-Math.sin(longitude), 0, -Math.cos(longitude));
    const north = new Vector3(
      -Math.sin(latitude) * Math.cos(longitude),
      Math.cos(latitude),
      Math.sin(latitude) * Math.sin(longitude),
    );
    const axisAt = (azimuthDeg: number) => east.clone()
      .multiplyScalar(Math.sin(MathUtils.degToRad(azimuthDeg)))
      .add(north.clone().multiplyScalar(Math.cos(MathUtils.degToRad(azimuthDeg))))
      .normalize();
    const columnAxis = axisAt(terrain.geometry.column_azimuth_deg);
    const rowAxis = axisAt(terrain.geometry.row_azimuth_deg);
    const kilometresToGlobe = MOON_SCENE_RADIUS / 1_737.4;
    const positions = new Float32Array(local.positions.length);
    const uvs = new Float32Array((local.positions.length / 3) * 2);
    const validRadius = Math.min(local.widthSceneUnits, local.depthSceneUnits) * 0.5;
    for (let offset = 0; offset < local.positions.length; offset += 3) {
      const world = up.clone().multiplyScalar(
        MOON_SCENE_RADIUS + (local.positions[offset + 1] + 0.22) * kilometresToGlobe,
      );
      world.addScaledVector(columnAxis, local.positions[offset] * kilometresToGlobe);
      world.addScaledVector(rowAxis, local.positions[offset + 2] * kilometresToGlobe);
      positions[offset] = world.x;
      positions[offset + 1] = world.y;
      positions[offset + 2] = world.z;
      const uvOffset = (offset / 3) * 2;
      if (projectionBounds) {
        const [left, bottom, right, top] = projectionBounds;
        const unit = world.clone().normalize();
        const vertexLatitude = Math.asin(MathUtils.clamp(unit.y, -1, 1));
        const vertexLongitude = Math.atan2(-unit.z, unit.x);
        const rho = 2 * terrain.geometry.lunar_reference_radius_m
          * Math.tan((vertexLatitude + Math.PI / 2) / 2);
        const projectedX = rho * Math.sin(vertexLongitude);
        const projectedY = rho * Math.cos(vertexLongitude);
        uvs[uvOffset] = (projectedX - left) / (right - left);
        uvs[uvOffset + 1] = (projectedY - bottom) / (top - bottom);
      } else {
        uvs[uvOffset] = local.positions[offset] / local.widthSceneUnits + 0.5;
        uvs[uvOffset + 1] = local.positions[offset + 2] / local.depthSceneUnits + 0.5;
      }
    }
    const circularIndices: number[] = [];
    for (let offset = 0; offset < local.indices.length; offset += 3) {
      const triangle = [
        local.indices[offset],
        local.indices[offset + 1],
        local.indices[offset + 2],
      ];
      if (triangle.every((index) => {
        const positionOffset = index * 3;
        return Math.hypot(
          local.positions[positionOffset],
          local.positions[positionOffset + 2],
        ) <= validRadius && Math.hypot(
          local.positions[positionOffset],
          local.positions[positionOffset + 2],
        ) >= innerRadiusSceneUnits;
      })) {
        circularIndices.push(...triangle);
      }
    }
    const output = new BufferGeometry();
    output.setAttribute("position", new Float32BufferAttribute(positions, 3));
    output.setAttribute("uv", new Float32BufferAttribute(uvs, 2));
    output.setIndex(new Uint32BufferAttribute(circularIndices, 1));
    output.computeVertexNormals();
    output.computeBoundingSphere();
    return output;
  }, [coordinate, innerRadiusSceneUnits, projectionBounds, terrain]);

  useEffect(() => () => geometry?.dispose(), [geometry]);
  return geometry;
}

function normalizedFootprintId(siteId: string | null) {
  if (!siteId) return null;
  return siteId.replace(/_P\d+$/, "").replace(/_dem$/, "");
}

function SiteFootprint({
  footprint,
  active,
}: {
  footprint: SouthPolarFootprint;
  active: boolean;
}) {
  const corners = useMemo(
    () => footprint.ring_lon_lat.map(([longitude, latitude]) =>
      coordinateToVector(
        { latitude, longitude },
        MOON_SCENE_RADIUS * (active ? 1.0036 : 1.0026),
      )),
    [active, footprint],
  );
  const cross = useMemo(() => {
    const midpoint = (a: Vector3, b: Vector3) => a.clone().add(b).normalize()
      .multiplyScalar(MOON_SCENE_RADIUS * (active ? 1.0038 : 1.0028));
    return [
      [midpoint(corners[0], corners[1]), midpoint(corners[2], corners[3])],
      [midpoint(corners[1], corners[2]), midpoint(corners[3], corners[0])],
    ];
  }, [active, corners]);
  const crossGeometry = useMemo(
    () => new BufferGeometry().setFromPoints(cross.flat()),
    [cross],
  );
  const outlineGeometry = useMemo(
    () => new BufferGeometry().setFromPoints(corners.slice(0, 4)),
    [corners],
  );
  useEffect(
    () => () => {
      crossGeometry.dispose();
      outlineGeometry.dispose();
    },
    [crossGeometry, outlineGeometry],
  );
  return (
    <group>
      <lineLoop geometry={outlineGeometry}>
        <lineBasicMaterial
          color={active ? "#67e8f9" : "#f2c66d"}
          transparent
          opacity={active ? 1 : 0.78}
          depthTest={false}
        />
      </lineLoop>
      <lineSegments geometry={crossGeometry}>
        <lineBasicMaterial
          color={active ? "#67e8f9" : "#f2c66d"}
          transparent
          opacity={active ? 0.7 : 0.3}
          depthTest={false}
        />
      </lineSegments>
    </group>
  );
}

function SouthPolarCap({
  terrain,
  selectedTerrains,
  selected,
  selectedSiteId,
  showSelectedDetail,
  onSelect,
  onHover,
}: {
  terrain: SouthPolarTerrain;
  selectedTerrains: TerrainWindow[];
  selected: LunarCoordinate | null;
  selectedSiteId: string | null;
  showSelectedDetail: boolean;
  onSelect: (coordinate: LunarCoordinate, siteId?: string) => void;
  onHover: (coordinate: LunarCoordinate | null) => void;
}) {
  const capGeometry = useSouthPolarCapMesh(terrain);
  const nearTerrain = selectedTerrains[0] ?? null;
  const midTerrain = selectedTerrains[1] ?? null;
  const farTerrain = selectedTerrains[2] ?? null;
  const contextTerrain = selectedTerrains[3] ?? null;
  const regionalTerrain = selectedTerrains[4] ?? null;
  const horizonTerrain = selectedTerrains[5] ?? null;
  const projectionBounds = terrain.projection.bounds_xy_m;
  const nearGeometry = useGlobeSiteTerrain(nearTerrain, selected, 0, projectionBounds);
  const midGeometry = useGlobeSiteTerrain(
    midTerrain,
    selected,
    (nearTerrain?.radius_km ?? 1.5) * 0.94,
    projectionBounds,
  );
  const farGeometry = useGlobeSiteTerrain(
    farTerrain,
    selected,
    (midTerrain?.radius_km ?? 6) * 0.94,
    projectionBounds,
  );
  const contextGeometry = useGlobeSiteTerrain(
    contextTerrain,
    selected,
    (farTerrain?.radius_km ?? 24) * 0.94,
    projectionBounds,
  );
  const regionalGeometry = useGlobeSiteTerrain(
    regionalTerrain,
    selected,
    (contextTerrain?.radius_km ?? 48) * 0.94,
    projectionBounds,
  );
  const horizonGeometry = useGlobeSiteTerrain(
    horizonTerrain,
    selected,
    (regionalTerrain?.radius_km ?? 120) * 0.94,
    projectionBounds,
  );
  const hillshade = useTexture("/assets/nasa/south_pole_hillshade_2k.png");
  const radialAlpha = useMemo(() => {
    const size = 256;
    const pixels = new Uint8Array(size * size * 4);
    for (let row = 0; row < size; row += 1) {
      for (let column = 0; column < size; column += 1) {
        const x = ((column + 0.5) / size) * 2 - 1;
        const y = ((row + 0.5) / size) * 2 - 1;
        const radius = Math.hypot(x, y);
        const opacity = MathUtils.smoothstep(1 - radius, 0, 0.045);
        const value = Math.round(opacity * 255);
        const offset = (row * size + column) * 4;
        pixels[offset] = value;
        pixels[offset + 1] = value;
        pixels[offset + 2] = value;
        pixels[offset + 3] = 255;
      }
    }
    const texture = new DataTexture(
      pixels,
      size,
      size,
      RGBAFormat,
      UnsignedByteType,
    );
    texture.minFilter = LinearFilter;
    texture.magFilter = LinearFilter;
    texture.needsUpdate = true;
    return texture;
  }, []);
  const activeFootprint = normalizedFootprintId(selectedSiteId);

  useEffect(() => {
    hillshade.colorSpace = SRGBColorSpace;
    hillshade.anisotropy = 8;
  }, [hillshade]);
  useEffect(() => () => radialAlpha.dispose(), [radialAlpha]);

  if (!capGeometry) return null;
  return (
    <group
      onPointerMove={(event) => {
        event.stopPropagation();
        onHover(surfaceRayToCoordinate(event.ray));
      }}
      onPointerOut={() => onHover(null)}
      onClick={(event) => {
        event.stopPropagation();
        if (!isSurfaceSelectionGesture(event.delta)) return;
        const coordinate = surfaceRayToCoordinate(event.ray);
        if (coordinate) onSelect(coordinate);
      }}
    >
      <mesh
        geometry={capGeometry}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial
          map={hillshade}
          alphaMap={radialAlpha}
          color="#c3beb4"
          transparent
          alphaTest={0.025}
          roughness={1}
          metalness={0}
          polygonOffset
          polygonOffsetFactor={-2}
          polygonOffsetUnits={-2}
        />
      </mesh>
      {showSelectedDetail && [
        horizonGeometry,
        regionalGeometry,
        contextGeometry,
        farGeometry,
        midGeometry,
        nearGeometry,
      ].map((geometry, index) => geometry && (
        <mesh key={index} geometry={geometry} castShadow receiveShadow>
          <meshStandardMaterial
            map={hillshade}
            color="#c3beb4"
            roughness={1}
            metalness={0}
            polygonOffset
            polygonOffsetFactor={-3 - index}
            polygonOffsetUnits={-3 - index}
          />
        </mesh>
      ))}
      {terrain.site_footprints.map((footprint) => (
        <SiteFootprint
          key={footprint.site_id}
          footprint={footprint}
          active={footprint.site_id === activeFootprint}
        />
      ))}
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
    () => coordinateToVector(site, MOON_SCENE_RADIUS * 1.0042),
    [site],
  );
  const normal = useMemo(() => position.clone().normalize(), [position]);
  const orientation = useMemo(
    () => new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), normal),
    [normal],
  );
  const reticleSize = active ? 0.03 : 0.019;
  const reticleGeometry = useMemo(
    () => new BufferGeometry().setFromPoints([
      new Vector3(-reticleSize, 0, -reticleSize),
      new Vector3(reticleSize, 0, -reticleSize),
      new Vector3(reticleSize, 0, reticleSize),
      new Vector3(-reticleSize, 0, reticleSize),
    ]),
    [reticleSize],
  );
  const stemGeometry = useMemo(
    () => new BufferGeometry().setFromPoints([
      new Vector3(0, 0, 0),
      new Vector3(0, 0.032, 0),
    ]),
    [],
  );
  useEffect(
    () => () => {
      reticleGeometry.dispose();
      stemGeometry.dispose();
    },
    [reticleGeometry, stemGeometry],
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
        <sphereGeometry args={[active ? 0.009 : 0.0055, 20, 20]} />
        <meshBasicMaterial color={active ? "#67e8f9" : "#f2c66d"} />
      </mesh>
      <lineLoop geometry={reticleGeometry}>
        <lineBasicMaterial
          color={active ? "#67e8f9" : "#f2c66d"}
          transparent
          opacity={active ? 1 : 0.72}
          depthTest={false}
        />
      </lineLoop>
      <lineSegments geometry={stemGeometry}>
        <lineBasicMaterial
          color={active ? "#67e8f9" : "#f2c66d"}
          transparent
          opacity={0.72}
          depthTest={false}
        />
      </lineSegments>
      {active && (
        <Html center position={[0, 0.052, 0]}>
          <div className="site-marker-label">{site.name}</div>
        </Html>
      )}
    </group>
  );
}

function SelectedMarker({ coordinate }: { coordinate: LunarCoordinate }) {
  const { t: tr } = useTranslation();
  const position = useMemo(
    () => coordinateToVector(coordinate, MOON_SCENE_RADIUS * 1.003),
    [coordinate],
  );

  return (
    <group position={[position.x, position.y, position.z]}>
      <mesh>
        <sphereGeometry args={[0.0035, 18, 18]} />
        <meshBasicMaterial color="#7ce3ff" toneMapped={false} />
      </mesh>
      <Billboard>
        <mesh>
          <ringGeometry args={[0.008, 0.0105, 48]} />
          <meshBasicMaterial color="#7ce3ff" transparent opacity={0.9} depthTest={false} />
        </mesh>
      </Billboard>
      <Html center position={[0, 0.026, 0]}>
        <div className="site-marker-label">{tr("Custom point")}</div>
      </Html>
    </group>
  );
}

function Moon({
  time,
  sunVector,
  cameraPreset,
  layers,
  sites,
  selected,
  selectedSiteId,
  terrainWindow,
  terrainLods,
  southPolarTerrain,
  onSelect,
  onHover,
  onReady,
  imagery = false,
  onImageryStatus,
}: MoonSceneProps) {
  const [imageryBaseReady,setImageryBaseReady]=useState(false);
  const markImageryReady=useCallback(()=>setImageryBaseReady(true),[]);
  const [colorMap, elevationMap] = useTexture([
    "/assets/nasa/lroc_color_2k.jpg",
    "/assets/nasa/lola_global_ldem64_4k.png",
  ]);
  const material = useRef<MeshStandardMaterial>(null);
  const sun = useMemo(() => sunVector ?? approximateSunVector(time), [sunVector, time]);

  useEffect(() => {
    colorMap.colorSpace = SRGBColorSpace;
    colorMap.anisotropy = 8;
    elevationMap.anisotropy = 4;
    // Keep the interactive Moon geometry in the MOON_ME coordinate frame.
    // The source rasters need a 180-degree longitude offset; applying it in UV
    // space avoids putting raycast hits and geographic markers in two frames.
    for (const texture of [colorMap, elevationMap]) {
      texture.wrapS = RepeatWrapping;
      texture.offset.x = 0.5;
      texture.needsUpdate = true;
    }
    onReady();
  }, [colorMap, elevationMap, onReady]);

  const handlePointer = (event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation();
    onHover(surfaceRayToCoordinate(event.ray));
  };

  return (
    <>
      <ambientLight intensity={layers.enhancedLight ? 0.12 : 0.035} />
      <hemisphereLight
        color="#fff8ec"
        groundColor="#050607"
        intensity={layers.enhancedLight ? 0.08 : 0.025}
      />
      <directionalLight
        castShadow
        color="#fff6e7"
        intensity={layers.enhancedLight ? 4.8 : 2.4}
        position={[sun.x * 8, sun.y * 8, sun.z * 8]}
        shadow-mapSize-width={4096}
        shadow-mapSize-height={4096}
        shadow-camera-left={-3.4}
        shadow-camera-right={3.4}
        shadow-camera-top={3.4}
        shadow-camera-bottom={-3.4}
        shadow-camera-near={0.1}
        shadow-camera-far={20}
        shadow-bias={-0.00008}
        shadow-normalBias={0.006}
      />
      <directionalLight
        color="#769ab1"
        intensity={layers.enhancedLight ? 0.035 : 0.015}
        position={[sun.x * -6, sun.y * -6, sun.z * -6]}
      />
      <mesh
        onPointerMove={handlePointer}
        onPointerOut={() => onHover(null)}
        onClick={(event) => {
          event.stopPropagation();
          if (!isSurfaceSelectionGesture(event.delta)) return;
          const coordinate = surfaceRayToCoordinate(event.ray);
          if (coordinate) onSelect(coordinate);
        }}
      >
        <sphereGeometry args={[MOON_SCENE_RADIUS, 768, 384]} />
        <meshStandardMaterial
          visible={!imagery || !imageryBaseReady}
          ref={material}
          map={colorMap}
          displacementMap={elevationMap}
          displacementScale={GLOBAL_LOLA_DISPLACEMENT_SCALE}
          displacementBias={GLOBAL_LOLA_DISPLACEMENT_BIAS}
          bumpMap={elevationMap}
          bumpScale={0.004}
          roughness={1}
          metalness={0}
          color={new Color("#d7d5cf")}
        />
      </mesh>
      {imagery && <MoonTrekGlobe elevationMap={elevationMap} onBaseReady={markImageryReady} onStatus={onImageryStatus}/>}
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
      {southPolarTerrain && !imagery && (
        <SouthPolarCap
          terrain={southPolarTerrain}
          selectedTerrains={terrainLods?.filter((item): item is TerrainWindow => item !== null) ?? (terrainWindow ? [terrainWindow] : [])}
          selected={selected}
          selectedSiteId={selectedSiteId}
          showSelectedDetail={cameraPreset === "south-pole"}
          onSelect={onSelect}
          onHover={onHover}
        />
      )}
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
  const localTerrain =
    (props.cameraPreset === "surface" || props.cameraPreset === "south-pole") &&
    props.selected !== null &&
    props.terrainWindow?.coverage_status === "COVERED";
  const surfaceViewDirection = useMemo<[number, number, number] | undefined>(() => {
    if (props.cameraPreset !== "surface" || !props.groundSky || !props.terrainWindow?.geometry) return undefined;
    const sun = skyDirectionToTerrainAxes(
      props.groundSky.sun.azimuthDeg,
      props.groundSky.sun.elevationDeg,
      props.terrainWindow.geometry,
    );
    const earth = skyDirectionToTerrainAxes(
      props.groundSky.earth.azimuthDeg,
      props.groundSky.earth.elevationDeg,
      props.terrainWindow.geometry,
    );
    const x = sun.x + earth.x;
    const z = sun.z + earth.z;
    return Math.hypot(x, z) > 0.15
      ? [x, sun.y + earth.y, z]
      : [sun.x, sun.y, sun.z];
  }, [props.cameraPreset, props.groundSky, props.terrainWindow?.geometry]);
  return (
    <Canvas
      shadows
      dpr={[1, 1.8]}
      camera={INITIAL_CAMERA}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.setClearColor("#030507");
        gl.shadowMap.type = PCFSoftShadowMap;
        gl.toneMappingExposure = 1.4;
        // The renderer is already usable at this point.  Reveal the shell now
        // and let Suspense stream the lunar textures into the scene instead of
        // keeping the whole application behind a texture-loading overlay.
        props.onReady();
      }}
    >
      <color attach="background" args={["#030507"]} />
      <fog attach="fog" args={["#030507", 700, 1_500]} />
      {props.cameraPreset !== "south-pole" && <Stars
        radius={54}
        depth={24}
        count={2600}
        factor={1.6}
        saturation={0.12}
        fade
        speed={0.08}
      />}
      <Suspense fallback={null}>
        {localTerrain && props.terrainWindow && props.selected ? (
          <DynamicTerrain
            terrain={props.terrainWindow}
            terrainLods={props.terrainLods}
            coordinate={props.selected}
            time={props.time}
            enhancedLight={props.layers.enhancedLight}
            groundSky={props.groundSky}
            overview={props.cameraPreset === "south-pole"}
            sites={props.sites}
            selectedSiteId={props.selectedSiteId}
            onSelect={props.onSelect}
            onHover={props.onHover}
            onReady={props.onReady}
            imagery={props.imagery}
            onImageryStatus={props.onImageryStatus}
          />
        ) : props.cameraPreset !== "south-pole" ? (
          <Moon {...props} />
        ) : null}
      </Suspense>
      <SceneRig
        preset={props.cameraPreset}
        surfaceTargetY={0}
        surfaceViewDirection={surfaceViewDirection}
      />
      {localTerrain && props.cameraPreset === "surface" ? (
        <OrbitControls
          makeDefault
          target={[
            0,
            0.018,
            0,
          ]}
          enableDamping
          dampingFactor={0.065}
          minDistance={0.18}
          maxDistance={12}
          rotateSpeed={0.38}
          zoomSpeed={0.65}
          panSpeed={0.35}
          enablePan
          minPolarAngle={MathUtils.degToRad(4)}
          maxPolarAngle={MathUtils.degToRad(88)}
        />
      ) : props.cameraPreset === "south-pole" ? (
        <MapControls
          makeDefault
          target={POLE_TARGET}
          enableDamping
          dampingFactor={0.1}
          minDistance={1.2}
          maxDistance={850}
          rotateSpeed={0.72}
          zoomSpeed={1}
          panSpeed={1.15}
          enablePan
          enableRotate
          enableZoom
          screenSpacePanning={false}
          minPolarAngle={MathUtils.degToRad(12)}
          maxPolarAngle={MathUtils.degToRad(86)}
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
