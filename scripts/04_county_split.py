#!/usr/bin/env python3
"""
04_county_split.py
以 OSM admin_level=4 縣市界將道路分縣市：
  data/county_stats.json                    各縣市分級長度統計（供地圖面板）
  docs/county_stats.json                    同上
  data/export/by_county/<縣市>_living_streets_twd97.zip   各縣市 ≤15m 道路 Shapefile
註：高雄市之 OSM 關聯因含東沙、南沙群島而超出 Geofabrik 擷取範圍，無法組成面，
    故以「未落入其他縣市且位於南部範圍」之路段指派為高雄市。
"""
import os, json, zipfile, shutil
import geopandas as gpd, pandas as pd

roads = gpd.read_parquet("data/roads_all.parquet")
adm = gpd.read_file("data/admin4.geojson")
adm = adm[(adm.admin_level == "4") & adm.name.fillna("").str.contains("縣|市")][["name", "geometry"]]
adm = adm.dissolve(by="name").reset_index()
print("counties:", len(adm))

# 以路段代表點做空間 join（快）
pts = roads.copy()
pts["geometry"] = roads.geometry.representative_point()
j = gpd.sjoin(pts[["geometry"]], adm, how="left", predicate="within")
j = j[~j.index.duplicated(keep="first")]
roads["county"] = j["name"].values
mask = roads.county.isna()
c = roads.loc[mask, "geometry"].representative_point()
roads.loc[mask & (c.y < 23.6) & (c.x < 121.05) & (c.x > 119.9) & (c.y > 22.3), "county"] = "高雄市"
roads["county"] = roads.county.fillna("其他／未歸屬")
print(roads.county.value_counts().to_string())

# 統計
stats = {}
for cty, g in roads.groupby("county"):
    stats[cty] = {
        "total_km": round(g.length_m.sum() / 1000, 1),
        **{k: round(g.loc[g.cls == k, "length_m"].sum() / 1000, 1) for k in "ABCX"},
    }
    stats[cty]["pct_le12"] = round(100 * (stats[cty]["A"] + stats[cty]["B"]) / max(stats[cty]["total_km"], 0.1), 1)
json.dump(stats, open("data/county_stats.json", "w"), ensure_ascii=False, indent=1)
shutil.copy("data/county_stats.json", "docs/county_stats.json")
print(pd.DataFrame(stats).T.sort_values("pct_le12", ascending=False).to_string())

# 各縣市 shapefile
out = "data/export/by_county"
os.makedirs(out, exist_ok=True)
living = roads[roads.cls.isin(["A", "B", "C"])].to_crs(3826).rename(columns={"width_tag": "w_osm", "lanes_tag": "lanes_osm"})
for cty, g in living.groupby("county"):
    stem = f"{cty.replace('／','_')}_living_streets_twd97"
    d = f"{out}/{stem}"; os.makedirs(d, exist_ok=True)
    g.drop(columns=["county"]).to_file(f"{d}/{stem}.shp", driver="ESRI Shapefile", encoding="utf-8")
    open(f"{d}/{stem}.cpg", "w").write("UTF-8")
    shutil.copy("scripts/FIELDS.txt", f"{d}/README.txt")
    with zipfile.ZipFile(f"{out}/{stem}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for fn in os.listdir(d):
            z.write(f"{d}/{fn}", fn)
    shutil.rmtree(d)
    print(stem, len(g), os.path.getsize(f"{out}/{stem}.zip") // 1_000_000, "MB")
roads.to_parquet("data/roads_all.parquet")
