import type { HorizonVisibility } from '../lib/horizonView';

export function HorizonMarker({ x, y, radius = 5, colour, state }: {
  x: number; y: number; radius?: number; colour: string; state: HorizonVisibility;
}) {
  return <circle cx={x} cy={y} r={radius} data-visibility={state}
    fill={state === 'visible' ? colour : 'none'} stroke={colour} strokeWidth={1.8}
    strokeDasharray={state === 'hidden' ? '3 2' : state === 'unknown' ? '1 3' : undefined}
    opacity={state === 'unknown' ? .55 : 1}/>;
}
