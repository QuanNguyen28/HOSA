import hashlib
import json
import sys
import zipfile

sys.path.insert(0,"scripts")
from import_nasa_delivery import import_delivery


def test_import_is_checksum_verified_idempotent_and_keeps_source_archive_unchanged(tmp_path,monkeypatch):
    from app.services.lunarsight import acquire

    delivery=tmp_path/"delivery"; delivery.mkdir()
    filename="Site01_final_adj_5mpp_surf.tif"
    member="nasa/Site01/"+filename
    data=b"II*\x00verified synthetic raster payload"
    archive_name="D01_PGDA78_Site01_01.zip"
    asset={"id":"Site01_dem","filename":filename,"url":"https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/"+filename,
           "source_page":"https://pgda.gsfc.nasa.gov/products/78","role":"dem","unit":"m","site":"Site01","frame":"MOON_ME/DE421"}
    source={"filename":filename,"region":"Site01","url":asset["url"],"bytes":len(data),
            "sha256":hashlib.sha256(data).hexdigest(),"status":"VERIFIED_BYTES_AND_FORMAT",
            "archive":archive_name,"member":member,"validation":{"shape":[2,2]}}
    embedded={"filename":filename,"url":asset["url"],"bytes":len(data),"sha256":source["sha256"],"status":"VERIFIED_BYTES"}
    archive_path=delivery/archive_name
    with zipfile.ZipFile(archive_path,"w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member,data)
        archive.writestr("receipts/"+filename+".json",json.dumps(embedded))
    archive_hash=hashlib.sha256(archive_path.read_bytes()).hexdigest()
    (delivery/"SOURCE_MANIFEST.json").write_text(json.dumps({"sources":[source]}),encoding="utf-8")
    (delivery/"DOWNLOAD_CHECKSUMS.json").write_text(json.dumps([{"filename":archive_name,
        "bytes":archive_path.stat().st_size,"sha256":archive_hash}]),encoding="utf-8")
    monkeypatch.setattr(acquire,"sources",lambda:[asset])

    target=tmp_path/"runtime"
    first=import_delivery(delivery,target,["Site01"])
    before=archive_path.read_bytes()
    second=import_delivery(delivery,target,["Site01"])
    receipt=json.loads((target/(filename+".receipt.json")).read_text(encoding="utf-8"))
    assert first["imported"][0]["status"]=="IMPORTED_VERIFIED"
    assert second["imported"][0]["status"]=="CACHE_VERIFIED"
    assert (target/filename).read_bytes()==data and archive_path.read_bytes()==before
    assert receipt["status"]=="VERIFIED_BYTES" and receipt["source_status"]=="VERIFIED_BYTES_AND_FORMAT"
    assert receipt["archive_sha256"]==archive_hash


def test_import_fails_closed_for_tampered_source_archive(tmp_path,monkeypatch):
    from app.services.lunarsight import acquire

    delivery=tmp_path/"delivery"; delivery.mkdir()
    filename="tile.tif"; archive_name="source.zip"; content=b"II*\x00data"
    asset={"id":"Site01_dem","filename":filename,"url":"https://pgda.gsfc.nasa.gov/asset",
           "source_page":"https://pgda.gsfc.nasa.gov/products/78","role":"dem","unit":"m","site":"Site01"}
    source={"filename":filename,"region":"Site01","url":asset["url"],"bytes":len(content),
            "sha256":hashlib.sha256(content).hexdigest(),"status":"VERIFIED_BYTES_AND_FORMAT",
            "archive":archive_name,"member":"nasa/../escape.tif"}
    with zipfile.ZipFile(delivery/archive_name,"w") as archive:
        archive.writestr("nasa/../escape.tif",content)
        archive.writestr("receipts/"+filename+".json",json.dumps({"url":asset["url"],"bytes":len(content),"sha256":source["sha256"]}))
    archive_path=delivery/archive_name
    (delivery/"SOURCE_MANIFEST.json").write_text(json.dumps({"sources":[source]}),encoding="utf-8")
    (delivery/"DOWNLOAD_CHECKSUMS.json").write_text(json.dumps([{"filename":archive_name,
        "bytes":archive_path.stat().st_size,"sha256":hashlib.sha256(archive_path.read_bytes()).hexdigest()}]),encoding="utf-8")
    monkeypatch.setattr(acquire,"sources",lambda:[asset])
    try:
        import_delivery(delivery,tmp_path/"runtime",["Site01"])
        assert False,"unsafe archive member must fail"
    except ValueError as error:
        assert "Unsafe archive member" in str(error)
    assert not (tmp_path/"runtime"/filename).exists()
