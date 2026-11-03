#!/usr/bin/env python3
"""
Convert a MATLAB rainfall file (.mat, v5/v7 or v7.3/HDF5) into dashboard-ready layers.

Usage
-----
  python rain_mat_to_dashboard.py inspect  rain.mat
  python rain_mat_to_dashboard.py convert  rain.mat -o out_dir [options]

Options for convert
  --rain NAME --lat NAME --lon NAME --time NAME   override auto-detected variable names
  --basin tapi_basin_boundary.geojson             polygon used for the basin-average series (default: none)
  --clip  tapi|thailand|none                      crop the grid before rendering (default: tapi)
  --vmax  FLOAT                                   top of the colour scale in mm (default: 99th percentile, rounded)
  --scale FLOAT                                   multiply values (e.g. 86400 for kg m-2 s-1 -> mm/day)
  --step  N                                       render every Nth time step (default 1)
  --start YYYY-MM-DD --end YYYY-MM-DD             time window
  --upsample N                                    pixel size multiplier for the PNG frames (default: auto)
  --min FLOAT                                     values below this are transparent (default 0.1)

Outputs (in out_dir)
  index.json        bounds (Leaflet [[S,W],[N,E]]), colour scale, units, list of frames with time + basin mean
  frames/*.png      one transparent PNG per time step, Web-Mercator-corrected rows, fixed colour scale
  basin_mean.csv    time, basin-average rainfall (if --basin given), domain mean, domain max
  legend.json       colour stops for the dashboard legend
For station data (time x stations) it writes stations.geojson + station_series.csv instead of frames.
"""
import argparse, json, math, os, re, sys, csv
from datetime import datetime, timedelta
import numpy as np

# ---------------------------------------------------------------- reading
def _load_v5(path):
    from scipy.io import loadmat
    raw = loadmat(path, squeeze_me=True, struct_as_record=False, mat_dtype=False)
    out = {}
    def walk(prefix, obj):
        if hasattr(obj, '_fieldnames'):                       # MATLAB struct
            for f in obj._fieldnames: walk(f"{prefix}.{f}", getattr(obj, f))
        elif isinstance(obj, np.ndarray) and obj.dtype == object and obj.size and all(isinstance(x, str) for x in obj.ravel()):
            out[prefix] = np.array([str(x) for x in obj.ravel()])
        elif isinstance(obj, (np.ndarray, int, float, str)):
            out[prefix] = np.asarray(obj)
    for k, v in raw.items():
        if not k.startswith('__'): walk(k, v)
    return out

def _load_v73(path):
    import h5py
    out = {}
    with h5py.File(path, 'r') as f:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset) and not name.startswith('#'):
                a = obj[()]
                cls = obj.attrs.get('MATLAB_class', b'')
                cls = cls.decode() if isinstance(cls, bytes) else str(cls)
                if a.dtype.kind == 'O':                        # cell array of refs (e.g. date strings)
                    try: a = np.array([''.join(chr(c) for c in f[r][()].ravel()) for r in a.ravel()])
                    except Exception: return
                elif cls == 'char':
                    a = np.array([''.join(chr(c) for c in a.ravel())]) if a.ndim <= 2 and min(a.shape) == 1 else \
                        np.array([''.join(chr(c) for c in row) for row in a.T])
                else:
                    a = a.T                                    # MATLAB is column-major: undo the transpose
                    if a.ndim == 2 and 1 in a.shape: a = a.ravel()
                out[name.replace('/', '.')] = np.asarray(a)
        f.visititems(visit)
    return out

def load_mat(path):
    with open(path, 'rb') as fh: head = fh.read(128)
    is_v73 = head[:8] == b'\x89HDF\r\n\x1a\n' or b'MATLAB 7.3' in head
    return (_load_v73(path) if is_v73 else _load_v5(path)), ('v7.3 (HDF5)' if is_v73 else 'v5/v7')

