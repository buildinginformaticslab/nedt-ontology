#!/usr/bin/env python3
"""Compare the catchment operator with county-maximum allocation.

Catchment operator (paper Eqs. station_demand and peak):
    P_t = max_h sum_a n_{a,t} d_a(h)

County-allocation comparator:
    P_t = max_h D_county(h) * n_t / N_county,  D_county(h) = sum_t D_t(h)

No coincidence factor is applied to either, so the only difference is the
operator. The Scenario 1 component construction below is copied unchanged from
scenario1_percatchment.py. Results go to rerun_out/operator_comparison_*.

Usage: python3 operator_comparison.py [--data-root PATH] [--out DIR]
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse
import scenario1_percatchment as sc
from scenario1_percatchment import hamilton, pv_kwp, pv_shape, pc

HERE = Path(__file__).resolve().parent


def station_counties() -> pd.Series:
    bm = pd.read_csv(pc.BLDG, usecols=["Station Name", "CountyNameNorm"], low_memory=False)
    bm["k"] = pc.norm_station(bm["Station Name"])
    bm = bm.dropna(subset=["CountyNameNorm"])
    return bm.groupby("k").CountyNameNorm.agg(lambda s: s.value_counts().idxmax())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=os.environ.get("NEDT_DATA_ROOT"))
    ap.add_argument("--out", type=Path, default=HERE / "rerun_out")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    ROOT = pc.configure_data_root(args.data_root)
    sc.ROOT = ROOT
    a = pd.read_csv(pc.COUNTS); a["k"] = pc.norm_station(a["Station Name"])
    a["BER"] = a.BER.astype(str).str.strip().str[0]; a["Occupancy"] = pd.to_numeric(a.Occupancy, errors="coerce").fillna(3).astype(int)
    a["n"] = a.ArchCount_original_2024_LV.astype(int); a["ev"] = a.ArchCount_EV2024_LV.fillna(0).astype(int); a["noev"] = a.ArchCount_NoEV2024_LV.fillna(0).astype(int)
    # Notebook HP move: 20% oil/gas BER C--E, rounded within build/occupancy/weather groups.
    eligible = a.BER.isin(list("CDE")) & a.HeatingSystem.isin(["Heating Oil", "gasboiler"])
    a["hp_move"] = 0
    for _, ix in a[eligible].groupby(["Build Type", "Occupancy", "WeatherClassification"], sort=True).groups.items():
        vals = a.loc[ix, "n"] * .20
        a.loc[ix, "hp_move"] = hamilton(vals, int(round(vals.sum()))).values
    a["hp_move"] = np.minimum(a.hp_move, a.n).astype(int)
    a["hp_ev"] = np.minimum(np.rint(a.hp_move * a.ev / a.n.replace(0, 1)).astype(int), a.ev)
    a["hp_noev"] = a.hp_move - a.hp_ev
    # Components preserve station identity; each can be assigned a profile independently.
    base = a.assign(HeatingSystem=a.HeatingSystem, count=a.n-a.hp_move, ev_count=a.ev-a.hp_ev, noev_count=a.noev-a.hp_noev, hp_transition=False)
    moved = a[a.hp_move > 0].copy(); moved["HeatingSystem"] = "Heat Pump"; moved["BER"] = "A"; moved["count"] = moved.hp_move; moved["ev_count"] = moved.hp_ev; moved["noev_count"] = moved.hp_noev; moved["hp_transition"] = True
    c = pd.concat([base, moved], ignore_index=True); c = c[c["count"] > 0].copy()
    # Notebook target is 10% of private-car stock, with only an incremental EV shift.
    cars = pd.read_csv(ROOT / "CountyAnalysis" / "private_car_stock_county.csv", thousands=",")
    target = int(round(float(cars.loc[cars.iloc[:,0].astype(str).str.lower().eq("ireland"), "2024"].iloc[0]) * .10))
    delta = max(0, target - int(c.ev_count.sum()))
    add_ev = hamilton(c.noev_count, min(delta, int(c.noev_count.sum())))
    c["ev_count"] += add_ev; c["noev_count"] -= add_ev
    c["ev_added"] = add_ev
    hp_ev_coadoption = int(c.loc[c.hp_transition, "ev_added"].sum())
    noev_lib, ev_lib = pc.scan_library(pc.ELEC)
    def file_for(row, lib): return pc.resolve(lib, row["Build Type"], row.BER, row.Occupancy, row.HeatingSystem)[0]
    c["f_noev"] = c.apply(lambda r: file_for(r, noev_lib), axis=1); c["f_ev"] = c.apply(lambda r: file_for(r, ev_lib), axis=1)
    c = c[c.f_noev.notna()].copy()
    names = set(c.f_noev.dropna()) | set(c.f_ev.dropna()); pidx, P = pc.load_profiles(names, pc.ELEC)
    stations = pd.Index(sorted(c.k.unique())); si = pd.Series(range(len(stations)), index=stations)
    rows = c.k.map(si).to_numpy(); nprof = len(pidx)
    S0 = sparse.csr_matrix((c.noev_count.to_numpy(float), (rows, c.f_noev.map(pidx).to_numpy())), shape=(len(stations),nprof))
    evok = c.f_ev.notna().to_numpy(); S1 = sparse.csr_matrix((c.loc[evok,"ev_count"].to_numpy(float),(rows[evok],c.loc[evok,"f_ev"].map(pidx).to_numpy())),shape=(len(stations),nprof))
    # PV uses baseline building composition and notebook building-type capacities.
    pv_per_station = a.assign(kwp=a["Build Type"].map(pv_kwp), pv_n=lambda x: x.n*.10).assign(pv_kwp=lambda x:x.kwp*x.pv_n).groupby("k").pv_kwp.sum().reindex(stations).fillna(0).to_numpy()
    shape = pv_shape(); cap = pd.read_csv(pc.CAP); cap["k"] = pc.norm_station(cap["Station Name"]); cap = cap.drop_duplicates("k").set_index("k").designed_kva
    # Baseline uses the unmodified archetype table with the same profile library.
    base_key = lambda r, lib: pc.resolve(lib, r["Build Type"], r.BER, r.Occupancy, r.HeatingSystem)[0]
    b = a.copy()
    b["f_noev"] = b.apply(lambda r: base_key(r, noev_lib), axis=1)
    b["f_ev"] = b.apply(lambda r: base_key(r, ev_lib), axis=1)
    b = b[b.f_noev.notna()].copy()
    names_b = (set(b.f_noev.dropna()) | set(b.f_ev.dropna())) - set(pidx)
    if names_b:
        extra_idx, extra = pc.load_profiles(names_b, pc.ELEC)
        offset = P.shape[0]
        P = np.vstack([P, extra])
        pidx = {**pidx, **{n: i + offset for n, i in extra_idx.items()}}
    nprof = len(pidx)
    S0 = sparse.csr_matrix((S0.data, S0.indices, S0.indptr), shape=(len(stations), nprof))
    S1 = sparse.csr_matrix((S1.data, S1.indices, S1.indptr), shape=(len(stations), nprof))
    rb = b.k.map(si).to_numpy()
    B0 = sparse.csr_matrix((b.noev.to_numpy(float), (rb, b.f_noev.map(pidx).to_numpy())), shape=(len(stations), nprof))
    eb = b.f_ev.notna().to_numpy()
    B1 = sparse.csr_matrix((b.loc[eb, "ev"].to_numpy(float), (rb[eb], b.loc[eb, "f_ev"].map(pidx).to_numpy())), shape=(len(stations), nprof))

    n_t = a.groupby("k").n.sum().reindex(stations).fillna(0).to_numpy(float)
    kva = cap.reindex(stations).fillna(pc.DEFAULT_KVA).to_numpy(float)
    county = pd.Series(stations).map(station_counties())
    cid, labels = pd.factorize(county)            # -1 where unresolved
    nc = len(labels)
    acc = {"base": np.zeros((nc, pc.HOURS)), "s1": np.zeros((nc, pc.HOURS))}
    peak = {"base": np.zeros(len(stations)), "s1": np.zeros(len(stations))}
    for i0 in range(0, len(stations), 2000):
        i1 = min(i0 + 2000, len(stations))
        blocks = {
            "base": (B0[i0:i1] @ P) + (B1[i0:i1] @ P),
            "s1": np.maximum((S0[i0:i1] @ P) + (S1[i0:i1] @ P) - pv_per_station[i0:i1, None] * shape[None, :], 0),
        }
        for key, blk in blocks.items():
            peak[key][i0:i1] = blk.max(1)
            for c_ in np.unique(cid[i0:i1]):
                if c_ >= 0:
                    acc[key][c_] += blk[cid[i0:i1] == c_].sum(0, dtype=np.float64)
        print(f"{i1:,}/{len(stations):,}", end="\r", flush=True)
    print()

    d = pd.DataFrame({"k": stations, "county": county.to_numpy(), "n": n_t, "kva": kva})
    N = pd.Series(n_t).groupby(cid).sum()
    for key in ("base", "s1"):
        d[f"peak_catch_{key}"] = peak[key]
        d[f"u_catch_{key}"] = peak[key] / kva
        cpk = acc[key].max(1)
        alloc = np.where(cid >= 0, cpk[np.clip(cid, 0, None)] * n_t / np.maximum(pd.Series(cid).map(N).to_numpy(), 1), np.nan)
        d[f"peak_county_{key}"] = alloc
        d[f"u_county_{key}"] = alloc / kva
    d.to_csv(args.out / "operator_comparison_stations.csv", index=False)

    out = {"stations_all": int(len(d)),
           "reproduce_red_base_all": int((d.u_catch_base > 1).sum()),
           "reproduce_red_s1_all": int((d.u_catch_s1 > 1).sum())}
    s = d[d.county.notna() & (d.n > 0)]
    out["stations_compared"] = int(len(s))
    out["counties"] = int(s.county.nunique())
    for key in ("base", "s1"):
        ca, co = s[f"u_catch_{key}"] > 1, s[f"u_county_{key}"] > 1
        out[key] = {
            "catchment_red": int(ca.sum()), "county_red": int(co.sum()),
            "both": int((ca & co).sum()),
            "catchment_only": int((ca & ~co).sum()), "county_only": int((co & ~ca).sum()),
            "dwellings_catchment_only": float(s.n[ca & ~co].sum()),
            "dwellings_county_only": float(s.n[co & ~ca].sum()),
            "jaccard": float((ca & co).sum() / (ca | co).sum()),
            "spearman_u": float(s[f"u_catch_{key}"].corr(s[f"u_county_{key}"], method="spearman")),
            "sum_peak_catchment_gw": float(s[f"peak_catch_{key}"].sum() / 1e6),
            "sum_peak_county_gw": float(s[f"peak_county_{key}"].sum() / 1e6),
            "kw_per_dwelling_catch_p5_p95": [float(x) for x in (s[f"peak_catch_{key}"] / s.n).quantile([.05, .95])],
            "kw_per_dwelling_county_p5_p95": [float(x) for x in (s[f"peak_county_{key}"] / s.n).quantile([.05, .95])],
        }
    new_ca = (s.u_catch_s1 > 1) & ~(s.u_catch_base > 1)
    new_co = (s.u_county_s1 > 1) & ~(s.u_county_base > 1)
    out["new_in_s1"] = {"catchment": int(new_ca.sum()), "county": int(new_co.sum()),
                        "both": int((new_ca & new_co).sum()),
                        "catchment_only": int((new_ca & ~new_co).sum()),
                        "county_only": int((new_co & ~new_ca).sum())}
    (args.out / "operator_comparison_summary.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
