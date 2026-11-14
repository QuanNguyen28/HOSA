import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useFrame } from '@react-three/fiber';
import { BufferGeometry, CanvasTexture, DoubleSide, Float32BufferAttribute, Frustum, Matrix4, PerspectiveCamera, Quaternion, SRGBColorSpace, ShaderChunk, Sphere, Texture, Vector2, Vector3, Vector4 } from 'three';
import { coordinateToVector, MOON_SCENE_RADIUS } from '../lib/lunar';
import { terrainShadowFragment } from '../lib/terrainShadowShader';
import { withGlobeDayNight, withTerrainDayNight } from '../lib/moonShading';
import { withRingFade } from '../lib/terrainSeams';


import { globeBounds, POLAR_CAP, polarAtlas, polarCapCenter, polarRho, selectGlobeTiles, southPolarXY, tileImage, tileUrl, trekCatalog, type AtlasPlan, type TrekLayer, type TrekTile } from '../lib/moonTrek';
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

const CAP_RHO = polarRho(POLAR_CAP.edgeLat), CAP_OPAQUE_RHO = polarRho(POLAR_CAP.opaqueLat);

function capDiscard(shader:{vertexShader:string;fragmentShader:string}) {
  shader.vertexShader='varying float vGlobeLatUv;\n'+shader.vertexShader.replace('#include <uv_vertex>',`#include <uv_vertex>
    vGlobeLatUv = uv1.y;`);
  shader.fragmentShader='varying float vGlobeLatUv;\n'+shader.fragmentShader.replace('#include <clipping_planes_fragment>',`#include <clipping_planes_fragment>
    if (vGlobeLatUv < ${((POLAR_CAP.opaqueLat+90)/180).toFixed(6)}) discard;`);
}

/** Draw a polar-stereographic atlas (≤ maxTiles tiles) into one texture. */
async function loadPolarAtlas(plan:AtlasPlan) {
  const images=await Promise.all(plan.tiles.map(tile=>tileImage(tileUrl(plan.layer.id,tile))));
  const canvas=document.createElement('canvas'), size=plan.matrix.tile_size;
  canvas.width=plan.columns*size;canvas.height=plan.rows*size;
  const context=canvas.getContext('2d');if(!context)throw new Error('Canvas unavailable');
  images.forEach((image,i)=>context.drawImage(image,(plan.tiles[i].column-plan.firstColumn)*size,(plan.tiles[i].row-plan.firstRow)*size));
  const texture=new CanvasTexture(canvas);texture.colorSpace=SRGBColorSpace;texture.anisotropy=8;
  return {texture,bounds:plan.bounds};
}
type PolarAtlas = Awaited<ReturnType<typeof loadPolarAtlas>>;

/** South polar cap mesh: sphere cells to POLAR_CAP.edgeLat with stereographic coordinates for the atlas. */
function polarCapGeometry() {
  const rings=120, segments=360;
  const positions:number[]=[], normals:number[]=[], uv:number[]=[], heightUv:number[]=[], polar:number[]=[], indices:number[]=[];
  for (let r=0; r<=rings; r++) for (let k=0; k<=segments; k++) {
    const latitude=-90+(POLAR_CAP.edgeLat+90)*r/rings, longitude=-180+360*k/segments;
    const normal=coordinateToVector({latitude,longitude},1);
    positions.push(normal.x*MOON_SCENE_RADIUS,normal.y*MOON_SCENE_RADIUS,normal.z*MOON_SCENE_RADIUS);
    normals.push(normal.x,normal.y,normal.z);
    uv.push(0,0);
    heightUv.push((longitude+180)/360,(latitude+90)/180);
    polar.push(...southPolarXY(latitude,longitude));
    if (r<rings && k<segments) {
      const a=r*(segments+1)+k, b=a+1, c=a+segments+1, d=c+1;
      indices.push(a,b,c,b,d,c);
    }
  }
  const geometry=new BufferGeometry();
  geometry.setAttribute('position',new Float32BufferAttribute(positions,3));
  geometry.setAttribute('normal',new Float32BufferAttribute(normals,3));
  geometry.setAttribute('uv',new Float32BufferAttribute(uv,2));
  geometry.setAttribute('uv1',new Float32BufferAttribute(heightUv,2));
  geometry.setAttribute('polarXY',new Float32BufferAttribute(polar,2));
  geometry.setIndex(indices);
  return geometry;
}

