"""Synthetic 10-day forecast for the Nan basin, used only to demonstrate the dashboard layout.
Every number here is invented. Replace with outputs of activities 1-2 (AI rain fusion, HEC-HMS/HEC-RAS)."""
import json, numpy as np, geopandas as gpd
from shapely.geometry import Point
from shapely import contains_xy
rng = np.random.default_rng(42)

B = gpd.read_file('/home/claude/basins22/tha_basins22_onwr_detail.geojson')
nan = B[B.code == '09'].geometry.iloc[0]
amph = gpd.read_file('/home/claude/nan/nan_basin_amphoe.geojson')

ISSUE = '2026-09-14T07:00:00+07:00'      # hypothetical event
DAYS = ['2026-09-%02d' % d for d in range(14, 25)]   # D0..D10
ND = len(DAYS)

# ---------------- rainfall grid 0.1 deg ----------------
W, E, S, N, d = 99.5, 101.4, 15.65, 19.7, 0.1
lons = np.round(np.arange(W + d / 2, E, d), 3); lats = np.round(np.arange(N - d / 2, S, -d), 3)
LON, LAT = np.meshgrid(lons, lats)
mask = contains_xy(nan.buffer(0.05), LON, LAT)

def storm(cx, cy, sx, sy, amp):
    return amp * np.exp(-(((LON - cx) / sx) ** 2 + ((LAT - cy) / sy) ** 2))
# truth: monsoon-trough event over upper Nan D2-D5, second pulse over lower basin D6-D7
track = [(100.9, 19.4, 0.0), (100.8, 19.2, 18), (100.85, 19.0, 55), (100.8, 18.8, 92), (100.75, 18.6, 78),
         (100.6, 18.2, 40), (100.35, 17.2, 52), (100.3, 16.8, 46), (100.4, 16.5, 18), (100.5, 16.3, 6), (100.5, 16.0, 3)]
truth = []
for k, (cx, cy, a) in enumerate(track):
    f = storm(cx, cy, 0.55, 0.45, a) + storm(cx - 0.4, cy + 0.3, 0.3, 0.25, a * 0.35) + rng.gamma(0.6, 2.2, LON.shape)
    truth.append(np.clip(f, 0, None))
truth = np.array(truth)
def source(bias, dx, dy, lag, noise):
    out = []
    for k in range(ND):
        kk = min(max(k - lag, 0), ND - 1)
        cx, cy, a = track[kk]
        f = (storm(cx + dx, cy + dy, 0.6, 0.5, a * bias) + storm(cx + dx - 0.4, cy + dy + 0.3, 0.3, 0.25, a * bias * 0.3)
             + rng.gamma(0.6, 2.2 * noise, LON.shape))
        out.append(np.clip(f, 0, None))
    return np.array(out)
src = {
    'wrf':   source(1.25, 0.25, 0.15, 0, 1.3),
    'ecmwf': source(0.80, -0.15, -0.2, 0, 0.8),
    'gfs':   source(0.65, 0.35, -0.35, 1, 1.0),
}
src['fused'] = np.clip(0.75 * truth + 0.25 * (src['wrf'] + src['ecmwf'] + src['gfs']) / 3 + rng.normal(0, 1.0, truth.shape), 0, None)

basin_mean = {k: [round(float(v[i][mask].mean()), 1) for i in range(ND)] for k, v in src.items()}
grid = {'lon0': float(lons[0]), 'lat0': float(lats[0]), 'd': d, 'nx': len(lons), 'ny': len(lats),
        'mask': ''.join('1' if m else '0' for m in mask.ravel()),
        'rain': {k: [[round(float(x), 1) for x in np.where(mask, v[i], 0).ravel()] for i in range(ND)] for k, v in src.items()}}

# ---------------- stations (demo locations along the Nan main stem) ----------------
ST = [
    # id, name_th, name_en, lon, lat, kind, watch, bank, base, peak_day, peak_amp, spread
    ('S1', 'อ.ท่าวังผา', 'Tha Wang Pha', 100.80, 19.12, 'river', 600, 850, 260, 3.0, 980, 0.18),
    ('S2', 'อ.เมืองน่าน', 'Mueang Nan', 100.78, 18.78, 'river', 900, 1250, 380, 3.8, 1450, 0.20),
    ('S3', 'อ.เวียงสา', 'Wiang Sa', 100.75, 18.57, 'river', 1150, 1600, 450, 4.3, 1550, 0.22),
    ('S4', 'อ.นาน้อย', 'Na Noi', 100.72, 18.32, 'river', 1300, 1800, 520, 4.8, 1500, 0.24),
    ('D1', 'เขื่อนสิริกิติ์ (ปริมาณน้ำไหลเข้า)', 'Sirikit Dam inflow', 100.56, 17.77, 'dam', None, None, 420, 5.3, 2100, 0.25),
    ('S5', 'อ.เมืองอุตรดิตถ์', 'Mueang Uttaradit', 100.10, 17.62, 'river', 700, 1000, 380, 6.2, 520, 0.28),
    ('S6', 'อ.พรหมพิราม', 'Phrom Phiram', 100.20, 17.03, 'river', 650, 900, 330, 6.8, 560, 0.30),
    ('S7', 'อ.เมืองพิษณุโลก', 'Mueang Phitsanulok', 100.26, 16.82, 'river', 700, 950, 360, 7.4, 600, 0.30),
    ('S8', 'อ.เมืองพิจิตร', 'Mueang Phichit', 100.35, 16.44, 'river', 600, 820, 320, 8.2, 470, 0.32),
    ('S9', 'อ.บางมูลนาก', 'Bang Mun Nak', 100.38, 16.03, 'river', 560, 760, 300, 9.0, 420, 0.34),
]
t = np.arange(-7, ND)           # days relative to issue
def pulse(t, t0, amp, width=1.6):
    x = np.clip(t - t0 + 2.2 * width, 0, None)
    g = (x / (2.2 * width)) ** 3 * np.exp(-3 * (x / (2.2 * width) - 1))
    return amp * g
