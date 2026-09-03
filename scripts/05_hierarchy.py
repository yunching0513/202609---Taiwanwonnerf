#!/usr/bin/env python3
"""
05_hierarchy.py
依荷蘭 Sustainable Safety（Duurzaam Veilig）三層道路功能分級，擷取主要道路：
  T  Through roads      （Stroomwegen）        ：國道、快速公路（OSM motorway / trunk 及其連絡道）
  D  Distributor roads  （Gebiedsontsluitingswegen）：省道、縣道、鄉道與市區幹道（OSM primary / secondary / tertiary）
  A  Access roads       （Erftoegangswegen）   ：其餘市區道路、巷弄（unclassified / residential / living_street / service …）
     → A 類已在 living_streets.pmtiles（依路寬分級），本腳本僅輸出 T 與 D。

台灣 OSM 慣例：motorway=國道（ref 1–2 位數）、trunk=快速公路（台61、台64…）、primary=省道（台X線）、
secondary=縣道（3 位數 ref）或市區主要道路、tertiary=鄉道（縣市簡稱＋數字）或市區次要道路。

輸出:
  data/hierarchy.geojsonl   T / D 道路（供 tippecanoe）
  data/hierarchy_stats.json docs/hierarchy_stats.json  三層長度統計
"""
import json, re, os
import osmium
import geopandas as gpd, pandas as pd
from shapely.geometry import LineString

PBF = "data/taiwan-latest.osm.pbf"
THROUGH = {"motorway", "motorway_link", "trunk", "trunk_link"}
DISTRIB = {"primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"}
county_ref = re.compile(r"^(北|桃|竹|苗|中|彰|投|雲|嘉|南|高|屏|宜|花|東|澎|金|馬)\s?\d")


def subtype(hw, ref):
    base = hw.replace("_link", "")
    if base == "motorway":
        return "國道"
    if base == "trunk":
        return "快速公路"
    if base == "primary":
        return "省道" if re.match(r"^\d{1,2}", ref) else "市區主要幹道"
    if base == "secondary":
        return "縣道" if re.match(r"^\d{3}", ref) else "市區主要幹道"
    if base == "tertiary":
        return "鄉道" if county_ref.match(ref) else "市區次要幹道"
    return ""


class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__(); self.rows = []; self.geoms = []

    def way(self, w):
        hw = w.tags.get("highway")
        if hw not in THROUGH and hw not in DISTRIB:
            return
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(coords) < 2:
            return
        ref = w.tags.get("ref", "") or ""
        self.rows.append({
            "id": w.id, "hw": hw, "ss": "T" if hw in THROUGH else "D",
            "sub": subtype(hw, ref), "ref": ref, "name": w.tags.get("name", "") or "",
            "link": 1 if hw.endswith("_link") else 0,
            "lanes": w.tags.get("lanes", "") or "", "maxspeed": w.tags.get("maxspeed", "") or "",
        })
        self.geoms.append(LineString(coords))


h = H(); h.apply_file(PBF, locations=True, idx="flex_mem")
g = gpd.GeoDataFrame(h.rows, geometry=h.geoms, crs="EPSG:4326")
g["len"] = g.geometry.to_crs(3826).length.round(1)
print(len(g), "ways"); print(g.groupby(["ss", "sub"]).len.sum().div(1000).round(0))

with open("data/hierarchy.geojsonl", "w") as f:
    for r in g.itertuples():
        f.write(json.dumps({"type": "Feature", "properties": {
            "id": r.id, "hw": r.hw, "ss": r.ss, "sub": r.sub, "ref": r.ref, "name": r.name,
            "link": r.link, "lanes": r.lanes, "ms": r.maxspeed, "len": r.len},
            "geometry": r.geometry.__geo_interface__}, ensure_ascii=False) + "\n")

# 三層統計（A 類取自 roads_all.parquet 中非 T/D 的道路）
ra = pd.read_parquet("data/roads_all.parquet", columns=["highway", "length_m"])
access_km = ra.loc[~ra.highway.isin(THROUGH | DISTRIB), "length_m"].sum() / 1000
stats = {
    "T": {"km": round(g.loc[g.ss == "T", "len"].sum() / 1000, 1),
          "by_sub": g[g.ss == "T"].groupby("sub").len.sum().div(1000).round(1).to_dict()},
    "D": {"km": round(g.loc[g.ss == "D", "len"].sum() / 1000, 1),
          "by_sub": g[g.ss == "D"].groupby("sub").len.sum().div(1000).round(1).to_dict()},
    "A": {"km": round(access_km, 1)},
}
json.dump(stats, open("data/hierarchy_stats.json", "w"), ensure_ascii=False, indent=1)
json.dump(stats, open("docs/hierarchy_stats.json", "w"), ensure_ascii=False)
print(json.dumps(stats, ensure_ascii=False, indent=1))
