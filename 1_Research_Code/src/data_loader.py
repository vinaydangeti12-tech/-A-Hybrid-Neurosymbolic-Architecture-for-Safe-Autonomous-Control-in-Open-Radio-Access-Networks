"""
Data loading for the Network Operator KPIs time-series dataset (Zenodo 8147768).

File formats (per the dataset README):
  * rXXX.txt / sYYY.txt : two whitespace-separated columns
        <timestamp_seconds>  <kpi_value in [0, 1000]>
    timestamps are shifted so each series starts at 0; step = 300 s.
  * data_real_incidents.txt : "<series_id> <start_sample> <end_sample>"
    a labelled fault window; end == -1 means "until end of series".
  * data_*_info.txt : "<series_id> <kpi_type>"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from . import config as C


@dataclass
class KpiSeries:
    """A single KPI time series (one 'cell' stream)."""
    series_id: str
    kpi_type: str
    kind: str                      # "real" or "synthetic"
    timestamps: np.ndarray         # seconds, shifted to start at 0
    values: np.ndarray             # raw KPI value in [0, 1000]
    incidents: List[Tuple[int, int]] = field(default_factory=list)  # (start, end) sample idx
    area: str = ""                 # assigned Local Team (Area_A / Area_B)

    @property
    def n(self) -> int:
        return len(self.values)

    def label_vector(self) -> np.ndarray:
        """Binary anomaly labels (1 inside any labelled fault window)."""
        y = np.zeros(self.n, dtype=int)
        for start, end in self.incidents:
            end = self.n - 1 if end < 0 else min(end, self.n - 1)
            start = max(0, start)
            y[start:end + 1] = 1
        return y


def _read_info(path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) == 2:
                mapping[parts[0]] = parts[1]
    return mapping


def _read_incidents(path) -> Dict[str, List[Tuple[int, int]]]:
    inc: Dict[str, List[Tuple[int, int]]] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) == 3:
                sid, start, end = parts[0], int(parts[1]), int(parts[2])
                inc.setdefault(sid, []).append((start, end))
    return inc


def _read_series_file(path) -> Tuple[np.ndarray, np.ndarray]:
    arr = np.loadtxt(path)
    if arr.ndim == 1:               # single-row safety net
        arr = arr.reshape(1, -1)
    return arr[:, 0].astype(np.int64), arr[:, 1].astype(np.float64)


def _assign_area(index: int) -> str:
    """Deterministically split streams across the two Local Teams."""
    return C.AREAS[index % len(C.AREAS)]


def load_all(sample: bool | None = None) -> List[KpiSeries]:
    """
    Load every KPI series with its KPI type, anomaly labels and area assignment.

    sample : if True, load all 14 real series but only the first
             SAMPLE_N_SYNTHETIC synthetic series (keeps evaluation runs fast).
             Defaults to config.USE_SAMPLE.
    """
    if sample is None:
        sample = C.USE_SAMPLE

    real_info = _read_info(C.REAL_INFO_FILE)
    series_info = _read_info(C.SERIES_INFO_FILE)
    incidents = _read_incidents(C.INCIDENTS_FILE)

    out: List[KpiSeries] = []
    idx = 0

    # Real series (carry the labelled fault windows) — always load all of them.
    for sid in sorted(real_info, key=lambda s: int(s[1:])):
        path = C.REAL_DIR / f"{sid}.txt"
        if not path.exists():
            continue
        ts, vals = _read_series_file(path)
        out.append(KpiSeries(
            series_id=sid, kpi_type=real_info[sid], kind="real",
            timestamps=ts, values=vals,
            incidents=incidents.get(sid, []), area=_assign_area(idx),
        ))
        idx += 1

    # Synthetic series (clean traffic for Night/Festival regimes).
    syn_ids = sorted(series_info, key=lambda s: int(s[1:]))
    loaded_syn = 0
    for sid in syn_ids:
        path = C.SERIES_DIR / f"{sid}.txt"
        if not path.exists():       # s16 / s17 are absent from the archive
            continue
        if sample and loaded_syn >= C.SAMPLE_N_SYNTHETIC:
            break
        ts, vals = _read_series_file(path)
        out.append(KpiSeries(
            series_id=sid, kpi_type=series_info[sid], kind="synthetic",
            timestamps=ts, values=vals, incidents=[], area=_assign_area(idx),
        ))
        idx += 1
        loaded_syn += 1

    return out


def to_long_frame(series: List[KpiSeries]) -> pd.DataFrame:
    """Flatten a list of KpiSeries into a tidy long DataFrame (for EDA)."""
    rows = []
    for s in series:
        labels = s.label_vector()
        sample_idx = np.arange(s.n)
        rows.append(pd.DataFrame({
            "series_id": s.series_id,
            "kpi_type": s.kpi_type,
            "kind": s.kind,
            "area": s.area,
            "sample": sample_idx,
            "timestamp_s": s.timestamps,
            "value": s.values,
            "is_anomaly": labels,
        }))
    return pd.concat(rows, ignore_index=True)


if __name__ == "__main__":
    data = load_all(sample=False)
    n_real = sum(s.kind == "real" for s in data)
    n_syn = sum(s.kind == "synthetic" for s in data)
    n_inc = sum(len(s.incidents) for s in data)
    print(f"Loaded {len(data)} series: {n_real} real, {n_syn} synthetic")
    print(f"Total labelled fault windows: {n_inc}")
    for s in data[:3]:
        print(f"  {s.series_id:>4} | {s.kpi_type:<10} | {s.kind:<9} | "
              f"{s.area} | n={s.n} | incidents={s.incidents}")
