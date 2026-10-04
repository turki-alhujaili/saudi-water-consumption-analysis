"""
Urban Water Consumption in Saudi Arabia's Regions (2010-2023)
-------------------------------------------------------------
Cleans SAMA water-consumption and population tables, computes daily per-capita
consumption by region, flags suspicious values, makes a simple demand projection
and draws the charts used in the README.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\analysis.py
"""

import io
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
IMAGES = ROOT / "images"

START_YEAR, END_YEAR = 2010, 2023   # 2007-2009 are incomplete and partly misaligned in the source
FORECAST_TO = 2030
ANOMALY_THRESHOLD = 0.35            # flag a region-year when consumption jumps more than 35% vs both neighbours

# SAMA spells some regions differently in the two tables
REGION_NAMES = {"Ha'il": "Hail", "Al-Baha": "Al-Bahah"}

# Water theme: deep water blue for data, desert sand for contrast (rises / population)
HIGHLIGHT = "#0b6fa4"
SECOND = "#d9822b"
OTHERS = "#a9c4d4"
INK = "#0a2a3d"
INK_2 = "#3d5a6c"
MUTED = "#7a93a3"
GRID = "#dbe8ef"
SURFACE = "#f3f8fb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": OTHERS,
    "axes.labelcolor": INK_2, "axes.titlecolor": INK, "axes.titlesize": 14,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "DejaVu Sans"],
    "savefig.dpi": 150, "savefig.bbox": "tight",
})


# ---------------------------------------------------------------------------
# 1. Load & clean
# ---------------------------------------------------------------------------

