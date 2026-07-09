"""
Flow Direction Mismatch Analysis — IFA2, 2022-2025
----------------------------------------------------
For each hour, checks whether IFA2's physical flow was in the economically
rational direction given the GB-FR price spread.

ENTSO-E naming convention (Out Area = delivery destination):
  col 'gb_to_fr' (Out Area=BZN|GB) = electricity arriving IN GB = FR→GB physical flow
  col 'fr_to_gb' (Out Area=BZN|FR) = electricity arriving IN FR = GB→FR physical flow
  net_flow_mw = gb_to_fr - fr_to_gb  →  positive = net FR→GB

Rational direction:
  spread > 0  (P_GB > P_FR)  →  FR→GB profitable  →  net_flow > 0
  spread < 0  (P_FR > P_GB)  →  GB→FR profitable  →  net_flow < 0

Wrong direction = cable flowing against the price signal.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

IC_DIR    = Path('/Users/aadesh/Documents/IC')
FLOW_PATH = Path('/Users/aadesh/Downloads/GUI_NET_CROSS_BORDER_IFA2_combined.csv')
OUTPUT_DIR = IC_DIR / 'M2'
CAPACITY_MW  = 1000.0
AVAILABILITY = 0.95
ACTUALS = {2022: 69.6, 2023: 100.8, 2024: 101.6, 2025: 72.2}

# ── 1. Build hourly spread from daily × 24-column Excel ──────────────────────
print('Loading price data...')
xl     = pd.ExcelFile(IC_DIR / 'Cleaned_GBFR.xlsx')
gb_raw = pd.read_excel(xl, 'GB_FINAL', index_col=0, parse_dates=True)
fr_raw = pd.read_excel(xl, 'FR_FINAL', index_col=0, parse_dates=True)
fx_raw = pd.read_excel(xl, 'GBP-EUR',  index_col=0, parse_dates=True)
fx_col = next(c for c in fx_raw.columns if 'EUR' in str(c) or 'GBP' in str(c))

def to_hourly(df_wide):
    out = {}
    for date, row in df_wide.iterrows():
        for h, col in enumerate(df_wide.columns):   # H01=hour0 … H24=hour23
            out[date + pd.Timedelta(hours=h)] = row[col]
    return pd.Series(out)

gb_h   = to_hourly(gb_raw)
fr_h   = to_hourly(fr_raw)
fx_h   = fx_raw[fx_col].reindex(gb_h.index, method='ffill')
spread_h = (gb_h - fr_h * fx_h).dropna().sort_index()
print(f'  Hourly spread: {len(spread_h):,} obs  '
      f'({spread_h.index.min().date()} – {spread_h.index.max().date()})')

# ── 2. Load ENTSO-E physical flow data ──────────────────────────────────────
print('Loading ENTSO-E flow data...')
flow_raw = pd.read_csv(FLOW_PATH, dtype=str)
flow_raw['ts'] = pd.to_datetime(
    flow_raw['MTU'].str.split(' - ').str[0].str.strip(),
    dayfirst=True, errors='coerce')
flow_raw['flow_mw'] = (flow_raw['Physical Flow (MW)']
                       .str.strip().replace({'n/e': None, '-': None, '': None})
                       .astype(float))

# Out Area = delivery destination (confusingly named)
# BZN|GB(IFA2) = delivered to GB = FR→GB physical flow
# BZN|FR       = delivered to FR = GB→FR physical flow
gb_recv = (flow_raw[flow_raw['Out Area'].str.contains('GB', na=False)]
           .dropna(subset=['ts','flow_mw'])
           .set_index('ts')['flow_mw'].rename('gb_to_fr'))   # label kept for consistency
fr_recv = (flow_raw[~flow_raw['Out Area'].str.contains('GB', na=False)]
           .dropna(subset=['ts','flow_mw'])
           .set_index('ts')['flow_mw'].rename('fr_to_gb'))

flow_df = (pd.concat([gb_recv, fr_recv], axis=1).fillna(0.0)
           .pipe(lambda d: d[~d.index.duplicated(keep='last')]).sort_index())
flow_df['net_flow_mw'] = flow_df['gb_to_fr'] - flow_df['fr_to_gb']
print(f'  Flow data: {flow_df.index.min().date()} – {flow_df.index.max().date()}'
      f'  ({len(flow_df):,} hours)')

# ── 3. Merge on hourly timestamp ─────────────────────────────────────────────
df = pd.DataFrame({'spread_gbp': spread_h}).join(flow_df, how='inner').dropna()
df = df.loc['2022':'2025'].copy()
df['year'] = df.index.year
print(f'  Merged: {len(df):,} hours  ({df.index.min().date()} – {df.index.max().date()})')

# ── 4. Revenue quantities ────────────────────────────────────────────────────
# Actual revenue: what the cable actually earned from its physical flows
df['actual_rev_gbpm'] = (
    df['gb_to_fr'] * df['spread_gbp'].clip(lower=0) +    # FR→GB earns when GB costly
    df['fr_to_gb'] * (-df['spread_gbp']).clip(lower=0)   # GB→FR earns when FR costly
) * AVAILABILITY / 1e6

# Theoretical: full 1000 MW, always right direction
df['theoretical_rev_gbpm'] = CAPACITY_MW * df['spread_gbp'].abs() * AVAILABILITY / 1e6

# ── 5. Direction classification ──────────────────────────────────────────────
IDLE_MW = 10.0
df['is_idle']   = df['net_flow_mw'].abs() < IDLE_MW

# Rational: spread>0 → net_flow>0 (FR→GB); spread<0 → net_flow<0 (GB→FR)
df['rational_positive'] = df['spread_gbp'] > 0   # rational = positive net_flow
df['actual_positive']   = df['net_flow_mw'] > 0

# Wrong = cable flowing but in opposite direction to price signal
df['wrong_direction'] = (
    (~df['is_idle']) &
    (df['rational_positive'] != df['actual_positive'])
)
df['correct_direction'] = (~df['is_idle']) & (~df['wrong_direction'])

# Opportunity cost: for wrong-direction hours, we forgo the full spread × 1000MW
df['opp_cost_gbpm'] = np.where(
    df['wrong_direction'],
    df['theoretical_rev_gbpm'],
    0.0
)

# ── 6. Summary ───────────────────────────────────────────────────────────────
print('\n' + '=' * 76)
print('FLOW DIRECTION MISMATCH  —  IFA2 hourly 2022-2025')
print('=' * 76)

n_total   = len(df)
n_wrong   = int(df['wrong_direction'].sum())
n_correct = int(df['correct_direction'].sum())
n_idle    = int(df['is_idle'].sum())

tot_actual = df['actual_rev_gbpm'].sum()
tot_theo   = df['theoretical_rev_gbpm'].sum()
tot_opp    = df['opp_cost_gbpm'].sum()

print(f'\n  Total hours:        {n_total:>8,}')
print(f'  Correct direction:  {n_correct:>8,}  ({n_correct/n_total*100:.1f}%)')
print(f'  Wrong direction:    {n_wrong:>8,}  ({n_wrong/n_total*100:.1f}%)')
print(f'  Idle (<{IDLE_MW:.0f} MW):    {n_idle:>8,}  ({n_idle/n_total*100:.1f}%)')

print(f'\n  Theoretical gross (1000MW, correct dir, all hours):  £{tot_theo:>7.1f}m')
print(f'  Actual revenue (from ENTSO-E flows × spread):        £{tot_actual:>7.1f}m')
print(f'  Opportunity cost from wrong-direction hours:         £{tot_opp:>7.1f}m')
print(f'  Wrong-direction cost as % of theoretical:            '
      f'{tot_opp/tot_theo*100:.1f}%')

print()
print(f'  {"Year":>5}  {"Hours":>7}  {"Correct":>8}  {"Wrong":>7}  {"Idle":>6}  '
      f'{"Theoretical":>13}  {"Actual":>9}  {"Audited":>9}  {"Residual gap":>13}')
print('  ' + '-' * 85)
for yr in [2022, 2023, 2024, 2025]:
    g = df[df['year'] == yr]
    th = g['theoretical_rev_gbpm'].sum()
    ac = g['actual_rev_gbpm'].sum()
    oc = g['opp_cost_gbpm'].sum()
    wr = int(g['wrong_direction'].sum())
    co = int(g['correct_direction'].sum())
    id_ = int(g['is_idle'].sum())
    audit = ACTUALS[yr]
    residual = ac - audit   # gap between flow-derived revenue and audited turnover
    print(f'  {yr:>5}  {len(g):>7,}  {co:>8,}  {wr:>7,}  {id_:>6,}  '
          f'{th:>13.1f}  {ac:>9.1f}  {audit:>9.1f}  {residual:>+13.1f}')

print()
print('  Residual gap = flow-derived actual minus audited turnover.')
print('  This gap = auction discount + TSO charges + balancing costs.')

print('\n  Wrong-direction hours by |spread| size:')
print(f'  {"Band (£/MWh)":>14}  {"Hours":>7}  {"Opp cost £m":>12}  {"Avg |spread|":>13}')
print('  ' + '-' * 52)
wrong_df = df[df['wrong_direction']].copy()
for lo, hi, label in [(0,5,'0–5'),(5,10,'5–10'),(10,20,'10–20'),(20,50,'20–50'),(50,999,'>50')]:
    sub = wrong_df[(wrong_df['spread_gbp'].abs() >= lo) & (wrong_df['spread_gbp'].abs() < hi)]
    if len(sub) > 0:
        print(f'  {label:>14}  {len(sub):>7,}  {sub["opp_cost_gbpm"].sum():>12.1f}  '
              f'{sub["spread_gbp"].abs().mean():>13.1f}')

# ── 7. Plots ─────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# Panel A: scatter spread vs net_flow coloured by direction match
ax = axes[0, 0]
c_mask = df['correct_direction']
w_mask = df['wrong_direction']
i_mask = df['is_idle']
ax.scatter(df.loc[c_mask,'spread_gbp'], df.loc[c_mask,'net_flow_mw'],
           s=1, alpha=0.12, color='steelblue', label='Correct direction')
ax.scatter(df.loc[w_mask,'spread_gbp'], df.loc[w_mask,'net_flow_mw'],
           s=2, alpha=0.35, color='crimson',   label='Wrong direction')
ax.scatter(df.loc[i_mask,'spread_gbp'], df.loc[i_mask,'net_flow_mw'],
           s=1, alpha=0.08, color='grey',      label='Idle')
ax.axhline(0, color='k', lw=0.8); ax.axvline(0, color='k', lw=0.8)
ax.set_xlabel('Spread GB−FR (£/MWh)'); ax.set_ylabel('Net flow MW (pos = FR→GB)')
ax.set_title('Spread vs Physical Flow Direction\n(red = flowing against price signal)',
             fontweight='bold')
ax.legend(fontsize=8, markerscale=4)

# Panel B: annual breakdown stacked bar
ax2 = axes[0, 1]
yrs = [2022, 2023, 2024, 2025]
pct_correct = [df[df['year']==y]['correct_direction'].mean()*100 for y in yrs]
pct_wrong   = [df[df['year']==y]['wrong_direction'].mean()*100   for y in yrs]
pct_idle    = [df[df['year']==y]['is_idle'].mean()*100            for y in yrs]
x = range(len(yrs))
ax2.bar(x, pct_correct, label='Correct', color='steelblue', alpha=0.8)
ax2.bar(x, pct_wrong, bottom=pct_correct, label='Wrong direction', color='crimson', alpha=0.8)
ax2.bar(x, pct_idle, bottom=[c+w for c,w in zip(pct_correct,pct_wrong)],
        label='Idle', color='lightgrey', alpha=0.8)
ax2.set_xticks(x); ax2.set_xticklabels(yrs)
ax2.set_ylabel('% of hours'); ax2.set_title('Flow Direction Quality by Year', fontweight='bold')
ax2.legend(fontsize=8)

# Panel C: revenue waterfall per year
ax3 = axes[1, 0]
bar_w = 0.25
for i, yr in enumerate(yrs):
    g = df[df['year']==yr]
    th = g['theoretical_rev_gbpm'].sum()
    ac = g['actual_rev_gbpm'].sum()
    au = ACTUALS[yr]
    ax3.bar(i - bar_w, th,  bar_w*0.9, color='steelblue',  alpha=0.7, label='Theoretical' if i==0 else '')
    ax3.bar(i,         ac,  bar_w*0.9, color='darkorange',  alpha=0.7, label='Flow-derived actual' if i==0 else '')
    ax3.bar(i + bar_w, au, bar_w*0.9, color='seagreen',    alpha=0.7, label='Audited turnover' if i==0 else '')
ax3.set_xticks(range(len(yrs))); ax3.set_xticklabels(yrs)
ax3.set_ylabel('£m'); ax3.set_title('Revenue Waterfall: Theoretical → Flow-Derived → Audited',
                                     fontweight='bold')
ax3.legend(fontsize=8)

# Panel D: wrong-direction flow by hour-of-day
ax4 = axes[1, 1]
df['hour'] = df.index.hour
wrong_by_hr = df.groupby('hour')['wrong_direction'].mean() * 100
ax4.bar(wrong_by_hr.index, wrong_by_hr.values, color='crimson', alpha=0.7)
ax4.set_xlabel('Hour of day'); ax4.set_ylabel('% hours wrong direction')
ax4.set_title('Wrong-Direction Frequency by Hour of Day\n(hints at auction timing effects)',
              fontweight='bold')
ax4.set_xticks(range(0, 24, 2))

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'flow_direction_mismatch.png', dpi=150, bbox_inches='tight')
print(f'\nSaved: flow_direction_mismatch.png')
