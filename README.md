# Taiwanwonnerf：全台生活街道指認地圖

以OpenStreetMap路網估算全台每一路段之路寬，指認15公尺以下、可能成為「生活街道」（living street）的道路，並以互動式網頁地圖呈現。

- 互動地圖：https://yunching0513.github.io/202609---Taiwanwonnerf/ （`docs/index.html`，GitHub Pages）
- 兩種模式：「路寬分級」（生活街道候選）與「道路功能層級」（荷蘭Sustainable Safety三層分級）
- 資料下載：`data/export/taiwan_living_streets_twd97.zip`（Shapefile, EPSG:3826）、`data/export/taiwan_roads_all_twd97.zip`（全部道路）
- 欄位說明：`scripts/FIELDS.txt`

## 分級

| 分級 | 估算路寬 | 說明 |
|---|---|---|
| A | ≤8m | 巷弄型生活街道（弄、巷、alley） |
| B | 8–12m | 社區街道（街、residential 路） |
| C | 12–15m | 邊界案例（tertiary、部分路） |
| X | >15m | 非生活街道（未納入地圖） |

## 道路功能層級（Sustainable Safety）

依荷蘭Duurzaam Veilig的道路功能三分法，以OSM highway標籤與台灣ref慣例對應：

| 層級 | 荷蘭語 | 台灣對應 | OSM |
|---|---|---|---|
| Through roads 通過性道路 | Stroomwegen | 國道、快速公路 | motorway、trunk（含_link） |
| Distributor roads 集散道路 | Gebiedsontsluitingswegen | 省道、縣道、鄉道、市區主要／次要幹道 | primary、secondary、tertiary（含_link） |
| Access roads 進出道路 | Erftoegangswegen | 市區道路、巷弄 | unclassified、residential、living_street、service、pedestrian |

子類型判定：primary且ref為1–2位數→省道；secondary且ref為3位數→縣道；tertiary且ref為「縣市簡稱＋數字」→鄉道；其餘依所在等級標為市區主要／次要幹道。長度：Through約4,888 km（3.5%）、Distributor約29,822 km（22%）、Access約102,980 km（75%）。

## 路寬估算方法

1. OSM `width` 標籤（實測，覆蓋率僅約0.3%）
2. OSM `lanes` 標籤：lanes × 3.5 + 2.0（覆蓋率約5%）
3. 台灣路名慣例：弄4m、巷6m、街10m、路12m（適用 residential / unclassified / service / living_street）
4. OSM 道路等級預設：service alley 4m、service 5m、living_street 6m、residential 8m、unclassified 10m、tertiary 15m、secondary 20m、primary 30m

每一路段皆記錄 `width_src`（估算依據），地圖上點選路段可見。

## 本機預覽地圖

```bash
python3 serve.py        # 開啟 http://localhost:8765/
```
（PMTiles 需 HTTP Range 支援，直接開 index.html 或用 `python -m http.server` 無法載入圖磚；GitHub Pages 可正常運作。）

## 重現

```bash
pip install osmium geopandas pyarrow shapely pyproj
# 下載 https://download.geofabrik.de/asia/taiwan-latest.osm.pbf 至 data/
python scripts/01_extract_roads.py data/taiwan-latest.osm.pbf
bash   scripts/02_build_tiles.sh        # 需 tippecanoe
python scripts/03_export_shp.py
python scripts/04_county_split.py
python scripts/05_hierarchy.py && tippecanoe -o docs/tiles/hierarchy.pmtiles -l hierarchy -Z5 -z13 -P --drop-densest-as-needed --extend-zooms-if-still-dropping --simplification=4 --force data/hierarchy.geojsonl
```

## 限制與後續

- OSM 的 `width` 標籤極稀疏，多數路寬為推估值，僅供初步指認。
- 建議以內政部國土測繪中心「臺灣通用電子地圖」ROAD 圖層之 `WIDTH`（最大路面寬度）欄位、各縣市都市計畫道路寬度或開放資料（如臺中市道路寬度）校正。
- 生活街道之指認除路寬外，宜再納入土地使用（住宅、商業混合）、街廓尺度、交通量與速限等條件。

## 授權

程式：MIT。資料：© OpenStreetMap contributors，ODbL 1.0。底圖：內政部國土測繪中心臺灣通用電子地圖（WMTS）。
