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
- `data/rain_hourly/` — hourly **forecast** rainfall (mm/hr, 0.1°, 72 h from 11 Dec 2025) converted from a `.mat` file with `tools/rain_mat_to_dashboard.py`: one PNG per hour (`frames/`) plus `rain.json` (bounds, times, legend, hourly mean per ONWR basin). Re-run with `--rain <variable>` for other files.
- `geo/tapi_rivers.geojson` — Tapi river network from OpenStreetMap (© OpenStreetMap contributors, ODbL). Line direction = flow direction; the 3rd coordinate is the approximate distance to the river mouth (km), used to order stations. Distances are approximate and only show order.
- `flood/`, `thumb/` — Tapi flood-depth layers, 18 climate scenarios.
- `geo/tha_basins22_onwr_*.geojson` — 22 main river basins (Royal Decree on River Basins B.E. 2564, ONWR; via [pratikkhanal16/thailand-water-storage-dss](https://github.com/pratikkhanal16/thailand-water-storage-dss)).
- `geo/tha_provinces_*`, `geo/tha_country_*`, `geo/surat_*` — Royal Thai Survey Department via [OCHA COD-AB](https://data.humdata.org/dataset/cod-ab-tha) (CC BY-IGO).
- Basemaps: © Esri, © OpenStreetMap contributors. Neighbouring countries: Natural Earth.

## Tools
- `tools/rain_mat_to_dashboard.py` — converts MATLAB `.mat` rainfall (v5/v7.3, gridded or station) into map frames + basin-mean series.

## Structure
```
index.html     single-page app (Leaflet 1.9.4 from cdnjs)
data/          hourly rainfall frames
geo/           basins, admin boundaries
flood/ thumb/  Tapi flood-depth overlays
tools/         data-preparation scripts
```
