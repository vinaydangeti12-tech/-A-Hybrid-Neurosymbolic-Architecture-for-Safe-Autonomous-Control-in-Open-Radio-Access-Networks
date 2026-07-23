"""
Data Loader for TRACE_v2
Loads and processes the Network Operator KPIs dataset.

Dataset: network_operator_KPIs.zip
  data_real/r1-r14.txt  — 14 real time series with documented anomalies
  data_series/s1-s50.txt — 50 synthetic time series
  4 KPI types: internet traffic, sessions, VPN traffic, downstream traffic

Format per file: two columns (timestamp_seconds, kpi_value)
  - 10,738 samples per series
  - 5-minute intervals (300 s between samples)
  - Values normalised to 0-1000 range
  - Total span: ~38 days per series
"""

import math
import os
import shutil
import threading
import zipfile
from typing import Dict, List, Optional, Tuple

# Path to the dataset (relative to this file)
_HERE = os.path.dirname(os.path.abspath(__file__))
# Local working cache the demo reads from.
_EXTRACT_DIR = os.path.join(_HERE, "_data_cache", "network_operator_KPIs_time_series_dataset")
# Primary source: the already-extracted dataset that ships with the Report_docs
# project folder (the canonical "main" docs/data location used by H-TRACE/src).
_REPORT_DOCS_DATA = os.path.abspath(os.path.join(
    _HERE, "..", "..", "Report_docs", "data", "raw", "extracted",
    "network_operator_KPIs_time_series_dataset",
))
# Preferred source for this submission: the dataset bundled at <submission>/3_Dataset.
_BUNDLED_DATA = os.path.abspath(os.path.join(
    _HERE, "..", "..", "3_Dataset", "network_operator_KPIs_time_series_dataset",
))
# Fallback source: a zipped copy, if one is present alongside the Report_docs data.
_DATASET_ZIP = os.path.abspath(os.path.join(
    _HERE, "..", "..", "Report_docs", "data", "raw", "network_operator_KPIs.zip",
))

# Nominal samples per series (used as the end bound for open-ended "-1" incidents).
_SERIES_LENGTH = 10738

_series_cache: Dict[str, List[Tuple[int, float]]] = {}
_incidents_cache: Optional[List[Dict]] = None
# Guards cache population — the preload thread and Flask request threads both
# call the loaders, so without this two threads could parse the same file twice
# or publish a half-built incidents list. Must NOT be held across calls to
# _ensure_extracted from outside (the Lock is non-reentrant).
_cache_lock = threading.Lock()


def _ensure_extracted() -> bool:
    """Make the Zenodo KPI dataset available in the local cache.

    Resolution order:
      1. Already present in the local ``_data_cache`` → use it.
      2. Copy from the dataset bundled with this submission (3_Dataset/).
      3. Copy from the Report_docs extracted dataset (the canonical main folder).
      4. Extract a ZIP fallback if one happens to be present.
    """
    if os.path.isdir(os.path.join(_EXTRACT_DIR, "data_real")):
        return True

    _cache_parent = os.path.dirname(_EXTRACT_DIR)
    os.makedirs(_cache_parent, exist_ok=True)

    # 2) Copy from the dataset bundled in this submission (3_Dataset/).
    if os.path.isdir(os.path.join(_BUNDLED_DATA, "data_real")):
        shutil.copytree(_BUNDLED_DATA, _EXTRACT_DIR, dirs_exist_ok=True)
        print(f"[data_loader] Copied dataset from {_BUNDLED_DATA}")
        return os.path.isdir(os.path.join(_EXTRACT_DIR, "data_real"))

    # 3) Copy from the Report_docs project data.
    if os.path.isdir(os.path.join(_REPORT_DOCS_DATA, "data_real")):
        shutil.copytree(_REPORT_DOCS_DATA, _EXTRACT_DIR, dirs_exist_ok=True)
        print(f"[data_loader] Copied dataset from {_REPORT_DOCS_DATA}")
        return os.path.isdir(os.path.join(_EXTRACT_DIR, "data_real"))

    # 3) Extract a ZIP fallback if available.
    if os.path.isfile(_DATASET_ZIP):
        with zipfile.ZipFile(_DATASET_ZIP, "r") as zf:
            zf.extractall(_cache_parent)
        print(f"[data_loader] Extracted dataset to {_cache_parent}")
        return os.path.isdir(os.path.join(_EXTRACT_DIR, "data_real"))

    print(f"[data_loader] WARNING: dataset not found at {_EXTRACT_DIR}")
    return False


def _read_series_file(path: str) -> List[Tuple[int, float]]:
    """Parse a two-column KPI file into (timestamp_s, value) tuples."""
    result = []
    with open(path, "r") as fh:
        for line in fh:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    result.append((int(float(parts[0])), float(parts[1])))
                except (ValueError, IndexError):
                    continue          # skip headers / malformed lines
    return result


