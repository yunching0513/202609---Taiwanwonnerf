#!/usr/bin/env python3
"""
01_extract_roads.py
從 OSM 台灣全圖 (taiwan-latest.osm.pbf) 擷取所有 highway 線段，
估算路寬 (width_est)，並分級為生活街道候選。

輸出:
  data/roads_all.parquet        全部道路 (GeoParquet, EPSG:4326)
  data/living_streets.geojsonl  ≤15m 的道路 (供 tippecanoe)
  data/summary.json             統計摘要

路寬估算優先序:
  1. OSM `width` 標籤 (公尺)                          -> src = "osm_width"
  2. OSM `lanes` 標籤: lanes*3.5 + 2.0 (路肩/側溝)     -> src = "osm_lanes"
  3. 台灣路名後綴 (路/街/巷/弄) 與 highway 等級的經驗預設 -> src = "class_default"
"""
import sys, os, json, re, time
import osmium
from shapely.geometry import LineString
import geopandas as gpd
import pandas as pd

PBF = sys.argv[1] if len(sys.argv) > 1 else "data/taiwan-latest.osm.pbf"
OUT = "data"
os.makedirs(OUT, exist_ok=True)

# 納入的 highway 類型（排除高速、快速、人行專用、step 等）
KEEP = {
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential",
    "living_street", "service", "road", "pedestrian",
}
# 依 highway 等級的預設路寬 (公尺)，以台灣市區道路常見斷面為準
CLASS_DEFAULT = {
    "primary": 30, "primary_link": 15, "secondary": 20, "secondary_link": 12,
    "tertiary": 15, "tertiary_link": 10, "unclassified": 10, "residential": 8,   # 未命名時的預設
    "living_street": 6, "service": 5, "road": 8, "pedestrian": 8,
}
# 台灣路名後綴 → 寬度上限 (道路命名慣例: 路 > 街 > 巷 > 弄)
SUFFIX_DEFAULT = {"弄": 4, "巷": 6, "街": 10, "路": 12}
SUFFIX_APPLY = {"residential", "unclassified", "service", "living_street", "road"}
suffix_re = re.compile(r"([路街巷弄])(?:[0-9一二三四五六七八九十]+段)?$")
SERVICE_EXCLUDE = {"parking_aisle", "driveway", "drive-through", "emergency_access", "slipway"}

num_re = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)")

def parse_num(v):
    if v is None:
        return None
    m = num_re.match(v.replace("m", "").replace("公尺", ""))
    return float(m.group(1)) if m else None


class RoadHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.geoms = []
        self.n = 0

    def way(self, w):
        hw = w.tags.get("highway")
        if hw not in KEEP:
            return
        if w.tags.get("area") == "yes":
            return
        # service 道路排除停車場走道、私人車道等非街道空間；保留 alley（巷弄）與一般 service
        if hw == "service" and w.tags.get("service") in SERVICE_EXCLUDE:
            return
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(coords) < 2:
            return
        t = w.tags
        name = t.get("name", "") or ""
        width_tag = parse_num(t.get("width"))
        lanes_tag = parse_num(t.get("lanes"))
        oneway = t.get("oneway", "")

        if width_tag and 1 <= width_tag <= 80:
            width, src = width_tag, "osm_width"
        elif lanes_tag and 1 <= lanes_tag <= 12:
            width, src = lanes_tag * 3.5 + 2.0, "osm_lanes"
        else:
            width, src = CLASS_DEFAULT[hw], "class_default"
            # 台灣路名慣例：以路名中最後出現的 路/街/巷/弄 判定層級（「中山路100巷」→巷；「中正路一段」→路）
            m = suffix_re.search(name)
            if m and hw in SUFFIX_APPLY:
                width, src = SUFFIX_DEFAULT[m.group(1)], "name_suffix"
            elif hw == "service" and t.get("service") == "alley":
                width, src = 4, "class_default"

        if width <= 8:
            cls = "A"       # ≤8m  巷弄型生活街道
        elif width <= 12:
            cls = "B"       # 8–12m 社區街道
        elif width <= 15:
            cls = "C"       # 12–15m 邊界案例
        else:
            cls = "X"       # >15m 非生活街道

        self.rows.append({
            "osm_id": w.id, "highway": hw, "name": name,
            "width_est": round(width, 1), "width_src": src,
            "width_tag": width_tag, "lanes_tag": lanes_tag,
            "oneway": oneway, "cls": cls,
            "service": t.get("service", ""),
            "surface": t.get("surface", ""),
            "maxspeed": t.get("maxspeed", ""),
        })
        self.geoms.append(LineString(coords))
        self.n += 1
        if self.n % 100000 == 0:
            print(f"  ... {self.n} ways", flush=True)


t0 = time.time()
print("Reading", PBF)
h = RoadHandler()
h.apply_file(PBF, locations=True, idx="flex_mem")
print(f"Extracted {h.n} ways in {time.time()-t0:.0f}s")

gdf = gpd.GeoDataFrame(h.rows, geometry=h.geoms, crs="EPSG:4326")
# 長度 (公尺)，用 TWD97 / TM2 (EPSG:3826)
gdf["length_m"] = gdf.geometry.to_crs(3826).length.round(1)
gdf.to_parquet(f"{OUT}/roads_all.parquet")

living = gdf[gdf.cls.isin(["A", "B", "C"])]
with open(f"{OUT}/living_streets.geojsonl", "w") as f:
    for r in living.itertuples():
        feat = {
            "type": "Feature",
            "properties": {
                "id": r.osm_id, "hw": r.highway, "name": r.name,
                "w": r.width_est, "src": r.width_src, "cls": r.cls,
                "len": r.length_m, "ow": r.oneway, "svc": r.service,
            },
            "geometry": r.geometry.__geo_interface__,
        }
        f.write(json.dumps(feat, ensure_ascii=False) + "\n")

summary = {
    "total_ways": int(len(gdf)),
    "total_km": round(float(gdf.length_m.sum()) / 1000, 1),
    "by_class": {
        c: {"ways": int((gdf.cls == c).sum()),
            "km": round(float(gdf.loc[gdf.cls == c, "length_m"].sum()) / 1000, 1)}
        for c in ["A", "B", "C", "X"]
    },
    "by_width_src": gdf.width_src.value_counts().to_dict(),
    "by_highway": gdf.highway.value_counts().to_dict(),
    "osm_width_tag_coverage_pct": round(100 * gdf.width_tag.notna().mean(), 2),
    "osm_lanes_tag_coverage_pct": round(100 * gdf.lanes_tag.notna().mean(), 2),
}
json.dump(summary, open(f"{OUT}/summary.json", "w"), ensure_ascii=False, indent=2)
print(json.dumps(summary, ensure_ascii=False, indent=2))