# ---------------------------------------------------------------- guessing
PAT = {
    'lat':  r'(^|[._])(lat|latitude|lats|y|ycoord|ylat|lat_?grid)\d*$',          # trailing digits allowed (lat1, date1 ...)
    'lon':  r'(^|[._])(lon|long|longitude|lons|x|xcoord|xlon|lon_?grid)\d*$',
    'time': r'(^|[._])(time|times|date|dates|datenum|dn|t|day|days|datetime|tt|yyyymmdd)\d*$',
    'rain': r'(^|[._])(rain|rainfall|precip|precipitation|pr|prcp|pre|p|rf|rr|tp|ppt|chirps|imerg|gsmap|aphro\w*|data|dat|value|values)\d*$',
}
def pick(vars_, kind, override=None):
    if override:
        if override not in vars_: sys.exit(f"variable '{override}' not found; have: {list(vars_)}")
        return override
    c = [k for k in vars_ if re.search(PAT[kind], k.lower())]
    if kind == 'rain':
        c = [k for k in c if vars_[k].dtype.kind in 'fiu' and vars_[k].ndim >= 2] or \
            sorted([k for k in vars_ if vars_[k].dtype.kind in 'fiu' and vars_[k].ndim >= 2], key=lambda k: -vars_[k].size)
    return max(sorted(c), key=lambda k: vars_[k].size) if c else None   # ties -> alphabetical first (dat1 before dat2)

def to_datetimes(t):
    t = np.asarray(t)
    if t.dtype.kind in 'US':
        out = []
        for s in t.ravel():
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%d-%b-%Y %H:%M:%S', '%d-%b-%Y', '%Y%m%d%H', '%Y%m%d', '%d/%m/%Y'):
                try: out.append(datetime.strptime(s.strip(), fmt)); break
                except ValueError: pass
            else: sys.exit(f"cannot parse date string '{s}'")
        return out, 'date strings'
    if t.ndim == 2 and t.shape[1] in (3, 4, 5, 6):            # [Y M D (h m s)] rows
        return [datetime(*[int(v) for v in row]) for row in t], 'Y M D [h m s] matrix'
    if t.ndim == 2 and t.shape[0] in (3, 4, 5, 6):
        return [datetime(*[int(v) for v in col]) for col in t.T], 'Y M D [h m s] matrix'
    t = t.astype(float).ravel()
    m = np.nanmedian(t)
    if 600000 < m < 800000:                                    # MATLAB datenum
        return [datetime(1, 1, 1) + timedelta(days=float(v) - 367) for v in t], 'MATLAB datenum'
    if 19000101 <= m <= 21001231:                              # yyyymmdd
        return [datetime.strptime(str(int(v)), '%Y%m%d') for v in t], 'yyyymmdd'
    if 1900000000 <= m <= 2100123123:                          # yyyymmddhh
        return [datetime.strptime(str(int(v)), '%Y%m%d%H') for v in t], 'yyyymmddhh'
    return None, f'unrecognised numeric time (median {m}); pass --start and the step, or fix in MATLAB'

# ---------------------------------------------------------------- colours
# rainfall ramp (mm), transparent below 0.1
RAMP = [(0.0, (198, 233, 255)), (0.15, (130, 202, 250)), (0.3, (60, 160, 235)), (0.45, (40, 120, 200)),
        (0.6, (110, 90, 200)), (0.75, (180, 70, 170)), (0.9, (230, 70, 110)), (1.0, (250, 150, 60))]
def ramp_lut(n=256):
    xs = np.linspace(0, 1, n); lut = np.zeros((n, 3))
    for i, x in enumerate(xs):
        for (a, ca), (b, cb) in zip(RAMP[:-1], RAMP[1:]):
            if a <= x <= b:
                f = (x - a) / (b - a); lut[i] = [ca[k] + (cb[k] - ca[k]) * f for k in range(3)]; break
    return lut.astype(np.uint8)

def nice(v):
    if v <= 0: return 1
    e = 10 ** math.floor(math.log10(v)); return float(min([1, 2, 2.5, 5, 10], key=lambda m: abs(m * e - v) if m * e >= v else 1e9) * e)

