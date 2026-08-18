#!/usr/bin/env python3
"""Executable Scenario 1, using the NEDT notebook's HP/EV/PV semantics.

This runner retains the paper's allocate-then-maximise station operator while
using the notebook's technology transitions: C--E oil/gas homes move to BER-A
heat-pump profiles; EV adoption targets 10% of national private-car stock;
and PV is derived from Nexsys ``PV generation`` sheets. Outputs are an LV
station table consumed by the RDF exporter and a compact JSON summary. It
does not infer MV/HV capacity utilisation, for which no released parent-asset
capacity join is available.
"""
from __future__ import annotations
import argparse
import hashlib, importlib.util, json, os
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pc", HERE / "rerun_percatchment.py")
pc = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(pc)
ROOT = pc.ROOT

def hamilton(values: pd.Series, total: int) -> pd.Series:
    """Deterministic largest-remainder integer allocation."""
    out = pd.Series(0, index=values.index, dtype=int)
    if total <= 0 or values.sum() <= 0: return out
    raw = values.astype(float) / values.sum() * total
    out = np.floor(raw).astype(int)
    for i in (raw - out).sort_values(ascending=False, kind="stable").index[:total-int(out.sum())]: out.loc[i] += 1
    return out


def pv_shape() -> np.ndarray:
    """Exact notebook construction: average peak-normalised Nexsys curves."""
    pv_xlsx = ROOT / "EV_profiles" / "modified_uncontrolled_results_dynamic.xlsx"
    xls = pd.ExcelFile(pv_xlsx); shapes = []
    for sheet in xls.sheet_names:
        frame = xls.parse(sheet)
        if "PV generation" not in frame: continue
        v = pd.to_numeric(frame["PV generation"], errors="coerce").fillna(0).to_numpy(float)
        # The supplied Nexsys workbook has 8,758--8,760 rows per sheet;
        # missing terminal hours are night-time zero-generation values. Do not
        # silently accept materially incomplete annual profiles.
        if len(v) not in {8758, 8759, pc.HOURS}:
            raise ValueError(f"{sheet}: expected 8,758--{pc.HOURS} PV values, found {len(v)}")
        if v.max() <= 0:
            raise ValueError(f"{sheet}: PV generation is non-positive")
        v = np.pad(v, (0, pc.HOURS-len(v)))
        shapes.append(v / v.max())
    if not shapes: raise ValueError("no valid Nexsys PV generation sheets")
    return np.mean(shapes, axis=0) * (1000.0 / 1284.0)


def pv_kwp(build: str) -> float:
    s = str(build).lower()
    if "apartment" in s or "flat" in s: return 0.0
    if "terrace" in s: return 2.5
    if "semi" in s: return 3.5
    if "detached" in s or "bungalow" in s: return 4.0
    return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default=None,
                        help="licensed DT_Model data workspace (or set NEDT_DATA_ROOT)")
    args = parser.parse_args()
    global ROOT
    ROOT = pc.configure_data_root(args.data_root or os.environ.get("NEDT_DATA_ROOT"))
    out = HERE / "results" / "scenario1"; out.mkdir(parents=True, exist_ok=True)
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
    peaks=np.zeros(len(stations)); hours=np.zeros(len(stations),dtype=int); annual=np.zeros(len(stations))
    for start in range(0,len(stations),2000):
        end=min(start+2000,len(stations)); block=(S0[start:end]@P)+(S1[start:end]@P)-pv_per_station[start:end,None]*shape[None,:]
        block=np.maximum(block,0); peaks[start:end]=block.max(1); annual[start:end]=block.sum(1)
        caps=cap.reindex(stations[start:end]).fillna(pc.DEFAULT_KVA).to_numpy(); hours[start:end]=(block>caps[:,None]).sum(1)
        print(f"{end:,}/{len(stations):,}",end="\r")
    d=pd.DataFrame({"k":stations,"n_bldg":a.groupby("k").n.sum().reindex(stations).to_numpy(),"peak_kw":peaks,"annual_kwh":annual,"designed_kva":cap.reindex(stations).fillna(pc.DEFAULT_KVA).to_numpy(),"kva_imputed":cap.reindex(stations).isna().to_numpy(),"overload_hours":hours})
    d["utilisation"]=d.peak_kw/d.designed_kva
    # Reconcile the profile/archetype population with the independent
    # building-to-station assignment before interpreting individual assets.
    # This is a diagnostic, not a post-hoc exclusion: all stations remain in
    # national model-screened counts and in the RDF result graph.
    bldg = pd.read_csv(pc.BLDG, usecols=["Station Name", "Dwellings"], low_memory=False)
    bldg["k"] = pc.norm_station(bldg["Station Name"])
    assigned = bldg.groupby("k").Dwellings.sum()
    d["assigned_dwellings"] = d.k.map(assigned)
    d["archetype_to_assignment_ratio"] = d.n_bldg / d.assigned_dwellings
    d["audit_count_reconciliation"] = (
        d.assigned_dwellings.notna()
        & ~d.archetype_to_assignment_ratio.between(0.8, 1.2)
    )
    # Outliers are retained in the results but explicitly flagged for asset or
    # connectivity review rather than treated as routine reinforcement cases.
    d["audit_extreme_utilisation"] = d.utilisation > 5.0
    d["audit_large_catchment"] = d.n_bldg > 1000
    d["requires_asset_audit"] = d.audit_extreme_utilisation | d.audit_large_catchment
    d.to_csv(out/"lv_scenario1.csv",index=False)
    # Attach the published availability snapshot for a compact reconciliation
    # artefact.  It is not treated as time-aligned overload ground truth.
    esb = pd.read_csv(pc.ESB)
    esb["k"] = pc.norm_station(esb["Station Name"])
    audit = d.loc[d.requires_asset_audit].merge(
        esb[["k", "installed_kva", "available_kva", "esb_load_kva", "esb_util", "esb_constrained"]],
        on="k", how="left",
    ).sort_values("utilisation", ascending=False)
    audit.to_csv(out/"station_data_quality_audit.csv", index=False)
    audit.to_csv(out/"asset_reconciliation_exceptions.csv", index=False)
    summary = {
        "stations": len(d), "hp_conversions": int(a.hp_move.sum()),
        "target_ev": target,
        "ev_added": int(add_ev.sum()),
        "hp_ev_coadoption": hp_ev_coadoption,
        "pv_eligible_installations": int(round((a["Build Type"].map(pv_kwp) > 0).mul(a.n).sum() * .10)),
        "red": int((d.utilisation > 1).sum()),
        "near": int(((d.utilisation >= .9) & (d.utilisation <= 1)).sum()),
        "utilisation_p95": float(d.utilisation.quantile(.95)),
        "utilisation_p99": float(d.utilisation.quantile(.99)),
        "maximum_utilisation": float(d.utilisation.max()),
        "stations_requiring_asset_audit": int(d.requires_asset_audit.sum()),
        "stations_with_count_reconciliation_flag": int(d.audit_count_reconciliation.sum()),
    }
    (out/"scenario1_summary.json").write_text(json.dumps(summary,indent=2)+"\n"); print("\n",summary)
    return 0
if __name__ == "__main__": raise SystemExit(main())
