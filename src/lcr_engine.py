"""
Shared calculation engine for LCR / NSFR / LDR.

ratios.py, sensitivity.py and stress_testing.py all import from here, so the three
scripts can never drift apart on formulas (previously each file had its own copy).

Formulas (see mapping/mapping_README.md, section "Ratio formulas"):

  HQLA (pre-cap)  = sum(value * (1 - haircut))   over rows with hqla_level in {L1, L2A, L2B}
  HQLA (post-cap) = L1 + L2A + L2B - adjustment       Basel LCR30.45-30.46 (simplified, no
                    adjustment = max(L2A + L2B - 2/3 * L1,        unwind of secured transactions)
                                     L2B - 15/85 * (L1 + L2A), 0)
                    -> Level 2 <= 40% of HQLA, Level 2B <= 15% of HQLA
  LCR outflow     = sum(value * lcr_outflow)    liabilities + off-balance-sheet commitments
  LCR inflow      = sum(value * lcr_inflow)     assets
  net outflow     = max(outflow - inflow, 25% * outflow)       Basel LCR40.11 inflow cap (75%)
  LCR             = HQLA (post-cap) / net outflow

  ASF             = sum(value * nsfr_asf)       liabilities + equity
  RSF             = sum(value * nsfr_rsf * k)   k = LNLSNET / LNLSGR for group == 'loans', else 1
  NSFR            = ASF / RSF

  LDR             = LNLSNET / DEP

Overrides: {line_id: {field: value}} temporarily replaces a mapping factor for one run
(used by sensitivity and stress testing). Factors are clamped to [0, 1] -- an outflow
rate or haircut above 100% has no economic meaning.

Note on eval(): mapping definitions are simple arithmetic over FDIC mnemonics, evaluated
with builtins disabled. Fine for the CSV maintained inside this repo; NOT safe for
untrusted input.
"""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDE_PATH = os.path.join(ROOT, "data", "processed", "jpm_628_wide.csv")
MAPPING_PATH = os.path.join(ROOT, "mapping", "liquidity_mapping.csv")

FACTOR_FIELDS = ("hqla_haircut", "lcr_outflow", "lcr_inflow", "nsfr_asf", "nsfr_rsf")


def load_mapping(path=MAPPING_PATH):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_wide(path=WIDE_PATH):
    with open(path, encoding="utf-8") as f:
        return sorted(csv.DictReader(f), key=lambda r: r["report_period"])


def to_num(x):
    if x in (None, ""):
        return None
    try:
        return float(x)
    except ValueError:
        return None


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def env_of(row):
    env = {k: (float(v) if v not in ("", None) else 0.0) for k, v in row.items() if k != "report_period"}
    env["min"] = min
    return env


def line_value(row, definition, env=None):
    """Evaluate a mapping 'definition' formula against one quarter's wide row."""
    return eval(definition, {"__builtins__": {}}, env if env is not None else env_of(row))


def compute(row, mapping, overrides=None, extra_l1_deduction=0.0):
    """Compute every ratio for one quarter. Returns a dict.

    extra_l1_deduction: amount (USD thousands) removed from Level 1 HQLA before the caps
    -- used only by the pledged-securities test in sensitivity.py.
    """
    overrides = overrides or {}
    env = env_of(row)
    lnlsnet, lnlsgr = env.get("LNLSNET", 0.0), env.get("LNLSGR", 0.0)
    netting = lnlsnet / lnlsgr if lnlsgr else 1.0

    lvl = {"L1": 0.0, "L2A": 0.0, "L2B": 0.0}
    outflow = inflow = asf = rsf = 0.0

    for m in mapping:
        ov = overrides.get(m["line_id"], {})

        def factor(col):
            if col in ov:
                return clamp01(ov[col])
            return to_num(m[col])

        v = line_value(row, m["definition"], env)

        hl = m["hqla_level"].strip()
        if hl:
            lvl[hl] += v * (1 - (factor("hqla_haircut") or 0.0))

        f = factor("lcr_outflow")
        if f is not None:
            outflow += v * f
        f = factor("lcr_inflow")
        if f is not None:
            inflow += v * f
        f = factor("nsfr_asf")
        if f is not None:
            asf += v * f
        f = factor("nsfr_rsf")
        if f is not None:
            rsf += v * f * (netting if m["group"] == "loans" else 1.0)

    l1 = lvl["L1"] - extra_l1_deduction
    l2a, l2b = lvl["L2A"], lvl["L2B"]
    cap_adj = max(l2a + l2b - 2 / 3 * l1, l2b - 15 / 85 * (l1 + l2a), 0.0)
    hqla_pre = l1 + l2a + l2b
    hqla = hqla_pre - cap_adj

    net_outflow = max(outflow - inflow, 0.25 * outflow)
    lcr = hqla / net_outflow * 100 if net_outflow else None
    nsfr = asf / rsf * 100 if rsf else None
    dep = env.get("DEP", 0.0)
    ldr = lnlsnet / dep * 100 if dep else None

    return dict(
        HQLA_L1=l1, HQLA_L2A=l2a, HQLA_L2B=l2b, HQLA_pre_cap=hqla_pre, HQLA_cap_adj=cap_adj, HQLA=hqla,
        outflow=outflow, inflow=inflow, net_outflow=net_outflow, LCR=lcr,
        ASF=asf, RSF=rsf, NSFR=nsfr, netting=netting, LDR=ldr,
    )
