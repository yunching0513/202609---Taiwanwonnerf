#!/usr/bin/env bash
# 產製 PMTiles 向量圖磚（GitHub 單檔上限 100MB，故 max zoom 13，MapLibre 會 overzoom 至 18）
set -e
mkdir -p docs/tiles
tippecanoe -o docs/tiles/living_streets.pmtiles -l living_streets -Z7 -z13 -P -q \
  --drop-densest-as-needed --extend-zooms-if-still-dropping --simplification=4 --detect-shared-borders \
  --no-tile-size-limit --maximum-tile-bytes=400000 \
  -y id -y hw -y name -y w -y src -y cls -y len -y ow -y svc \
  --force data/living_streets.geojsonl
cp data/summary.json docs/summary.json
ls -la docs/tiles/
