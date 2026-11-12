"""Import only receipt-verified engine rasters from an immutable NASA delivery."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys_path = ROOT / "backend"
import sys
sys.path.insert(0, str(sys_path))


def _json_finite(value):
    if isinstance(value,float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else "Infinity" if value>0 else "-Infinity"
    if isinstance(value,dict):
        return {key:_json_finite(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):
        return [_json_finite(item) for item in value]
    return value


def sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_path(delivery_root: Path, name: str) -> Path:
    if not name or Path(name).name != name or name in {".",".."}:
        raise ValueError("Unsafe archive filename in source manifest")
    path=(delivery_root/name).resolve()
    if not path.is_relative_to(delivery_root.resolve()):
        raise ValueError("Archive path escapes delivery directory")
    return path


def _member_path(name: str) -> PurePosixPath:
    path=PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in {".",".."} for part in path.parts):
        raise ValueError("Unsafe archive member path in source manifest")
    return path


def _copy_member(archive: zipfile.ZipFile, member_name: str, destination: Path,
                 expected_bytes: int, expected_hash: str, role: str) -> None:
    member_path=_member_path(member_name)
    info=archive.getinfo(member_path.as_posix())
    mode=info.external_attr >> 16
    if stat.S_ISLNK(mode) or info.is_dir() or info.file_size != expected_bytes:
        raise ValueError("Archive member type or byte count does not match source manifest")
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,temp_name=tempfile.mkstemp(prefix=destination.name+".",suffix=".part",dir=destination.parent)
    digest=hashlib.sha256(); total=0
    try:
        with os.fdopen(fd,"wb") as output, archive.open(info,"r") as source:
            for chunk in iter(lambda:source.read(4*1024*1024),b""):
                total+=len(chunk)
                if total>expected_bytes:
                    raise ValueError("Expanded member exceeds its manifest byte count")
                digest.update(chunk); output.write(chunk)
        if total!=expected_bytes or digest.hexdigest()!=expected_hash:
            raise ValueError("Extracted member failed byte count or SHA-256 verification")
        from app.services.lunarsight.acquire import validate_payload
        validate_payload(Path(temp_name),role)
        os.replace(temp_name,destination)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def import_delivery(delivery_root: Path, destination: Path, datasets: list[str]) -> dict:
    delivery_root=delivery_root.resolve()
    if not delivery_root.is_dir():
        raise FileNotFoundError("NASA delivery directory does not exist")
    manifest=json.loads((delivery_root/"SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    checksums=json.loads((delivery_root/"DOWNLOAD_CHECKSUMS.json").read_text(encoding="utf-8"))
    rows={row["filename"]:row for row in manifest.get("sources",[])
          if isinstance(row,dict) and isinstance(row.get("filename"),str)}
    archive_rows={row["filename"]:row for row in checksums}

    from app.services.lunarsight.acquire import sources
    selected=[]
    groups=set(datasets)
    for item in sources():
        group=item["site"] if item.get("site") else item["id"]
        if group in groups and item["role"] in {"dem","error","count"}:
            selected.append(item)
    missing=[item["filename"] for item in selected if item["filename"] not in rows]
    if missing:
        raise ValueError("Requested engine source is absent from source manifest: "+", ".join(missing))

    total_bytes=sum(int(rows[item["filename"]]["bytes"]) for item in selected)
    destination.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(destination).free < total_bytes:
        raise OSError("Not enough free space for selected engine rasters")

    verified_archives={}
    imported=[]
    for item in selected:
        record=rows[item["filename"]]
        if record.get("status") not in {"VERIFIED_BYTES","VERIFIED_BYTES_AND_FORMAT"}:
            raise ValueError("Refusing unverified source row: "+item["filename"])
        archive_name=record.get("archive")
        member_name=record.get("member")
        if not archive_name or not member_name or not _member_path(member_name).as_posix().startswith("nasa/"):
            raise ValueError("Missing or invalid archive mapping for "+item["filename"])
        archive_path=_archive_path(delivery_root,archive_name)
        expected_archive=archive_rows.get(archive_name)
        if not expected_archive:
            raise ValueError("Archive has no verified delivery checksum: "+archive_name)
        if archive_name not in verified_archives:
            stat_result=archive_path.stat()
            if stat_result.st_size!=int(expected_archive["bytes"]) or sha256_file(archive_path)!=expected_archive["sha256"]:
                raise ValueError("Delivery archive checksum failed: "+archive_name)
            verified_archives[archive_name]=expected_archive["sha256"]

        target=destination/item["filename"]
        receipt_path=target.with_name(target.name+".receipt.json")
        recover_receipt=False
        if target.exists() or receipt_path.exists():
            if not target.is_file() or target.stat().st_size!=int(record["bytes"]) or sha256_file(target)!=record["sha256"]:
                raise ValueError("Existing raw cache failed integrity validation: "+target.name)
            if receipt_path.is_file():
                receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
                if receipt.get("sha256")!=record["sha256"] or receipt.get("bytes")!=record["bytes"]:
                    raise ValueError("Existing raw receipt failed integrity validation: "+target.name)
                imported.append({"id":item["id"],"status":"CACHE_VERIFIED","filename":target.name,"sha256":record["sha256"]})
                continue
            recover_receipt=True

        with zipfile.ZipFile(archive_path,"r") as archive:
            embedded_receipt_path=_member_path("receipts/"+item["filename"]+".json")
            embedded_info=archive.getinfo(embedded_receipt_path.as_posix())
            if stat.S_ISLNK(embedded_info.external_attr >> 16) or embedded_info.file_size>256_000:
                raise ValueError("Embedded receipt is not a bounded regular file")
            embedded_receipt=json.loads(archive.read(embedded_info).decode("utf-8"))
            if (embedded_receipt.get("sha256")!=record["sha256"] or
                    embedded_receipt.get("bytes")!=record["bytes"] or
                    embedded_receipt.get("url")!=record["url"]):
                raise ValueError("Embedded source receipt disagrees with source manifest")
            if not recover_receipt:
                _copy_member(archive,member_name,target,int(record["bytes"]),record["sha256"],item["role"])
        receipt={**item,**record,"status":"VERIFIED_BYTES","source_status":record["status"],
                 "archive_sha256":verified_archives[archive_name],"archive_member":member_name,
                 "transfer":"extracted from checksum-verified immutable delivery ZIP"}
        fd,temp_name=tempfile.mkstemp(prefix=receipt_path.name+".",suffix=".part",dir=receipt_path.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as stream:
                stream.write(json.dumps(_json_finite(receipt),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
            os.replace(temp_name,receipt_path)
        finally:
            Path(temp_name).unlink(missing_ok=True)
        imported.append({"id":item["id"],"status":"RECEIPT_REBUILT_VERIFIED" if recover_receipt else "IMPORTED_VERIFIED",
                         "filename":target.name,"sha256":record["sha256"]})
    return {"delivery":str(delivery_root),"destination":str(destination),"archive_count":len(verified_archives),
            "imported":imported}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery-path",type=Path,default=os.getenv("LUNARSIGHT_RAW_DATASET_PATH"))
    parser.add_argument("--datasets",nargs="+",choices=["Site01","Site04","dem80","dem240"],
                        default=["Site01","Site04","dem80","dem240"])
    parser.add_argument("--destination",type=Path,default=ROOT/"data/raw/nasa")
    args=parser.parse_args(argv)
    if not args.delivery_path:
        parser.error("Pass --delivery-path or set LUNARSIGHT_RAW_DATASET_PATH")
    try:
        report=import_delivery(args.delivery_path,args.destination,args.datasets)
    except (OSError,ValueError,KeyError,zipfile.BadZipFile) as error:
        print("Import failed: "+type(error).__name__+": "+str(error),file=sys.stderr)
        return 1
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
