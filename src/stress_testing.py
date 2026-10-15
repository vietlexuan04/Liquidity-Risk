"""
Stress testing engine -- LCR only (NSFR stress is out of scope for this version).

Explicit assumption: NO management action / counterbalancing capacity is modelled. All
results are the "mechanical" response of the balance sheet as reported to the stated shock;
a real bank would respond (draw contingency lines, sell non-HQLA assets, cut new lending).

Every result is reported both as an absolute LCR% and as a delta vs the same quarter's OWN
baseline, because the proxy baseline already sits well below the LCR JPMorgan discloses
(see mapping/mapping_README.md, "Benchmark"). The absolute stressed number alone would
overstate how distressed the bank looks.

All factor overrides are clamped to [0, 1] by lcr_engine.compute (a run-off rate or haircut
above 100% is meaningless).

Outputs (data/processed/):
  stress_scenarios_by_quarter.csv   3 fixed scenarios x 14 quarters
  stress_montecarlo_2026Q2.csv      deposit run-off distribution, latest quarter
  stress_survival_horizon.csv       days until HQLA is exhausted, 2 outflow profiles
  stress_reverse_test.csv           shock intensity needed to hit target LCRs
"""
import csv
import random

from lcr_engine import compute, load_mapping, load_wide

mapping_rows = load_mapping()
mapping = {m["line_id"]: m for m in mapping_rows}
wide = load_wide()
latest = wide[-1]


def run(row, overrides=None):
    return compute(row, mapping_rows, overrides)


def base_factor(line_id, field):
    v = mapping[line_id][field]
    return float(v) if v not in ("", None) else 0.0


# ---------------------------------------------------------------------------
# 1. Fixed scenarios
# ---------------------------------------------------------------------------
OFF_BS_LINES = ["O_CARD", "O_HELOC", "O_CRE", "O_OTHER", "O_SBLC"]

IDIOSYNCRATIC = {
    "D_INS_STABLE": {"lcr_outflow": 0.10},
    "D_INS_BRO": {"lcr_outflow": 0.25},
    "D_DOM_UNINS_OTH": {"lcr_outflow": 0.70},
    "D_FO_IPC": {"lcr_outflow": 0.70},
    **{lid: {"lcr_outflow": base_factor(lid, "lcr_outflow") * 1.5} for lid in OFF_BS_LINES},
}
MARKET_WIDE = {
    "S_GSE": {"hqla_haircut": 0.25},
    "S_MUNI": {"hqla_haircut": 0.65},
    "B_REPO": {"lcr_outflow": 0.50},
    # B_ST is not stressed: the baseline already assumes 100% non-rollover of the share of
    # <=1y borrowings that matures within 30 days (the Basel maximum for maturing unsecured
    # wholesale funding). The remainder is not contractually due inside the 30-day window,
    # so there is no further outflow to stress without changing the maturity assumption.
}
COMBINED = {**IDIOSYNCRATIC, **MARKET_WIDE}
SCENARIOS = {"idiosyncratic": IDIOSYNCRATIC, "market_wide": MARKET_WIDE, "combined": COMBINED}

print("=== 1. Fixed scenarios across all 14 quarters ===\n")
scenario_rows, scenario_raw = [], []
for row in wide:
    base_lcr = run(row)["LCR"]
    raw = dict(report_period=row["report_period"], baseline_LCR_pct=base_lcr)
    for name, ov in SCENARIOS.items():
        s_lcr = run(row, ov)["LCR"]
        raw[f"{name}_LCR_pct"] = s_lcr
        raw[f"{name}_delta_pp"] = s_lcr - base_lcr
        raw[f"{name}_delta_pct_of_baseline"] = (s_lcr - base_lcr) / base_lcr * 100
    scenario_raw.append(raw)  # printed from unrounded values (avoids 105.6476 -> 105.65 -> "105.7")
    scenario_rows.append({k: (v if k == "report_period" else round(v, 2)) for k, v in raw.items()})

