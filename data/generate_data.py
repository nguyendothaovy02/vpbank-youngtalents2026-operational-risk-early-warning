"""
generate_data.py
------------------------------------------------------------------
Synthetic operational-risk data generator for the VPBank Young
Talents 2026 case study (Topic 2).

ALL DATA PRODUCED HERE IS SYNTHETIC AND ILLUSTRATIVE.
It does not represent real VPBank systems, customers, or incidents.

Outputs (written into the same /data folder):
  1. transactions_daily.csv   -> feeds KRI 1, 2, 3, 5
  2. transactions_sample.csv  -> small raw sample so slide SQL is runnable
  3. ekyc_daily.csv           -> feeds KRI 4
  4. incidents.csv            -> System Downtime (outcome metric, excluded)
  5. hr_daily.csv             -> feeds KRI 6

Design goals (so the numbers are defensible in interview):
  - A realistic BASELINE: failure rate wanders around ~2-3% with noise.
  - SEASONALITY: pay-days (5th, 20th) and a Tet-like peak raise volume
    and mildly raise failures  ->  these are FALSE ALARMS the ML must
    learn to ignore via calendar features.
  - 3 INJECTED OUTAGES: known bad windows where SYSTEM failure spikes.
    These are the TRUE anomalies used to measure recall.
The injected-outage dates are printed at the end so you always know the
"answer key" when explaining the notebook.
"""

import numpy as np
import pandas as pd

# ------------------------------------------------------------------
# 0. Reproducibility: a fixed seed means identical data every run.
# ------------------------------------------------------------------
SEED = 42
rng = np.random.default_rng(SEED)

# ------------------------------------------------------------------
# 1. Time frame: 180 days (matches "N = 180 days" on Slide 9)
# ------------------------------------------------------------------
START = pd.Timestamp("2026-01-01")
N_DAYS = 180
dates = pd.date_range(START, periods=N_DAYS, freq="D")

# ------------------------------------------------------------------
# 2. The "story" planted in the data
# ------------------------------------------------------------------
PAYDAYS = {5, 20}                     # higher volume + mild failures
TET_WINDOW = set(range(40, 47))       # seasonal peak (FALSE ALARM source)
INJECTED_OUTAGES = {                  # ground-truth anomalies (TRUE)
    58:  0.07,
    103: 0.09,
    150: 0.06,
}

# ------------------------------------------------------------------
# 3. TRANSACTION data: daily aggregate + a small raw sample
# ------------------------------------------------------------------
daily_rows = []
sample_rows = []
SAMPLE_DAY_INDEX = 58   # capture raw rows for one outage day as a demo

for i, day in enumerate(dates):
    base_vol = 8000
    if day.day in PAYDAYS:
        base_vol = int(base_vol * 1.6)
    if i in TET_WINDOW:
        base_vol = int(base_vol * 2.0)
    volume = int(rng.normal(base_vol, base_vol * 0.05))

    base_fail = 0.025 + rng.normal(0, 0.004)
    if day.day in PAYDAYS:
        base_fail += 0.008
    if i in TET_WINDOW:
        base_fail += 0.012
    outage_extra = INJECTED_OUTAGES.get(i, 0.0)
    p_fail = max(base_fail + outage_extra, 0.005)

    if outage_extra > 0:
        cls_mix = [0.75, 0.15, 0.10]   # outage: mostly SYSTEM
    else:
        cls_mix = [0.30, 0.20, 0.50]   # normal: client mistakes dominate

    n_fail = rng.binomial(volume, p_fail)
    n_success = volume - n_fail
    n_override = rng.binomial(volume, 0.002)
    fail_counts = rng.multinomial(n_fail, cls_mix)

    active_users = int(volume * 0.7)
    if outage_extra > 0:
        users_3fails = int(rng.normal(active_users * 0.03, active_users * 0.005))
    else:
        users_3fails = int(rng.normal(active_users * 0.006, active_users * 0.002))
    users_3fails = max(users_3fails, 0)

    daily_rows.append({
        "date": day.date(),
        "total_tx": volume,
        "success": n_success,
        "fail_system": int(fail_counts[0]),
        "fail_partner": int(fail_counts[1]),
        "fail_client": int(fail_counts[2]),
        "manual_override": int(n_override),
        "active_users": active_users,
        "users_3plus_fails": users_3fails,
    })

    if i == SAMPLE_DAY_INDEX:
        labels = (["SYSTEM"] * int(fail_counts[0])
                  + ["PARTNER"] * int(fail_counts[1])
                  + ["CLIENT"] * int(fail_counts[2])
                  + ["NONE"] * n_success)
        rng.shuffle(labels)
        for ec in labels:
            status = "SUCCESS" if ec == "NONE" else "FAILED"
            is_override = rng.random() < 0.002
            sample_rows.append((day.date(), status, ec, is_override))