def read_sama_export(path: Path) -> pd.DataFrame:
    """SAMA's 'Excel' export is an MHTML web page; the data is its first HTML table."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    return pd.read_html(io.StringIO(raw[raw.find("<html"):]))[0]


def find_export(keyword: str) -> Path:
    for path in sorted(RAW.glob("*.xls")):
        if keyword in path.read_text(encoding="utf-8", errors="replace"):
            return path
    raise FileNotFoundError(f"No SAMA export in {RAW} mentions '{keyword}'")


def load_water() -> pd.DataFrame:
    t = read_sama_export(find_export("Water Consumption in Regions"))
    t.columns = [c[-1] for c in t.columns]                 # keep the bottom header row (region names)
    t = t.rename(columns={"Date": "year"})
    t = t[pd.to_numeric(t["year"], errors="coerce").notna()].copy()   # drop footnote rows
    t["year"] = t["year"].astype(int)
    long = t.melt(id_vars="year", var_name="region", value_name="consumption_k_m3")
    long["consumption_k_m3"] = pd.to_numeric(long["consumption_k_m3"], errors="coerce")  # "-" -> NaN
    long["region"] = long["region"].replace(REGION_NAMES)
    return long[long["year"].between(START_YEAR, END_YEAR)]


def load_population() -> pd.DataFrame:
    t = read_sama_export(find_export("Female"))          # the population export has no title row, but has sex rows
    t = t.rename(columns={"Column": "label"})
    rows, region = [], None
    for _, r in t.iterrows():
        label = str(r["label"])
        if r.drop("label").astype(str).eq("-").all():      # a region header row: values are all "-"
            region = label
        elif label == "Total" and region:
            for year, value in r.drop("label").items():
                rows.append({"region": region, "year": int(year), "population": float(value)})
    pop = pd.DataFrame(rows)
    return pop[pop["year"].between(START_YEAR, END_YEAR)]


def flag_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """A value is suspicious when it differs from BOTH the previous and next year by more than the threshold."""
    df = df.sort_values(["region", "year"]).copy()
    g = df.groupby("region")["consumption_k_m3"]
    prev, nxt = g.shift(1), g.shift(-1)
    jump_prev = (df["consumption_k_m3"] / prev - 1).abs()
    jump_next = (df["consumption_k_m3"] / nxt - 1).abs()
    same_direction = np.sign(df["consumption_k_m3"] - prev) == np.sign(df["consumption_k_m3"] - nxt)
    df["suspicious"] = (jump_prev > ANOMALY_THRESHOLD) & (jump_next > ANOMALY_THRESHOLD) & same_direction
    return df


def build_table() -> pd.DataFrame:
    water, pop = load_water(), load_population()
    df = water.merge(pop, on=["region", "year"], how="left", validate="one_to_one")
    missing = df[df["population"].isna()]
    if not missing.empty:
        raise ValueError(f"Regions without population data: {sorted(missing['region'].unique())}")
    # thousand m3 -> litres (x 1,000,000), per person, per day
    df["litres_per_capita_day"] = df["consumption_k_m3"] * 1e6 / df["population"] / 365
    return flag_anomalies(df)


# ---------------------------------------------------------------------------
# 2. Charts
# ---------------------------------------------------------------------------

def finish(fig, name, source="Source: Saudi Central Bank (SAMA) statistical reports; 2023 data preliminary"):
    fig.text(0.01, -0.02, source, color=MUTED, fontsize=8, ha="left")
    fig.savefig(IMAGES / name)
    plt.close(fig)


def chart_national_trend(nat):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(nat["year"], nat["litres_per_capita_day"], color=HIGHLIGHT, linewidth=2)
    peak = nat.loc[nat["litres_per_capita_day"].idxmax()]
    last = nat.iloc[-1]
    for row, dy in ((peak, 10), (last, -16)):
        ax.annotate(f"{row['litres_per_capita_day']:.0f} L ({int(row['year'])})",
                    (row["year"], row["litres_per_capita_day"]), xytext=(0, dy),
                    textcoords="offset points", ha="center", color=INK, fontsize=10, fontweight="bold")
    ax.scatter([peak["year"], last["year"]], [peak["litres_per_capita_day"], last["litres_per_capita_day"]],
               color=HIGHLIGHT, s=36, zorder=3, edgecolor=SURFACE, linewidth=2)
    ax.set_ylim(0, nat["litres_per_capita_day"].max() * 1.2)
    ax.set_title("Saudi Arabia: urban water use per person, litres per day")
    ax.grid(axis="x", visible=False)
    finish(fig, "01_national_per_capita.png")


def chart_regions_latest(df, national_value):
    latest = df[df["year"] == END_YEAR].sort_values("litres_per_capita_day")
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.barh(latest["region"], latest["litres_per_capita_day"], color=HIGHLIGHT, height=0.6)
    for bar, v in zip(bars, latest["litres_per_capita_day"]):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f"  {v:.0f}",
                va="center", color=INK_2, fontsize=9)
    ax.axvline(national_value, color=INK_2, linewidth=1, linestyle="--")
    ax.text(national_value, -0.9, f" National average: {national_value:.0f} L",
            color=INK_2, fontsize=9, va="center")
    ax.set_ylim(-1.3, len(latest) - 0.4)
    ax.tick_params(axis="y", colors=INK_2)
    ax.set_xlim(0, latest["litres_per_capita_day"].max() * 1.15)
    ax.set_title(f"Urban water use per person by region, {END_YEAR} (litres/day)")
    ax.grid(axis="y", visible=False)
    finish(fig, "02_regions_per_capita.png")


def chart_change_by_region(df):
    first = df[df["year"] == START_YEAR].set_index("region")["litres_per_capita_day"]
    last = df[df["year"] == END_YEAR].set_index("region")["litres_per_capita_day"]
    change = ((last / first - 1) * 100).sort_values()
    colors = [HIGHLIGHT if v < 0 else SECOND for v in change]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.barh(change.index, change.values, color=colors, height=0.6)
    for bar, v in zip(bars, change.values):
        ax.text(v, bar.get_y() + bar.get_height() / 2, f" {v:+.0f}% " if v >= 0 else f" {v:+.0f}% ",
                va="center", ha="left" if v >= 0 else "right", color=INK_2, fontsize=9)
    ax.axvline(0, color=INK_2, linewidth=1)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlim(min(change.min() * 3, -80), change.max() * 1.15)
    ax.tick_params(axis="y", colors=INK_2)
    ax.set_title(f"Change in water use per person, {START_YEAR} to {END_YEAR}")
    ax.text(0.99, 0.02, "blue = fell, orange = rose", transform=ax.transAxes, ha="right",
            color=MUTED, fontsize=8)
    ax.grid(axis="y", visible=False)
    finish(fig, "03_change_by_region.png")
    return change


def chart_consumption_vs_population(nat):
    base = nat.iloc[0]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for col, color, label in (("consumption_k_m3", HIGHLIGHT, "Total consumption"),
                              ("population", SECOND, "Population")):
        idx = nat[col] / base[col] * 100
        ax.plot(nat["year"], idx, color=color, linewidth=2)
        ax.annotate(f"{label}: {idx.iloc[-1]:.0f}", (nat["year"].iloc[-1], idx.iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", color=INK, fontsize=9)
    ax.axhline(100, color=OTHERS, linewidth=1)
    ax.set_title(f"Consumption vs population, indexed ({START_YEAR} = 100)")
    ax.set_xlim(START_YEAR - 0.5, END_YEAR + 4)
    ax.set_xticks(range(START_YEAR, END_YEAR + 1, 2))
    ax.grid(axis="x", visible=False)
    finish(fig, "04_consumption_vs_population.png")


def chart_forecast(nat):
    hist = nat[["year", "consumption_k_m3"]]
    recent = hist[hist["year"] >= 2018]              # demand plateaued after 2018; use the recent trend
    slope, intercept = np.polyfit(recent["year"], recent["consumption_k_m3"], 1)
    future = np.arange(END_YEAR, FORECAST_TO + 1)
    proj = slope * future + intercept
    proj[0] = hist["consumption_k_m3"].iloc[-1]       # start the dashed line from the last actual value
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(hist["year"], hist["consumption_k_m3"] / 1e6, color=HIGHLIGHT, linewidth=2, label="Actual")
    ax.plot(future, proj / 1e6, color=HIGHLIGHT, linewidth=2, linestyle="--", label="Trend (2018-2023)")
    ax.annotate(f"{proj[-1] / 1e6:.2f}B m³ in {FORECAST_TO}", (future[-1], proj[-1] / 1e6),
                xytext=(0, 10), textcoords="offset points", ha="center", color=INK, fontsize=10, fontweight="bold")
    ax.set_ylim(0, max(hist["consumption_k_m3"].max(), proj.max()) / 1e6 * 1.25)
    ax.set_title("Total urban water consumption, billion m³")
    ax.legend(frameon=False, loc="lower right")
    ax.xaxis.set_major_locator(mtick.MaxNLocator(integer=True))
    ax.grid(axis="x", visible=False)
    finish(fig, "05_consumption_trend.png",
           source="Source: SAMA. Dashed line = linear trend of 2018-2023, an illustration, not an official forecast")
    return slope, proj[-1]


# ---------------------------------------------------------------------------
# 3. Findings
# ---------------------------------------------------------------------------

def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)

    df = build_table()
    regions = df[df["region"] != "Total"].copy()
    nat = df[df["region"] == "Total"].sort_values("year").reset_index(drop=True)

    regions.to_csv(PROCESSED / "water_per_capita_by_region.csv", index=False)
    nat.drop(columns="suspicious").to_csv(PROCESSED / "water_national.csv", index=False)

    national_latest = nat["litres_per_capita_day"].iloc[-1]
    chart_national_trend(nat)
    chart_regions_latest(regions, national_latest)
    change = chart_change_by_region(regions)
    chart_consumption_vs_population(nat)
    slope, proj_last = chart_forecast(nat)

    latest = regions[regions["year"] == END_YEAR].sort_values("litres_per_capita_day", ascending=False)
    share = latest.set_index("region")["consumption_k_m3"] / nat["consumption_k_m3"].iloc[-1] * 100
    peak = nat.loc[nat["litres_per_capita_day"].idxmax()]

    print(f"Saved {len(regions)} region-year rows and {len(nat)} national rows to data/processed")
    print("\nKEY FINDINGS")
    print(f"- National use per person: {nat['litres_per_capita_day'].iloc[0]:.0f} L/day ({START_YEAR}) -> "
          f"peak {peak['litres_per_capita_day']:.0f} L ({int(peak['year'])}) -> {national_latest:.0f} L ({END_YEAR})")
    print(f"- Highest {END_YEAR}: " + ", ".join(f"{r.region} {r.litres_per_capita_day:.0f} L" for r in latest.head(3).itertuples()))
    print(f"- Lowest {END_YEAR}: " + ", ".join(f"{r.region} {r.litres_per_capita_day:.0f} L" for r in latest.tail(3).itertuples()))
    print(f"- Gap highest/lowest: {latest['litres_per_capita_day'].iloc[0] / latest['litres_per_capita_day'].iloc[-1]:.1f}x")
    print(f"- Riyadh + Makkah + Eastern share of total {END_YEAR}: {share[['Riyadh', 'Makkah', 'Eastern Region']].sum():.0f}%")
    print(f"- Total consumption {START_YEAR}->{END_YEAR}: +{(nat['consumption_k_m3'].iloc[-1] / nat['consumption_k_m3'].iloc[0] - 1) * 100:.0f}%, "
          f"population +{(nat['population'].iloc[-1] / nat['population'].iloc[0] - 1) * 100:.0f}%")
    print(f"- Per-capita change {START_YEAR}->{END_YEAR}: largest rise {change.idxmax()} {change.max():+.0f}%, "
          f"largest fall {change.idxmin()} {change.min():+.0f}%")
    print(f"- Trend 2018-2023: {slope / 1e3:+.1f} million m3/year -> {proj_last / 1e6:.2f}B m3 by {FORECAST_TO}")
    sus = regions[regions["suspicious"]]
    print(f"- Suspicious values flagged: {len(sus)}")
    for r in sus.itertuples():
        print(f"    {r.region} {r.year}: {r.consumption_k_m3:,.0f} thousand m3")


if __name__ == "__main__":
    main()
