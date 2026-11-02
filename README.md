# Thailand Flood Explorer

Interactive map of flood hazard, rainfall and climate scenarios across Thailand's river basins. The first pilot basin is the Tapi (Surat Thani); prepared for a research proposal.

**Live site:** https://kboonma.github.io/TH_flood_explorer/

- 18 flood-depth scenarios: CMIP6 SSP2-4.5 / SSP3-7.0 / SSP5-8.5 × 2040s / 2060s / 2080s × peak driven by the Tapi (X.217) or Phum Duang (X.36)
- Per-subdistrict inundation by depth class for Mueang Surat Thani and Phunphin (27 tambon)
- Gauging and rainfall stations

## Data sources
- Flood depth maps and subdistrict tables: project final report (HEC-HMS + HEC-RAS 1D/2D). Flood maps were georeferenced from the report figures (~25 m pixels) and are for display only.
- Administrative boundaries: Royal Thai Survey Department via [OCHA COD-AB](https://data.humdata.org/dataset/cod-ab-tha) (CC BY-IGO)
- Neighbouring countries: [Natural Earth](https://www.naturalearthdata.com/)
- Basemap: © OpenStreetMap contributors © CARTO
- River basins: the 22 main basins under the Royal Decree on River Basins B.E. 2564 (2021), Office of the National Water Resources (ONWR/สทนช.). Layer obtained via [pratikkhanal16/thailand-water-storage-dss](https://github.com/pratikkhanal16/thailand-water-storage-dss) (`MainBasin_ONWR_Law_WGS84`); simplified for the web (`geo/tha_basins22_onwr_web.geojson`, ~300 m) with a detailed copy (`geo/tha_basins22_onwr_detail.geojson`, ~50 m).
- Tapi study-area outline: digitised from the project report (pilot area inside basin 19, Peninsula – Upper East Coast).

Preliminary figures for demonstration; not for operational use.

## Structure
```
index.html   single-page app (Leaflet 1.9.4 from cdnjs)
flood/       18 flood-depth overlays (PNG, EPSG:4326 bounds in index.html)
thumb/       thumbnails for the scenario grid
geo/         provinces, Surat Thani districts, 27 subdistricts (GeoJSON)
```