stations = []
for sid, th, en, lon, lat, kind, watch, bank, base, pk, amp, spr in ST:
    obs_true = base * (1 + 0.05 * np.sin(t / 2.0)) + pulse(t, pk, amp)
    obs = [round(float(v * (1 + rng.normal(0, 0.03))), 0) for v, tt in zip(obs_true, t) if tt <= 0]
    members = []
    for m in range(20):
        a = amp * rng.lognormal(0, spr); dt = rng.normal(0, 0.45 + 0.05 * pk)
        q = base * (1 + 0.05 * np.sin(t / 2.0)) + pulse(t, pk + dt, a)
        q = q[t >= 0]; q[0] = obs[-1]
        members.append([round(float(v), 0) for v in q])
    st = {'id': sid, 'name_th': th, 'name_en': en, 'lon': lon, 'lat': lat, 'kind': kind, 'unit': 'm³/s',
          'watch': watch, 'bank': bank, 'obs': obs, 'members': members}
    if kind == 'dam':
        st.update({'capacity_mcm': 9510, 'storage_pct': [72.4, 72.9, 73.6, 74.9, 76.8, 78.6, 79.9, 80.8, 81.3, 81.6, 81.8],
                   'urc_pct': 84.0, 'release_m3s': 260})
    stations.append(st)

# amphoe -> nearest station (within 35 km), same-province preference skipped for simplicity
sxy = np.array([[s['lon'], s['lat']] for s in stations if s['kind'] == 'river'])
sid = [s['id'] for s in stations if s['kind'] == 'river']
assign = {}
for r in amph.itertuples():
    dd = np.hypot((sxy[:, 0] - r.clon) * 105.5, (sxy[:, 1] - r.clat) * 110.6)
    i = int(dd.argmin()); assign[r.pcode] = sid[i] if dd[i] < 35 else None

skill = {'note': 'ตัวอย่างการแสดงผลเท่านั้น จะแทนด้วยผลประเมินจริงตาม KPI กิจกรรมที่ 1–2',
         'rain': {'metric': ['POD', 'FAR', 'CSI', 'RMSE (มม./วัน)'], 'threshold': 'ฝนหนัก ≥ 35 มม./วัน',
                  'rows': {'fused': [0.82, 0.21, 0.67, 9.8], 'wrf': [0.74, 0.38, 0.51, 15.2], 'ecmwf': [0.69, 0.24, 0.56, 12.1], 'gfs': [0.58, 0.33, 0.45, 16.9]}},
         'flow': {'metric': ['NSE', 'KGE', 'PBIAS (%)'], 'station': 'S2',
                  'rows': {'fused': [0.81, 0.79, -4.2], 'wrf': [0.62, 0.58, 18.5], 'ecmwf': [0.70, 0.66, -11.3], 'gfs': [0.48, 0.51, -23.0]}}}

out = {'demo': True, 'basin': {'code': '09', 'name_th': 'น่าน', 'name_en': 'Nan'}, 'issued': ISSUE, 'days': DAYS,
       'sources': {'fused': 'AI หลอมรวมหลายแหล่ง', 'wrf': 'TMD-WRF', 'ecmwf': 'ECMWF', 'gfs': 'GFS'},
       'grid': grid, 'basin_mean': basin_mean, 'stations': stations, 'amphoe_station': assign, 'skill': skill}
json.dump(out, open('/home/claude/nan/nan_forecast_demo.json', 'w'), ensure_ascii=False, separators=(',', ':'))
import os; print(os.path.getsize('/home/claude/nan/nan_forecast_demo.json'), 'bytes; grid', grid['nx'], 'x', grid['ny'], 'cells in basin', int(mask.sum()))
print('basin mean fused', basin_mean['fused'])
for s in stations: print(s['id'], s['name_en'], 'obs', s['obs'][-1], 'p50 max', int(np.median(np.max(s['members'], axis=1))), 'bank', s['bank'])
print('amphoe assigned', sum(v is not None for v in assign.values()), '/', len(assign))
