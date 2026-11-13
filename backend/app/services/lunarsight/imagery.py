"""Bounded, same-origin Moon Trek tile cache; imagery never enters science inputs."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from .point import repository_root

router = APIRouter(prefix='/lunar/imagery', tags=['lunar imagery'])


def image_size(data):
    if (data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 45
            and data.endswith(b'\x00\x00\x00\x00IEND\xaeB`\x82')):
        return struct.unpack('>II', data[16:24]), 'image/png'
    if data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9'):
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 255:
                break
            marker = data[offset + 1]
            offset += 2
            if marker == 255:
                offset -= 1
                continue
            if marker in {0xD8, 0xD9, 0x01}:
                continue
            size = int.from_bytes(data[offset:offset + 2], 'big')
            if size < 2:
                break
            if marker in {0xC0, 0xC1, 0xC2}:
                h, w = struct.unpack('>HH', data[offset + 3:offset + 7])
                return (w, h), 'image/jpeg'
            offset += size
    raise ValueError('Not a supported image')


class ImageryCache:
    def __init__(self, client, root=None, manifest=None):
        path = repository_root() / 'manifests/lunarsight/moontrek_imagery.json'
        self.manifest = manifest or json.loads(path.read_text(encoding='utf-8'))
        self.layers = {layer['id']: layer for layer in self.manifest['layers']}
        self.version = hashlib.sha256(json.dumps(self.manifest, sort_keys=True).encode()).hexdigest()[:16]
        self.root = Path(root or repository_root() / 'data/cache/moontrek') / self.version
        self.client = client
        self.gate = asyncio.Semaphore(6)
        self.locks = {}

    def tile(self, layer_id, level, row, column):
        layer = self.layers.get(layer_id)
        matrix = next((m for m in layer['matrices'] if m['level'] == level), None) if layer else None
        if not matrix or not 0 <= row < matrix['height'] or not 0 <= column < matrix['width']:
            raise HTTPException(404, detail={'code': 'IMAGERY_OUTSIDE_COVERAGE'})
        url = layer['tile_template'].replace('{TileMatrix}', str(level)).replace('{TileRow}', str(row)).replace('{TileCol}', str(column))
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'trek.nasa.gov' or not parsed.path.startswith('/tiles/Moon/'):
            raise HTTPException(503, detail={'code': 'IMAGERY_SOURCE_INVALID'})
        return layer, matrix, url

    def cached(self, path, source, matrix):
        try:
            data = path.read_bytes()
            receipt = json.loads(path.with_suffix('.json').read_text())
            dimensions, mime = image_size(data)
            if (receipt['url'] == source and receipt['bytes'] == len(data)
                    and receipt['sha256'] == hashlib.sha256(data).hexdigest()
                    and dimensions == (matrix['tile_size'], matrix['tile_size'])):
                return data, receipt['sha256'], mime
        except (OSError, ValueError, KeyError, struct.error):
            pass
        return None

    async def read(self, layer_id, level, row, column):
        layer, matrix, url = self.tile(layer_id, level, row, column)
        path = self.root / layer_id / str(level) / str(row) / f'{column}.tile'
        if hit := self.cached(path, url, matrix):
            return (*hit, True)
        key = (layer_id, level, row, column)
        entry = self.locks.setdefault(key, [asyncio.Lock(), 0])
        entry[1] += 1
        lock = entry[0]
        try:
            async with lock:
                if hit := self.cached(path, url, matrix):
                    return (*hit, True)
                async with self.gate:
                    try:
                        async with self.client.stream('GET', url) as upstream:
                            if upstream.status_code == 404:
                                raise HTTPException(404, detail={'code': 'IMAGERY_TILE_MISSING'})
                            upstream.raise_for_status()
                            body = bytearray()
                            async for chunk in upstream.aiter_bytes():
                                body.extend(chunk)
                                if len(body) > 2_000_000:
                                    raise ValueError('Tile exceeds byte limit')
                            data = bytes(body)
                            dimensions, mime = image_size(data)
                            if dimensions != (matrix['tile_size'], matrix['tile_size']) or mime != layer['format']:
                                raise ValueError('Tile format/size mismatch')
                    except (httpx.HTTPError, ValueError, struct.error) as error:
                        raise HTTPException(502, detail={'code': 'IMAGERY_SOURCE_UNAVAILABLE'}) from error
                sha = hashlib.sha256(data).hexdigest()
                receipt = {'url': url, 'sha256': sha, 'bytes': len(data), 'layer': layer_id,
                           'acquired_utc': datetime.now(timezone.utc).isoformat(), 'usage': 'observational_display_only'}
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix('.' + uuid4().hex + '.part')
                temporary.write_bytes(data)
                temporary.replace(path)
                temporary = path.with_suffix('.' + uuid4().hex + '.part')
                temporary.write_text(json.dumps(receipt), encoding='utf-8')
                temporary.replace(path.with_suffix('.json'))
                return data, sha, mime, False
        finally:
            entry[1] -= 1
            if entry[1] == 0:
                self.locks.pop(key, None)


@router.get('/layers')
async def layers(request: Request):
    return request.app.state.imagery.manifest


@router.get('/{layer_id}/{level}/{row}/{column}')
async def tile(request: Request, layer_id: str, level: int, row: int, column: int):
    data, sha, mime, cached = await request.app.state.imagery.read(layer_id, level, row, column)
    headers = {'ETag': f'"{sha}"', 'Cache-Control': 'public, max-age=86400',
               'X-Imagery-Source': 'NASA Moon Trek', 'X-Imagery-Cache': 'hit' if cached else 'miss'}
    if request.headers.get('if-none-match') == headers['ETag']:
        return Response(status_code=304, headers=headers)
    return Response(content=data, media_type=mime, headers=headers)
