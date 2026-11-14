import { describe, expect, it, vi } from 'vitest';
import { instantTime, startInstantReader, type InstantQuery } from './instantReader';
import { DEFAULT_MISSION, EXAMPLES, missionRequest, type Interval } from './contracts';

const row: Interval = {start_utc:'2026-11-24T00:00:00Z',end_utc:'2026-11-24T00:05:00Z',sun_state:'V',earth_state:'B',joint_state:'B'};
const request=missionRequest(DEFAULT_MISSION,EXAMPLES[0]);
describe('current visibility reads before Analyze', () => {
  it('clamps the first sample inside the mission and keeps refined minute resolution', () => {
    const start='2026-11-24T07:02:00Z';
    expect(instantTime(Date.parse(start),start,false)).toBe(Date.parse(start));
    expect(instantTime(Date.parse('2026-11-24T07:04:00Z'),start,false)).toBe(Date.parse(start));
    expect(instantTime(Date.parse('2026-11-24T07:04:00Z'),start,true)).toBe(Date.parse('2026-11-24T07:04:00Z'));
  });
  it('keeps reading while Play moves the cursor faster than the old debounce', async () => {
    vi.useFakeTimers();
    let cursor=0;
    const load=vi.fn(async()=>row), publish=vi.fn();
    const stop=startInstantReader(()=>({key:String(cursor),at:cursor,request}),load,publish,vi.fn());
    try {
      for(let i=0;i<40;i++) {cursor=i*60000;await vi.advanceTimersByTimeAsync(10);}
      expect(load.mock.calls.length).toBeGreaterThanOrEqual(3);
      expect(publish.mock.calls.at(-1)![0].at).toBeGreaterThan(0);
    } finally {stop();vi.useRealTimers();}
  });
  it('aborts on observer changes and never publishes a late response', async () => {
    vi.useFakeTimers();
    let finish!: (row:Interval)=>void;
    let signal!:AbortSignal;
    const publish=vi.fn();
    const stop=startInstantReader(()=>({key:'old',at:0,request}),(_query,nextSignal)=>{
      signal=nextSignal;return new Promise(resolve=>{finish=resolve;});
    },publish,vi.fn());
    try {
      await vi.advanceTimersByTimeAsync(1);stop();finish(row);await Promise.resolve();
      expect(signal.aborted).toBe(true);expect(publish).not.toHaveBeenCalled();
    } finally {stop();vi.useRealTimers();}
  });
  it('reports missing evidence and backs off instead of retrying every frame', async () => {
    vi.useFakeTimers();
    const load=vi.fn(async(_query:InstantQuery)=>{throw new Error('INSTANT_NOT_PREPARED');}), fail=vi.fn();
    const stop=startInstantReader(()=>({key:'point',at:0,request}),load,vi.fn(),fail);
    try {
      await vi.advanceTimersByTimeAsync(500);
      expect(fail).toHaveBeenCalledOnce();expect(load).toHaveBeenCalledOnce();
    } finally {stop();vi.useRealTimers();}
  });
});
