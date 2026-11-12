export const METRES_PER_SCENE_UNIT = 1_000;

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
  column_azimuth_deg: number;
  row_azimuth_deg: number;
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