function PolarCapLayer({geometry,atlas,heightMap,detail}: {geometry:BufferGeometry;atlas:PolarAtlas;heightMap:Texture;detail:boolean}) {
  const b=atlas.bounds;
  return <mesh geometry={geometry} raycast={()=>{}}>
    <meshStandardMaterial key={atlas.texture.uuid} color="#ffffff" map={atlas.texture} roughness={1} metalness={0} toneMapped={false}
      bumpMap={heightMap} bumpScale={0.004}
      displacementMap={heightMap} displacementScale={0.022906066536203522} displacementBias={-0.0105047772533671}
      polygonOffset polygonOffsetFactor={detail?-24:-20} polygonOffsetUnits={detail?-24:-20}
      customProgramCacheKey={()=>`polar-cap-v1-${detail}`}
      onBeforeCompile={shader=>{
        shader.uniforms.trekBounds={value:new Vector4(b[0],b[1],b[2]-b[0],b[3]-b[1])};
        shader.vertexShader='attribute vec2 polarXY;\nuniform vec4 trekBounds;\nvarying float vCapRho;\n'+shader.vertexShader.replace('#include <uv_vertex>',`#include <uv_vertex>
          vMapUv = (polarXY - trekBounds.xy) / trekBounds.zw;
          vCapRho = length(polarXY);`);
        shader.fragmentShader='varying float vCapRho;\n'+withGlobeDayNight(shader.fragmentShader).replace('#include <clipping_planes_fragment>',`#include <clipping_planes_fragment>
          ${detail?'if (any(lessThan(vMapUv, vec2(0.001))) || any(greaterThan(vMapUv, vec2(0.999)))) discard;':''}
          // Dithered fade into the global mosaic over the cap's outer band.
          float capFade = 1.0 - smoothstep(${CAP_OPAQUE_RHO.toFixed(1)}, ${CAP_RHO.toFixed(1)}, vCapRho);
          float capNoise = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
          if (capFade < capNoise) discard;`);
      }} />
  </mesh>;
}

/**
 * The equirectangular global mosaic converges at the pole (a level-7 polar
 * row alone is 256 wedge tiles), so close views of the south pole drew coarse
 * faceted tiles. The cap draws the polar-stereographic WAC mosaic instead: a
 * whole-cap atlas plus a detail atlas around the point under the camera.
 */
function PolarCap({layer,heightMap,onReady}: {layer:TrekLayer;heightMap:Texture;onReady:()=>void}) {
  const geometry=useMemo(polarCapGeometry,[]);
  useEffect(()=>()=>geometry.dispose(),[geometry]);
  const [base,setBase]=useState<PolarAtlas|null>(null);
  const [detail,setDetail]=useState<PolarAtlas|null>(null);
  const wanted=useRef(''), last=useRef({time:-1,position:new Vector3(Infinity,Infinity,Infinity)});
  useEffect(()=>{
    let cancelled=false, owned:CanvasTexture|null=null;
    const plan=polarAtlas([layer],0,0,CAP_RHO);
    if(plan) loadPolarAtlas(plan).then(atlas=>{
      if(cancelled){atlas.texture.dispose();return;}
      owned=atlas.texture;setBase(atlas);onReady();
    }).catch(()=>{});
    return ()=>{cancelled=true;owned?.dispose();};
  },[layer,onReady]);
  useEffect(()=>()=>{detail?.texture.dispose();},[detail]);
  useFrame(({camera,clock,size})=>{
    if(clock.elapsedTime-last.current.time<.4 || camera.position.distanceTo(last.current.position)<.01) return;
    last.current={time:clock.elapsedTime,position:camera.position.clone()};
    // Ground half-width seen at nadir (the globe controls always look at the centre).
    const fov=(camera as PerspectiveCamera).fov ?? 36;
    const altitudeM=(camera.position.length()-MOON_SCENE_RADIUS)*1_737_400/MOON_SCENE_RADIUS;
    const radius=Math.max(20_000,altitudeM*Math.tan(fov*Math.PI/360)*(size.width/Math.max(1,size.height))*1.1);
    if(radius>CAP_RHO*.7){wanted.current='';setDetail(null);return;}
    const [x,y]=polarCapCenter(camera.position);
    const plan=polarAtlas([layer],x,y,radius,36);
    if(!plan)return;
    const key=`${plan.matrix.level}/${plan.firstRow}/${plan.firstColumn}/${plan.rows}/${plan.columns}`;
    if(key===wanted.current)return;
    wanted.current=key;
    loadPolarAtlas(plan).then(atlas=>{
      if(wanted.current!==key){atlas.texture.dispose();return;}
      setDetail(atlas);
    }).catch(()=>{});
  });
  return <group>
    {base && <PolarCapLayer geometry={geometry} atlas={base} heightMap={heightMap} detail={false}/>}
    {base && detail && <PolarCapLayer geometry={geometry} atlas={detail} heightMap={heightMap} detail/>}
  </group>;
}

