"""
Two naive scenarios vs properly anchored:
A) tau extrapolated (trend not frozen) + no Annex M
B) tau=0, demeaned, no Annex M (zero level)
Parameters from v2 notebook (cell 38). No changes to main notebook.
"""
import numpy as np

PHI     = 0.70369
THETA   = -0.3363
C_OU    = (1 - PHI) * THETA
SIGMA_D = 15.0431
PHI_Y   = 0.62872
JP_RATE = 0.036
JP_MEAN = 50.0  # abs size, symmetric

# OLS trend coefficient (from notebook: b1 = +9.45 GBP/MWh per unit tau)
# tau is fraction of year from t0_spread (≈ 2021-12-01)
B1_TREND   = 9.45   # GBP/MWh per year
OLS_MEAN_2021 = 36.62  # daily mean f_S at tau=0 (estimation-period intercept)
T0_YEAR    = 2021.92   # approx fractional year of t0_spread

CAP_W1   = 61.6
FLOOR_W1 = 37.8

N_PATHS = 5000
N_PROJ_YEARS = 20
DAYS_PER_YEAR = 365.25
N_DAYS = int(N_PROJ_YEARS * DAYS_PER_YEAR)
AVAIL = 0.9659
CR    = 0.2591
CAPACITY_MWH_PER_HOUR = 1000.0  # 1 GW

# Within-day shape proxy: zero-mean, ≈28 peak-to-trough
HOURS = np.arange(24)
SHAPE_H = 14.14 * np.sin(2 * np.pi * (HOURS - 5) / 24)

def run_sim(label, level_fn):
    """level_fn(year_int) -> annual mean level in GBP/MWh"""
    rng = np.random.default_rng(42)
    annual_rev = np.zeros((N_PATHS, N_PROJ_YEARS))
    BATCH = 500
    for b0 in range(0, N_PATHS, BATCH):
        b1 = min(b0 + BATCH, N_PATHS)
        n  = b1 - b0
        X  = np.zeros(n)
        Y  = np.zeros(n)
        yr_rev = np.zeros((N_PROJ_YEARS, n))
        for d in range(N_DAYS):
            yr_idx = min(int(d / DAYS_PER_YEAR), N_PROJ_YEARS - 1)
            cal_yr = 2026 + yr_idx
            lvl    = level_fn(cal_yr, d)
            X = C_OU + PHI * X + SIGMA_D * rng.standard_normal(n)
            arrivals = rng.uniform(size=n) < JP_RATE
            sizes    = rng.exponential(JP_MEAN / 2, size=n) * rng.choice([-1, 1], size=n)
            Y = PHI_Y * Y + arrivals * sizes
            daily = 0.0
            for h in range(24):
                spread_h = lvl + SHAPE_H[h] + X + Y
                daily += np.abs(spread_h) * CAPACITY_MWH_PER_HOUR
            yr_rev[yr_idx] += daily
        for yr in range(N_PROJ_YEARS):
            annual_rev[b0:b1, yr] = yr_rev[yr] * AVAIL * CR / 1e6

    print(f"\n=== {label} ===")
    print(f"  {'Year':>4}  {'P10':>7}  {'P50':>7}  {'P90':>7}  {'P>Cap':>7}  {'P<Flr':>7}")
    print("  " + "-"*50)
    for yr in [0, 4, 9, 14, 19]:
        p10 = np.percentile(annual_rev[:, yr], 10)
        p50 = np.percentile(annual_rev[:, yr], 50)
        p90 = np.percentile(annual_rev[:, yr], 90)
        pc  = np.mean(annual_rev[:, yr] > CAP_W1) * 100
        pf  = np.mean(annual_rev[:, yr] < FLOOR_W1) * 100
        print(f"  {2026+yr:>4}  {p10:>7.1f}  {p50:>7.1f}  {p90:>7.1f}  {pc:>6.1f}%  {pf:>6.1f}%")
    overall_p50 = np.percentile(annual_rev, 50, axis=0).mean()
    print(f"  Mean P50 (all years): £{overall_p50:.0f}m")
    return annual_rev

# Scenario A: trend extrapolated (not frozen), no Annex M — pure naive
def level_A(cal_yr, day_abs):
    tau = (cal_yr + (day_abs % DAYS_PER_YEAR) / DAYS_PER_YEAR) - T0_YEAR
    return OLS_MEAN_2021 + B1_TREND * tau  # raw f_S mean including trend

# Scenario B: tau=0, demeaned, no Annex M
def level_B(cal_yr, day_abs):
    return 0.0

run_sim("A: Naive — trend extrapolated, no Annex M anchoring", level_A)
run_sim("B: tau frozen, demeaned, no Annex M (zero level)", level_B)
