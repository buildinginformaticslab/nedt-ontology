#!/usr/bin/env python3
"""Run the four executed NEDT competency questions against supplied RDF."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"
QUERIES = {
    "CQ3_scenario_parameters": """
        PREFIX nedt: <https://example.org/nedt#>
        SELECT ?scenario ?hp ?ev ?pv WHERE { ?scenario a nedt:Scenario ;
          nedt:hasHPAdoptionFraction ?hp ; nedt:hasEVAdoptionFraction ?ev ;
          nedt:hasPVAdoptionFraction ?pv . }""",
    "CQ6_over_capacity_stations": """
        PREFIX nedt: <https://example.org/nedt#>
        PREFIX sosa: <http://www.w3.org/ns/sosa/>
        SELECT ?station ?peak ?capacity ?utilisation WHERE { ?kpi a nedt:CapacityKPI ;
          nedt:forLVStation ?station ; nedt:hasPeakDemandKW ?peak ;
          nedt:hasRatedCapacityKVA ?capacity ; nedt:hasUtilisation ?u .
          ?u sosa:hasSimpleResult ?utilisation . FILTER(?utilisation > 1.0) }
        ORDER BY DESC(?utilisation)""",
    "CQ12_provenance_trace": """
        PREFIX nedt: <https://example.org/nedt#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        SELECT ?kpi ?activity WHERE { ?kpi a nedt:CapacityKPI ; prov:wasGeneratedBy ?activity . }
        LIMIT 10""",
    "CQ1_county_archetype_inventory": """
        PREFIX nedt: <https://example.org/nedt#>
        SELECT ?county (COUNT(?cohort) AS ?cohorts) WHERE { ?cohort a nedt:ArchetypeCount ;
          nedt:inCounty ?county . } GROUP BY ?county ORDER BY ?county""",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent / "results" / "scenario1" / "competency_queries.json")
    parser.add_argument("--scenario-graph", type=Path, default=ONTOLOGY / "scenario1_results.ttl")
    args = parser.parse_args()
    graph = Graph()
    for source in (ONTOLOGY / "DT_ontology.ttl", ONTOLOGY / "DT_kg.ttl", args.scenario_graph):
        graph.parse(source, format="turtle")
    summary = {"triples": len(graph), "queries": {}}
    for name, query in QUERIES.items():
        start = time.perf_counter()
        rows = list(graph.query(query))
        elapsed_ms = (time.perf_counter() - start) * 1000
        summary["queries"][name] = {"rows": len(rows), "elapsed_ms": round(elapsed_ms, 3),
                                    "sample": [[str(x) for x in row] for row in rows[:5]]}
        print(f"{name}: {len(rows):,} rows in {elapsed_ms:.1f} ms")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
