"""
aquind_descriptive_stats.py
═══════════════════════════
Prototype Step 2 — Descriptive Statistics
Aquind GB–France Interconnector Valuation (Ofgem Cap & Floor Window 3)

Methodology:  Abadie & Chamorro (2021), Energy 233, 121177
              "Evaluation of a cross-border electricity interconnection"
Project flow: Interconnectors_Equity_focus (Steps 1–2)

Data sources (from Cleaned_GBFR.xlsx):
  GB_FINAL   — GB N2EX hourly day-ahead prices, GBP/MWh (Bloomberg N2EXEH01-24)
  FR_FINAL   — FR EPEX hourly day-ahead prices, EUR/MWh (Bloomberg PWNXFR01-24)
  GBP-EUR    — EURGBP daily FX rate (Bloomberg "EURGBP Currency")

FX convention (confirmed from Bloomberg ticker):
  Column "EUR/GBP" = EURGBP rate = GBP per 1 EUR
  e.g. 0.8937 means 1 EUR = 0.8937 GBP
  → FR_price_GBP = FR_price_EUR × fx_eur_gbp

Outputs:
  • Table 1 — Hourly descriptive statistics (Abadie Table 1 analogue)
  • Table 2 — Daily average descriptive statistics (Abadie Table 3 analogue)
  • ADF unit-root tests on daily series (Step 2, project flow)
  • Brief model-selection interpretation

Stops before: deterministic OLS component, OU/jump estimation, Monte Carlo.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from statsmodels.tsa.stattools import adfuller

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
EXCEL_PATH = Path("/Users/aadesh/Documents/IC/Cleaned_GBFR.xlsx")
GB_SHEET   = "GB_FINAL"
FR_SHEET   = "FR_FINAL"
FX_SHEET   = "GBP-EUR"

# Gap-filling thresholds
SHORT_GAP_H = 4   # ≤ 4 consecutive missing hours → linear interpolation
# Gaps longer than SHORT_GAP_H are dropped (not imputed)

# ─────────────────────────────────────────────────────────────────────────────
# 1.  LOAD
# ─────────────────────────────────────────────────────────────────────────────

def load_from_excel(filepath: Path):
    """
    Load GB_FINAL, FR_FINAL, and GBP-EUR sheets from the cleaned Excel file.
    Returns three raw DataFrames in wide day × H01..H24 format.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Excel file not found: {filepath}")

    xl = pd.ExcelFile(filepath)
    gb_wide  = xl.parse(GB_SHEET)
    fr_wide  = xl.parse(FR_SHEET)
    fx_daily = xl.parse(FX_SHEET)

    print(f"Loaded '{filepath.name}'")
    print(f"  {GB_SHEET}: {gb_wide.shape[0]} days × {gb_wide.shape[1] - 1} hours")
    print(f"  {FR_SHEET}: {fr_wide.shape[0]} days × {fr_wide.shape[1] - 1} hours")
    print(f"  {FX_SHEET}: {fx_daily.shape[0]} daily FX observations")

    return gb_wide, fr_wide, fx_daily


# ─────────────────────────────────────────────────────────────────────────────
# 2.  CLEAN
# ─────────────────────────────────────────────────────────────────────────────

def _wide_to_hourly(wide_df: pd.DataFrame, value_col: str) -> pd.Series:
    """
    Melt a wide day × H01..H24 DataFrame into a long hourly Series.

    Hour convention (UK/FR day-ahead market standard):
      H01 = settlement period 00:00–01:00  →  timestamp  2024-01-15 00:00
      H02 = settlement period 01:00–02:00  →  timestamp  2024-01-15 01:00
      ...
      H24 = settlement period 23:00–00:00  →  timestamp  2024-01-15 23:00
    i.e. the timestamp is the *start* of each one-hour delivery period.
    """
    df = wide_df.rename(columns={"Unnamed: 0": "date"}).copy()
    df["date"] = pd.to_datetime(df["date"])

    hour_cols = sorted(
        [c for c in df.columns if c.startswith("H") and c[1:].isdigit()],
        key=lambda x: int(x[1:]),
    )

    melted = df.melt(
        id_vars="date",
        value_vars=hour_cols,
        var_name="hour_col",
        value_name=value_col,
    )

    # H01 → offset 0 hours, H02 → 1 hour, ..., H24 → 23 hours
    melted["offset"]    = melted["hour_col"].str[1:].astype(int) - 1
    melted["timestamp"] = melted["date"] + pd.to_timedelta(melted["offset"], unit="h")

    return (
        melted
        .set_index("timestamp")[value_col]
        .sort_index()
        .astype(float)
    )


