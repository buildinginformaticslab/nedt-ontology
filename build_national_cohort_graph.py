#!/usr/bin/env python3
"""Build the (station, archetype) cohort instance graph and validate it.

Keeps every capacity-screened station, takes each station's county from its
assigned buildings, as build_cq_abox.py does, and uses only terms declared in
the released ontology. IRIs join to the released result graphs:

  stations    lv_station_<slug>, the target of nedt:scenarioStateOf
  archetypes  and counties, as minted by build_cq_abox.py

Validation uses the released DT_shapes.ttl with inference="none". Negative
controls then corrupt a copy of the Dublin graph, one change at a time, and each
must be rejected. Source records are restricted, so the generated graphs are not
distributed; pass --data-root (or NEDT_DATA_ROOT) to a licensed data workspace.

Usage: python3 build_national_cohort_graph.py --data-root PATH [--scope Dublin|Ireland|all]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import pandas as pd
from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import XSD

REPO = Path(__file__).resolve().parent
NEDT = Namespace("https://example.org/nedt#")
INST = Namespace("https://example.org/nedt/inst/")

# Same mappings as build_cq_abox.py, so archetype individuals match its IRIs.
HEAT_CLASS = {"Heating Oil": "OilBoiler", "gasboiler": "GasBoiler", "Heat Pump": "HeatPump",
              "Electric": "HeatingSystem", "Solar Thermal": "HeatingSystem"}
BUILD_FALLBACK = {"Terraced house": "Terraced", "Duplex": "Apartment",
                  "Temporary Structure": "Terraced"}

def norm(s: pd.Series) -> pd.Series:
    return (s.astype(str).str.replace(r"^MV/LV Substation\s*", "", regex=True)
             .str.strip().str.upper())


def iri(prefix: str, name: object) -> str:
    """build_cq_abox.py convention."""
    safe = "".join(c if c.isalnum() else "_" for c in str(name))[:40]
    return f"{prefix}_{safe}_{hashlib.sha1(str(name).encode()).hexdigest()[:10]}"


def station_slug(value: object) -> str:
    """export_scenario_results_to_rdf.py convention."""
    readable = "".join(ch if ch.isalnum() else "_" for ch in str(value).upper()).strip("_")
    return f"{readable}_{hashlib.sha1(str(value).encode()).hexdigest()[:10]}"


def text(v: object) -> str:
    return '"%s"' % str(v).replace("\\", "\\\\").replace('"', "'")


def load_inputs(root: Path):
    paper = root / "AEI-2006-PredictiveEnergyModelling"
    d = pd.read_csv(paper / "rerun_out/lv_per_catchment_2024.csv")[["k", "n_bldg", "designed_kva", "kva_imputed"]]
    assert d.k.is_unique and len(d) == 37287, len(d)
    bm = pd.read_csv(root / "LV_analysis/2024/BuildingMaster_LV_Assigned_2024.csv", usecols=["Station Name", "CountyNameNorm"], low_memory=False)
    bm["k"] = norm(bm["Station Name"])
    bm = bm.dropna(subset=["CountyNameNorm"])
    d["county"] = d.k.map(bm.groupby("k").CountyNameNorm.agg(lambda s: s.value_counts().idxmax()))
    assert d.county.notna().all(), "station without a county"
    net = pd.read_csv(root / "lv_mv_hv/lv_stations_2024.csv")
    net["k"] = norm(net["Station Name"])
    net["mv"] = (net.Parent_Station.astype(str).str.split(":").str[0]
                    .str.split("[").str[0].str.strip().str.upper())
    d["mv"] = d.k.map(net.drop_duplicates("k").set_index("k").mv)

    c = pd.read_csv(root / "CountyAnalysis/ArchetypeCounts_CountyLevel2024/ArchetypeCounts_LV_heating.csv", usecols=["Station Name", "Build Type", "BER", "Occupancy",
                                     "HeatingSystem", "ArchCount_original_2024_LV"], low_memory=False)
    c["k"] = norm(c["Station Name"])
    c["BER"] = c.BER.astype(str).str.strip().str[0]
    c["Occupancy"] = pd.to_numeric(c.Occupancy, errors="coerce").fillna(3).astype(int)
    c["Build Type"] = c["Build Type"].replace(BUILD_FALLBACK)
    cohorts = (c.groupby(["k", "Build Type", "BER", "Occupancy", "HeatingSystem"], as_index=False)
                .ArchCount_original_2024_LV.sum().rename(columns={"ArchCount_original_2024_LV": "n"}))
    return d, cohorts[cohorts.n > 0]


def write_graph(d: pd.DataFrame, cohorts: pd.DataFrame, path: Path) -> dict:
    keep = set(d.k)
    cohorts = cohorts[cohorts.k.isin(keep)]
    county_of = d.set_index("k").county
    w = []
    W = w.append
    W(f"@prefix nedt: <{NEDT}> .\n@prefix inst: <{INST}> .")
    W("@prefix prov: <http://www.w3.org/ns/prov#> .")
    W("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
    W("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n")
    W("inst:cohort_graph_build a prov:Activity ;")
    W('    rdfs:label "NEDT national cohort graph construction (build_national_cohort_graph.py)" ;')
    W("    prov:used inst:dataset_archetype_counts_2024 , inst:dataset_building_master_2024 ,")
    W("              inst:dataset_lv_network_2024 .")
    for ds, lbl in [("dataset_archetype_counts_2024", "SEAI/CSO archetype counts 2024"),
                    ("dataset_building_master_2024", "GeoDirectory building master, LV-assigned 2024"),
                    ("dataset_lv_network_2024", "ESB Networks LV asset register 2024")]:
        W(f'inst:{ds} a prov:Entity ; rdfs:label "{lbl}" .')
    for cty in sorted(d.county.unique()):
        W(f"inst:{iri('county', cty)} a nedt:County ; rdfs:label {text(cty)} .")
    for hs in sorted(cohorts.HeatingSystem.unique()):
        W(f"inst:{iri('heatsys', hs)} a nedt:{HEAT_CLASS.get(hs, 'HeatingSystem')} ; rdfs:label {text(hs)} .")
    arche = cohorts[["Build Type", "BER", "Occupancy", "HeatingSystem"]].drop_duplicates()
    for b, ber, occ, hs in arche.itertuples(index=False):
        aid = iri("arch", f"{b}_{ber}_{occ}_{hs}")
        W(f"inst:{aid} a nedt:Archetype ; rdfs:label {text(f'{b} BER {ber} occ {occ} {hs}')} ;")
        W(f'    nedt:hasBuildType {text(b)} ; nedt:hasBERCategory {text(ber)} ;')
        W(f'    nedt:hasOccupancyCategory "{int(occ)}"^^xsd:integer ; nedt:usesHeatingSystem inst:{iri("heatsys", hs)} .')
    mvs = sorted(set(d.mv.dropna()) - {"NAN", ""})
    for mv in mvs:
        W(f"inst:{iri('mv', mv)} a nedt:MVFeeder ; rdfs:label {text(mv)} .")
    for r in d.itertuples(index=False):
        W(f"inst:lv_station_{station_slug(r.k)} a nedt:LVStation ; rdfs:label {text(r.k)} ;")
        W(f'    nedt:hasCapacityValue "{float(r.designed_kva):.6f}"^^xsd:decimal ;')
        W(f"    nedt:hasCapacityImputed {'true' if r.kva_imputed else 'false'} ;")
        if isinstance(r.mv, str) and r.mv not in ("NAN", ""):
            W(f"    nedt:hasParentMVFeeder inst:{iri('mv', r.mv)} ;")
        W(f"    nedt:locatedInCounty inst:{iri('county', r.county)} .")
    for r in cohorts.itertuples(index=False):
        b, ber, occ, hs, n = r[1], r[2], r[3], r[4], r[5]
        # Separate from build_cq_abox.py's scenario-scoped "ac_" nodes, which point at
        # the s1_lv_station_ state rather than the physical station.
        W(f"inst:{iri('stock_ac', f'{r.k}_{b}_{ber}_{occ}_{hs}')} a nedt:ArchetypeCount ;")
        W(f"    nedt:forLVStation inst:lv_station_{station_slug(r.k)} ;")
        W(f"    nedt:countsArchetype inst:{iri('arch', f'{b}_{ber}_{occ}_{hs}')} ;")
        W(f"    nedt:inCounty inst:{iri('county', county_of[r.k])} ;")
        W(f'    nedt:dwellingCount "{int(n)}"^^xsd:integer ; prov:wasGeneratedBy inst:cohort_graph_build .')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(w) + "\n", encoding="utf-8")
    return {"stations": int(len(d)), "counties": int(d.county.nunique()), "archetypes": int(len(arche)),
            "cohort_nodes": int(len(cohorts)), "mv_feeders": len(mvs),
            "stations_with_mv_parent": int(d.mv.notna().sum()),
            "imputed_ratings": int(d.kva_imputed.sum()), "dwellings": int(cohorts.n.sum())}


def count_results(report: Graph) -> int:
    return sum(1 for _ in report.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#ValidationResult")))


def run_validation(g: Graph, shapes: Graph) -> dict:
    t = time.perf_counter()
    conforms, report, _ = validate(g, shacl_graph=shapes, inference="none")
    return {"conforms": bool(conforms), "violations": count_results(report),
            "elapsed_s": round(time.perf_counter() - t, 1)}


def recount(g: Graph) -> dict:
    """Counts read back from the parsed graph, not from the source tables."""
    return {"triples": len(g),
            "stations": sum(1 for _ in g.subjects(RDF.type, NEDT.LVStation)),
            "archetypes": sum(1 for _ in g.subjects(RDF.type, NEDT.Archetype)),
            "cohort_nodes": sum(1 for _ in g.subjects(RDF.type, NEDT.ArchetypeCount)),
            "dwellings": sum(int(o) for o in g.objects(None, NEDT.dwellingCount)),
            # The shape accepts a station or a county; this graph must have both.
            "cohort_links": {p: sum(1 for _ in g.subject_objects(NEDT[p]))
                             for p in ("forLVStation", "countsArchetype", "inCounty")}}


def negative_controls(g: Graph, shapes: Graph) -> dict:
    """Corrupt one thing at a time in a copy; each must be rejected."""
    station = next(g.subjects(RDF.type, NEDT.LVStation))
    arche = next(g.subjects(RDF.type, NEDT.Archetype))
    county = next(g.subjects(RDF.type, NEDT.County))
    cohort = next(g.subjects(RDF.type, NEDT.ArchetypeCount))
    own_station = g.value(cohort, NEDT.forLVStation)
    other_station = next(s for s in g.subjects(RDF.type, NEDT.LVStation) if s != own_station)
    def setv(s, p, v): return lambda x: (x.remove((s, p, None)), x.add((s, p, v)))
    cases = {
        "capacity_negative": setv(station, NEDT.hasCapacityValue, Literal("-5.0", datatype=XSD.decimal)),
        "capacity_above_2000": setv(station, NEDT.hasCapacityValue, Literal("2500.0", datatype=XSD.decimal)),
        "imputed_flag_missing": lambda x: x.remove((station, NEDT.hasCapacityImputed, None)),
        "two_mv_parents": lambda x: (x.add((station, NEDT.hasParentMVFeeder, INST.mv_a)),
                                     x.add((INST.mv_a, RDF.type, NEDT.MVFeeder)),
                                     x.add((station, NEDT.hasParentMVFeeder, INST.mv_b)),
                                     x.add((INST.mv_b, RDF.type, NEDT.MVFeeder))),
        "ber_outside_a_g": setv(arche, NEDT.hasBERCategory, Literal("Z", datatype=XSD.string)),
        "unknown_build_type": setv(arche, NEDT.hasBuildType, Literal("Castle", datatype=XSD.string)),
        "occupancy_out_of_range": setv(arche, NEDT.hasOccupancyCategory, Literal(9, datatype=XSD.integer)),
        "county_without_label": lambda x: x.remove((county, RDFS.label, None)),
        "cohort_zero_count": setv(cohort, NEDT.dwellingCount, Literal(0, datatype=XSD.integer)),
        "cohort_without_archetype": lambda x: x.remove((cohort, NEDT.countsArchetype, None)),
        "cohort_two_stations": lambda x: x.add((cohort, NEDT.forLVStation, other_station)),
        "cohort_without_scope": lambda x: (x.remove((cohort, NEDT.forLVStation, None)),
                                           x.remove((cohort, NEDT.inCounty, None))),
    }
    out = {}
    for name, corrupt in cases.items():
        x = Graph()
        for tr in g:
            x.add(tr)
        corrupt(x)
        res = run_validation(x, shapes)
        out[name] = {"rejected": not res["conforms"], "violations": res["violations"]}
        print(f"  control {name}: rejected={not res['conforms']} violations={res['violations']}", flush=True)
    return out


def join_check(nat: Graph, shapes: Graph) -> dict:
    """Confirm IRIs and ratings match the released result graphs, then validate the union."""
    sc = Graph().parse(REPO / "scenario1_results.ttl", format="turtle")
    cq = Graph().parse(REPO / "cq_test_abox.ttl", format="turtle")
    stations = set(nat.subjects(RDF.type, NEDT.LVStation))
    out = {"stations_matching_scenario_graph": len(stations & set(sc.objects(None, NEDT.scenarioStateOf)))}
    for name, cls in (("archetypes", NEDT.Archetype), ("counties", NEDT.County), ("mv_feeders", NEDT.MVFeeder)):
        a, b = set(nat.subjects(RDF.type, cls)), set(cq.subjects(RDF.type, cls))
        out[name] = {"cohort_graph": len(a), "cq_graph": len(b), "common": len(a & b)}
    rating = {s: float(o) for s, o in nat.subject_objects(NEDT.hasCapacityValue)}
    pairs = [(float(sc.value(s, NEDT.hasCapacityValue)), rating[p])
             for s, p in sc.subject_objects(NEDT.scenarioStateOf) if p in rating]
    out["ratings_compared"] = len(pairs)
    out["ratings_differing"] = sum(abs(x - y) > 1e-3 for x, y in pairs)
    union = nat + sc + cq
    out["union_triples"] = len(union)
    out["union_released_shapes"] = run_validation(union, shapes)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=os.environ.get("NEDT_DATA_ROOT"), required=not os.environ.get("NEDT_DATA_ROOT"))
    ap.add_argument("--out", default=None, help="output folder (default: <data-root>/AEI-2006-PredictiveEnergyModelling/results/national_graph)")
    ap.add_argument("--scope", choices=["Dublin", "Ireland", "all"], default="all")
    args = ap.parse_args()
    root = Path(args.data_root).expanduser().resolve()
    out = Path(args.out) if args.out else root / "AEI-2006-PredictiveEnergyModelling/results/national_graph"
    shapes = Graph().parse(REPO / "DT_shapes.ttl", format="turtle")
    n_shapes = sum(1 for _ in shapes.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#NodeShape")))
    d, cohorts = load_inputs(root)
    print(f"inputs: {len(d):,} stations, {len(cohorts):,} cohorts, {cohorts.n.sum():,} dwellings; "
          f"{n_shapes} node shapes", flush=True)
    summary_path = out / "validation_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    summary["shape_graph"] = {"file": "DT_shapes.ttl", "node_shapes": n_shapes,
        "sha256": hashlib.sha256((REPO / "DT_shapes.ttl").read_bytes()).hexdigest()}
    for scope in (["Dublin", "Ireland"] if args.scope == "all" else [args.scope]):
        sub = d if scope == "Ireland" else d[d.county.str.lower() == scope.lower()]
        path = out / f"nedt_cohort_graph_{scope.lower()}.ttl"
        built = write_graph(sub, cohorts, path)
        print(scope, built, flush=True)
        g = Graph().parse(path, format="turtle")
        seen = recount(g)
        print(scope, "read back", seen, flush=True)
        res = run_validation(g, shapes)
        print(scope, "released shapes", res, flush=True)
        entry = {"built": built, "read_back": seen, "released_shapes": res}
        if scope == "Dublin":
            entry["negative_controls"] = negative_controls(g, shapes)
        if scope == "Ireland":
            entry["join_with_released_graphs"] = join_check(g, shapes)
            print(entry["join_with_released_graphs"], flush=True)
        summary[scope] = entry
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
