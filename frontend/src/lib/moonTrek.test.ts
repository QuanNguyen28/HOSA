import { Vector3 } from 'three';
import { describe, expect, it } from 'vitest';
import manifest from '../../../manifests/lunarsight/moontrek_imagery.json';
import { globeBounds, POLAR_CAP, polarAtlas, polarCapCenter, polarRho, selectGlobeTiles, southPolarXY, tileUrl, type TrekCatalog, type TrekTile } from './moonTrek';

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

describe('globe tile selection',()=>{
  // The ground seen from ~200 km above 66°S with the app's 36° field of view: about ±3° of arc.
  const above=new Vector3(0.9,-2.05,0);
  const look=above.clone().normalize();
  const narrow=(center:Vector3,radius:number)=>Math.acos(Math.min(1,center.clone().normalize().dot(look)))
    <3*Math.PI/180+Math.asin(Math.min(1,radius/center.length()));
  const maxLevel=(tiles:TrekTile[])=>Math.max(...tiles.map(t=>t.level));
  it('refines only tiles in the camera frustum, down to fine levels close up',()=>{
    const tiles=selectGlobeTiles({position:above,focalPx:1323,maxLevel:8,inView:narrow,coveredBelowLat:POLAR_CAP.opaqueLat});
    expect(maxLevel(tiles)).toBeGreaterThanOrEqual(6);
    for(const tile of tiles.slice(2)) {
      const b=globeBounds(tile);
      expect(b.north).toBeGreaterThan(-90+5);
      expect(b.south).toBeLessThan(-40);
    }
  });
  it('never exceeds the tile budget',()=>{
    const tiles=selectGlobeTiles({position:above,focalPx:1323,maxLevel:8,inView:()=>true,budget:12});
    expect(tiles.length).toBeLessThanOrEqual(2+12);
  });
  it('does not refine a far globe beyond what the screen resolves',()=>{
    const tiles=selectGlobeTiles({position:new Vector3(0,0.35,6.4),focalPx:1323,maxLevel:8,inView:()=>true});
    expect(maxLevel(tiles)).toBeLessThanOrEqual(4);
  });
  it('leaves tiles inside the opaque polar cap to the cap',()=>{
    const below=new Vector3(0,-2.3,0);
    const tiles=selectGlobeTiles({position:below,focalPx:1323,maxLevel:8,inView:()=>true,coveredBelowLat:POLAR_CAP.opaqueLat});
    expect(tiles.slice(2).every(t=>globeBounds(t).north>POLAR_CAP.opaqueLat)).toBe(true);
  });
});

describe('south polar cap',()=>{
  it('centres the detail atlas under the camera and keeps it inside the cap',()=>{
    const [x,y]=polarCapCenter(new Vector3(0,-2.3,0));
    expect(Math.hypot(x,y)).toBeLessThan(1);
    const [ex,ey]=polarCapCenter(new Vector3(2.3,0,0));
    expect(Math.hypot(ex,ey)).toBeCloseTo(polarRho(POLAR_CAP.edgeLat),0);
  });
  it('builds the whole-cap and close-up atlases from bounded tile sets',()=>{
    const wac=layers.filter(l=>l.id==='wac-south');
    const base=polarAtlas(wac,0,0,polarRho(POLAR_CAP.edgeLat))!;
    expect(base.tiles.length).toBeLessThanOrEqual(16);
    const close=polarAtlas(wac,0,0,75_000,36)!;
    expect(close.tiles.length).toBeLessThanOrEqual(36);
    expect(close.matrix.level).toBe(wac[0].matrices.at(-1)!.level);
  });
});
