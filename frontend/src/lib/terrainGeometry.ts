export const METRES_PER_SCENE_UNIT = 1_000;
export const LUNAR_REFERENCE_RADIUS_M = 1_737_400;

export type TerrainGrid = {
  rows: number;
  columns: number;
  elevation_m_row_major: Array<number | null>;
  min_elevation_m: number;
  max_elevation_m: number;
  valid_fraction: number;
  spacing_m: number;
};

export type TerrainGeometryMetadata = {
  horizontal_scale: number;
  vertical_scale: number;
  horizontal_unit: "metre";
  vertical_unit: "metre";
  lunar_reference_radius_m: number;
  center_elevation_m: number;
  center_x_m?: number;
  center_y_m?: number;
  column_azimuth_deg: number;
  row_azimuth_deg: number;
  projection?: string;
  surface_model: string;
};

export type TerrainMeshData = {
  positions: Float32Array;
  indices: Uint32Array;
  widthSceneUnits: number;
  depthSceneUnits: number;
  minYSceneUnits: number;
  maxYSceneUnits: number;
  centerYSceneUnits: number;
};

export type TerrainSkyDirection = {
  x: number;
  y: number;
  z: number;
};

export type SouthPolarCapGrid = {
  rows: number;
  columns: number;
  elevation_m_row_major: Array<number | null>;
};

export type SouthPolarCapMeshData = {
  positions: Float32Array;
  indices: Uint32Array;
  uvs: Float32Array;
};

export function buildSouthPolarCapMeshData(
  grid: SouthPolarCapGrid,
  bounds: [number, number, number, number],
  moonSceneRadius: number,
  lunarReferenceRadiusM = LUNAR_REFERENCE_RADIUS_M,
): SouthPolarCapMeshData {
  const [left, bottom, right, top] = bounds;
  if (
    grid.rows < 2 ||
    grid.columns < 2 ||
    grid.elevation_m_row_major.length !== grid.rows * grid.columns ||
    !(left < right && bottom < top)
  ) {
    throw new Error("Invalid south-polar terrain grid");
  }

  const positions = new Float32Array(grid.rows * grid.columns * 3);
  const uvs = new Float32Array(grid.rows * grid.columns * 2);
  const valid = new Uint8Array(grid.rows * grid.columns);
  const indices: number[] = [];
  const displayLiftM = 220;
  const polarRadiusM = Math.min(
    Math.abs(left),
    Math.abs(right),
    Math.abs(bottom),
    Math.abs(top),
  );

  for (let row = 0; row < grid.rows; row += 1) {
    const rowFraction = row / (grid.rows - 1);
    const projectedY = top - rowFraction * (top - bottom);
    for (let column = 0; column < grid.columns; column += 1) {
      const columnFraction = column / (grid.columns - 1);
      const projectedX = left + columnFraction * (right - left);
      const index = row * grid.columns + column;
      const elevation = grid.elevation_m_row_major[index] ?? 0;
      const rho = Math.hypot(projectedX, projectedY);
      valid[index] =
        grid.elevation_m_row_major[index] !== null && rho <= polarRadiusM ? 1 : 0;
      const latitude = -Math.PI / 2 + 2 * Math.atan(rho / (2 * lunarReferenceRadiusM));
      const longitude = Math.atan2(projectedX, projectedY);
      const radialScene =
        moonSceneRadius *
        (1 + (elevation + displayLiftM) / lunarReferenceRadiusM);
      const horizontal = Math.cos(latitude);
      const positionOffset = index * 3;
      positions[positionOffset] = radialScene * horizontal * Math.cos(longitude);
      positions[positionOffset + 1] = radialScene * Math.sin(latitude);
      positions[positionOffset + 2] = -radialScene * horizontal * Math.sin(longitude);
      const uvOffset = index * 2;
      uvs[uvOffset] = columnFraction;
      uvs[uvOffset + 1] = 1 - rowFraction;
    }
  }

  for (let row = 0; row < grid.rows - 1; row += 1) {
    for (let column = 0; column < grid.columns - 1; column += 1) {
      const a = row * grid.columns + column;
      const b = a + 1;
      const c = a + grid.columns;
      const d = c + 1;
      if ([a, b, c, d].every((index) => valid[index] === 1)) {
        indices.push(a, c, b, b, c, d);
      }
    }
  }
  return { positions, indices: new Uint32Array(indices), uvs };
}

