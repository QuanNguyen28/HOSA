import { describe, expect, it } from 'vitest';
import manifest from '../../../manifests/lunarsight/moontrek_imagery.json';
import { globeBounds, polarAtlas, southPolarXY, tileUrl, type TrekCatalog } from './moonTrek';

const layers=(manifest as unknown as TrekCatalog).layers;

describe('NASA display coordinate alignment',()=>{
  it('uses lunar south-polar stereographic axes, including the antimeridian',()=>{
    expect(southPolarXY(-90,0)).toEqual([0,0]);
    const [x,y]=southPolarXY(-89.43892646479243,222.90402192622227);
    expect(x).toBeCloseTo(-11582.5,3);
    expect(y).toBeCloseTo(-12462.5,3);
    const wrapped=southPolarXY(-89.43892646479243,-137.09597807377773);
    expect(wrapped[0]).toBeCloseTo(x,6);expect(wrapped[1]).toBeCloseTo(y,6);
  });
  it('places the two global roots on opposite longitude hemispheres without swapping north and south',()=>{
    expect(globeBounds({level:0,row:0,column:0})).toEqual({west:-180,east:0,north:90,south:-90});
    expect(globeBounds({level:0,row:0,column:1})).toEqual({west:0,east:180,north:90,south:-90});
    expect(globeBounds({level:1,row:1,column:2})).toEqual({west:0,east:90,north:0,south:-90});
  });
  it('uses NAC only inside source coverage and keeps atlas requests bounded',()=>{
    const plan=polarAtlas(layers,-11582.5,-12462.5,1500)!;
    expect(plan.layer.id).toBe('nac-south');expect(plan.tiles.length).toBeLessThanOrEqual(16);
    expect(plan.bounds[0]).toBeLessThanOrEqual(-13082.5);expect(plan.bounds[2]).toBeGreaterThanOrEqual(-10082.5);
    expect(plan.bounds[1]).toBeLessThanOrEqual(-13962.5);expect(plan.bounds[3]).toBeGreaterThanOrEqual(-10962.5);
    expect(polarAtlas(layers,-11582.5,-12462.5,300000)!.layer.id).toBe('wac-south');
    expect(polarAtlas(layers,2e6,2e6,1500)).toBeNull();
  });
  it('fetches through the local proxy, without exposing configurable remote URLs',()=>{
    expect(tileUrl('nac-south',{level:10,row:512,column:511})).toBe('/api/lunar/imagery/nac-south/10/512/511');
  });
});
