# FloodCast TH

**ระบบพยากรณ์อุทกภัยระยะสั้น** · flood dashboard prototype for Thailand, pilot basin **Tapi (ตาปี)**.

Prototype of the decision-support dashboard (activity 3) in the NRCT 2027 proposal *Development of a Short-Term Flood Forecasting System Using Artificial Intelligence through the Integration of Multi-Source Meteorological Data and Physical Models to Support Disaster Management in Thailand*.

**Live site:** https://kboonma.github.io/TH_flood_explorer/

## Views
- **Thailand (22 ONWR basins):** hourly forecast-rainfall map with a Windy-style timeline, basins ranked by rainfall, and live water-level stations nationwide.
- **Tapi basin (opens by default):** flood extent and depth by climate scenario (SSP2-4.5 / 3-7.0 / 5-8.5 × 2040s / 2060s / 2080s, Tapi or Phum Duang driver); modelled peak flow vs current discharge at X.217 and X.36; hourly basin forecast rainfall; river flow view (animated flow direction on the map, stations ordered upstream → downstream with approximate distance to the river mouth, like ThaiWater's river page); live ThaiWater stations in the basin.

## Live monitoring (real data)
Station water levels and discharge come live from the **ThaiWater public API** (HII/สสน., with stations from HII, RID, EGAT and others). The browser calls it directly; no key or server needed.
- `waterlevel_load`: latest reading for ~770 stations (water level m MSL, bank level, discharge, situation class 1–5)
- `waterlevel_graph?station_type=tele_waterlevel&station_id=…&start_date=…&end_date=…`: hourly history for the 7-day charts when a station is clicked

Situation classes follow ThaiWater: น้ำน้อยวิกฤต · น้ำน้อย · ปกติ · น้ำมาก · ล้นตลิ่ง. Shown for decision support; not an official warning.

## Data
- `data/rain_hourly/` — hourly **forecast** rainfall (mm/hr, WRF grid ≈ 3 km, 72 h from 11 Dec 2025 00:00 UTC; shown in Thai time, 08:00 11 Dec – 07:00 14 Dec, each frame = rain in the hour ending at that time) from `wrfda_gsmap_20251211_20251213.mat`, variable `dat1` (`dat2` in the same file is not shown). Built with `tools/build_dashboard_rain.py file.mat -o data/rain_hourly --tz-offset 7`: one PNG per hour (`frames/`) and `rain.json` (bounds, times, legend, hourly mean per ONWR basin).
- `geo/tapi_rivers.geojson` — Tapi river network from OpenStreetMap (© OpenStreetMap contributors, ODbL). Line direction = flow direction; the 3rd coordinate is the approximate distance to the river mouth (km), used to order stations. Distances are approximate and only show order.
- `data/model_results.json` — daily modelled hydrographs of the 18 scenario events at X.217 and X.36 (digitised from the report figures, peaks matched to the report table; `tools/digitise_hydrographs.py`).
- `flood/`, `thumb/` — Tapi flood-depth layers, 18 climate scenarios.
- `geo/tha_basins22_onwr_*.geojson` — 22 main river basins (Royal Decree on River Basins B.E. 2564, ONWR; via [pratikkhanal16/thailand-water-storage-dss](https://github.com/pratikkhanal16/thailand-water-storage-dss)).
- `geo/tha_provinces_*`, `geo/tha_country_*`, `geo/surat_*` — Royal Thai Survey Department via [OCHA COD-AB](https://data.humdata.org/dataset/cod-ab-tha) (CC BY-IGO).
- Basemaps: © Esri, © OpenStreetMap contributors. Neighbouring countries: Natural Earth.

## Tools
- `tools/rain_mat_to_dashboard.py` — inspects/converts MATLAB `.mat` rainfall (v5/v7.3, gridded or station; regular or irregular latitude spacing; names like `dat1`/`lat1`/`date1` auto-detected).
- `tools/build_dashboard_rain.py` — builds `data/rain_hourly/` for the dashboard (frames + `rain.json` with 22-basin hourly means).

## Structure
```
index.html     single-page app (Leaflet 1.9.4 from cdnjs)
data/          hourly rainfall frames
geo/           basins, admin boundaries
flood/ thumb/  Tapi flood-depth overlays
tools/         data-preparation scripts
```
