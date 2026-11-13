import { useEffect, useState } from "react";
import { api } from "../mvp/api";
import type { MissionRequest } from "../mvp/contracts";
import { responseCache } from "../lib/responseCache";
import { compactTrack, type CompactTrack, type HorizonData, type TrackChunk } from "../lib/horizonView";
import { loadHorizonProfile } from "../lib/horizonPreload";

const profiles = responseCache<HorizonData>(24);
const EMPTY_TRACK = {chunks: [] as CompactTrack[], total: 0, error: undefined};
const keyForProfile = (request?: MissionRequest) => request ? JSON.stringify([
  request.latitude_deg, request.longitude_e_deg, request.panel_height_m, request.antenna_height_m]) : "";

export function useHorizonProfile(request?: MissionRequest, analysisRevision?: string) {
  const profileKey = keyForProfile(request);
  const [profile, setProfile] = useState<{key: string; data?: HorizonData; error?: string}>({key: ""});
  useEffect(() => {
    if (!request) return;
    let active = true;
    // Avoid queuing a terrain scan for every digit while coordinates are typed.
    const timer = setTimeout(() => {
      void profiles(profileKey, () => loadHorizonProfile(request))
        .then(data => { if (active) setProfile({key: profileKey, data}); })
        .catch((error: Error) => { if (active) setProfile({key: profileKey, error: error.message}); });
    }, 350);
    return () => { active = false; clearTimeout(timer); };
  }, [profileKey, analysisRevision]);
  return {profile: profile.key === profileKey ? profile.data : undefined,
    profileError: profile.key === profileKey ? profile.error : undefined};
}

export function useHorizonView(request?: MissionRequest, analysisRevision?: string) {
  const profileKey = keyForProfile(request);
  const trackKey = request ? JSON.stringify([profileKey, request.start_utc, request.end_utc]) : "";
  const profile = useHorizonProfile(request, analysisRevision);
  const [track, setTrack] = useState<{key: string; chunks: CompactTrack[]; total: number; error?: string}>({key: "", chunks: [], total: 0});
  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    setTrack({key: trackKey, chunks: [], total: 0});
    const run = async () => {
      const first = await api<TrackChunk>("/lunar/point/sky-track?chunk_index=0", controller.signal, request);
      if (controller.signal.aborted) return;
      setTrack({key: trackKey, chunks: [compactTrack(first)], total: first.chunk_count});
      let next = 1;
      const worker = async () => {
        while (!controller.signal.aborted && next < first.chunk_count) {
          const index = next++;
          const chunk = await api<TrackChunk>(`/lunar/point/sky-track?chunk_index=${index}`, controller.signal, request);
          if (!controller.signal.aborted) setTrack(current => current.key === trackKey
            ? {...current, chunks: [...current.chunks, compactTrack(chunk)]} : current);
        }
      };
      await Promise.all([worker(), worker()]);
    };
    void run().catch((error: Error) => { if (!controller.signal.aborted) setTrack(current => ({...current, key: trackKey, error: error.message})); });
    return () => controller.abort();
  }, [trackKey]);
  return { ...profile,
    track: track.key === trackKey ? track : EMPTY_TRACK };
}
