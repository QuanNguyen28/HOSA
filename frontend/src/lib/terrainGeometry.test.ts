import { describe, expect, it } from "vitest";

import {
  buildTerrainHorizonProfile,
  buildTerrainMeshData,
  buildSouthPolarCapMeshData,
  horizonAtAzimuth,
  skyDirectionToTerrainAxes,
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

  it("places celestial directions in the DEM local axes", () => {
    const east = skyDirectionToTerrainAxes(90, 0, metadata);
    const zenith = skyDirectionToTerrainAxes(15, 90, metadata);

    expect(east.x).toBeCloseTo(1, 8);
    expect(east.y).toBeCloseTo(0, 8);
    expect(east.z).toBeCloseTo(0, 8);
    expect(zenith.y).toBeCloseTo(1, 8);
  });

  it("derives a local horizon from actual terrain vertices", () => {
    const mesh = buildTerrainMeshData(grid, metadata);
    const profile = buildTerrainHorizonProfile(mesh, metadata, 0, 360);

    expect(horizonAtAzimuth(profile, 90)).toBeGreaterThan(5);
    expect(Number.isFinite(horizonAtAzimuth(profile, 270))).toBe(true);
  });

  it("wraps projected south-polar DEM samples onto the lunar reference sphere", () => {
    const cap = buildSouthPolarCapMeshData(
      {
        rows: 5,
        columns: 5,
        elevation_m_row_major: Array(25).fill(0),
      },
      [-304_000, -304_000, 304_000, 304_000],
      2,
    );
    const centre = (2 * 5 + 2) * 3;
    expect(cap.positions[centre]).toBeCloseTo(0, 8);
    expect(cap.positions[centre + 1]).toBeLessThan(-2);
    expect(cap.positions[centre + 2]).toBeCloseTo(0, 8);
    expect(cap.indices.length).toBeGreaterThan(0);
    expect(cap.indices.length).toBeLessThan(16 * 2 * 3);
    expect(cap.uvs).toHaveLength(25 * 2);
  });
});