function GlobeTile({tile,heightMap,onState,capped}: {tile:TrekTile;heightMap:Texture;onState:(tile:TrekTile,ok:boolean)=>void;capped:boolean}) {
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
    <meshStandardMaterial key={String(capped)} color="#ffffff" map={texture} roughness={1} metalness={0} toneMapped={false}
      customProgramCacheKey={()=>`trek-globe-day-night-v2-${capped}`}
      onBeforeCompile={shader=>{
        shader.fragmentShader=withGlobeDayNight(shader.fragmentShader);
        // Inside the opaque polar cap only the cap draws, so no coarse tile
        // can poke through it.
        if(capped) capDiscard(shader);
      }}
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
  const [polarLayer,setPolarLayer]=useState<TrekLayer|null>(null);
  const [capReady,setCapReady]=useState(false);
  const markCapReady=useCallback(()=>setCapReady(true),[]);
  const last=useRef({time:-1,position:new Vector3(Infinity,Infinity,Infinity),quaternion:new Quaternion()});
  const roots=useRef(new Set<number>()), failed=useRef(false);
  const heightMap=useMemo(()=>{const map=elevationMap.clone();map.channel=1;map.needsUpdate=true;return map;},[elevationMap]);
  useEffect(()=>()=>heightMap.dispose(),[heightMap]);
  useEffect(()=>{
    let cancelled=false;
    onStatus?.('loading');
    trekCatalog().then(c=>{if(!cancelled){setLayer(c.layers.find(l=>l.id==='wac-global')??null);setPolarLayer(c.layers.find(l=>l.id==='wac-south')??null);}})
      .catch(()=>{if(!cancelled)onStatus?.('unavailable');});
    return ()=>{cancelled=true;};
  },[onStatus]);
  const onState=useCallback((tile:TrekTile,ok:boolean)=>{
    if(!ok)failed.current=true;
    if(ok && tile.level===0)roots.current.add(tile.column);
    if(roots.current.size===2) {onBaseReady();onStatus?.(failed.current?'partial':'ready');}
    else if(!ok) onStatus?.('partial');
  },[onBaseReady,onStatus]);
  const view=useMemo(()=>({frustum:new Frustum(),matrix:new Matrix4(),sphere:new Sphere()}),[]);
  useFrame(({camera,clock,size})=>{
    // Re-plan after a move or a turn of the view, at most every 0.4 s.
    if(!layer || clock.elapsedTime-last.current.time<.4 || (camera.position.distanceTo(last.current.position)<.025
      && camera.quaternion.angleTo(last.current.quaternion)<.02)) return;
    last.current={time:clock.elapsedTime,position:camera.position.clone(),quaternion:camera.quaternion.clone()};
    camera.updateMatrixWorld();
    view.frustum.setFromProjectionMatrix(view.matrix.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse));
    const visible=selectGlobeTiles({
      position:camera.position,
      focalPx:size.height/(2*Math.tan(((camera as PerspectiveCamera).fov ?? 36)*Math.PI/360)),
      maxLevel:layer.matrices[layer.matrices.length-1].level,
      inView:(center,radius)=>view.frustum.intersectsSphere(view.sphere.set(center,radius)),
      coveredBelowLat:capReady?POLAR_CAP.opaqueLat:undefined,
    });
    setTiles(old=>JSON.stringify(old)===JSON.stringify(visible)?old:visible);
  });
  return <group>
    {tiles.map(tile=><GlobeTile key={`${tile.level}/${tile.row}/${tile.column}`} tile={tile} heightMap={heightMap} onState={onState} capped={capReady}/>)}
    {polarLayer && <PolarCap layer={polarLayer} heightMap={heightMap} onReady={markCapReady}/>}
  </group>;
}

