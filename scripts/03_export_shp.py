#!/usr/bin/env python3
"""
03_export_shp.py
將 data/roads_all.parquet 匯出為 Shapefile（TWD97 / TM2, EPSG:3826）並壓縮：
  data/export/taiwan_roads_all_twd97.zip       全部道路（含估算路寬與分級）
  data/export/taiwan_living_streets_twd97.zip  ≤15m（cls A/B/C）
Shapefile 欄位名稱限 10 字元。
"""
import os, shutil, zipfile
import geopandas as gpd

os.makedirs("data/export", exist_ok=True)
gdf = gpd.read_parquet("data/roads_all.parquet").to_crs(3826)
gdf = gdf.rename(columns={
    "osm_id": "osm_id", "highway": "highway", "name": "name",
    "width_est": "width_est", "width_src": "width_src", "width_tag": "w_osm",
    "lanes_tag": "lanes_osm", "oneway": "oneway", "cls": "cls",
    "service": "service", "surface": "surface", "maxspeed": "maxspeed", "length_m": "length_m",
})

def export(df, stem):
    d = f"data/export/{stem}"
    os.makedirs(d, exist_ok=True)
    df.to_file(f"{d}/{stem}.shp", driver="ESRI Shapefile", encoding="utf-8")
    with open(f"{d}/{stem}.cpg", "w") as f:
        f.write("UTF-8")
    with open(f"{d}/README.txt", "w") as f:
        f.write(open("scripts/FIELDS.txt").read())
    with zipfile.ZipFile(f"data/export/{stem}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for fn in os.listdir(d):
            z.write(f"{d}/{fn}", fn)
    shutil.rmtree(d)
    print(stem, len(df), "features ->", os.path.getsize(f"data/export/{stem}.zip") // 1_000_000, "MB")

export(gdf, "taiwan_roads_all_twd97")
export(gdf[gdf.cls.isin(["A", "B", "C"])], "taiwan_living_streets_twd97")
