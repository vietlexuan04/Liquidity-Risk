"""
Benchmark the proxy LCR against the LCR that JPMorgan Chase Bank, N.A. actually disclosed.

  proxy LCR : read from data/processed/ratios_by_quarter.csv (output of ratios.py)
  real LCR  : typed in by hand below. It is MANUAL INPUT, not computed -- if you update it,
              re-check each number against the source document.

Source: JPMorgan Chase & Co. Form 10-Q, "Consolidated financial highlights" table, row
"JPMorgan Chase Bank, N.A. LCR (average)". Each 10-Q shows five quarters:
  - 10-Q for 1Q24 -> 1Q23, 2Q23, 3Q23, 4Q23, 1Q24
  - 10-Q for 1Q25 -> 2Q24, 3Q24, 4Q24, 1Q25
  - 10-Q for 2Q26 -> 2Q25, 3Q25, 4Q25, 1Q26, 2Q26
All 14 quarters of the dataset are covered.

Output: data/processed/lcr_benchmark.csv (report_period, proxy, real, gap in pp)

Caveat for reading the gap: the disclosed figure is a quarterly AVERAGE under the US
liquidity rule (12 CFR 249), while the proxy uses END-OF-QUARTER balances and Basel factors.
The gap therefore mixes data-granularity limits with method differences
(see mapping/mapping_README.md, "Benchmark").
"""
import csv

RATIOS_PATH = "data/processed/ratios_by_quarter.csv"
OUT_PATH = "data/processed/lcr_benchmark.csv"

# Manual input (percent): JPMorgan Chase Bank, N.A. average LCR per quarter
REAL_LCR = {
    "20230331": 140, "20230630": 129, "20230930": 123, "20231231": 129,  # 10-Q 1Q24
    "20240331": 129,                                                     # 10-Q 1Q24
    "20240630": 125, "20240930": 121, "20241231": 124, "20250331": 124,  # 10-Q 1Q25
    "20250630": 120, "20250930": 117, "20251231": 115,                   # 10-Q 2Q26
    "20260331": 120, "20260630": 118,                                    # 10-Q 2Q26
}

with open(RATIOS_PATH, encoding="utf-8") as f:
    proxy = {r["report_period"]: float(r["LCR_pct"]) for r in csv.DictReader(f)}

rows = []
for period in sorted(REAL_LCR):
    p, real = proxy[period], REAL_LCR[period]
    rows.append([period, p, real, p - real])

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["report_period", "proxy_LCR_pct", "real_bank_LCR_pct_avg", "gap_pp"])
    w.writerows([[per, round(p, 2), real, round(g, 2)] for per, p, real, g in rows])

gaps = [g for *_, g in rows]
print(f"Wrote {OUT_PATH} ({len(rows)} quarters)")
for period, p, real, gap in rows:
    print(f"{period}  proxy={p:6.1f}%  real={real}%  gap={gap:+.1f}pp")
print(f"gap range: {min(gaps):+.1f} to {max(gaps):+.1f}pp, mean {sum(gaps)/len(gaps):+.1f}pp")
