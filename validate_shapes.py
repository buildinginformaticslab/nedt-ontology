#!/usr/bin/env python3
"""Validate the NEDT SHACL shapes and ensure known-invalid data is rejected."""
from pathlib import Path
from rdflib import Graph
from pyshacl import validate

ROOT = Path(__file__).parent

def load(name: str) -> Graph:
    graph = Graph()
    graph.parse(ROOT / name, format="turtle")
    return graph

def main() -> int:
    shapes = load("DT_shapes.ttl")
    invalid = load("test_shapes_trap.ttl")
    conforms, report, text = validate(invalid, shacl_graph=shapes, inference="rdfs")
    violations = sum(1 for _ in report.triples((None, None, None)))
    print(f"trap conforms = {conforms}; report triples = {violations}")
    if conforms:
        print(text)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