export function MoonTrekTerrainMaterial({terrain,fallback,onStatus,fade,offset}: {
  terrain:TerrainWindow;fallback:ReactNode;onStatus?:(status:ImageryStatus)=>void;color?:string;
  /** Fade band and polygon offset of a nested terrain ring (see terrainSeams). */
  fade?:[number,number];offset?:number;
}) {
  const [atlas,setAtlas]=useState<{photo:PolarAtlas;fill:PolarAtlas|null}|null>(null);
  const x=terrain.geometry?.center_x_m, y=terrain.geometry?.center_y_m, radius=(terrain.radius_km??1.5)*1000;
  useEffect(()=>{
    let cancelled=false;
    const owned:CanvasTexture[]=[];
    setAtlas(null);onStatus?.('loading');
    if(x==null || y==null || terrain.geometry?.projection!=='spherical south polar stereographic') {
      onStatus?.('unavailable');return;
    }
    trekCatalog().then(async catalog=>{
      const plan=polarAtlas(catalog.layers,x,y,radius);
      if(!plan)throw new Error('No imagery coverage');
      // Near the pole the NAC mosaic was largely imaged in shadow, so its dark
      // pixels are filled from the illumination-composite WAC mosaic.
      const fillPlan=plan.layer.id==='nac-south' ? polarAtlas(catalog.layers.filter(l=>l.id==='wac-south'),x,y,radius) : null;
      const [photo,fill]=await Promise.all([loadPolarAtlas(plan), fillPlan ? loadPolarAtlas(fillPlan).catch(()=>null) : null]);
      for(const item of [photo,fill]) if(item) owned.push(item.texture);
      if(cancelled)return;
      setAtlas({photo,fill});onStatus?.('ready');
    }).catch(()=>{if(!cancelled)onStatus?.('unavailable');});
    return ()=>{cancelled=true;owned.forEach(texture=>texture.dispose());};
  },[x,y,radius,terrain.geometry?.projection,onStatus]);
  if(!atlas)return <>{fallback}</>;
  // Moon view's day/night look (see lib/moonShading): the photo with its own
  // contrast, sunlit ground as recorded and ground in the simulated shadow at
  // 30%.
  const {photo,fill}=atlas;
  return <meshStandardMaterial key={photo.texture.uuid} map={photo.texture} color="#ffffff" toneMapped={false}
    roughness={0.98} metalness={0} shadowSide={DoubleSide}
    transparent={fade!==undefined} polygonOffset={offset!==undefined} polygonOffsetFactor={offset??0} polygonOffsetUnits={offset??0}
    customProgramCacheKey={()=>`trek-terrain-day-night-ring-fade-${fill?'fill':'single'}`} onBeforeCompile={shader=>{
    const b=photo.bounds, f=fill?.bounds ?? b;
    shader.uniforms.trekBounds={value:new Vector4(b[0],b[1],b[2]-b[0],b[3]-b[1])};
    shader.uniforms.fillBounds={value:new Vector4(f[0],f[1],f[2]-f[0],f[3]-f[1])};
    shader.uniforms.fillMap={value:fill?.texture ?? photo.texture};
    shader.uniforms.trekOrigin={value:new Vector2(x,y)};
    shader.uniforms.ringFade={value:new Vector2(fade?.[0]??0,fade?.[1]??0)};
    withRingFade(shader);
    shader.vertexShader='uniform vec4 trekBounds;\nuniform vec4 fillBounds;\nuniform vec2 trekOrigin;\nvarying vec2 vFillUv;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <uv_vertex>',`#include <uv_vertex>
      vec2 trekXY = vec2(trekOrigin.x + position.x * 1000.0, trekOrigin.y - position.z * 1000.0);
      vMapUv = (trekXY - trekBounds.xy) / trekBounds.zw;
      vFillUv = (trekXY - fillBounds.xy) / fillBounds.zw;`);
    shader.fragmentShader='uniform sampler2D fillMap;\nvarying vec2 vFillUv;\n'+withTerrainDayNight(terrainShadowFragment(shader.fragmentShader),ShaderChunk.lights_fragment_begin)
      .replace('#include <map_fragment>',fill ? `#include <map_fragment>
        float photoLuma = dot(sRGBTransferOETF(vec4(diffuseColor.rgb, 1.0)).rgb, vec3(0.2126, 0.7152, 0.0722));
        diffuseColor.rgb = mix(texture2D(fillMap, vFillUv).rgb, diffuseColor.rgb, smoothstep(0.04, 0.12, photoLuma));` : '#include <map_fragment>');
  }}/>;
}
