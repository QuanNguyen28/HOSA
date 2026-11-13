"""Display-source correctness, provenance and failure isolation."""
import asyncio
import json
from pathlib import Path
import struct
import sys
import zlib

import httpx
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services.lunarsight.imagery import ImageryCache, image_size


def png(size=256):
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name+data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + bytes(size))*size)) + chunk(b'IEND', b''))


def test_real_manifest_keeps_native_lunar_metadata():
    path = Path(__file__).resolve().parents[1] / 'manifests/lunarsight/moontrek_imagery.json'
    manifest = json.loads(path.read_text())
    layers = {layer['id']: layer for layer in manifest['layers']}
    assert set(layers) == {'wac-global', 'wac-south', 'nac-south'}
    assert layers['nac-south']['native_resolution_m'] == 1
    assert layers['nac-south']['matrices'][-1]['resolution'] > 1  # Served pixels differ from native source.
    assert all(layer['radius_m'] == 1737400 for layer in layers.values())
    assert layers['nac-south']['crs'].endswith('30120')


def test_single_fetch_concurrent_cache_integrity_and_offline_reuse(tmp_path):
    async def run():
        calls = []
        async def handler(request):
            calls.append(str(request.url))
            await asyncio.sleep(.01)
            return httpx.Response(200, content=png())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            cache = ImageryCache(client, root=tmp_path)
            results = await asyncio.gather(*(cache.read('nac-south', 0, 0, 0) for _ in range(4)))
            assert len(calls) == 1 and sum(not row[3] for row in results) == 1
            assert cache.locks == {}
            receipt = next(tmp_path.rglob('*.json'))
            assert json.loads(receipt.read_text())['usage'] == 'observational_display_only'
            data_file = next(tmp_path.rglob('*.tile'))
            data_file.write_bytes(b'<html>corrupt cache</html>')
            fixed = await cache.read('nac-south', 0, 0, 0)
            assert len(calls) == 2 and not fixed[3] and image_size(fixed[0])[0] == (256,256)
        def offline(request):
            raise AssertionError('Verified cache reuse must not call NASA')
        async with httpx.AsyncClient(transport=httpx.MockTransport(offline)) as client:
            result = await ImageryCache(client, root=tmp_path).read('nac-south', 0, 0, 0)
            assert result[3]
    asyncio.run(run())


@pytest.mark.parametrize('content,status', [(b'<html>error</html>',200),(png()[:-10],200),(png(128),200),(b'',404),(b'',503)])
def test_invalid_or_missing_tile_is_never_published(tmp_path, content, status):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status,content=content))) as client:
            with pytest.raises(HTTPException) as exc:
                await ImageryCache(client, root=tmp_path).read('nac-south', 0, 0, 0)
            assert exc.value.status_code == (404 if status == 404 else 502)
            assert not list(tmp_path.rglob('*.tile'))
    asyncio.run(run())


@pytest.mark.parametrize('layer,z,row,column', [('https://evil.invalid',0,0,0),('nac-south',99,0,0),('wac-global',0,-1,0),('wac-global',0,0,2)])
def test_outside_whitelist_or_grid_never_calls_network(tmp_path, layer, z, row, column):
    async def run():
        def forbidden(request):
            raise AssertionError('Invalid request must not call a remote host')
        async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
            with pytest.raises(HTTPException) as exc:
                await ImageryCache(client, root=tmp_path).read(layer,z,row,column)
            assert exc.value.status_code == 404
    asyncio.run(run())
