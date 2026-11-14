import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useFrame } from '@react-three/fiber';
import { BufferGeometry, CanvasTexture, DoubleSide, Float32BufferAttribute, SRGBColorSpace, ShaderChunk, Texture, Vector2, Vector3, Vector4 } from 'three';
import { coordinateToVector, MOON_SCENE_RADIUS } from '../lib/lunar';
import { terrainShadowFragment } from '../lib/terrainShadowShader';
import { meanLitLuminance, withGlobeDayNight, withTerrainLighting } from '../lib/moonShading';

import { globeBounds, polarAtlas, tileImage, tileUrl, trekCatalog, type TrekLayer, type TrekTile } from '../lib/moonTrek';
import type { TerrainWindow } from '../hooks/useTerrainWindow';

export type ImageryStatus = 'loading' | 'ready' | 'partial' | 'unavailable';

function globeGeometry(tile: TrekTile) {
  const bounds = globeBounds(tile), segments = 48;
  const positions: number[] = [], normals: number[] = [], uv: number[] = [], heightUv: number[] = [], indices: number[] = [];
  for (let y=0; y<=segments; y++) for (let x=0; x<=segments; x++) {
    const longitude = bounds.west+(bounds.east-bounds.west)*x/segments;
    const latitude = bounds.north+(bounds.south-bounds.north)*y/segments;
    const normal = coordinateToVector({latitude,longitude},1);
    positions.push(normal.x*MOON_SCENE_RADIUS, normal.y*MOON_SCENE_RADIUS, normal.z*MOON_SCENE_RADIUS);
    normals.push(normal.x,normal.y,normal.z);
    uv.push(x/segments,1-y/segments);
    // Same sphere UV/180-degree source alignment as the existing LOLA globe.
    heightUv.push((longitude+180)/360,(latitude+90)/180);
    if (x<segments && y<segments) {
      const a=y*(segments+1)+x, b=a+1, c=a+segments+1, d=c+1;
      indices.push(a,c,b,b,c,d);
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute('position',new Float32BufferAttribute(positions,3));
  geometry.setAttribute('normal',new Float32BufferAttribute(normals,3));
  geometry.setAttribute('uv',new Float32BufferAttribute(uv,2));
  geometry.setAttribute('uv1',new Float32BufferAttribute(heightUv,2));
  geometry.setIndex(indices);
  return geometry;
}

function GlobeTile({tile,heightMap,onState}: {tile:TrekTile;heightMap:Texture;onState:(tile:TrekTile,ok:boolean)=>void}) {
  const [texture,setTexture] = useState<Texture|null>(null);
  const key=`${tile.level}/${tile.row}/${tile.column}`;
  const geometry=useMemo(()=>globeGeometry(tile),[key]);
  useEffect(()=>()=>geometry.dispose(),[geometry]);
  useEffect(()=>{
    let cancelled=false, owned:Texture|null=null;
    tileImage(tileUrl('wac-global',tile)).then(image=>{
      if (cancelled) return;
      owned=new Texture(image); owned.colorSpace=SRGBColorSpace; owned.anisotropy=8; owned.needsUpdate=true;
      setTexture(owned); onState(tile,true);
    }).catch(()=>{ if (!cancelled) onState(tile,false); });
    return ()=>{cancelled=true;owned?.dispose();};
  },[key,onState]);
  if (!texture) return null;
  // Cesium day/night rule from the reference: the day side shows the photo as
  // recorded, the night side 30% of it (see lib/moonShading).
  return <mesh geometry={geometry} raycast={()=>{}}>
    <meshStandardMaterial color="#ffffff" map={texture} roughness={1} metalness={0} toneMapped={false}
      customProgramCacheKey={()=>'trek-globe-day-night-v1'}
      onBeforeCompile={shader=>{shader.fragmentShader=withGlobeDayNight(shader.fragmentShader);}}
      bumpMap={heightMap} bumpScale={0.004}
      displacementMap={heightMap} displacementScale={0.022906066536203522} displacementBias={-0.0105047772533671}
      polygonOffset polygonOffsetFactor={-1-tile.level} polygonOffsetUnits={-1-tile.level} />
  </mesh>;
}

export function MoonTrekGlobe({elevationMap,onBaseReady,onStatus}: {
  elevationMap:Texture;onBaseReady:()=>void;onStatus?:(status:ImageryStatus)=>void;
}) {
  const [tiles,setTiles]=useState<TrekTile[]>([{level:0,row:0,column:0},{level:0,row:0,column:1}]);
  const [layer,setLayer]=useState<TrekLayer|null>(null);
  const last=useRef({time:-1,position:new Vector3(Infinity,Infinity,Infinity)});
  const roots=useRef(new Set<number>()), failed=useRef(false);
  const heightMap=useMemo(()=>{const map=elevationMap.clone();map.channel=1;map.needsUpdate=true;return map;},[elevationMap]);
  useEffect(()=>()=>heightMap.dispose(),[heightMap]);
  useEffect(()=>{
    let cancelled=false;
    onStatus?.('loading');
    trekCatalog().then(c=>{if(!cancelled)setLayer(c.layers.find(l=>l.id==='wac-global')??null);})
      .catch(()=>{if(!cancelled)onStatus?.('unavailable');});
    return ()=>{cancelled=true;};
  },[onStatus]);
  const onState=useCallback((tile:TrekTile,ok:boolean)=>{
    if(!ok)failed.current=true;
    if(ok && tile.level===0)roots.current.add(tile.column);
    if(roots.current.size===2) {onBaseReady();onStatus?.(failed.current?'partial':'ready');}
    else if(!ok) onStatus?.('partial');
  },[onBaseReady,onStatus]);
  useFrame(({camera,clock,size})=>{
    if(!layer || clock.elapsedTime-last.current.time<.4 || camera.position.distanceTo(last.current.position)<.025) return;
    last.current={time:clock.elapsedTime,position:camera.position.clone()};
    const visible:TrekTile[]=[{level:0,row:0,column:0},{level:0,row:0,column:1}];
    const direction=camera.position.clone().normalize(), distance=camera.position.length();
    const focal=size.height/(2*Math.tan(36*Math.PI/360));
    const max=layer.matrices[layer.matrices.length-1].level;
    const descend=(tile:TrekTile)=>{
      const b=globeBounds(tile), lat=(b.north+b.south)/2, lon=(b.west+b.east)/2;
      const normal=coordinateToVector({latitude:lat,longitude:lon},1);
      const angle=Math.min(Math.PI/2, Math.hypot(b.north-b.south,(b.east-b.west)*Math.cos(lat*Math.PI/180))*Math.PI/360);
      if(normal.dot(direction)<MOON_SCENE_RADIUS/distance-Math.sin(angle)-.05) return;
      const pixels=2*angle*MOON_SCENE_RADIUS*focal/Math.max(.02,camera.position.distanceTo(normal.clone().multiplyScalar(MOON_SCENE_RADIUS)));
      if(pixels<300 || tile.level>=max || visible.length>90) return;
      const children=[0,1,2,3].map(i=>({level:tile.level+1,row:tile.row*2+Math.floor(i/2),column:tile.column*2+i%2}));
      for(const child of children) {visible.push(child);descend(child);}
    };
    descend(visible[0]);descend(visible[1]);
    setTiles(old=>JSON.stringify(old)===JSON.stringify(visible)?old:visible);
  });
  return <group>{tiles.map(tile=><GlobeTile key={`${tile.level}/${tile.row}/${tile.column}`} tile={tile} heightMap={heightMap} onState={onState}/>)}</group>;
}

export function MoonTrekTerrainMaterial({terrain,fallback,onStatus}: {
  terrain:TerrainWindow;fallback:ReactNode;onStatus?:(status:ImageryStatus)=>void;
}) {
  const [atlas,setAtlas]=useState<{texture:CanvasTexture;bounds:[number,number,number,number];mean:number}|null>(null);
  const x=terrain.geometry?.center_x_m, y=terrain.geometry?.center_y_m, radius=(terrain.radius_km??1.5)*1000;
  useEffect(()=>{
    let cancelled=false, owned:CanvasTexture|null=null;
    setAtlas(null);onStatus?.('loading');
    if(x==null || y==null || terrain.geometry?.projection!=='spherical south polar stereographic') {
      onStatus?.('unavailable');return;
    }
    trekCatalog().then(async catalog=>{
      const plan=polarAtlas(catalog.layers,x,y,radius);
      if(!plan)throw new Error('No imagery coverage');
      const images=await Promise.all(plan.tiles.map(tile=>tileImage(tileUrl(plan.layer.id,tile))));
      if(cancelled)return;
      const canvas=document.createElement('canvas'), size=plan.matrix.tile_size;
      canvas.width=plan.columns*size;canvas.height=plan.rows*size;
      const context=canvas.getContext('2d');if(!context)throw new Error('Canvas unavailable');
      images.forEach((image,i)=>context.drawImage(image,(plan.tiles[i].column-plan.firstColumn)*size,(plan.tiles[i].row-plan.firstRow)*size));
      owned=new CanvasTexture(canvas);owned.colorSpace=SRGBColorSpace;owned.anisotropy=8;
      const mean=meanLitLuminance(context.getImageData(0,0,canvas.width,canvas.height).data);
      setAtlas({texture:owned,bounds:plan.bounds,mean});onStatus?.('ready');
    }).catch(()=>{if(!cancelled)onStatus?.('unavailable');});
    return ()=>{cancelled=true;owned?.dispose();};
  },[x,y,radius,terrain.geometry?.projection,onStatus]);
  if(!atlas)return <>{fallback}</>;
  // Reference terrain light (see lib/moonShading): the DEM normals, the
  // mission-time Sun with terrain shadows and earthshine set the brightness;
  // the photo only varies the reference albedo, so its recorded shadows do
  // not compete with the simulated ones.
  return <meshStandardMaterial key={atlas.texture.uuid} map={atlas.texture} color="#ffffff"
    roughness={0.98} metalness={0} shadowSide={DoubleSide} toneMapped={false}
    customProgramCacheKey={()=>`trek-terrain-reference-v1-${atlas.mean.toFixed(3)}`} onBeforeCompile={shader=>{
    const b=atlas.bounds;
    shader.uniforms.trekBounds={value:new Vector4(b[0],b[1],b[2]-b[0],b[3]-b[1])};
    shader.uniforms.trekOrigin={value:new Vector2(x,y)};
    shader.vertexShader='uniform vec4 trekBounds;\nuniform vec2 trekOrigin;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <uv_vertex>',`#include <uv_vertex>
      vMapUv = (vec2(trekOrigin.x + position.x * 1000.0, trekOrigin.y - position.z * 1000.0) - trekBounds.xy) / trekBounds.zw;`);
    shader.fragmentShader=withTerrainLighting(terrainShadowFragment(shader.fragmentShader),ShaderChunk.lights_fragment_begin,atlas.mean);
  }}/>;
}