# ---------------------------------------------------------------- geometry
CLIPS = {'tapi': (98.2, 7.7, 100.1, 9.8), 'thailand': (97.2, 5.5, 105.8, 20.6)}
def merc_y(lat): return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
def nearest_index(coord, q):
    """index of the grid value nearest to each q; coord may be ascending or descending, regular or not"""
    c = np.asarray(coord, float); desc = c[0] > c[-1]; asc = c[::-1] if desc else c
    j = np.clip(np.searchsorted(asc, q), 1, len(asc) - 1)
    j = np.where(np.abs(asc[j - 1] - q) <= np.abs(asc[j] - q), j - 1, j)
    return (len(c) - 1 - j) if desc else j

def basin_mask(lon2, lat2, geojson):
    from shapely.geometry import shape
    from shapely import contains_xy
    g = json.load(open(geojson)); geom = shape(g['features'][0]['geometry'] if 'features' in g else g)
    return contains_xy(geom, lon2, lat2)

# ---------------------------------------------------------------- main steps
def inspect(path):
    v, fmt = load_mat(path)
    print(f"{path}  [{fmt}]  {len(v)} variables")
    for k, a in v.items():
        s = f"  {k:30s} {str(a.shape):18s} {a.dtype}"
        if a.dtype.kind in 'fiu' and a.size:
            s += f"  min={np.nanmin(a):.4g} max={np.nanmax(a):.4g}" + (f"  NaN={np.isnan(a).mean()*100:.0f}%" if a.dtype.kind == 'f' else '')
        elif a.size: s += f"  e.g. {a.ravel()[0]!r}"
        print(s)
    g = {k: pick(v, k) for k in ('rain', 'lat', 'lon', 'time')}
    print("\nauto-detected:", g)
    if g['time']:
        ts, how = to_datetimes(v[g['time']])
        print("time:", how, '' if ts is None else f"{ts[0]} -> {ts[-1]} ({len(ts)} steps)")
    return v, g

