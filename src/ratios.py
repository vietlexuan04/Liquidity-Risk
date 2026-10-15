"""
Compute HQLA, LCR, NSFR and LDR for every quarter.

Inputs : data/processed/jpm_628_wide.csv, mapping/liquidity_mapping.csv
Output : data/processed/ratios_by_quarter.csv

All formulas live in src/lcr_engine.py (shared with sensitivity.py and stress_testing.py);
see mapping/mapping_README.md, section "Ratio formulas".

Ratios are written with 4 decimals so that every downstream file (benchmark, stress, README)
rounds from the same unrounded value -- avoids double-rounding mismatches such as
105.6497 -> 105.65 -> 105.7 in one file but 105.6 in another.
"""
import csv

from lcr_engine import compute, load_mapping, load_wide

OUT_PATH = "data/processed/ratios_by_quarter.csv"

mapping = load_mapping()
results = []
for row in load_wide():
    r = compute(row, mapping)
    results.append(dict(
        report_period=row["report_period"],
        HQLA_L1=round(r["HQLA_L1"]),
        HQLA_L2A=round(r["HQLA_L2A"]),
        HQLA_L2B=round(r["HQLA_L2B"]),
        HQLA_cap_adj=round(r["HQLA_cap_adj"]),
        HQLA=round(r["HQLA"]),
        LCR_outflow_gross=round(r["outflow"]),
        LCR_inflow=round(r["inflow"]),
        LCR_net_outflow=round(r["net_outflow"]),
        LCR_pct=round(r["LCR"], 4),
        NSFR_ASF=round(r["ASF"]),
        NSFR_RSF=round(r["RSF"]),
        NSFR_pct=round(r["NSFR"], 4),
        loan_netting_factor=round(r["netting"], 4),
        LDR_pct=round(r["LDR"], 4),
    ))

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)

print(f"Wrote {OUT_PATH} ({len(results)} quarters)  [amounts in USD thousands; printed below in $B]\n")
print(f"{'quarter':10s} {'LCR%':>7s} {'NSFR%':>7s} {'LDR%':>7s} {'HQLA':>8s} {'L2 share':>9s} {'cap adj':>8s} {'ASF':>8s} {'RSF':>8s}")
for r in results:
    l2_share = (r["HQLA_L2A"] + r["HQLA_L2B"]) / (r["HQLA_L1"] + r["HQLA_L2A"] + r["HQLA_L2B"]) * 100
    print(f"{r['report_period']:10s} {r['LCR_pct']:>7.1f} {r['NSFR_pct']:>7.1f} {r['LDR_pct']:>7.1f} "
          f"{r['HQLA']/1e6:>8,.1f} {l2_share:>8.1f}% {r['HQLA_cap_adj']/1e6:>8,.1f} "
          f"{r['NSFR_ASF']/1e6:>8,.1f} {r['NSFR_RSF']/1e6:>8,.1f}")
