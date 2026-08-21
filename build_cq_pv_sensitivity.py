#!/usr/bin/env python3
"""Compute the two competency-question inputs that require simulation.

CQ7  rooftop-PV flexibility: self-consumption ratio, grid export and
     reverse-flow hours per archetype under the scenario PV assumption.
CQ11 scenario-parameter sensitivity: marginal effect of the heat-pump and EV
     adoption fractions on national coincident peak and annual CO2.

Both are appended to cq_test_abox.ttl.

PV CAVEAT, stated in the output graph as well as here: the NEDT workflow's own
normalised PV shape lives in a 128 MB Nexsys workbook that is not redistributable.
This script substitutes a clear-sky geometric model for Dublin (53.35 N) scaled
to 1,000 kWh/kWp/yr, the PVGIS reference the workflow documents. The shape is an
approximation and the graph records it as such via nedt:hasAssumptionBasis.
Self-consumption is computed against the real archetype load profiles.

Usage:  python3 build_cq_pv_sensitivity.py --data-root /path/to/DT_Model
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

HERE = Path(__file__).resolve().parent
HOURS = 8760
EF_ELEC = 0.226
PV_KWP = 4.0                 # typical Irish domestic system
PV_YIELD_KWH_PER_KWP = 1000.0
LAT = np.deg2rad(53.35)      # Dublin


def iri(prefix, name):
    safe = "".join(c if c.isalnum() else "_" for c in str(name))[:40]
    return f"{prefix}_{safe}_{hashlib.sha1(str(name).encode()).hexdigest()[:10]}"


def pv_shape() -> np.ndarray:
    """Normalised hourly PV output, kW per kWp, summing to PV_YIELD_KWH_PER_KWP."""
    h = np.arange(HOURS)
    doy = h // 24 + 1
    hod = h % 24
    decl = np.deg2rad(23.45) * np.sin(2 * np.pi * (284 + doy) / 365.0)
    ha = np.deg2rad(15.0 * (hod + 0.5 - 12.0))
    cos_z = np.sin(LAT) * np.sin(decl) + np.cos(LAT) * np.cos(decl) * np.cos(ha)
    clear = np.clip(cos_z, 0, None) ** 1.15          # crude atmospheric mass effect
    # Seasonal cloudiness: Irish winters are markedly duller than summers.
    cloud = 0.42 + 0.30 * np.sin(2 * np.pi * (doy - 100) / 365.0)
    gen = clear * cloud
    total = gen.sum()
    return gen * (PV_YIELD_KWH_PER_KWP / total) if total > 0 else gen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default="/Users/divyanshusood/Documents/DT_Model")
    ap.add_argument("--abox", default=str(HERE / "cq_test_abox.ttl"))
    args = ap.parse_args()
    root = Path(args.data_root)

    sys.path.insert(0, str(root / "AEI-2006-PredictiveEnergyModelling"))
    src = (root / "AEI-2006-PredictiveEnergyModelling/rerun_percatchment.py").read_text()
    ns: dict = {"__file__": str(root / "AEI-2006-PredictiveEnergyModelling/rerun_percatchment.py")}
    exec(src.split("def main()")[0], ns)
    ns["configure_data_root"](str(root))
    scan_library, resolve, load_profiles = ns["scan_library"], ns["resolve"], ns["load_profiles"]
    ELEC, COUNTS = ns["ELEC"], ns["COUNTS"]

    print("loading archetype counts ...")
    a = pd.read_csv(COUNTS)
    a["BER"] = a.BER.astype(str).str.strip().str[0]
    a["Occupancy"] = pd.to_numeric(a.Occupancy, errors="coerce").fillna(3).astype(int)
    a = a[a.ArchCount_original_2024_LV > 0]
    noev, evl = scan_library(ELEC)

    keys = sorted(set(zip(a["Build Type"], a.BER, a.Occupancy, a.HeatingSystem)))
    res_n = {k: resolve(noev, *k)[0] for k in keys}
    res_e = {k: resolve(evl, *k)[0] for k in keys}
    names = {v for v in list(res_n.values()) + list(res_e.values()) if v}
    pidx, P = load_profiles(names, ELEC)
    print(f"  {len(pidx)} profiles loaded")

    a["_k"] = list(zip(a["Build Type"], a.BER, a.Occupancy, a.HeatingSystem))
    a["fn"] = a._k.map(res_n)
    a["fe"] = a._k.map(res_e)
    a = a[a.fn.notna()]

    out = []
    W = out.append
    W("\n# ---- appended by build_cq_pv_sensitivity.py ----\n")

    # =================== CQ7: PV flexibility per archetype ===================
    print("computing PV flexibility per archetype ...")
    pv = pv_shape() * PV_KWP
    W("inst:assum_pv_shape a nedt:ScenarioAssumption ;")
    W('    nedt:hasAssumptionText "Rooftop PV output modelled as a 4 kWp system on a clear-sky '
      'geometric profile for Dublin scaled to 1,000 kWh/kWp/yr" ;')
    W('    nedt:hasAssumptionBasis "APPROXIMATION. The workflow\'s own normalised PV shape is not '
      'redistributable; this substitutes a geometric clear-sky model at the documented PVGIS yield. '
      'Self-consumption is computed against real archetype load profiles." .')
    W("")

    agg = a.groupby("_k", as_index=False).agg(n=("ArchCount_original_2024_LV", "sum"),
                                              fn=("fn", "first"))
    agg = agg.nlargest(60, "n")
    for r in agg.itertuples(index=False):
        load = P[pidx[r.fn]].astype(np.float64)
        onsite = np.minimum(load, pv)
        export = np.clip(pv - load, 0, None)
        scr = onsite.sum() / pv.sum() if pv.sum() > 0 else 0.0
        rev = int((pv > load).sum())
        fid = "inst:" + iri("flexstate", "%s_%s_%s_%s" % r._0)
        aid = "inst:" + iri("arch", "%s_%s_%s_%s" % r._0)
        W(f"{fid} a nedt:FlexibilityState ;")
        W(f"    nedt:forArchetype {aid} ;")
        W("    nedt:evaluatedUnderScenario inst:scenario_1_2024 ;")
        W(f'    nedt:hasSelfConsumptionRatio "{scr:.6f}"^^xsd:decimal ;')
        W(f'    nedt:hasGridExport "{export.sum():.6f}"^^xsd:decimal ;')
        W(f'    nedt:hasReverseFlowHours "{rev}"^^xsd:integer ;')
        W("    prov:wasGeneratedBy inst:cq_abox_build_activity .")
    print(f"  {len(agg)} flexibility states")

    # =================== CQ11: parameter sensitivity =========================
    print("computing scenario parameter sensitivity ...")

    def national(hp_frac: float, ev_frac: float):
        """National hourly series (kW) under given HP and EV adoption fractions."""
        rows = []
        for r in a.itertuples(index=False):
            n = float(r.ArchCount_original_2024_LV)
            conv = hp_frac * n if r.HeatingSystem in ("Heating Oil", "gasboiler") else 0.0
            rows.append((r.fn, r.fe, n - conv))
            if conv > 0:
                hk = (r._1, "B", r.Occupancy, "Heat Pump")
                fn2, fe2 = res_n.get(hk), res_e.get(hk)
                if fn2:
                    rows.append((fn2, fe2, conv))
        v = np.zeros(len(pidx))
        for fn, fe, n in rows:
            v[pidx[fn]] += n * (1 - ev_frac)
            if fe and fe in pidx:
                v[pidx[fe]] += n * ev_frac
        series = v @ P
        return series.max(), series.sum()

    base_pk, base_en = national(0.20, 0.10)
    print(f"  baseline: peak {base_pk/1000:.1f} MW, energy {base_en/1e6:.0f} GWh")
    sens = []
    for label, hp, ev, delta_pp in [("hp_adoption_fraction", 0.25, 0.10, 5.0),
                                    ("ev_adoption_fraction", 0.20, 0.15, 5.0)]:
        pk, en = national(hp, ev)
        d_peak_mw = (pk - base_pk) / 1000.0 / delta_pp
        d_co2_kt = (en - base_en) * EF_ELEC / 1e6 / delta_pp
        sens.append((label, d_peak_mw, d_co2_kt, delta_pp))
        print(f"  {label}: {d_peak_mw:+.3f} MW/pp, {d_co2_kt:+.3f} ktCO2/pp")

    for label, dp, dc, pp in sens:
        sid = "inst:" + iri("sens", label)
        pid = "inst:" + iri("param", label)
        W(f'{pid} a nedt:ScenarioVariable ; rdfs:label "{label}" .')
        W(f"{sid} a nedt:SensitivityResult ;")
        W("    nedt:evaluatedUnderScenario inst:scenario_1_2024 ;")
        W(f"    nedt:forParameter {pid} ;")
        W(f'    nedt:hasMarginalEffectOnPeak "{dp:.6f}"^^xsd:decimal ;')
        W(f'    nedt:hasMarginalEffectOnCO2 "{dc:.6f}"^^xsd:decimal ;')
        W(f'    nedt:hasPerturbation "{pp:.6f}"^^xsd:decimal ;')
        W("    prov:wasGeneratedBy inst:cq_abox_build_activity .")

    with open(args.abox, "a") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"\nappended to {args.abox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