function tangentHeightMetres(
  xMetres: number,
  zMetres: number,
  elevationMetres: number,
  metadata: TerrainGeometryMetadata,
): number {
  const referenceRadius =
    metadata.lunar_reference_radius_m + metadata.center_elevation_m;
  const surfaceRadius = metadata.lunar_reference_radius_m + elevationMetres;
  const radialSquared =
    surfaceRadius * surfaceRadius - xMetres * xMetres - zMetres * zMetres;
  if (radialSquared <= 0) {
    throw new Error("Terrain window exceeds the local lunar tangent frame");
  }
  return Math.sqrt(radialSquared) - referenceRadius;
}

export function buildTerrainMeshData(
  grid: TerrainGrid,
  metadata: TerrainGeometryMetadata,
): TerrainMeshData {
  if (metadata.horizontal_scale !== 1 || metadata.vertical_scale !== 1) {
    throw new Error("Scientific terrain renderer requires a true 1:1 metre scale");
  }
  if (
    grid.rows < 2 ||
    grid.columns < 2 ||
    grid.spacing_m <= 0 ||
    grid.elevation_m_row_major.length !== grid.rows * grid.columns
  ) {
    throw new Error("Invalid terrain grid dimensions");
  }

  const positions = new Float32Array(grid.rows * grid.columns * 3);
  const triangles: number[] = [];
  const centerColumn = (grid.columns - 1) / 2;
  const centerRow = (grid.rows - 1) / 2;
  let minY = Number.POSITIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  for (let row = 0; row < grid.rows; row += 1) {
    for (let column = 0; column < grid.columns; column += 1) {
      const index = row * grid.columns + column;
      const elevation = grid.elevation_m_row_major[index];
      const xMetres = (column - centerColumn) * grid.spacing_m;
      const zMetres = (row - centerRow) * grid.spacing_m;
      const yMetres =
        elevation === null
          ? 0
          : tangentHeightMetres(xMetres, zMetres, elevation, metadata);
      const offset = index * 3;
      positions[offset] = xMetres / METRES_PER_SCENE_UNIT;
      positions[offset + 1] = yMetres / METRES_PER_SCENE_UNIT;
      positions[offset + 2] = zMetres / METRES_PER_SCENE_UNIT;
      if (elevation !== null) {
        minY = Math.min(minY, positions[offset + 1]);
        maxY = Math.max(maxY, positions[offset + 1]);
      }
    }
  }

  for (let row = 0; row < grid.rows - 1; row += 1) {
    for (let column = 0; column < grid.columns - 1; column += 1) {
      const a = row * grid.columns + column;
      const b = a + 1;
      const c = a + grid.columns;
      const d = c + 1;
      if ([a, b, c, d].every((index) => grid.elevation_m_row_major[index] !== null)) {
        triangles.push(a, c, b, b, c, d);
      }
    }
  }

  const centerIndex =
    Math.floor(centerRow) * grid.columns + Math.floor(centerColumn);
  const centerYSceneUnits = positions[centerIndex * 3 + 1];
  return {
    positions,
    indices: new Uint32Array(triangles),
    widthSceneUnits: ((grid.columns - 1) * grid.spacing_m) / METRES_PER_SCENE_UNIT,
    depthSceneUnits: ((grid.rows - 1) * grid.spacing_m) / METRES_PER_SCENE_UNIT,
    minYSceneUnits: Number.isFinite(minY) ? minY : 0,
    maxYSceneUnits: Number.isFinite(maxY) ? maxY : 0,
    centerYSceneUnits,
  };
}

type VectorLike = { x: number; y: number; z: number };
type LunarCoordinateLike = { latitude: number; longitude: number };

function dot(a: VectorLike, b: VectorLike): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function axisAtAzimuth(
  azimuthDegrees: number,
  east: VectorLike,
  north: VectorLike,
): VectorLike {
  const azimuth = (azimuthDegrees * Math.PI) / 180;
  return {
    x: east.x * Math.sin(azimuth) + north.x * Math.cos(azimuth),
    y: east.y * Math.sin(azimuth) + north.y * Math.cos(azimuth),
    z: east.z * Math.sin(azimuth) + north.z * Math.cos(azimuth),
  };
}

