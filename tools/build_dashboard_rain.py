"""Build data/rain_hourly/ for the FloodCast TH dashboard from a MATLAB rainfall file.

    python tools/build_dashboard_rain.py rain.mat -o data/rain_hourly [--rain dat1] [--tz-offset 7 --time-ref "..."]

Current dashboard data (wrfda_gsmap_20251211_20251213.mat, dat1, file times in UTC, hour-ending):
    python tools/build_dashboard_rain.py wrfda_gsmap_20251211_20251213.mat -o data/rain_hourly --tz-offset 7 \
        --time-ref "เวลาไทย (UTC+7) · ฝนสะสม 1 ชม. สิ้นสุด ณ เวลาที่แสดง"

Writes rain.json (times, frames, bounds, legend, per-basin hourly means for the 22 ONWR basins) and frames/*.png
(one Web-Mercator PNG per hour, transparent below --min). Variable names are auto-detected (dat1/lat1/lon1/date1 work);
works for regular and irregular (e.g. WRF Mercator) latitude spacing.
"""
import argparse, json, os, sys, shutil
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rain_mat_to_dashboard import load_mat, pick, to_datetimes, ramp_lut, merc_y, nearest_index, RAMP, CLIPS

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('mat'); p.add_argument('-o', '--out', default='data/rain_hourly')
for k in ('rain', 'lat', 'lon', 'time'): p.add_argument(f'--{k}')
p.add_argument('--basins', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'geo', 'tha_basins22_onwr_web.geojson'))
p.add_argument('--clip', default='thailand', choices=list(CLIPS) + ['none'])
p.add_argument('--vmax', type=float, default=20.0); p.add_argument('--min', type=float, default=0.5)
p.add_argument('--label', default='ฝนพยากรณ์รายชั่วโมง'); p.add_argument('--type', default='forecast')
p.add_argument('--tz-offset', type=float, default=0, help='hours added to the file times, e.g. 7 for UTC -> Thai time')
p.add_argument('--time-ref', default='ตามไฟล์ (ยังไม่ระบุเขตเวลา)')
a = p.parse_args()

v, fmt = load_mat(a.mat)
nm = {k: pick(v, k, getattr(a, k)) for k in ('rain', 'lat', 'lon', 'time')}
print(f'[{fmt}] using {nm}')
R = v[nm['rain']].astype('float32'); lat = v[nm['lat']].astype(float).ravel(); lon = v[nm['lon']].astype(float).ravel()
times, how = to_datetimes(v[nm['time']]); nt = len(times)
from datetime import timedelta
times = [t + timedelta(hours=a.tz_offset) for t in times]
ax_t = R.shape.index(nt); rest = [i for i in range(3) if i != ax_t]
ax_y = next(i for i in rest if R.shape[i] == len(lat)); ax_x = next(i for i in rest if i != ax_y and R.shape[i] == len(lon))
R = np.transpose(R, (ax_t, ax_y, ax_x))
if lat[0] < lat[-1]: lat = lat[::-1]; R = R[:, ::-1, :]
if lon[0] > lon[-1]: lon = lon[::-1]; R = R[:, :, ::-1]
R[(R < 0) | (R > 5000)] = np.nan
if a.clip != 'none':
    W, S, E, N = CLIPS[a.clip]
    iy = np.where((lat >= S) & (lat <= N))[0]; ix = np.where((lon >= W) & (lon <= E))[0]
    R = R[:, iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1]; lat = lat[iy[0]:iy[-1] + 1]; lon = lon[ix[0]:ix[-1] + 1]
dyN, dyS, dx = abs(lat[0] - lat[1]), abs(lat[-1] - lat[-2]), abs(lon[1] - lon[0])
Nb, Sb, Wb, Eb = lat[0] + dyN / 2, lat[-1] - dyS / 2, lon[0] - dx / 2, lon[-1] + dx / 2

# per-basin hourly means (grid cells whose centre lies in the basin)
from shapely.geometry import shape
from shapely import contains_xy
LON, LAT = np.meshgrid(lon, lat)
basins = {}
for f in json.load(open(a.basins))['features']:
    pr = f['properties']; m = contains_xy(shape(f['geometry']), LON, LAT)
    hr = np.nanmean(R[:, m], axis=1) if m.any() else np.zeros(nt)
    basins[pr['code']] = {'name': pr['name_th'], 'cells': int(m.sum()), 'hourly': [round(float(x), 2) for x in hr],
                          'total': round(float(np.nansum(hr)), 1), 'max_hr': round(float(np.nanmax(hr)), 2)}

# frames
H, Wd = R.shape[1], R.shape[2]
yN, yS = merc_y(Nb), merc_y(Sb)
row_lat = np.degrees(2 * np.arctan(np.exp(yN - (np.arange(H) + .5) / H * (yN - yS))) - np.pi / 2)
src_r = nearest_index(lat, row_lat); src_c = np.arange(Wd)
lut = ramp_lut(); from PIL import Image
if os.path.isdir(f'{a.out}/frames'): shutil.rmtree(f'{a.out}/frames')
os.makedirs(f'{a.out}/frames')
frames = []
for t, grid in zip(times, R):
    g = grid[src_r][:, src_c]
    idx = np.clip(np.nan_to_num(g, nan=0) / a.vmax * 255, 0, 255).astype(int)
    rgba = np.zeros(g.shape + (4,), np.uint8); rgba[..., :3] = lut[idx]
    rgba[..., 3] = np.where(np.isnan(g) | (g < a.min), 0, np.clip(120 + 135 * np.sqrt(np.clip(g / a.vmax, 0, 1)), 0, 235)).astype(np.uint8)
    fn = f"frames/rain_{t.strftime('%Y%m%d%H%M')}.png"; Image.fromarray(rgba).save(f'{a.out}/{fn}', optimize=True); frames.append(fn)
legend = [{'value': round(a.vmax * x, 2) if x < 1 else a.vmax, 'color': '#%02x%02x%02x' % c} for x, c in RAMP]
meta = {'label': a.label, 'variable': nm['rain'], 'source_file': os.path.basename(a.mat), 'unit': 'mm/hr', 'time_ref': a.time_ref,
        'bounds': [[round(float(Sb), 6), round(float(Wb), 6)], [round(float(Nb), 6), round(float(Eb), 6)]],
        'vmax': a.vmax, 'legend': legend, 'times': [t.strftime('%Y-%m-%dT%H:%M') for t in times], 'frames': frames,
        'domain_max': [round(float(np.nanmax(g)), 2) for g in R], 'basins': basins, 'min': a.min, 'type': a.type,
        'grid': {'rows': int(H), 'cols': int(Wd), 'dlat_range': [round(float(np.min(np.abs(np.diff(lat)))), 5), round(float(np.max(np.abs(np.diff(lat)))), 5)], 'dlon': round(float(dx), 5)}}
json.dump(meta, open(f'{a.out}/rain.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(f"{len(frames)} frames {Wd}x{H}px, bounds {meta['bounds']}, {meta['times'][0]} -> {meta['times'][-1]}")
for c in ('19', '22', '20', '09'): b = basins[c]; print(f"  basin {c} {b['name']}: {b['cells']} cells, total {b['total']} mm, max {b['max_hr']} mm/hr")