def _synthetic_fallback(n: int = 1440) -> List[Tuple[int, float]]:
    """Generate a realistic synthetic series when real data is unavailable."""
    return [
        (
            i * 300,
            max(20.0, min(980.0,
                500 + 280 * math.sin(math.pi * (i % 288) / 144)
                + 40 * math.sin(math.pi * i / 12)
                + ((i * 7919 + 3571) % 100 - 50) * 0.6
            )),
        )
        for i in range(n)
    ]


def load_real_series(series_id: int) -> List[Tuple[int, float]]:
    """Load real anomaly series r{series_id} (1-14)."""
    key = f"r{series_id}"
    cached = _series_cache.get(key)
    if cached is not None:
        return cached
    with _cache_lock:
        if key not in _series_cache:
            if _ensure_extracted():
                path = os.path.join(_EXTRACT_DIR, "data_real", f"r{series_id}.txt")
                _series_cache[key] = _read_series_file(path) if os.path.isfile(path) else _synthetic_fallback()
            else:
                _series_cache[key] = _synthetic_fallback()
        return _series_cache[key]


def load_synthetic_series(series_id: int) -> List[Tuple[int, float]]:
    """Load synthetic series s{series_id} (1-50)."""
    key = f"s{series_id}"
    cached = _series_cache.get(key)
    if cached is not None:
        return cached
    with _cache_lock:
        if key not in _series_cache:
            if _ensure_extracted():
                # dataset uses the "data_series" directory name
                path = os.path.join(_EXTRACT_DIR, "data_series", f"s{series_id}.txt")
                _series_cache[key] = _read_series_file(path) if os.path.isfile(path) else _synthetic_fallback()
            else:
                _series_cache[key] = _synthetic_fallback()
        return _series_cache[key]


def load_incidents() -> List[Dict]:
    """Load documented anomaly incidents from data_real_incidents.txt."""
    global _incidents_cache
    if _incidents_cache is not None:
        return _incidents_cache

    with _cache_lock:
        if _incidents_cache is not None:
            return _incidents_cache

        # Build into a local list and publish only when complete, so a
        # concurrent reader never sees a half-parsed cache.
        incidents: List[Dict] = []
        if _ensure_extracted():
            path = os.path.join(_EXTRACT_DIR, "data_real_incidents.txt")
            if os.path.isfile(path):
                with open(path, "r") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split()
                        if len(parts) >= 3:
                            try:
                                start, end = int(parts[1]), int(parts[2])
                            except (ValueError, IndexError):
                                continue          # skip headers / malformed lines
                            # -1 means the anomaly extends to the end of the series
                            incidents.append({
                                "series": parts[0],
                                "start_sample": start,
                                "end_sample": end if end >= 0 else _SERIES_LENGTH,
                            })
        _incidents_cache = incidents
        return _incidents_cache


# ------------------------------------------------------------------
# Scenario-specific slices
# ------------------------------------------------------------------

def get_night_mode_samples(series_id: int = 1) -> List[float]:
    """
    Extract samples for Scenario A (Night Mode): 02:00-05:00 AM.
    Each day has 288 five-minute samples.
    02:00 = sample 24 per day, 05:00 = sample 60 per day.
    """
    series = load_real_series(series_id)
    DAY_SAMPLES = 288
    night_start = 24   # 02:00
    night_end = 60     # 05:00

    values: List[float] = []
    n_days = len(series) // DAY_SAMPLES
    for day in range(n_days):
        base = day * DAY_SAMPLES
        for i in range(night_start, min(night_end, DAY_SAMPLES)):
            idx = base + i
            if idx < len(series):
                values.append(series[idx][1])

    return values[:2000] if values else [v for _, v in _synthetic_fallback(500)]


def get_festival_mode_samples(series_id: int = 1, surge_factor: float = 5.0) -> List[float]:
    """
    Extract samples for Scenario B (Festival Mode): peak-hour traffic × surge_factor.
    Peak hours: 08:00-22:00, surge_factor default = 5.0 (500% increase).
    """
    series = load_synthetic_series(series_id)
    DAY_SAMPLES = 288
    peak_start = 96    # 08:00
    peak_end = 264     # 22:00

    values: List[float] = []
    n_days = min(7, len(series) // DAY_SAMPLES)
    for day in range(n_days):
        base = day * DAY_SAMPLES
        for i in range(peak_start, min(peak_end, DAY_SAMPLES)):
            idx = base + i
            if idx < len(series):
                surged = min(1000.0, series[idx][1] * surge_factor)
                values.append(surged)

    return values[:2000] if values else [min(1000.0, v * surge_factor) for _, v in _synthetic_fallback(500)]


def get_anomaly_samples(series_id: int = 1) -> Tuple[List[float], List[Tuple[int, int]]]:
    """
    Get all samples for Scenario C (Self-Healing) with annotated anomaly windows.
    Returns (all_kpi_values, [(start_sample, end_sample), ...]).
    """
    series = load_real_series(series_id)
    incidents = load_incidents()
    series_name = f"r{series_id}"
    anomaly_ranges = [
        (inc["start_sample"], inc["end_sample"])
        for inc in incidents
        if inc["series"] == series_name
    ]
    values = [v for _, v in series]
    return values, anomaly_ranges