export function worldSunToTerrainAxes(
  sun: VectorLike,
  coordinate: LunarCoordinateLike,
  metadata: TerrainGeometryMetadata,
): [number, number, number] {
  const latitude = (coordinate.latitude * Math.PI) / 180;
  const longitude = (coordinate.longitude * Math.PI) / 180;
  const up = {
    x: Math.cos(latitude) * Math.cos(longitude),
    y: Math.sin(latitude),
    z: -Math.cos(latitude) * Math.sin(longitude),
  };
  const east = {
    x: -Math.sin(longitude),
    y: 0,
    z: -Math.cos(longitude),
  };
  const north = {
    x: -Math.sin(latitude) * Math.cos(longitude),
    y: Math.cos(latitude),
    z: Math.sin(latitude) * Math.sin(longitude),
  };
  const columnAxis = axisAtAzimuth(metadata.column_azimuth_deg, east, north);
  const rowAxis = axisAtAzimuth(metadata.row_azimuth_deg, east, north);
  const local: [number, number, number] = [
    dot(sun, columnAxis),
    dot(sun, up),
    dot(sun, rowAxis),
  ];
  const length = Math.hypot(...local) || 1;
  return [local[0] / length, local[1] / length, local[2] / length];
}

export function skyDirectionToTerrainAxes(
  azimuthDeg: number,
  elevationDeg: number,
  metadata: TerrainGeometryMetadata,
): TerrainSkyDirection {
  const azimuth = (azimuthDeg * Math.PI) / 180;
  const elevation = (elevationDeg * Math.PI) / 180;
  const horizontal = Math.cos(elevation);
  const east = horizontal * Math.sin(azimuth);
  const north = horizontal * Math.cos(azimuth);
  const project = (axisAzimuthDeg: number) => {
    const axis = (axisAzimuthDeg * Math.PI) / 180;
    return east * Math.sin(axis) + north * Math.cos(axis);
  };
  const direction = {
    x: project(metadata.column_azimuth_deg),
    y: Math.sin(elevation),
    z: project(metadata.row_azimuth_deg),
  };
  const length = Math.hypot(direction.x, direction.y, direction.z) || 1;
  return {
    x: direction.x / length,
    y: direction.y / length,
    z: direction.z / length,
  };
}

export function buildTerrainHorizonProfile(
  mesh: TerrainMeshData,
  metadata: TerrainGeometryMetadata,
  observerHeightM: number,
  bins = 360,
): Float32Array {
  if (!Number.isInteger(bins) || bins < 36) {
    throw new Error("Terrain horizon requires at least 36 azimuth bins");
  }
  const profile = new Float32Array(bins);
  profile.fill(Number.NEGATIVE_INFINITY);
  const columnAzimuth = (metadata.column_azimuth_deg * Math.PI) / 180;
  const rowAzimuth = (metadata.row_azimuth_deg * Math.PI) / 180;
  const observerY = mesh.centerYSceneUnits + observerHeightM / METRES_PER_SCENE_UNIT;

  for (let offset = 0; offset < mesh.positions.length; offset += 3) {
    const x = mesh.positions[offset];
    const y = mesh.positions[offset + 1] - observerY;
    const z = mesh.positions[offset + 2];
    const east = x * Math.sin(columnAzimuth) + z * Math.sin(rowAzimuth);
    const north = x * Math.cos(columnAzimuth) + z * Math.cos(rowAzimuth);
    const distance = Math.hypot(east, north);
    if (distance < 0.02) continue;
    const azimuth = ((Math.atan2(east, north) * 180) / Math.PI + 360) % 360;
    const bin = Math.round((azimuth / 360) * bins) % bins;
    const elevation = (Math.atan2(y, distance) * 180) / Math.PI;
    profile[bin] = Math.max(profile[bin], elevation);
  }

  for (let bin = 0; bin < bins; bin += 1) {
    if (Number.isFinite(profile[bin])) continue;
    for (let distance = 1; distance < bins; distance += 1) {
      const left = profile[(bin - distance + bins) % bins];
      const right = profile[(bin + distance) % bins];
      if (Number.isFinite(left) || Number.isFinite(right)) {
        profile[bin] = Number.isFinite(left) && Number.isFinite(right)
          ? (left + right) / 2
          : Number.isFinite(left)
            ? left
            : right;
        break;
      }
    }
  }
  return profile;
}

export function horizonAtAzimuth(profile: Float32Array, azimuthDeg: number): number {
  if (profile.length === 0) return Number.NaN;
  const wrapped = ((azimuthDeg % 360) + 360) % 360;
  const scaled = (wrapped / 360) * profile.length;
  const lower = Math.floor(scaled) % profile.length;
  const upper = (lower + 1) % profile.length;
  const fraction = scaled - Math.floor(scaled);
  return profile[lower] * (1 - fraction) + profile[upper] * fraction;
}
