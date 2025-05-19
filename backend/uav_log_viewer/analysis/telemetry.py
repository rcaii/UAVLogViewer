from __future__ import annotations
"""Telemetry Analytics Toolkit
================================
A collection of **pure‑Python** helper functions that compute commonly needed
metrics from UAV telemetry dictionaries (same structure your backend receives
after parsing the `.tlog` / `.bin`).

▸ *No heavy deps* – only `numpy`.
▸ *Composable* – every helper is side‑effect free.
▸ *Unit‑aware* – cm→m, mV→V, rad→deg, ms→s.
▸ *Graceful fallback* – functions return `None` when data is missing.

```python
from telemetry import compute_metrics
summary = compute_metrics(tele)
# {'flight_duration_s': 312.4, 'altitude_max_m': 123.8, ...}
```
"""

from typing import Dict, Any, Tuple, List, Optional, Sequence
import numpy as np

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _get_msg(tele: Dict[str, Any], msg: str) -> Optional[Dict[str, Sequence[Any]]]:
    return tele.get("messages", {}).get(msg)


def _to_np(arr: Sequence[Any], dtype=float) -> np.ndarray:
    if isinstance(arr, np.ndarray):
        return arr.astype(dtype, copy=False)
    return np.asarray(arr, dtype=dtype)

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def time_vector(tele: Dict[str, Any]) -> Optional[np.ndarray]:
    sys_time = _get_msg(tele, "SYSTEM_TIME")
    if sys_time and "time_boot_ms" in sys_time:
        return _to_np(sys_time["time_boot_ms"], float) / 1_000.0
    gpos = _get_msg(tele, "GLOBAL_POSITION_INT")
    if gpos and "time_boot_ms" in gpos:
        return _to_np(gpos["time_boot_ms"], float) / 1_000.0
    return None

# ---------------------------------------------------------------------------
# Basic summaries
# ---------------------------------------------------------------------------

def flight_duration(tele: Dict[str, Any]) -> Optional[float]:
    t = time_vector(tele)
    if t is None or t.size < 2:
        return None
    return float(t[-1] - t[0])

# ---------------------------------------------------------------------------
# Altitude metrics
# ---------------------------------------------------------------------------

def altitude_vector(tele: Dict[str, Any], source: str = "GLOBAL_POSITION_INT.alt") -> Optional[np.ndarray]:
    msg_name, field = source.split(".")
    msg = _get_msg(tele, msg_name)
    if msg is None or field not in msg:
        return None
    alt = _to_np(msg[field], float)
    if source.startswith("GLOBAL_POSITION_INT"):
        alt = alt / 1_000.0  # cm → m
    return alt


def altitude_stats(tele: Dict[str, Any], source: str = "GLOBAL_POSITION_INT.alt") -> Optional[Tuple[float, float, float]]:
    alt = altitude_vector(tele, source)
    if alt is None or alt.size == 0:
        return None
    return float(alt.min()), float(alt.max()), float(alt.mean())


def average_altitude_time_window(tele: Dict[str, Any], *, start_s: float, end_s: float, source: str = "GLOBAL_POSITION_INT.alt") -> Optional[float]:
    alt = altitude_vector(tele, source)
    t = time_vector(tele)
    if alt is None or t is None or alt.size != t.size:
        return None
    mask = (t >= start_s) & (t <= end_s)
    if not mask.any():
        return None
    return float(alt[mask].mean())

# ---------------------------------------------------------------------------
# Vertical speed
# ---------------------------------------------------------------------------

def vertical_speed_vector(tele: Dict[str, Any]) -> Optional[np.ndarray]:
    alt = altitude_vector(tele)
    t = time_vector(tele)
    if alt is None or t is None or alt.size < 2:
        return None
    return np.diff(alt) / np.diff(t)


def max_climb_rate(tele: Dict[str, Any]) -> Optional[float]:
    vs = vertical_speed_vector(tele)
    if vs is None:
        return None
    return float(np.nanmax(vs))


def max_descent_rate(tele: Dict[str, Any]) -> Optional[float]:
    vs = vertical_speed_vector(tele)
    if vs is None:
        return None
    return float(np.nanmin(vs))

# ---------------------------------------------------------------------------
# Horizontal movement
# ---------------------------------------------------------------------------

def velocity_vectors(tele: Dict[str, Any]) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    gpos = _get_msg(tele, "GLOBAL_POSITION_INT")
    if gpos is None or not all(k in gpos for k in ("vx", "vy", "vz")):
        return None
    vx = _to_np(gpos["vx"], float) / 100.0
    vy = _to_np(gpos["vy"], float) / 100.0
    vz = _to_np(gpos["vz"], float) / 100.0
    return vx, vy, vz


