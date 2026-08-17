#!/usr/bin/env python3
"""Validate a NEDT A-Box against the NEDT shape graph.

Two modes:
  python validate_shapes.py                 # self-test: the trap fixture MUST fail
  python validate_shapes.py <abox.ttl>      # validate a real A-Box

The self-test exists because a shape graph that cannot fail proves nothing.
test_shapes_trap.ttl contains nine deliberately malformed instances; a shape
graph that reports `conforms = True` against it is broken and the exit status
will be non-zero.
"""
import sys
from pathlib import Path
from rdflib import Graph
from pyshacl import validate

HERE = Path(__file__).parent
SHAPES = HERE / "DT_shapes.ttl"
ONTO = HERE / "DT_ontology.ttl"
TRAP = HERE / "test_shapes_trap.ttl"


def run(data_path: Path):
    data = Graph().parse(data_path, format="turtle")
    shapes = Graph().parse(SHAPES, format="turtle")
    onto = Graph().parse(ONTO, format="turtle")
    conforms, _, text = validate(
        data, shacl_graph=shapes, ont_graph=onto, inference="none", advanced=True
    )
    return conforms, text


def main() -> int:
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        conforms, text = run(target)
        print(f"{target.name}: conforms = {conforms}")
        if not conforms:
            print(text)
        return 0 if conforms else 1

    conforms, text = run(TRAP)
    n = text.count("Message:")
    print(f"self-test on {TRAP.name}: conforms = {conforms}, violations = {n}")
    if conforms:
        print("FAIL: the trap fixture conformed. The shape graph is not falsifiable.")
        return 1
    print("OK: shape graph rejects all planted defects.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
