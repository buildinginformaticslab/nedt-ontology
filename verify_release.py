#!/usr/bin/env python3
"""Verify the public NEDT Scenario 1 release without restricted source data."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from pyshacl import validate
from rdflib import Graph


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "ontology").exists() else HERE
ONTOLOGY = ROOT / "ontology" if (ROOT / "ontology").exists() else ROOT
RESULTS = HERE / "results" / "scenario1"


def main() -> int:
    required = {
        "station table": RESULTS / "lv_scenario1.csv",
        "summary": RESULTS / "scenario1_summary.json",
        "query output": RESULTS / "competency_queries.json",
        "ontology": ONTOLOGY / "DT_ontology.ttl",
        "shape graph": ONTOLOGY / "DT_shapes.ttl",
        "scenario graph": ONTOLOGY / "scenario1_results.ttl",
        "national graph": ONTOLOGY / "DT_kg.ttl",
        "example graph": ONTOLOGY / "DT_instances_v11.ttl",
        "merged graph": ONTOLOGY / "DT_kg_full.ttl",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"release is incomplete; missing: {', '.join(missing)}")

    stations = pd.read_csv(required["station table"])
    summary = json.loads(required["summary"].read_text())
    queries = json.loads(required["query output"].read_text())
    assert len(stations) == 37_287
    assert int((stations.utilisation > 1).sum()) == 3_378
    assert int(((stations.utilisation >= .9) & (stations.utilisation <= 1)).sum()) == 693
    assert summary["stations_requiring_asset_audit"] == 46
    assert queries["queries"]["CQ6_over_capacity_stations"]["rows"] == 3_378

    data = Graph()
    for name in ("ontology", "national graph", "scenario graph"):
        data.parse(required[name], format="turtle")
    shapes = Graph().parse(required["shape graph"], format="turtle")
    conforms, report, _ = validate(data, shacl_graph=shapes, inference="none")
    assert conforms, "combined graph violates distributed SHACL shapes"
    assert len(data) == queries["triples"] == 764_115
    for name in ("example graph", "national graph", "merged graph"):
        graph = Graph().parse(required["ontology"], format="turtle")
        graph.parse(required[name], format="turtle")
        conforms, _, _ = validate(graph, shacl_graph=shapes, inference="none")
        assert conforms, f"{name} violates distributed SHACL shapes"
    print(
        f"OK: {len(stations):,} stations; {summary['red']:,} red; "
        f"{summary['near']:,} near; {len(data):,} triples; all release graphs SHACL conform."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
