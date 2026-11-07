"""Build the four stage notebooks and the single-file Kaggle submission."""
import argparse, base64, io, json, textwrap, zipfile
from pathlib import Path
import nbformat as n

def payload(root):
    buffer=io.BytesIO()
    include=["config","src","tests",".agents/skills"]
    files=[root/"README.md",root/"requirements.txt",root/"skill_inventory.md"]
    for rel in include:
        files.extend(p for p in (root/rel).rglob("*") if p.is_file() and p.suffix in {".py",".json",".md",".yaml"})
    with zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(set(files)):
            if not p.exists(): continue
            name=p.relative_to(root).as_posix()
            i=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            i.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(i,p.read_bytes())
    return base64.b64encode(buffer.getvalue()).decode()

def make(root):
    root=root.resolve(); nd=root/"notebooks";nd.mkdir(exist_ok=True)
    def write(name,title,md,code):
        nb=n.v4.new_notebook(cells=[n.v4.new_markdown_cell("# "+title+"\n\n"+md),*[n.v4.new_code_cell(textwrap.dedent(s).strip()) for s in code]],
            metadata={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python","file_extension":".py"}})
        n.validate(nb);n.write(nb,nd/name)
    shared="""
        from pathlib import Path
        import os, sys
        root=Path(os.environ.get("LUNARSIGHT_ROOT", Path.cwd())).resolve()
        if not (root/"src/pipeline.py").exists() and (root.parent/"src/pipeline.py").exists():
            root=root.parent
        assert (root/"src/pipeline.py").exists(), "Set LUNARSIGHT_ROOT to the extracted lunarsight-data folder."
        sys.path.insert(0,str(root/"src"))
        for name in ("reports","manifests","processed","figures"): (root/name).mkdir(exist_ok=True)
    """
    write("01_data_collection.ipynb","01 NASA data collection",
          "Fetch official Site01 and regional inputs, validate byte integrity and preserve raw files. Site04 is gated by the integrated run. Use this notebook from the extracted package.",[shared,"""
        from acquire import environment, sources, inventory
        from pipeline import select_sources
        import pandas as pd
        environment(root)
        items=sources()
        rec={x["id"]:dict(x,status="NOT_REQUESTED") for x in items}
        rec.update(select_sources(root,items,{x["id"] for x in items if x["site"]!="Site04"},False))
        inventory(root,list(rec.values()))
        table=pd.read_csv(root/"reports/data_inventory.csv")
        display(table[["id","status","bytes","sha256"]])
        assert all(x["status"] in {"VERIFIED_BYTES","NOT_REQUESTED"} for x in rec.values())
    """])
    write("02_dem_eda.ipynb","02 DEM metadata and EDA",
          "Use verified assets in the same working tree. Validate the registered pixel centre and NASA ROI, summarize windowed statistics and inspect terrain previews.",[shared,"""
        from acquire import load, inventory, download
        from terrain import site_geojson
        from pipeline import stage_dem
        from IPython.display import Image, display
        import pandas as pd
        old=load(root/"manifests/source_manifest.json")
        records={x["id"]:x for x in old["records"]}
        for rec in records.values():
            if rec["status"] in {"PASS","VERIFIED_BYTES"}:
                download(root,rec,offline=True)
        for key in ["dem80","dem240","Site01_count","Site01_error"]:
            stage_dem(root,key,records,"Site01" if key.startswith("Site01") else None)
        site=stage_dem(root,"Site01_dem",records,"Site01")
        site_geojson(root/"processed/site_catalog.geojson",[site])
        inventory(root,list(records.values()),old.get("horizons",[]))
        display(pd.DataFrame([dict(id=k,**v["stats"]) for k,v in records.items() if "stats" in v]))
        display(Image(filename=str(root/"figures/Site01_dem_eda.png")))
    """])
    write("03_horizons_eda.ipynb","03 JPL Horizons EDA",
          "Request or reuse exact-match Sun/Earth responses for catalogued points. The configured UTC epoch is provisional.",[shared,"""
        from acquire import load, inventory
        from horizons import fetch
        from pipeline import validate_config, plot_ephem
        from IPython.display import Image, display
        import pandas as pd
        s=load(root/"config/scenario.json"); g=load(root/"config/geometry_config.json")
        a,b,end=validate_config(s,g)
        reports=[]
        for f in load(root/"processed/site_catalog.geojson")["features"]:
            site=f["properties"]; series=[]
            for target,h in ((10,1),(399,2)):
                data,m=fetch(root,site,target,h,a,end,5,g["R_ref_m"],g["horizons_candidate_radius_m"])
                series.append(data);reports.append(m)
            assert series[0].index.equals(series[1].index)
            assert all(not r["missing_timestamps"] and not r["missing_angles"] for r in reports)
            plot_ephem(root,site["site_id"],*series)
            display(Image(filename=str(root/"figures"/f"{site['site_id']}_horizons.png")))
        old=load(root/"manifests/source_manifest.json")
        by_name={x["name"]:x for x in old.get("horizons",[])+reports}
        inventory(root,old["records"],by_name.values())
        display(pd.DataFrame(reports)[["target","step_minutes","received_rows","missing_timestamps","missing_angles","observer_frame"]])
    """])
    write("04_scientific_validation.ipynb","04 Scientific validation and export",
          "Run the integrated scientific checks and package the verified products. Set LUNARSIGHT_OFFLINE=1 only with a retained, matching raw cache.",[shared,"""
        from pipeline import run
        status=run(root,offline=os.environ.get("LUNARSIGHT_OFFLINE")=="1")
        assert status["pipeline_status"]=="PASS", "Read reports/execution_status.json"
        display(status["steps"])
    """])
    payload_text="\n".join(textwrap.wrap(payload(root),100))
    bootstrap=f"""
from pathlib import Path, PurePosixPath
import base64, io, os, sys, zipfile
kaggle=Path("/kaggle/working").is_dir()
root=Path(os.environ.get("LUNARSIGHT_ROOT", "/kaggle/temp/lunarsight-data" if kaggle else str(Path.cwd()/"lunarsight-run"))).resolve()
root.mkdir(parents=True,exist_ok=True)
archive = '''{payload_text}'''
with zipfile.ZipFile(io.BytesIO(base64.b64decode(archive))) as src:
    for item in src.infolist():
        rel=PurePosixPath(item.filename)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unexpected notebook source path")
        target=root.joinpath(*rel.parts)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(src.read(item))
sys.path.insert(0,str(root/"src"))
from build_notebooks import make
make(root)
print("LunarSight working tree:", root)
"""
    write("lunarsight-data-pipeline.ipynb","LunarSight data pipeline",
          "Private CPU run. Enable Internet and execute each code cell in order in the Draft session. Downloads NASA PGDA data, requests JPL Horizons, runs scientific checks, and writes a compact ZIP. The epoch 2026-11-14T00:00Z and G0 tolerances are PROVISIONAL.",
          [bootstrap,"""
            from pipeline import run
            import shutil
            status=run(root,offline=os.environ.get("LUNARSIGHT_OFFLINE")=="1")
            out=Path("/kaggle/working") if kaggle else root.parent
            bundle=root.parent/"lunarsight-data-deliverables.zip"
            if bundle.resolve()!=(out/bundle.name).resolve():
                shutil.copy2(bundle,out/bundle.name)
            for name in ("execution_status.json","pytest.log","scientific_validation.md","eda_summary.md","sensitivity.json"):
                src=root/"reports"/name
                if src.exists(): shutil.copy2(src,out/name)
            print("BUNDLE:", out/bundle.name, (out/bundle.name).stat().st_size,"bytes")
            print("PIPELINE_STATUS:",status["pipeline_status"])
            assert status["pipeline_status"]=="PASS", "Partial run; inspect execution_status.json and ZIP for successful stages."
          ""","""
            from IPython.display import Image, display
            for name in ("Site01_dem_eda.png","Site01_horizons.png","Site01_horizon.png","Site04_horizon.png"):
                p=root/"figures"/name
                if p.exists(): display(Image(filename=str(p),width=900))
          """])
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,required=True,help="Extracted lunarsight-data directory from the release ZIP.")
    root=ap.parse_args().root
    if not (root/"src/pipeline.py").is_file():
        ap.error("--root must point to the extracted standalone runner")
    make(root)