def clean_panel(
    gb_wide: pd.DataFrame,
    fr_wide: pd.DataFrame,
    fx_daily: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a clean hourly panel with columns:
        gb_price_gbp  — GB day-ahead price (GBP/MWh)
        fr_price_eur  — FR day-ahead price (EUR/MWh)
        fx_eur_gbp    — EURGBP rate (GBP per 1 EUR)

    Cleaning rules (explicitly documented):
      1. Duplicate timestamps  → keep the *last* occurrence.
      2. Missing hours (≤ SHORT_GAP_H = 4 consecutive)  → linear interpolation.
      3. Missing hours (> SHORT_GAP_H consecutive)       → dropped (not imputed).

    FX handling:
      • Daily FX is forward-filled over weekends and public holidays
        (up to 3 calendar days between business-day observations).
      • Each hourly timestamp inherits its calendar day's FX rate.
      • Any remaining FX gaps are back-filled then forward-filled as a fallback.

    The returned panel covers only the period where BOTH GB and FR prices
    are available (overlap of the two series).
    """
    # ── 1. Wide → long hourly ─────────────────────────────────────────────
    gb_s = _wide_to_hourly(gb_wide, "gb_price_gbp")
    fr_s = _wide_to_hourly(fr_wide, "fr_price_eur")

    # ── 2. FX: parse, forward-fill over non-trading days ─────────────────
    fx = fx_daily.copy()
    fx.columns = ["date", "fx_eur_gbp"]          # EUR/GBP = GBP per 1 EUR
    fx["date"] = pd.to_datetime(fx["date"])
    fx = fx.dropna(subset=["fx_eur_gbp"]).set_index("date").sort_index()

    # Reindex to every calendar day then forward-fill (covers weekends/holidays)
    all_days = pd.date_range(fx.index.min(), fx.index.max(), freq="D")
    fx = fx.reindex(all_days).ffill()

    # ── 3. Combine into hourly panel ─────────────────────────────────────
    panel = pd.concat([gb_s, fr_s], axis=1, sort=True)

    # Rule 1: duplicate timestamps → keep last
    n_dups = panel.index.duplicated().sum()
    if n_dups:
        panel = panel[~panel.index.duplicated(keep="last")]
        print(f"  [clean] Removed {n_dups} duplicate timestamps (kept last).")

    # Restrict to the overlap period (where both series carry data)
    gb_start = panel["gb_price_gbp"].first_valid_index()
    gb_end   = panel["gb_price_gbp"].last_valid_index()
    fr_start = panel["fr_price_eur"].first_valid_index()
    fr_end   = panel["fr_price_eur"].last_valid_index()
    overlap_start = max(gb_start, fr_start)
    overlap_end   = min(gb_end,   fr_end)
    panel = panel.loc[overlap_start:overlap_end]

    # Reindex to a complete hourly grid over the overlap window
    full_idx = pd.date_range(panel.index.min(), panel.index.max(), freq="h")
    panel = panel.reindex(full_idx)

    # Rule 2: short gaps → linear interpolation (≤ 4 h)
    panel = panel.interpolate(method="linear", limit=SHORT_GAP_H)

    # Rule 3: long gaps → drop
    n_dropped = panel.isnull().any(axis=1).sum()
    if n_dropped:
        panel = panel.dropna()
        print(f"  [clean] Dropped {n_dropped} hours with gaps > {SHORT_GAP_H} h.")

    # ── 4. Attach FX (broadcast daily rate to all 24 hours of each day) ──
    # Normalise each hourly timestamp to midnight to look up the daily FX
    daily_dates = panel.index.normalize()
    panel["fx_eur_gbp"] = daily_dates.map(fx["fx_eur_gbp"])

    # Fallback: fill any remaining FX gaps at edges of the FX series
    panel["fx_eur_gbp"] = panel["fx_eur_gbp"].bfill().ffill()

    n_fx_missing = panel["fx_eur_gbp"].isna().sum()
    if n_fx_missing:
        print(f"  [clean] Warning: {n_fx_missing} hours still missing FX after fill.")

    print(
        f"  [clean] Panel: {panel.index.min().date()} → {panel.index.max().date()}"
        f"  ({len(panel):,} hourly obs)"
    )

    return panel

# ─────────────────────────────────────────────────────────────────────────────
# 3.  SPREAD CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def construct_spread(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Convert FR price to GBP and compute the hourly GB–FR spread.

    FX convention (confirmed from Bloomberg EURGBP Currency ticker):
        fx_eur_gbp  =  EUR/GBP rate  =  GBP per 1 EUR  (≈ 0.89 in Jan-2021)
        FR_price_GBP = FR_price_EUR × fx_eur_gbp
        Spread_GBP   = GB_price_GBP − FR_price_GBP

    NOTE — assumption flagged for user confirmation:
        If the Excel column "EUR/GBP" were instead GBP/EUR (i.e. how many EUR
        you get for 1 GBP, ≈ 1.12 in 2021), the correct formula would be
            FR_GBP = FR_EUR / fx
        and you should set FX_INVERT = True at the top of the script.
        The Bloomberg label "EURGBP Currency" and value ≈ 0.89 (= 1/1.12)
        confirm the multiply convention used here.
    """
    out = panel.copy()
    out["fr_price_gbp"] = out["fr_price_eur"] * out["fx_eur_gbp"]
    out["spread_gbp"]   = out["gb_price_gbp"] - out["fr_price_gbp"]
    return out

    
# ─────────────────────────────────────────────────────────────────────────────
# 4.  DESCRIPTIVE STATISTICS
# ─────────────────────────────────────────────────────────────────────────────

_STAT_LABELS = [
    "Mean",
    "Minimum",
    "Maximum",
    "Std Dev",
    "Skewness",
    "Excess Kurtosis",
    "Percentile 5%",
    "Percentile 95%",
]


def _stats_series(s: pd.Series) -> dict:
    """
    Compute the eight Abadie-style descriptive statistics for one Series.
    Excess kurtosis = kurtosis − 3 (0 for a Gaussian, > 0 for fat tails).
    """
    s = s.dropna()
    return {
        "Mean":            float(s.mean()),
        "Minimum":         float(s.min()),
        "Maximum":         float(s.max()),
        "Std Dev":         float(s.std(ddof=1)),
        "Skewness":        float(sp_stats.skew(s)),
        # fisher=True returns kurtosis − 3  (scipy default)
        "Excess Kurtosis": float(sp_stats.kurtosis(s, fisher=True)),
        "Percentile 5%":   float(np.percentile(s, 5)),
        "Percentile 95%":  float(np.percentile(s, 95)),
    }


def hourly_stats(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Abadie & Chamorro (2021) Table 1 analogue.
    Descriptive statistics computed on the raw hourly price series —
    no aggregation, no transformation.

    Returns a DataFrame: rows = statistics, columns = GB Price / FR Price / Spread.
    """
    series_map = {
        "GB Price (GBP/MWh)": panel["gb_price_gbp"],
        "FR Price (GBP/MWh)": panel["fr_price_gbp"],
        "Spread (GBP/MWh)":   panel["spread_gbp"],
    }

    table = pd.DataFrame(
        {name: _stats_series(s) for name, s in series_map.items()},
        index=_STAT_LABELS,
    )
    return table


def daily_stats(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Abadie & Chamorro (2021) Table 3 analogue.
    Aggregate the hourly panel to daily *averages*, then compute the same
    eight statistics.  Aggregation reduces sampling noise and shows whether
    the heavy tails seen at hourly frequency are driven by within-day spikes
    (consistent with infrequent jumps that mean-revert within a few hours).

    Returns a DataFrame: rows = statistics, columns = GB Price / FR Price / Spread.
    """
    daily = (
        panel[["gb_price_gbp", "fr_price_gbp", "spread_gbp"]]
        .resample("D")
        .mean()
        .dropna()
    )

    series_map = {
        "GB Price (GBP/MWh)": daily["gb_price_gbp"],
        "FR Price (GBP/MWh)": daily["fr_price_gbp"],
        "Spread (GBP/MWh)":   daily["spread_gbp"],
    }

    table = pd.DataFrame(
        {name: _stats_series(s) for name, s in series_map.items()},
        index=_STAT_LABELS,
    )
    return table


# ─────────────────────────────────────────────────────────────────────────────
# 5.  ADF UNIT-ROOT TESTS  (Step 2, Interconnectors_Equity_focus)
# ─────────────────────────────────────────────────────────────────────────────

def adf_tests(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Augmented Dickey-Fuller (ADF) tests on daily-averaged GB price, FR price,
    and spread.

    H₀: the series contains a unit root (non-stationary, random walk).
    Rejection of H₀ at 5% supports mean reversion — a precondition for the
    Abadie-style OU model used in Step 3 onwards.

    Following Cartea & González-Pedraz (2012): regression includes a constant
    and a linear trend; lag length selected by AIC.  Tests run on daily
    averages (consistent with Abadie's parameter estimation on daily data).
    """
    daily = (
        panel[["gb_price_gbp", "fr_price_gbp", "spread_gbp"]]
        .resample("D")
        .mean()
        .dropna()
    )

    series_map = {
        "GB Price (GBP/MWh)": daily["gb_price_gbp"],
        "FR Price (GBP/MWh)": daily["fr_price_gbp"],
        "Spread (GBP/MWh)":   daily["spread_gbp"],
    }

    rows = {}
    for name, s in series_map.items():
        # regression="ct": constant + time trend in null (standard for prices)
        res = adfuller(s.dropna(), autolag="AIC", regression="ct")
        rows[name] = {
            "ADF Statistic":  round(res[0], 3),
            "p-value":        round(res[1], 4),
            "Lags Used":      int(res[2]),
            "Critical 1%":    round(res[4]["1%"], 3),
            "Critical 5%":    round(res[4]["5%"], 3),
            "Reject H₀ (5%)": "YES" if res[1] < 0.05 else "no",
        }

    return pd.DataFrame(rows).T


# ─────────────────────────────────────────────────────────────────────────────
# 6.  INTERPRETATION
# ─────────────────────────────────────────────────────────────────────────────

def interpret_stats(
    hourly_tbl: pd.DataFrame,
    daily_tbl: pd.DataFrame,
) -> None:
    """
    Print spread skewness and excess kurtosis at hourly vs daily frequency.
    Excess kurtosis = kurtosis − 3; a Normal distribution has excess kurtosis = 0.
    No model recommendations are made here — findings only.
    """
    skew_h = hourly_tbl.loc["Skewness",        "Spread (GBP/MWh)"]
    ek_h   = hourly_tbl.loc["Excess Kurtosis",  "Spread (GBP/MWh)"]
    skew_d = daily_tbl.loc["Skewness",          "Spread (GBP/MWh)"]
    ek_d   = daily_tbl.loc["Excess Kurtosis",   "Spread (GBP/MWh)"]

    SEP = "═" * 72

    print(f"\n{SEP}")
    print("  SPREAD DISTRIBUTION SUMMARY — Step 2, Interconnectors_Equity_focus")
    print(SEP)

    print(f"\n  Excess kurtosis (= kurtosis − 3; Normal = 0):")
    print(f"    Hourly spread:  {ek_h:.2f}")
    print(f"    Daily  spread:  {ek_d:.2f}")
    print(f"    Change hourly → daily: {ek_d - ek_h:+.2f}")

    print(f"\n  Skewness (Normal = 0):")
    print(f"    Hourly spread:  {skew_h:+.3f}")
    print(f"    Daily  spread:  {skew_d:+.3f}")

    print(f"\n{SEP}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    SEP = "═" * 72

    print(f"\n{SEP}")
    print("  AQUIND INTERCONNECTOR — DESCRIPTIVE STATISTICS  (Step 2)")
    print(f"{SEP}\n")

    # ── 1. Load ───────────────────────────────────────────────────────────
    gb_wide, fr_wide, fx_daily = load_from_excel(EXCEL_PATH)

    # ── 2. Clean ──────────────────────────────────────────────────────────
    print("\nCleaning panel ...")
    panel = clean_panel(gb_wide, fr_wide, fx_daily)

    # ── 3. Construct spread ───────────────────────────────────────────────
    print("\nConstructing spread ...")
    panel = construct_spread(panel)

    # Drop any remaining NaN rows in the columns used for stats
    stat_cols = ["gb_price_gbp", "fr_price_gbp", "spread_gbp"]
    panel_complete = panel.dropna(subset=stat_cols)
    n_obs  = len(panel_complete)
    n_days = panel_complete.resample("D").mean().shape[0]
    print(
        f"  Analysis window: "
        f"{panel_complete.index.min().date()} → {panel_complete.index.max().date()}"
    )
    print(f"  {n_obs:,} hourly obs  |  {n_days:,} days")

    # ── 4a. Hourly stats — Abadie Table 1 analogue ───────────────────────
    print(f"\n{SEP}")
    print(
        "  TABLE 1 — Hourly Prices and Spread: Descriptive Statistics\n"
        "  (Abadie & Chamorro 2021, Table 1 analogue — GB/France)"
    )
    print(SEP)
    h_tbl = hourly_stats(panel_complete)
    fmt = "{:.4f}".format
    with pd.option_context("display.float_format", fmt, "display.max_columns", 10):
        print(h_tbl.to_string())

    # ── 4b. Daily stats — Abadie Table 3 analogue ────────────────────────
    print(f"\n{SEP}")
    print(
        "  TABLE 2 — Daily Average Prices and Spread: Descriptive Statistics\n"
        "  (Abadie & Chamorro 2021, Table 3 analogue — GB/France)"
    )
    print(SEP)
    d_tbl = daily_stats(panel_complete)
    with pd.option_context("display.float_format", fmt, "display.max_columns", 10):
        print(d_tbl.to_string())

    # ── 5. ADF unit-root tests ────────────────────────────────────────────
    print(f"\n{SEP}")
    print(
        "  ADF UNIT-ROOT TESTS  (H₀: unit root; rejection → mean reversion)\n"
        "  Regression: constant + trend;  lag selection: AIC;  daily averages"
    )
    print(SEP)
    adf_tbl = adf_tests(panel_complete)
    print(adf_tbl.to_string())

    # ── 6. Interpretation ─────────────────────────────────────────────────
    interpret_stats(h_tbl, d_tbl)

    # ── 7. Save outputs ───────────────────────────────────────────────────
    out_dir = EXCEL_PATH.parent
    h_tbl.to_csv(out_dir / "table1_hourly_stats.csv")
    d_tbl.to_csv(out_dir / "table2_daily_stats.csv")
    adf_tbl.to_csv(out_dir / "adf_tests.csv")
    print(f"  CSV outputs saved to: {out_dir}")

    # ── 8. Confirmation prompt ────────────────────────────────────────────
    print(f"\n{SEP}")
    print(
        "  ASSUMPTIONS TO CONFIRM BEFORE PROCEEDING\n"
        "  ─────────────────────────────────────────\n"
        "  [1] FX direction: 'EUR/GBP' column (Bloomberg EURGBP) ≈ 0.89\n"
        "      → interpreted as 1 EUR = 0.89 GBP\n"
        "      → FR_GBP = FR_EUR × fx   [multiply convention]\n"
        "      If this is wrong, set FX_INVERT = True in the script.\n"
        "\n"
        "  [2] GB prices are in GBP/MWh (not pence/MWh).  Assumed: YES.\n"
        "\n"
        "  [3] FR prices are in EUR/MWh.  Assumed: YES.\n"
        "\n"
    )
    print(SEP + "\n")

    return panel_complete, h_tbl, d_tbl, adf_tbl


if __name__ == "__main__":
    panel_out, hourly_table, daily_table, adf_table = main()
