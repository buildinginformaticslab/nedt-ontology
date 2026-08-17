#!/usr/bin/env python3
"""Per-catchment profile summation for NEDT LV capacity and MV diagnostics.

Implements the allocate-then-maximise operator that the paper's Eq. (3)-(4)
describe but the released pipeline did not use:

    D_t(h) = sum over archetypes a in catchment t of  n_{a,t} * d_a(h)
    P_t    = max_h D_t(h)

instead of the released maximise-then-allocate operator

    P_t    = gamma * max_h D_county(h) * n_t / N_county

Three corrections are applied together (steps 1-3 of the revision plan):

  1. ONE BASIS. LV capacity and MV coincident peaks are derived from the same
     station-level hourly series. Upstream capacity verdicts are not produced
     until parent capacity registers are reconciled.

  2. PER-CATCHMENT SUMMATION. Station demand is built from the archetype mix
     actually present in that catchment.

  3. NO SECOND DIVERSITY DISCOUNT. max_h sum_b d_b(h) is already an
     after-diversity quantity, so the coincidence factor gamma is not applied.
     The released pipeline applied gamma=0.67 on top of it.

Outputs a per-station table and a comparison against ESB Networks published
utilisation, against the uniform-rate baseline the paper currently reports.

Usage:  python3 rerun_percatchment.py [--data-root PATH] [--county Dublin] [--out DIR]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

# The default supports a checkout inside the DT_Model workspace.  A public
# clone cannot include restricted source inputs, so external users must point
# --data-root (or NEDT_DATA_ROOT) at their licensed data workspace.
ROOT = Path(__file__).resolve().parents[1]
COUNTS: Path
ELEC: Path
CAP: Path
ESB: Path
LVNET: Path
BLDG: Path


def configure_data_root(root: str | Path | None = None, *, validate: bool = True) -> Path:
    """Configure restricted-source locations and fail early when incomplete."""
    global ROOT, COUNTS, ELEC, CAP, ESB, LVNET, BLDG
    ROOT = Path(root).expanduser().resolve() if root else ROOT.resolve()
    COUNTS = ROOT / "CountyAnalysis/ArchetypeCounts_CountyLevel2024/ArchetypeCounts_LV_heating.csv"
    ELEC = ROOT / "CountyAnalysis/2024_disaggregated/total_electricity copy 2"
    CAP = ROOT / "LV_analysis/LV Network Creation/station_capacities_2024_filled.csv"
    ESB = ROOT / "catchment_methods_study/data/esb_lv_availability_2024.csv"
    LVNET = ROOT / "lv_mv_hv/lv_stations_2024.csv"
    BLDG = ROOT / "catchment_methods_study/data/BuildingMaster_LV_Assigned_2024.csv"
    if not validate:
        return ROOT
    missing = [p for p in (COUNTS, ELEC, CAP, ESB, LVNET, BLDG) if not p.exists()]
    if missing:
        details = "\n  ".join(str(p) for p in missing)
        raise FileNotFoundError(
            f"NEDT data root is incomplete: {ROOT}\nMissing:\n  {details}\n"
            "Pass --data-root PATH or set NEDT_DATA_ROOT to a licensed DT_Model data workspace."
        )
    return ROOT


configure_data_root(validate=False)

HOURS = 8760
DEFAULT_KVA = 200.0
# Released pipeline's coincidence factor, applied here only to reproduce the
# published baseline for comparison. It is NOT applied to the new operator.
GAMMA_RELEASED = 0.67
RATE_RELEASED = 0.7768498  # kW/dwelling, published national baseline

BUILD_FALLBACK = {"Terraced house": "Terraced", "Duplex": "Apartment",
                  "Temporary Structure": "Terraced"}
HEAT_MAP = {"Heating Oil": "Oilboiler", "Heat Pump": "HeatPump",
            "gasboiler": "gasboiler", "Electric": "HeatPump",
            "Solar Thermal": "gasboiler"}
BER_ORDER = "ABCDEFG"


def norm_station(s: pd.Series) -> pd.Series:
    return (s.astype(str)
             .str.replace(r"^MV/LV Substation\s*", "", regex=True)
             .str.strip().str.upper())


def scan_library(d: Path):
    """Return {(build, heat): {(ber, occ): filename}} for non-EV and EV."""
    noev, ev = defaultdict(dict), defaultdict(dict)
    pat = re.compile(r"([A-Za-z]+)_([A-G])_(\d)_([A-Za-z]+?)(_EV)?_(\d{4}_\d{4})\.csv$")
    for f in d.iterdir():
        m = pat.match(f.name)
        if not m:
            continue
        build, ber, occ, heat, is_ev, _ = m.groups()
        (ev if is_ev else noev)[(build, heat)][(ber, int(occ))] = f.name
    return noev, ev


def resolve(lib, build, ber, occ, heat):
    """Nearest available (ber, occ) within the same build+heat cell."""
    build = BUILD_FALLBACK.get(build, build)
    heat = HEAT_MAP.get(heat)
    if heat is None:
        return None, "no-heating-map"
    cell = lib.get((build, heat))
    if not cell:
        return None, "no-cell"
    if (ber, occ) in cell:
        return cell[(ber, occ)], "exact"
    bi = BER_ORDER.index(ber) if ber in BER_ORDER else 3
    best, bestd = None, None
    for (b2, o2), fn in cell.items():
        d = (abs(BER_ORDER.index(b2) - bi), abs(o2 - occ))
        if bestd is None or d < bestd:
            best, bestd = fn, d
    return best, "nearest"


def load_profiles(names, d: Path):
    """Load each profile once into a (n_profiles, 8760) float32 array, in kW."""
    idx = {n: i for i, n in enumerate(sorted(names))}
    P = np.zeros((len(idx), HOURS), dtype=np.float32)
    for n, i in idx.items():
        frame = pd.read_csv(d / n)
        required = {"Date/Time", "Electricity:Facility [GWh](Hourly)"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{n}: missing required profile columns {sorted(missing)}")
        v = frame["Electricity:Facility [GWh](Hourly)"].to_numpy(dtype=np.float64)
        if len(v) != HOURS:
            raise ValueError(f"{n}: expected {HOURS} hourly values, found {len(v)}")
        if not np.isfinite(v).all():
            raise ValueError(f"{n}: profile contains non-finite values")
        P[i] = (v * 1e6).astype(np.float32)   # GWh/h -> kW
    return idx, P


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=None,
                    help="licensed DT_Model data workspace (or set NEDT_DATA_ROOT)")
    ap.add_argument("--county", default=None, help="restrict to one county")
    ap.add_argument("--out", default=str(Path(__file__).parent / "rerun_out"))
    args = ap.parse_args()
    configure_data_root(args.data_root or os.environ.get("NEDT_DATA_ROOT"))
    out = Path(args.out); out.mkdir(exist_ok=True)

    print("loading archetype counts ...")
    a = pd.read_csv(COUNTS)
    a["k"] = norm_station(a["Station Name"])
    a["BER"] = a.BER.astype(str).str.strip().str[0]
    a["Occupancy"] = pd.to_numeric(a.Occupancy, errors="coerce").fillna(3).astype(int)

    if args.county:
        print(f"restricting to county = {args.county}")
        bm = pd.read_csv(BLDG, usecols=["Station Name", "CountyNameNorm"], low_memory=False)
        bm["k"] = norm_station(bm["Station Name"])
        cty = (bm.groupby("k").CountyNameNorm
                 .agg(lambda s: s.value_counts().idxmax()))
        keep = set(cty[cty.astype(str).str.lower() == args.county.lower()].index)
        a = a[a.k.isin(keep)]
        print(f"  stations in county: {a.k.nunique():,}")

    print("resolving archetypes to profiles ...")
    noev_lib, ev_lib = scan_library(ELEC)
    combos = a[["Build Type", "BER", "Occupancy", "HeatingSystem"]].drop_duplicates()
    res_n, res_e, how = {}, {}, {}
    for r in combos.itertuples(index=False):
        key = (r[0], r[1], r[2], r[3])
        fn, h = resolve(noev_lib, *key)
        fe, _ = resolve(ev_lib, *key)
        res_n[key], res_e[key], how[key] = fn, fe, h
    a["_key"] = list(zip(a["Build Type"], a.BER, a.Occupancy, a.HeatingSystem))
    a["f_noev"] = a._key.map(res_n)
    a["f_ev"] = a._key.map(res_e)
    a["match"] = a._key.map(how)
    a = a[a.f_noev.notna()].copy()

    tot = a.ArchCount_original_2024_LV.sum()
    exact = a.loc[a.match == "exact", "ArchCount_original_2024_LV"].sum()
    print(f"  dwellings resolved : {tot:,.0f}")
    print(f"  exact archetype hit: {exact:,.0f} ({100*exact/tot:.1f}%)")
    print(f"  nearest-BER/occ    : {tot-exact:,.0f} ({100*(tot-exact)/tot:.1f}%)")

    print("loading profiles ...")
    names = set(a.f_noev.dropna()) | set(a.f_ev.dropna())
    pidx, P = load_profiles(names, ELEC)
    print(f"  {len(pidx)} unique profiles, {P.nbytes/1e6:.1f} MB")

    print("building sparse station x profile matrices ...")
    stations = pd.Index(sorted(a.k.unique()))
    si = pd.Series(range(len(stations)), index=stations)
    rows = a.k.map(si).to_numpy()
    cn = a.f_noev.map(pidx).to_numpy()
    ce = a.f_ev.map(pidx).to_numpy()
    vn = a.ArchCount_NoEV2024_LV.fillna(0).to_numpy(dtype=np.float32)
    ve = a.ArchCount_EV2024_LV.fillna(0).to_numpy(dtype=np.float32)
    ok = ~pd.isna(ce)
    S_n = sparse.csr_matrix((vn, (rows, cn)), shape=(len(stations), len(pidx)))
    S_e = sparse.csr_matrix((ve[ok], (rows[ok], ce[ok].astype(int))),
                            shape=(len(stations), len(pidx)))
    nb = a.groupby("k").ArchCount_original_2024_LV.sum().reindex(stations).fillna(0)

    print(f"computing hourly series for {len(stations):,} stations ...")
    peak = np.zeros(len(stations), dtype=np.float64)
    annual = np.zeros(len(stations), dtype=np.float64)
    lv_parent = None
    mv_acc = {}
    net = pd.read_csv(LVNET)
    net["k"] = norm_station(net["Station Name"])
    net["mv"] = net.Parent_Station.astype(str).str.split(":").str[0].str.split("[").str[0].str.strip().str.upper()
    pmap = net.drop_duplicates("k").set_index("k").mv
    lv_parent = pd.Series(stations).map(pmap).to_numpy()

    CH = 4000
    for i0 in range(0, len(stations), CH):
        i1 = min(i0 + CH, len(stations))
        blk = (S_n[i0:i1] @ P) + (S_e[i0:i1] @ P)
        peak[i0:i1] = blk.max(axis=1)
        annual[i0:i1] = blk.sum(axis=1)
        for j in range(i1 - i0):
            p = lv_parent[i0 + j]
            if isinstance(p, str) and p and p != "NAN":
                mv_acc[p] = mv_acc.get(p, 0) + blk[j].astype(np.float64)
        print(f"  {i1:,}/{len(stations):,}", end="\r")
    print()

    d = pd.DataFrame({"k": stations, "n_bldg": nb.to_numpy(),
                      "peak_kw": peak, "annual_kwh": annual,
                      "mv_parent": lv_parent})
    cap = pd.read_csv(CAP); cap["k"] = norm_station(cap["Station Name"])
    cap = cap.drop_duplicates("k")[["k", "designed_kva"]]
    d = d.merge(cap, on="k", how="left")
    d["kva_imputed"] = d.designed_kva.isna()
    d["designed_kva"] = d.designed_kva.fillna(DEFAULT_KVA)
    d = d[d.n_bldg > 0].copy()
    d["util_new"] = d.peak_kw / d.designed_kva
    d["kw_per_dwelling"] = d.peak_kw / d.n_bldg
    d["util_released"] = RATE_RELEASED * d.n_bldg / d.designed_kva

    d.to_csv(out / "lv_per_catchment_2024.csv", index=False)

    print("\n" + "=" * 74)
    print("PER-DWELLING PEAK  (released pipeline vs per-catchment summation)")
    print("=" * 74)
    print(f"  released (uniform)      : {RATE_RELEASED:.4f} kW/dwelling  (1 unique value)")
    r = d.kw_per_dwelling
    print(f"  per-catchment           : mean {r.mean():.4f}  median {r.median():.4f}")
    print(f"                            p5 {r.quantile(.05):.4f}  p95 {r.quantile(.95):.4f}")
    print(f"                            min {r.min():.4f}  max {r.max():.4f}")
    print(f"  unique values           : {r.round(6).nunique():,}  <- was 1")
    print(f"  coefficient of variation: {r.std()/r.mean():.4f}")

    print("\n" + "=" * 74)
    print("LV CAPACITY STATUS")
    print("=" * 74)
    for lab, u in [("released (uniform rate)", d.util_released), ("per-catchment summation", d.util_new)]:
        red = int((u > 1).sum()); near = int(((u >= .9) & (u <= 1)).sum())
        print(f"  {lab:26s} red={red:6,} near={near:5,} "
              f"stressed={100*(red+near)/len(d):5.2f}%  max={100*u.max():8.1f}%")

    # ---- ESB comparison -------------------------------------------------
    e = pd.read_csv(ESB); e["k"] = norm_station(e["Station Name"])
    e = e.drop_duplicates("k")[["k", "esb_util"]]
    m = d.merge(e, on="k", how="inner").dropna(subset=["esb_util"])
    print("\n" + "=" * 74)
    print(f"COMPARISON WITH ESB PUBLISHED UTILISATION  (n = {len(m):,})")
    print("=" * 74)
    for lab, col in [("released (uniform rate)", "util_released"),
                     ("per-catchment summation", "util_new")]:
        pr = m[col].corr(m.esb_util)
        sp = m[col].corr(m.esb_util, method="spearman")
        n90 = int((m[col] >= .9).sum())
        print(f"  {lab:26s} Pearson r={pr:+.4f}  Spearman={sp:+.4f}  "
              f">=90%: {n90:6,}  median util={m[col].median():.3f}")
    print(f"  {'ESB published':26s} {'':32s} >=90%: {int((m.esb_util>=.9).sum()):6,}  "
          f"median util={m.esb_util.median():.3f}")
    m.to_csv(out / "lv_vs_esb_percatchment.csv", index=False)

    # ---- MV roll-up on the same basis -----------------------------------
    if mv_acc:
        mv = pd.DataFrame({"mv_parent": list(mv_acc.keys()),
                           "peak_kw": [v.max() for v in mv_acc.values()],
                           "sum_of_child_peaks": [0.0] * len(mv_acc)})
        cp = d.groupby("mv_parent").peak_kw.sum()
        mv["sum_of_child_peaks"] = mv.mv_parent.map(cp).fillna(0)
        mv["diversity_ratio"] = mv.peak_kw / mv.sum_of_child_peaks.replace(0, np.nan)
        mv.to_csv(out / "mv_rollup_percatchment.csv", index=False)
        print("\n" + "=" * 74)
        print(f"MV ROLL-UP ON THE SAME BASIS  ({len(mv):,} feeders)")
        print("=" * 74)
        print("  coincident MV peak / sum of child LV peaks:")
        print(f"    median {mv.diversity_ratio.median():.4f}   "
              f"IQR {mv.diversity_ratio.quantile(.25):.4f}-{mv.diversity_ratio.quantile(.75):.4f}")
        print("  (<1 means real inter-catchment diversity, recovered by summing")
        print("   hourly series rather than adding station peaks)")

    print(f"\nwritten to {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
