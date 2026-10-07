"""
Benchmark the proxy LCR against the LCR that JPMorgan Chase Bank, N.A. actually disclosed.

  proxy LCR  : read from data/processed/ratios_by_quarter.csv (output of ratios.py)
  real LCR   : typed in by hand below from the public disclosures (10-Q / LCR Disclosure
               Report, "average LCR" line). It is MANUAL INPUT, not computed -- if you
               update it, re-check each number against the source document.

Output: data/processed/lcr_benchmark.csv  (report_period, proxy, real, gap in pp)

Caveat for reading the gap: the disclosed figure is a quarterly AVERAGE under the US
liquidity rule, while the proxy is built from end-of-quarter balances using Basel factors.
So the gap mixes model-detail limits with method differences (see mapping/mapping_README.md).
"""
import csv

RATIOS_PATH = "data/processed/ratios_by_quarter.csv"
OUT_PATH = "data/processed/lcr_benchmark.csv"

# Manual input (percent), JPMorgan Chase Bank, N.A. average LCR per quarter
REAL_LCR = {
    "20240630": 125,
    "20240930": 121,
    "20250331": 124,
    "20250630": 120,
    "20250930": 117,
    "20251231": 115,
    "20260331": 120,
    "20260630": 118,
}

proxy = {r["report_period"]: float(r["LCR_pct"]) for r in csv.DictReader(open(RATIOS_PATH, encoding="utf-8"))}

rows = []
for period, real in REAL_LCR.items():
    p = proxy[period]
    rows.append([period, p, real, p - real])

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["report_period", "proxy_LCR_pct", "real_bank_LCR_pct_avg", "gap_pp"])
    w.writerows(rows)

print(f"Wrote {OUT_PATH} ({len(rows)} quarters)")
for period, p, real, gap in rows:
    print(f"{period}  proxy={p:6.1f}%  real={real}%  gap={gap:+.1f}pp")