with open("data/processed/stress_scenarios_by_quarter.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(scenario_rows[0].keys()))
    w.writeheader()
    w.writerows(scenario_rows)

print(f"{'quarter':10s} {'baseline':>9s} {'idio':>9s}(dpp) {'market':>9s}(dpp) {'combined':>9s}(dpp)")
for r in scenario_raw:
    print(f"{r['report_period']:10s} {r['baseline_LCR_pct']:>9.1f} "
          f"{r['idiosyncratic_LCR_pct']:>9.1f}({r['idiosyncratic_delta_pp']:+.1f}) "
          f"{r['market_wide_LCR_pct']:>9.1f}({r['market_wide_delta_pp']:+.1f}) "
          f"{r['combined_LCR_pct']:>9.1f}({r['combined_delta_pp']:+.1f})")

# ---------------------------------------------------------------------------
# 2. Monte Carlo deposit run-off (latest quarter)
# ---------------------------------------------------------------------------
print("\n=== 2. Monte Carlo deposit run-off (latest quarter, 10,000 draws) ===\n")
MC_LINES = ["D_INS_STABLE", "D_INS_BRO", "D_DOM_UNINS_OTH", "D_FO_IPC"]
MC_REL_STD = 0.20  # std = 20% of mean -- a chosen parameter, not calibrated
N_DRAWS = 10_000


def beta_params(mean, std):
    common = mean * (1 - mean) / std ** 2 - 1
    return mean * common, (1 - mean) * common


random.seed(42)
base_lcr_latest = run(latest)["LCR"]
mc = []
for _ in range(N_DRAWS):
    ov = {k: dict(v) for k, v in COMBINED.items()}
    for lid in MC_LINES:  # drawn independently (correlation = 0, stated limitation)
        mean = COMBINED[lid]["lcr_outflow"]
        ov[lid]["lcr_outflow"] = random.betavariate(*beta_params(mean, MC_REL_STD * mean))
    mc.append(run(latest, ov)["LCR"])
mc.sort()


def pct(p):
    return mc[int(p / 100 * (N_DRAWS - 1))]


with open("data/processed/stress_montecarlo_2026Q2.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["percentile", "LCR_pct", "delta_pp_vs_baseline"])
    for p in (5, 25, 50, 75, 95):
        v = pct(p)
        w.writerow([p, round(v, 2), round(v - base_lcr_latest, 2)])
        print(f"p{p:<3d} LCR={v:6.1f}%  delta={v - base_lcr_latest:+.1f}pp")

# ---------------------------------------------------------------------------
# 3. Survival horizon (latest quarter)
#    Two outflow profiles for the 30-day net outflow, HQLA assumed usable from day 1:
#    - uniform     : net_outflow/30 per day. NOTE: survival days = 30 x LCR exactly, so this
#                    profile adds no information beyond the LCR -- kept only as a reference.
#    - front-loaded: 40% of the 30-day net outflow in days 1-5 (8%/day), the remaining 60%
#                    over days 6-30 (2.4%/day). Illustrative profile: run-offs concentrate
#                    early in a real stress. This is the informative column.
# ---------------------------------------------------------------------------
print("\n=== 3. Survival horizon (latest quarter) ===\n")
FRONT_DAYS, FRONT_SHARE = 5, 0.40


def survival_uniform(hqla, net_out):
    return min(hqla / (net_out / 30), 30.0)


def survival_front_loaded(hqla, net_out):
    early = FRONT_SHARE * net_out
    if hqla <= early:
        return hqla / (early / FRONT_DAYS)
    late_daily = (1 - FRONT_SHARE) * net_out / (30 - FRONT_DAYS)
    return min(FRONT_DAYS + (hqla - early) / late_daily, 30.0)


survival_rows = []
for name, ov in {"baseline": {}, **SCENARIOS}.items():
    r = run(latest, ov)
    su, sf = survival_uniform(r["HQLA"], r["net_outflow"]), survival_front_loaded(r["HQLA"], r["net_outflow"])
    survival_rows.append(dict(scenario=name, HQLA_B=round(r["HQLA"] / 1e6, 1),
                              net_outflow_30d_B=round(r["net_outflow"] / 1e6, 1), LCR_pct=round(r["LCR"], 2),
                              survival_days_uniform=round(su, 1), survival_days_front_loaded=round(sf, 1),
                              survives_30d="Yes" if r["HQLA"] >= r["net_outflow"] else "No"))
    print(f"{name:14s} HQLA={r['HQLA']/1e6:7.1f}B net_out={r['net_outflow']/1e6:7.1f}B LCR={r['LCR']:5.1f}% "
          f"uniform={su:4.1f}d front-loaded={sf:4.1f}d")

with open("data/processed/stress_survival_horizon.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(survival_rows[0].keys()))
    w.writeheader()
    w.writerows(survival_rows)

# ---------------------------------------------------------------------------
# 4. Reverse stress test (latest quarter)
#    theta = shock intensity: 0 = baseline, 1 = full combined scenario; each factor is
#    interpolated linearly (extrapolated outside [0, 1]) and then clamped to [0, 1].
#    Because of the clamp, LCR has a FLOOR: once every stressed factor reaches 100%, more
#    theta changes nothing. Targets below that floor are not reachable with these levers.
# ---------------------------------------------------------------------------
print("\n=== 4. Reverse stress test (latest quarter) ===\n")
THETA_LO, THETA_HI = -1.0, 50.0


def overrides_at(theta):
    return {lid: {f: base_factor(lid, f) + theta * (tgt - base_factor(lid, f)) for f, tgt in fields.items()}
            for lid, fields in COMBINED.items()}


def lcr_at(theta):
    return run(latest, overrides_at(theta))["LCR"]


def solve_theta(target, lo=THETA_LO, hi=THETA_HI, iters=80):
    if not (lcr_at(hi) <= target <= lcr_at(lo)):  # LCR is non-increasing in theta
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if lcr_at(mid) > target else (lo, mid)
    return (lo + hi) / 2


floor_lcr = run(latest, {lid: {f: 1.0 for f in fields} for lid, fields in COMBINED.items()})["LCR"]

reverse_rows = []
for target in (100, 75, 50):
    th = solve_theta(target)
    if th is None:
        note = "not reachable"
    elif th < 0:
        note = f"baseline is already below target; stress would have to be REDUCED by {abs(th)*100:.0f}% of the combined-scenario gap"
    else:
        note = f"{th*100:.0f}% of the combined-scenario shock"
    reverse_rows.append(dict(target_LCR_pct=target, required_theta=round(th, 3) if th is not None else "",
                             LCR_floor_pct="", interpretation=note))
    print(f"target {target:3d}%: theta={th:.3f}  -> {note}")

reverse_rows.append(dict(target_LCR_pct="floor", required_theta="", LCR_floor_pct=round(floor_lcr, 2),
                         interpretation="every stressed factor at 100% (all stressed deposits and commitments run off, "
                                        "repo fully lost, GSE/muni HQLA worthless); lower LCRs need levers outside this scenario"))
print(f"\nLCR floor with every stressed factor at 100%: {floor_lcr:.1f}%")

with open("data/processed/stress_reverse_test.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(reverse_rows[0].keys()))
    w.writeheader()
    w.writerows(reverse_rows)

print("\nWrote: stress_scenarios_by_quarter.csv, stress_montecarlo_2026Q2.csv, "
      "stress_survival_horizon.csv, stress_reverse_test.csv")
