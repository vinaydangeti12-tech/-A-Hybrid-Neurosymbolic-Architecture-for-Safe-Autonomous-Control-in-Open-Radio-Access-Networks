"""
Exploratory Data Analysis for the Network Operator KPIs dataset.

Produces (into results/figures and results/tables):
  * dataset_overview.csv     — per-series summary (length, missing %, stats)
  * eda_summary.md           — human-readable dataset summary
  * fig_kpi_distributions    — value distribution per KPI type
  * fig_daily_profile        — mean diurnal profile (Night vs Festival regimes)
  * fig_real_with_anomalies  — sample real series with fault windows shaded
  * fig_series_lengths       — record-length / coverage overview
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C
from .data_loader import KpiSeries, load_all
from .preprocessing import build_feature_frame

plt.rcParams.update({"figure.dpi": 120, "savefig.bbox": "tight", "font.size": 9})
KPI_COLORS = {"internet": "#1f77b4", "sessions": "#2ca02c",
              "vpn": "#9467bd", "downstream": "#d62728"}


def per_series_summary(series_list) -> pd.DataFrame:
    rows = []
    for s in series_list:
        df = build_feature_frame(s)
        rows.append({
            "series_id": s.series_id,
            "kpi_type": s.kpi_type,
            "kind": s.kind,
            "area": s.area,
            "n_raw": s.n,
            "n_grid": len(df),
            "missing_pct": 100.0 * df["was_missing"].mean(),
            "days": round(len(df) / C.SAMPLES_PER_DAY, 1),
            "mean": round(float(df["value"].mean()), 1),
            "std": round(float(df["value"].std()), 1),
            "min": round(float(df["value"].min()), 1),
            "max": round(float(df["value"].max()), 1),
            "n_anomaly_samples": int(df["is_anomaly"].sum()),
            "n_incidents": len(s.incidents),
        })
    return pd.DataFrame(rows)


def fig_kpi_distributions(frames: dict) -> None:
    fig, axes = plt.subplots(1, len(C.KPI_TYPES), figsize=(14, 3.2), sharey=False,
                             constrained_layout=True)
    for ax, kpi in zip(axes, C.KPI_TYPES):
        vals = np.concatenate([f["value"].to_numpy() for sid, f in frames.items()
                               if f["kpi_type"].iloc[0] == kpi]) if frames else np.array([])
        if vals.size:
            ax.hist(vals, bins=60, color=KPI_COLORS[kpi], alpha=0.85)
        ax.set_title(f"{kpi}  (n={vals.size:,})")
        ax.set_xlabel("KPI value [0–1000]")
    axes[0].set_ylabel("count")
    fig.suptitle("KPI value distributions by type", fontweight="bold")
    fig.savefig(C.FIGURES_DIR / "fig_kpi_distributions.png")
    plt.close(fig)


def fig_daily_profile(frames: dict) -> None:
    """Mean value vs time-of-day per KPI — reveals Night vs Festival regimes."""
    fig, ax = plt.subplots(figsize=(9, 4))
    hours = np.arange(C.SAMPLES_PER_DAY) * 5 / 60.0
    for kpi in C.KPI_TYPES:
        profiles = []
        for sid, f in frames.items():
            if f["kpi_type"].iloc[0] != kpi:
                continue
            prof = f.groupby("sample_of_day")["value"].mean().reindex(
                range(C.SAMPLES_PER_DAY))
            profiles.append(prof.to_numpy())
        if profiles:
            m = np.nanmean(np.vstack(profiles), axis=0)
            ax.plot(hours, m, label=kpi, color=KPI_COLORS[kpi], lw=2)
    ax.axhspan(0, ax.get_ylim()[1], xmin=0, xmax=0, alpha=0)  # no-op to keep ylim
    ax.set_xlabel("relative time-of-day (h)")
    ax.set_ylabel("mean KPI value")
    ax.set_title("Mean diurnal traffic profile  (low ≈ Night Mode, peaks ≈ Festival Mode)",
                 fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.savefig(C.FIGURES_DIR / "fig_daily_profile.png")
    plt.close(fig)


def fig_real_with_anomalies(series_list) -> None:
    reals = [s for s in series_list if s.kind == "real" and s.incidents][:4]
    if not reals:
        return
    fig, axes = plt.subplots(len(reals), 1, figsize=(11, 2.4 * len(reals)),
                             sharex=False, constrained_layout=True)
    if len(reals) == 1:
        axes = [axes]
    for ax, s in zip(axes, reals):
        df = build_feature_frame(s)
        ax.plot(df.index, df["value"], color="#333", lw=0.6)
        for start, end in s.incidents:
            end = s.n - 1 if end < 0 else end
            ax.axvspan(start, end, color="red", alpha=0.35)
        ax.set_title(f"{s.series_id} ({s.kpi_type}) — {len(s.incidents)} labelled fault window(s)")
        ax.set_ylabel("value")
    axes[-1].set_xlabel("sample index")
    fig.suptitle("Real series with labelled fault windows (Self-Healing scenario)",
                 fontweight="bold")
    fig.savefig(C.FIGURES_DIR / "fig_real_with_anomalies.png")
    plt.close(fig)


def fig_series_lengths(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 4))
    order = summary.sort_values(["kind", "kpi_type", "series_id"])
    colors = [KPI_COLORS[k] for k in order["kpi_type"]]
    ax.bar(range(len(order)), order["days"], color=colors,
           edgecolor=["black" if k == "real" else "none" for k in order["kind"]])
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order["series_id"], rotation=90, fontsize=6)
    ax.set_ylabel("record length (days)")
    ax.set_title("Series coverage in days (black edge = real series with fault labels)",
                 fontweight="bold")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in KPI_COLORS.values()]
    ax.legend(handles, KPI_COLORS.keys(), title="KPI", ncol=4, fontsize=8)
    fig.savefig(C.FIGURES_DIR / "fig_series_lengths.png")
    plt.close(fig)


def write_summary_md(summary: pd.DataFrame) -> None:
    n_real = int((summary["kind"] == "real").sum())
    n_syn = int((summary["kind"] == "synthetic").sum())
    lines = [
        "# EDA Summary — Network Operator KPIs Dataset\n",
        f"- **Series loaded:** {len(summary)}  ({n_real} real, {n_syn} synthetic)",
        f"- **Total labelled fault windows:** {int(summary['n_incidents'].sum())}",
        f"- **Sampling period:** {C.SAMPLE_PERIOD_SEC}s ({C.SAMPLES_PER_DAY} samples/day)",
        f"- **Median record length:** {summary['days'].median():.1f} days",
        f"- **Mean missing (after grid reindex):** {summary['missing_pct'].mean():.3f}%",
        f"- **KPI value range:** [{summary['min'].min():.0f}, {summary['max'].max():.0f}] "
        "(dataset-normalised 0–1000 scale)\n",
        "## Series count by KPI type\n",
        summary.groupby(["kpi_type", "kind"]).size().unstack(fill_value=0).to_markdown(),
        "\n## Scenario coverage\n",
        "| Scenario | Source | Series |",
        "|---|---|---|",
        f"| Night Mode | low-traffic regime of synthetic series | {n_syn} synthetic |",
        f"| Festival Mode | high-traffic / peak regime of synthetic series | {n_syn} synthetic |",
        f"| Self-Healing | labelled real fault windows | {n_real} real "
        f"({int(summary['n_incidents'].sum())} windows) |",
    ]
    (C.TABLES_DIR / "eda_summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_eda(sample: bool | None = None) -> pd.DataFrame:
    series_list = load_all(sample=sample)
    frames = {s.series_id: build_feature_frame(s) for s in series_list}
    summary = per_series_summary(series_list)

    summary.to_csv(C.TABLES_DIR / "dataset_overview.csv", index=False)
    write_summary_md(summary)
    fig_kpi_distributions(frames)
    fig_daily_profile(frames)
    fig_real_with_anomalies(series_list)
    fig_series_lengths(summary)

    print(f"EDA complete on {len(series_list)} series.")
    print(f"  Figures -> {C.FIGURES_DIR}")
    print(f"  Tables  -> {C.TABLES_DIR}")
    print("\nPer-KPI counts:")
    print(summary.groupby(["kpi_type", "kind"]).size().unstack(fill_value=0))
    return summary


if __name__ == "__main__":
    run_eda(sample=False)
