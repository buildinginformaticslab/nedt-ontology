#!/usr/bin/env python3
"""Materialise reproducible station-level scenario outputs as a NEDT RDF graph.

The input table is deliberately the workflow output (rather than a manually
curated publication table).  Each row becomes a CapacityKPI linked to its LV
station, the Scenario~1 entity, and the PROV activity that generated it.

Usage:
  python3 export_scenario_results_to_rdf.py --input results/scenario1/lv_scenario1.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import PROV, XSD

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"
NEDT = Namespace("https://example.org/nedt#")
INST = Namespace("https://example.org/nedt/inst/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")


def slug(value: object) -> str:
    readable = "".join(ch if ch.isalnum() else "_" for ch in str(value).upper()).strip("_")
    # Preserve audit readability while making IDs injective for redacted
    # station codes such as ``O****040`` and ``O****040A``.
    digest = hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:10]
    return f"{readable}_{digest}"


def decimal(value: float) -> Literal:
    return Literal(f"{float(value):.6f}", datatype=XSD.decimal)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=ONTOLOGY / "scenario1_results.ttl")
    parser.add_argument("--summary", type=Path,
                        default=Path(__file__).parent / "results" / "scenario1" / "scenario1_summary.json")
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text()) if args.summary.exists() else {}
    df = pd.read_csv(args.input)
    # The published legacy extract uses peak_scn/util_scn; a regenerated
    # workflow writes the canonical peak_kw/utilisation names.  Normalise at
    # this boundary so the RDF contract remains stable across both artefacts.
    df = df.rename(columns={"peak_scn": "peak_kw", "util_scn": "utilisation"})
    required = {"k", "peak_kw", "designed_kva", "utilisation", "n_bldg"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"scenario output lacks required columns: {sorted(missing)}")

    graph = Graph()
    graph.bind("nedt", NEDT); graph.bind("inst", INST); graph.bind("prov", PROV)
    graph.bind("sosa", SOSA); graph.bind("rdfs", RDFS)
    scenario = INST.scenario_1_2024
    activity = INST.scenario_1_workflow_run
    graph.add((scenario, RDF.type, NEDT.Scenario))
    graph.add((scenario, RDFS.label, Literal("Scenario 1: 2024 residential electrification")))
    graph.add((scenario, NEDT.hasScenarioYear, Literal(2024, datatype=XSD.integer)))
    for prop, value in ((NEDT.hasHPAdoptionFraction, 0.20),
                        (NEDT.hasEVAdoptionFraction, 0.10),
                        (NEDT.hasPVAdoptionFraction, 0.10)):
        graph.add((scenario, prop, Literal(f"{value:.2f}", datatype=XSD.decimal)))
    if "hp_ev_coadoption" in summary:
        graph.add((scenario, NEDT.hasHPEVCoAdoptionCount,
                   Literal(int(summary["hp_ev_coadoption"]), datatype=XSD.integer)))
    graph.add((activity, RDF.type, PROV.Activity))
    graph.add((activity, RDFS.label, Literal("Scenario 1 workflow execution")))
    graph.add((activity, PROV.endedAtTime,
               Literal(datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime)))

    for row in df.itertuples(index=False):
        # The national KG already contains a spatial-asset A-Box with partial
        # source values.  A scenario evaluation is a versioned asset view, so
        # use a scenario-scoped identifier and avoid silently coalescing two
        # independently sourced capacity assertions.
        station = INST[f"s1_lv_station_{slug(row.k)}"]
        kpi = INST[f"capacity_kpi_s1_{slug(row.k)}"]
        util = INST[f"utilisation_s1_{slug(row.k)}"]
        graph.add((station, RDF.type, NEDT.LVStation))
        graph.add((station, RDFS.label, Literal(str(row.k))))
        graph.add((station, NEDT.hasCapacityValue, decimal(row.designed_kva)))
        graph.add((station, NEDT.hasCapacityImputed,
                   Literal(bool(row.kva_imputed) if hasattr(row, "kva_imputed") else False,
                           datatype=XSD.boolean)))
        graph.add((kpi, RDF.type, NEDT.CapacityKPI))
        graph.add((kpi, NEDT.forLVStation, station))
        graph.add((kpi, NEDT.evaluatedUnderScenario, scenario))
        graph.add((kpi, NEDT.hasPeakDemandKW, decimal(row.peak_kw)))
        graph.add((kpi, NEDT.hasRatedCapacityKVA, decimal(row.designed_kva)))
        if hasattr(row, "overload_hours"):
            graph.add((kpi, NEDT.hasOverloadHours,
                       Literal(int(row.overload_hours), datatype=XSD.integer)))
        graph.add((kpi, NEDT.hasUtilisation, util))
        graph.add((util, RDF.type, NEDT.Utilisation))
        graph.add((util, SOSA.hasSimpleResult, decimal(row.utilisation)))
        graph.add((kpi, PROV.wasGeneratedBy, activity))
        if float(row.utilisation) > 1:
            graph.add((station, RDF.type, NEDT.OverloadedStation))
            graph.add((scenario, NEDT.triggers, station))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(args.output, format="turtle")
    print(f"wrote {len(graph):,} triples for {len(df):,} station KPIs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
