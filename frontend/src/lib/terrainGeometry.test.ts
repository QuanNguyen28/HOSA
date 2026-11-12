import { describe, expect, it } from "vitest";

import {
  buildTerrainMeshData,
  type TerrainGeometryMetadata,
  type TerrainGrid,
} from "./terrainGeometry";

const metadata: TerrainGeometryMetadata = {
  horizontal_scale: 1,
  vertical_scale: 1,
  horizontal_unit: "metre",
  vertical_unit: "metre",
  lunar_reference_radius_m: 1_737_400,
  center_elevation_m: 100,
  column_azimuth_deg: 90,
  row_azimuth_deg: 180,
  surface_model: "test",
};

const grid: TerrainGrid = {
  rows: 3,
  columns: 3,
  elevation_m_row_major: [100, 100, 100, 100, 100, 200, 100, 100, 100],
  min_elevation_m: 100,
  max_elevation_m: 200,
  valid_fraction: 1,
  spacing_m: 1_000,
};

describe("scientific terrain mesh", () => {
  it("keeps horizontal and vertical dimensions in the same physical scale", () => {
    const mesh = buildTerrainMeshData(grid, metadata);
    const centerOffset = (1 * grid.columns + 1) * 3;
    const eastOffset = (1 * grid.columns + 2) * 3;

    expect(mesh.positions[eastOffset] - mesh.positions[centerOffset]).toBeCloseTo(1, 8);
    expect(mesh.positions[eastOffset + 1]).toBeGreaterThan(0.099);
    expect(mesh.positions[eastOffset + 1]).toBeLessThan(0.1);
  });

  it("curves a flat DEM away from the tangent point", () => {
    const flat = { ...grid, elevation_m_row_major: Array(9).fill(100) };
    const mesh = buildTerrainMeshData(flat, metadata);
    const centerY = mesh.positions[(1 * 3 + 1) * 3 + 1];
    const cornerY = mesh.positions[1];

    expect(centerY).toBeCloseTo(0, 8);
    expect(cornerY).toBeLessThan(0);
  });

  it("builds two triangles for every valid grid cell", () => {
    const mesh = buildTerrainMeshData(grid, metadata);
    expect(mesh.indices).toHaveLength(4 * 2 * 3);
  });
});
