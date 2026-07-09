"""
IFA2 Flow-Based Revenue: 2021-2026
===================================
Computes gross congestion rent earned by IFA2 based on actual ENTSO-E hourly
physical flows and observed GB/FR day-ahead prices.

Revenue formula per hour:
  rev_h = (fr_to_gb_MW × max(spread, 0) + gb_to_fr_MW × max(-spread, 0)) / 1e6  [£m]
  where spread = GB_price_GBP - FR_price_GBP

This is the gross congestion rent. No capture ratio or cost deduction applied.
Both nominal and 2016/17-RPI-real outputs are shown.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
FLOW_PATH  = Path('/Users/aadesh/Documents/IC/ENTSO-E/GUI_NET_CROSS_BORDER_IFA2_combined.csv')
PRICE_PATH = Path('/Users/aadesh/Documents/IC/Cleaned_GBFR.xlsx')

# ── FPA RPI index (row 97, CHAW Jan 1987=100) for nominal → 2016/17-real ─────
FPA_RPI = {
    2021: 310.794, 2022: 320.864, 2023: 331.260,
    2024: 341.993, 2025: 353.073, 2026: 364.513,
}
RPI_1617 = 264.992  # FPA row 96: 2016/17 base

# ── 1. Load ENTSO-E physical flows ────────────────────────────────────────────
print('Loading ENTSO-E flow data...')
raw = pd.read_csv(FLOW_PATH)

# Parse start timestamp from MTU column  "dd/mm/yyyy HH:MM:SS - ..."
raw['ts'] = pd.to_datetime(
    raw['MTU'].str.split(' - ').str[0].str.strip(),
    format='%d/%m/%Y %H:%M:%S',
    utc=False
)

# Convert flow to numeric (n/e → NaN)
raw['flow_mw'] = pd.to_numeric(raw['Physical Flow (MW)'], errors='coerce')

# Direction flags
raw['fr_to_gb'] = ((raw['Out Area'].str.contains('FR', na=False)) &
                   (raw['In Area'].str.contains('GB', na=False))).astype(float)
raw['gb_to_fr'] = ((raw['Out Area'].str.contains('GB', na=False)) &
                   (raw['In Area'].str.contains('FR', na=False))).astype(float)

# Pivot: one row per timestamp with directional flows
flows = (raw.pivot_table(index='ts', values='flow_mw',
                         columns=raw['Out Area'].str.contains('GB').map(
                             {True: 'gb_to_fr', False: 'fr_to_gb'}),
                         aggfunc='sum')
         .rename_axis(None, axis=1)
         .reindex(columns=['fr_to_gb', 'gb_to_fr'])
         .fillna(0.0))

flows.index = flows.index.tz_localize(None)
print(f'  Flow data: {flows.index.min().date()} to {flows.index.max().date()}'
      f'  ({len(flows):,} hourly obs)')
print(f'  n/e (missing) rows removed: {raw["flow_mw"].isna().sum() // 2:,} hours')

# ── 2. Load GB and FR prices (wide format: day × H01-H24) ────────────────────
print('\nLoading prices...')
gb_wide = pd.read_excel(PRICE_PATH, sheet_name='GB_FINAL', index_col=0, parse_dates=True)
fr_wide = pd.read_excel(PRICE_PATH, sheet_name='FR_FINAL', index_col=0, parse_dates=True)
fx_raw  = pd.read_excel(PRICE_PATH, sheet_name='GBP-EUR',  index_col=0, parse_dates=True)

def wide_to_hourly(df_wide, name):
    """Melt day × H01-H24 → hourly DatetimeIndex Series."""
    df_wide.index = pd.to_datetime(df_wide.index).tz_localize(None)
    rows = []
    for date, row in df_wide.iterrows():
        for h, col in enumerate(df_wide.columns, start=1):  # H01=hour 0, H02=hour 1...
            ts = date + pd.Timedelta(hours=h - 1)
            rows.append((ts, row[col]))
    s = pd.Series(dict(rows), name=name)
    s.index = pd.DatetimeIndex(s.index)
    return pd.to_numeric(s, errors='coerce').dropna()

gb_h = wide_to_hourly(gb_wide, 'gb_gbp')
fr_h = wide_to_hourly(fr_wide, 'fr_eur')

# Daily FX → forward-fill to hourly
fx_raw.index = pd.to_datetime(fx_raw.index).tz_localize(None)
fx_daily = fx_raw['EUR/GBP']
fx_h = fx_daily.reindex(gb_h.index, method='ffill').bfill()

fr_gbp = (fr_h.reindex(gb_h.index, method='ffill') * fx_h).rename('fr_gbp')

prices = pd.concat([gb_h, fr_gbp], axis=1).dropna()
prices['spread'] = prices['gb_gbp'] - prices['fr_gbp']

print(f'  GB prices: {gb_h.index.min().date()} to {gb_h.index.max().date()}'
      f'  ({len(gb_h):,} hourly obs)')
print(f'  FR prices: {fr_h.index.min().date()} to {fr_h.index.max().date()}'
      f'  ({len(fr_h):,} hourly obs)')
print(f'  Joined price panel: {prices.index.min().date()} to {prices.index.max().date()}'
      f'  ({len(prices):,} hourly obs)')

# ── 3. Join flows with prices ─────────────────────────────────────────────────
df = flows.join(prices[['gb_gbp', 'fr_gbp', 'spread']], how='inner').dropna()
print(f'\nJoined panel: {df.index.min().date()} to {df.index.max().date()}'
      f'  ({len(df):,} hourly obs)')

# ── 4. Compute hourly gross congestion rent ───────────────────────────────────
# Revenue = flow × spread-in-flow-direction × 1h / 1e6 [£m]
df['rev_h'] = (
    df['fr_to_gb'] * df['spread'].clip(lower=0) +
    df['gb_to_fr'] * (-df['spread']).clip(lower=0)
) / 1e6

# ── 5. Annual summary ─────────────────────────────────────────────────────────
yr  = df.index.year
ann = df.groupby(yr).agg(
    hours       =('rev_h', 'count'),
    fr_to_gb_gwh=('fr_to_gb', lambda x: x.sum() / 1e3),   # MWh → GWh
    gb_to_fr_gwh=('gb_to_fr', lambda x: x.sum() / 1e3),
    rev_nom_m   =('rev_h', 'sum'),                          # £m nominal
    mean_spread =('spread', 'mean'),
).reset_index().rename(columns={'ts': 'year'})
ann.columns = ['year','hours','fr_to_gb_gwh','gb_to_fr_gwh',
               'rev_nom_m','mean_spread_gbp']

# RPI deflation → 2016/17-real
ann['rpi_factor'] = ann['year'].map(lambda y: RPI_1617 / FPA_RPI.get(y, FPA_RPI[max(FPA_RPI)]))
ann['rev_real_m'] = ann['rev_nom_m'] * ann['rpi_factor']

# Net flow
ann['net_fr_to_gb_gwh'] = ann['fr_to_gb_gwh'] - ann['gb_to_fr_gwh']

# ── 6. Merge Ofgem actuals and compute implied capture ratios ─────────────────
# Audited turnover from IFA2 annual accounts (nominal £m)
ACTUALS_NOM = {2022: 69.6, 2023: 100.8, 2024: 101.6, 2025: 72.2}

ann['actual_nom_m']  = ann['year'].map(ACTUALS_NOM)
ann['actual_real_m'] = ann['actual_nom_m'] * ann['rpi_factor']

# Implied capture ratio: actual turnover / gross congestion rent
# Deflation cancels in the ratio, so nominal and real give the same CR.
# Computed both ways to confirm consistency.
ann['cr_from_nom']  = ann['actual_nom_m']  / ann['rev_nom_m']
ann['cr_from_real'] = ann['actual_real_m'] / ann['rev_real_m']

# ── 7. Print extended table ───────────────────────────────────────────────────
W = 128
print()
print('=' * W)
print('IFA2: GROSS CONGESTION RENT vs OFGEM ACTUAL TURNOVER — 2021 to 2026')
print('(ENTSO-E physical flows × observed GB/FR prices | Actuals from audited accounts)')
print('=' * W)

H1 = (f'  {"Year":>5}  {"Hrs":>5}  {"FR→GB":>7}  {"GB→FR":>7}  {"Net":>7}  '
      f'{"Spread":>7}  {"Gross nom":>10}  {"Gross real":>11}  '
      f'{"Actual nom":>11}  {"Actual real":>12}  {"CR (nom)":>9}  {"CR (real)":>10}')
print(H1)
print(f'  {"":>5}  {"":>5}  {"GWh":>7}  {"GWh":>7}  {"GWh":>7}  '
      f'{"£/MWh":>7}  {"£m":>10}  {"£m 16/17":>11}  '
      f'{"£m":>11}  {"£m 16/17":>12}  {"actual/gross":>9}  {"actual/gross":>10}')
print('  ' + '-' * (W - 2))

for _, r in ann.iterrows():
    yr   = int(r.year)
    note = ' *' if yr == 2021 else (' †' if yr == 2026 else '  ')
    act_n  = f'{r.actual_nom_m:>11.1f}'  if pd.notna(r.actual_nom_m)  else f'{"n/a":>11}'
    act_r  = f'{r.actual_real_m:>12.1f}' if pd.notna(r.actual_real_m) else f'{"n/a":>12}'
    cr_n   = f'{r.cr_from_nom:>8.1%}'   if pd.notna(r.cr_from_nom)   else f'{"n/a":>8}'
    cr_r   = f'{"(=" + f"{r.cr_from_real:.1%}" + ")":>10}' if pd.notna(r.cr_from_real) else f'{"n/a":>10}'
    print(f'  {yr:>5}{note} {int(r.hours):>5}  {r.fr_to_gb_gwh:>7.0f}  '
          f'{r.gb_to_fr_gwh:>7.0f}  {r.net_fr_to_gb_gwh:>7.0f}  '
          f'{r.mean_spread_gbp:>7.2f}  {r.rev_nom_m:>10.1f}  {r.rev_real_m:>11.1f}  '
          f'{act_n}  {act_r}  {cr_n}  {cr_r}')

print()
# Full-year totals 2022-2025
fy = ann[ann.year.isin(range(2022, 2026))]
tot_gn  = fy.rev_nom_m.sum();   tot_gr  = fy.rev_real_m.sum()
tot_an  = fy.actual_nom_m.sum();  tot_ar  = fy.actual_real_m.sum()
cr_tot  = tot_an / tot_gn
print(f'  {"2022-25 total":>16}  {"":>7}  {"":>7}  {"":>7}  {"":>7}  '
      f'{tot_gn:>10.1f}  {tot_gr:>11.1f}  {tot_an:>11.1f}  {tot_ar:>12.1f}  '
      f'{cr_tot:>8.1%}  {"(=" + f"{cr_tot:.1%}" + ")":>10}')

print()
print('  Notes:')
print('  * 2021: GB price data available from Dec 2021 only; partial year coverage.')
print('  † 2026: GB price data available to Mar 2026 only; Ofgem actual not yet published.')
print()
print('  Gross = ENTSO-E physical flow_MW × spread_in_flow_direction (no capacity or')
print('          availability deduction — actual MW as reported by ENTSO-E).')
print('  Actual = Ofgem-assessed turnover from IFA2 audited accounts (nominal £m).')
print('  2016/17-real = deflated by FPA model Input row 97 RPI index (CHAW).')
print('  CR = implied capture ratio (actual turnover / gross congestion rent).')
print('  CR is identical in nominal and real because deflation cancels in the ratio.')
print('=' * W)

# ── 8. Save to CSV ────────────────────────────────────────────────────────────
out_path = Path('/Users/aadesh/Documents/IC/M2/ifa2_flow_revenue_2021_2026.csv')
ann[['year','hours','fr_to_gb_gwh','gb_to_fr_gwh','net_fr_to_gb_gwh',
     'mean_spread_gbp','rev_nom_m','rev_real_m',
     'actual_nom_m','actual_real_m','cr_from_nom']].to_csv(out_path, index=False)
print(f'\nSaved: {out_path}')
