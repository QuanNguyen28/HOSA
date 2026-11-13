import { api } from "../mvp/api";
import type { MissionRequest } from "../mvp/contracts";
import type { HorizonData } from "./horizonView";

export type HorizonPreparation = {status: "ready"; profile: HorizonData}
  | {status: "preparing"; stage: string; retry_after_ms: number};

/** A coordinate/hardware job survives view changes; time/requirements do not affect its horizon. */
export async function loadHorizonProfile(request: MissionRequest,
  call = (body: MissionRequest) => api<HorizonPreparation>("/lunar/point/horizon-profile/preload", undefined, body),
  pause = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms)),
): Promise<HorizonData> {
  for (let attempt = 0; attempt < 480; attempt++) {
    try {
      const state = await call(request);
      if (state.status === "ready") return state.profile;
      await pause(Math.min(2000, Math.max(250, state.retry_after_ms)));
    } catch (error) {
      if (!(error instanceof Error) || error.message !== "HORIZON_PREPARATION_BUSY") throw error;
      await pause(1500);
    }
  }
  throw new Error("Horizon preparation is taking longer than expected. Select this point again to check progress.");
}
