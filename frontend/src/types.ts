export type LunarCoordinate = {
  latitude: number;
  longitude: number;
};

export type Site = LunarCoordinate & {
  id: string;
  name: string;
  elevationM: number;
  status: "verified" | "provisional";
};

export type CameraPreset = "orbit" | "south-pole" | "surface";

export type LayerState = {
  labels: boolean;
  grid: boolean;
  sites: boolean;
  enhancedLight: boolean;
};