def groundspeed_vector(tele: Dict[str, Any]) -> Optional[np.ndarray]:
    vv = velocity_vectors(tele)
    if vv is None:
        return None
    vx, vy, _ = vv
    return np.hypot(vx, vy)


def groundspeed_stats(tele: Dict[str, Any]) -> Optional[Tuple[float, float, float]]:
    gs = groundspeed_vector(tele)
    if gs is None or gs.size == 0:
        return None
    return float(gs.min()), float(gs.max()), float(gs.mean())


def distance_travelled_2d(tele: Dict[str, Any]) -> Optional[float]:
    gs = groundspeed_vector(tele)
    t = time_vector(tele)
    if gs is None or t is None or gs.size != t.size:
        return None
    return float(np.sum(gs[1:] * np.diff(t)))


def distance_travelled_3d(tele: Dict[str, Any]) -> Optional[float]:
    vv = velocity_vectors(tele)
    t = time_vector(tele)
    if vv is None or t is None:
        return None
    speed = np.sqrt(vv[0] ** 2 + vv[1] ** 2 + vv[2] ** 2)
    return float(np.sum(speed[1:] * np.diff(t)))

# ---------------------------------------------------------------------------
# Battery & power
# ---------------------------------------------------------------------------

def battery_stats(tele: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    batt = _get_msg(tele, "BATTERY_STATUS")
    if batt is None or "voltages" not in batt:
        return None
    v = _to_np(batt["voltages"], float) / 1000.0
    c = _to_np(batt.get("current_battery", [np.nan] * len(v)), float) / 100.0
    return float(np.nanmin(v)), float(np.nanmax(c))

# ---------------------------------------------------------------------------
# GPS quality
# ---------------------------------------------------------------------------

def satellite_visibility_stats(tele: Dict[str, Any]) -> Optional[Tuple[int, int, float]]:
    gps = _get_msg(tele, "GPS_RAW_INT")
    if gps is None or "satellites_visible" not in gps:
        return None
    sats = _to_np(gps["satellites_visible"], int)
    return int(sats.min()), int(sats.max()), float(sats.mean())

# ---------------------------------------------------------------------------
# Attitude
# ---------------------------------------------------------------------------

def attitude_stats(tele: Dict[str, Any]) -> Optional[Dict[str, Tuple[float, float]]]:
    att = _get_msg(tele, "ATTITUDE")
    if att is None:
        return None
    out: Dict[str, Tuple[float, float]] = {}
    for f in ("roll", "pitch", "yaw"):
        if f in att:
            arr = _to_np(att[f], float) * 180.0 / np.pi
            out[f] = (float(arr.mean()), float(arr.std()))
    return out

# ---------------------------------------------------------------------------
# Metric aggregator – produces flat dict for LLM
# ---------------------------------------------------------------------------

_METRIC_FUNCS = [
    ("flight_duration_s", flight_duration),
    ("altitude_stats", altitude_stats),
    ("max_climb_rate_mps", max_climb_rate),
    ("max_descent_rate_mps", max_descent_rate),
    ("groundspeed_stats", groundspeed_stats),
    ("distance_2d_m", distance_travelled_2d),
    ("distance_3d_m", distance_travelled_3d),
    ("battery_stats", battery_stats),
    ("satellite_visibility", satellite_visibility_stats),
    ("attitude_stats", attitude_stats),
]


def compute_metrics(tele: Dict[str, Any]) -> Dict[str, Any]:
    """Return **flat dict** of every metric we can compute from *tele*.

    Keys are snake‑case descriptive names suitable for LLM prompt‑stuffing.
    """
    results: Dict[str, Any] = {}

    for name, fn in _METRIC_FUNCS:
        try:
            val = fn(tele)
        except Exception:
            continue
        if val is None:
            continue
        # Flatten based on return type.
        if isinstance(val, tuple):
            if name.endswith("_stats"):
                # Assume (min, max, mean)
                base = name.replace("_stats", "")
                if len(val) == 3:
                    results[f"{base}_min"] = val[0]
                    results[f"{base}_max"] = val[1]
                    results[f"{base}_mean"] = val[2]
                elif len(val) == 2:
                    results[f"{base}_min"] = val[0]
                    results[f"{base}_max"] = val[1]
            elif name == "battery_stats":
                results["battery_min_voltage_v"] = val[0]
                results["battery_max_current_a"] = val[1]
            else:
                results[name] = val
        elif isinstance(val, dict):
            for k, v in val.items():
                if isinstance(v, tuple) and len(v) == 2:
                    results[f"{k}_mean_deg"] = v[0]
                    results[f"{k}_std_deg"] = v[1]
                else:
                    results[f"{k}"] = v
        else:
            results[name] = val

    return results