pd.DataFrame(daily_rows).to_csv("transactions_daily.csv", index=False)
pd.DataFrame(
    sample_rows, columns=["date", "status", "error_class", "is_override"]
).to_csv("transactions_sample.csv", index=False)

# ------------------------------------------------------------------
# 4. eKYC onboarding funnel (KRI 4). Liveness is the bottleneck and
#    slowly worsens over the 180 days.
# ------------------------------------------------------------------
ekyc_rows = []
for i, day in enumerate(dates):
    sessions = int(rng.normal(500, 40))
    liveness_drop = 0.18 + (i / N_DAYS) * 0.12 + rng.normal(0, 0.01)
    p1, p2, p4 = 0.05, 0.08, 0.03
    p3 = liveness_drop
    probs = [p1, p2, p3, p4, max(1 - (p1 + p2 + p3 + p4), 0.01)]
    counts = rng.multinomial(sessions, np.array(probs) / sum(probs))
    ekyc_rows.append({
        "date": day.date(),
        "started": sessions,
        "drop_start": int(counts[0]),
        "drop_document": int(counts[1]),
        "drop_liveness": int(counts[2]),
        "drop_matching": int(counts[3]),
        "completed": int(counts[4]),
    })
pd.DataFrame(ekyc_rows).to_csv("ekyc_daily.csv", index=False)

# ------------------------------------------------------------------
# 5. System incidents / downtime (outcome metric, excluded from EWS)
# ------------------------------------------------------------------
inc_rows = []
for i, day in enumerate(dates):
    if i in INJECTED_OUTAGES:
        downtime = int(rng.normal(35, 8))
    elif rng.random() < 0.05:
        downtime = int(rng.normal(8, 3))
    else:
        downtime = 0
    inc_rows.append((day.date(), max(downtime, 0)))
pd.DataFrame(inc_rows, columns=["date", "downtime_min"]).to_csv(
    "incidents.csv", index=False)

# ------------------------------------------------------------------
# 6. HR daily snapshot (KRI 6: overdue mandatory training)
# ------------------------------------------------------------------
hr_rows = []
overdue = 0.08
for i, day in enumerate(dates):
    overdue += rng.normal(0, 0.003)
    overdue = min(max(overdue, 0.03), 0.15)
    hr_rows.append((day.date(), round(overdue * 100, 2)))
pd.DataFrame(hr_rows, columns=["date", "overdue_training_pct"]).to_csv(
    "hr_daily.csv", index=False)

# ------------------------------------------------------------------
# 7. Report (the "answer key")
# ------------------------------------------------------------------
print("=" * 60)
print("SYNTHETIC DATA GENERATED (illustrative only)")
print("=" * 60)
print(f"transactions_daily.csv  : {len(daily_rows):>7,} rows (1 per day)")
print(f"transactions_sample.csv : {len(sample_rows):>7,} rows (raw, 1 day)")
print(f"ekyc_daily.csv          : {len(ekyc_rows):>7,} rows")
print(f"incidents.csv           : {len(inc_rows):>7,} rows")
print(f"hr_daily.csv            : {len(hr_rows):>7,} rows")
print("-" * 60)
print("Injected SYSTEM outages (ground-truth anomalies):")
for d, extra in INJECTED_OUTAGES.items():
    print(f"  - {dates[d].date()} (day {d}): +{int(extra*100)}pp failure")
print("=" * 60)