def convert(a):
    v, fmt = load_mat(a.mat)
    nm = {k: pick(v, k, getattr(a, k)) for k in ('rain', 'lat', 'lon', 'time')}
    print(f"[{fmt}] using {nm}")
    if not nm['rain']: sys.exit('no rainfall array found; use --rain')
    R = v[nm['rain']].astype('float32') * a.scale
    lat = v[nm['lat']].astype(float) if nm['lat'] else None
    lon = v[nm['lon']].astype(float) if nm['lon'] else None
    times, how = to_datetimes(v[nm['time']]) if nm['time'] else (None, 'none')
    if times is None:
        if not a.start: sys.exit(f"time: {how}. Use --time or --start")
        times = [datetime.fromisoformat(a.start) + timedelta(days=i) for i in range(max(R.shape))]
    nt = len(times)
    os.makedirs(a.out, exist_ok=True)

    # ---- station layout: R is (time, station) or (station, time) with 1-D lat/lon per station
    if R.ndim == 2 and lat is not None and lat.ndim == 1 and lon.ndim == 1 and len(lat) == len(lon) and nt in R.shape and len(lat) in R.shape:
        if R.shape[0] != nt: R = R.T
        sid = [f"S{i+1:03d}" for i in range(len(lat))]
        for k in v:
            if re.search(r'(id|name|code|station)s?$', k.lower()) and len(v[k]) == len(lat): sid = [str(int(x)) if isinstance(x, (float, np.floating)) and float(x).is_integer() else str(x) for x in v[k]]; break
        json.dump({'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'id': s, 'mean': float(np.nanmean(R[:, i])), 'max': float(np.nanmax(R[:, i]))},
                   'geometry': {'type': 'Point', 'coordinates': [float(lon[i]), float(lat[i])]}} for i, s in enumerate(sid)]}, open(f'{a.out}/stations.geojson', 'w'))
        with open(f'{a.out}/station_series.csv', 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['time'] + sid)
            for t, row in zip(times, R): w.writerow([t.isoformat()] + [None if np.isnan(x) else round(float(x), 2) for x in row])
        print(f"station data: {len(sid)} stations x {nt} steps -> stations.geojson, station_series.csv"); return

    # ---- gridded layout: find which axis is time / lat / lon
    if R.ndim != 3: sys.exit(f"rain array has shape {R.shape}; expected 3-D grid or 2-D stations")
    if lat.ndim == 2: lat = lat[:, 0] if np.ptp(lat[:, 0]) > 0 else lat[0, :]
    if lon.ndim == 2: lon = lon[0, :] if np.ptp(lon[0, :]) > 0 else lon[:, 0]
    lon = np.where(lon > 180, lon - 360, lon)
    ax_t = [i for i, n in enumerate(R.shape) if n == nt]
    ax_y = [i for i, n in enumerate(R.shape) if n == len(lat) and i not in ax_t[:1]]
    ax_x = [i for i, n in enumerate(R.shape) if n == len(lon) and i not in ax_t[:1] + ax_y[:1]]
    if not (ax_t and ax_y and ax_x): sys.exit(f"cannot match axes: rain {R.shape}, time {nt}, lat {len(lat)}, lon {len(lon)}")
    R = np.transpose(R, (ax_t[0], ax_y[0], ax_x[0]))           # -> (time, lat, lon)
    if lat[0] < lat[-1]: lat = lat[::-1]; R = R[:, ::-1, :]     # north up
    if lon[0] > lon[-1]: lon = lon[::-1]; R = R[:, :, ::-1]
    R[R < 0] = np.nan                                           # common fill values (-999, -9999)
    R[R > 5000] = np.nan

    # time window / step
    sel = [i for i, t in enumerate(times) if (not a.start or t >= datetime.fromisoformat(a.start)) and (not a.end or t <= datetime.fromisoformat(a.end))][::a.step]
    R = R[sel]; times = [times[i] for i in sel]

    # crop
    if a.clip != 'none':
        W, S, E, N = CLIPS[a.clip]
        iy = np.where((lat >= S) & (lat <= N))[0]; ix = np.where((lon >= W) & (lon <= E))[0]
        if len(iy) >= 2 and len(ix) >= 2:
            R = R[:, iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1]; lat = lat[iy[0]:iy[-1] + 1]; lon = lon[ix[0]:ix[-1] + 1]
        else: print(f"warning: grid does not cover clip '{a.clip}', keeping full extent")
    dy = abs(lat[1] - lat[0]) if len(lat) > 1 else 0.1; dx = abs(lon[1] - lon[0]) if len(lon) > 1 else 0.1
    dyS = abs(lat[-1] - lat[-2]) if len(lat) > 1 else dy                 # spacing may vary (e.g. WRF Mercator grid)
    Nb, Sb, Wb, Eb = lat[0] + dy / 2, lat[-1] - dyS / 2, lon[0] - dx / 2, lon[-1] + dx / 2

    # basin means
    LON, LAT = np.meshgrid(lon, lat)
    bm = None
    if a.basin:
        m = basin_mask(LON, LAT, a.basin)
        if m.sum() == 0:                                         # coarse grid: use cells touching the basin
            from shapely.geometry import shape, box
            g = json.load(open(a.basin)); geom = shape(g['features'][0]['geometry'] if 'features' in g else g)
            m = np.array([[geom.intersects(box(x - dx / 2, y - dy / 2, x + dx / 2, y + dy / 2)) for x in lon] for y in lat])
        bm = np.nanmean(np.where(m[None], R, np.nan), axis=(1, 2))
        print(f"basin mask: {int(m.sum())} cells")

    vmax = a.vmax or nice(float(np.nanpercentile(R[R > 0.1], 99)) if np.any(R > 0.1) else 1)
    lut = ramp_lut()

    # web-mercator row mapping so the PNG lines up in Leaflet
    up = a.upsample or max(1, int(round(600 / max(R.shape[1:]))))
    H = R.shape[1] * up; Wd = R.shape[2] * up
    yN, yS = merc_y(Nb), merc_y(Sb)
    row_lat = np.degrees(2 * np.arctan(np.exp(yN - (np.arange(H) + .5) / H * (yN - yS))) - np.pi / 2)
    src_r = nearest_index(lat, row_lat)                                  # works for regular and irregular latitude spacing
    src_c = np.clip(((np.arange(Wd) + .5) / up).astype(int), 0, R.shape[2] - 1)

    from PIL import Image
    os.makedirs(f'{a.out}/frames', exist_ok=True)
    frames = []
    fmt_t = '%Y%m%d%H%M' if len(times) > 1 and (times[1] - times[0]) < timedelta(days=1) else '%Y%m%d'
    for k, (t, grid) in enumerate(zip(times, R)):
        g = grid[src_r][:, src_c]
        idx = np.clip(np.nan_to_num(g, nan=0) / vmax * 255, 0, 255).astype(int)
        rgba = np.zeros(g.shape + (4,), np.uint8)
        rgba[..., :3] = lut[idx]
        alpha = np.where(np.isnan(g) | (g < a.min), 0, np.clip(120 + 135 * np.sqrt(np.clip(g / vmax, 0, 1)), 0, 235))
        rgba[..., 3] = alpha.astype(np.uint8)
        fn = f"frames/rain_{t.strftime(fmt_t)}.png"
        Image.fromarray(rgba).save(f'{a.out}/{fn}', optimize=True)
        frames.append({'time': t.isoformat(), 'file': fn,
                       'basin_mean': None if bm is None or np.isnan(bm[k]) else round(float(bm[k]), 2),
                       'domain_mean': round(float(np.nanmean(grid)), 2), 'domain_max': round(float(np.nanmax(grid)), 2)})
    stops = [{'value': round(vmax * p, 2), 'color': '#%02x%02x%02x' % c} for p, c in RAMP]
    meta = {'source_file': os.path.basename(a.mat), 'mat_format': fmt, 'variables': nm, 'time_format': how,
            'bounds': [[round(float(Sb), 6), round(float(Wb), 6)], [round(float(Nb), 6), round(float(Eb), 6)]], 'grid_deg': [round(float(dx), 6), round(float(dy), 6)],
            'shape': list(R.shape), 'units': 'mm' + (f' (x{a.scale})' if a.scale != 1 else ''), 'vmax': float(vmax),
            'legend': stops, 'frames': frames}
    json.dump(meta, open(f'{a.out}/index.json', 'w'), indent=1)
    json.dump(stops, open(f'{a.out}/legend.json', 'w'))
    with open(f'{a.out}/basin_mean.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['time', 'basin_mean_mm', 'domain_mean_mm', 'domain_max_mm'])
        for fr in frames: w.writerow([fr['time'], fr['basin_mean'], fr['domain_mean'], fr['domain_max']])
    print(f"{len(frames)} frames, grid {R.shape[1]}x{R.shape[2]} ({dx:.4g}°), vmax {vmax} mm, bounds {meta['bounds']} -> {a.out}")

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('cmd', choices=['inspect', 'convert']); p.add_argument('mat')
    p.add_argument('-o', '--out', default='rain_out')
    for k in ('rain', 'lat', 'lon', 'time'): p.add_argument(f'--{k}')
    p.add_argument('--basin'); p.add_argument('--clip', default='tapi', choices=['tapi', 'thailand', 'none'])
    p.add_argument('--vmax', type=float); p.add_argument('--scale', type=float, default=1.0)
    p.add_argument('--step', type=int, default=1); p.add_argument('--start'); p.add_argument('--end')
    p.add_argument('--upsample', type=int)
    p.add_argument('--min', type=float, default=0.1, help='values below this are transparent (default 0.1)')
    a = p.parse_args()
    inspect(a.mat) if a.cmd == 'inspect' else convert(a)
